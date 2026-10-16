"""Gestion et finalisation atomique des dossiers P4-C d'encaissement groupé."""
import hashlib
import json
from decimal import Decimal
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, delete

from neosys_pharma.application.caisse_service import serial
from neosys_pharma.domain.caisse import francs
from neosys_pharma.domain.encaissement_groupe import (
    AllocationReglement,
    ReglementGroupe,
    VenteGroupe,
    repartir_automatiquement,
    valider_allocations,
)
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.caisse_models import (
    AllocationReglementGroupeModel,
    ClientFideliteModel,
    CompteFideliteModel,
    EncaissementModel,
    EncaissementGroupeModel,
    EncaissementGroupeVenteModel,
    EvenementCaisseModel,
    JournalFideliteModel,
    MouvementCaisseGroupeModel,
    PeriodeCaisseSiteModel,
    ReglementGroupeModel,
    ReglementModel,
    ConfirmationReglementModel,
    SessionCaisseModel,
    now,
)
from neosys_pharma.infrastructure.vente_models import (
    DemandeRemiseModel,
    ReservationVenteModel,
    VenteModel,
)
from neosys_pharma.infrastructure.stock_models import (
    AllocationReservationModel,
    LotModel,
    ReservationStockModel,
    StockEmplacementModel,
)
from neosys_pharma.domain.stock import perime
from neosys_pharma.infrastructure.catalogue_models import ProduitModel
from neosys_pharma.infrastructure.organisation_models import OrganisationModel, SiteModel
from neosys_pharma.infrastructure.regularisation_models import (
    RemboursementModel,
)


class EncaissementGroupeService:
    """Prépare les dossiers et finalise leurs ventes dans la transaction appelante."""

    def __init__(self, caisse, control=None):
        self.caisse = caisse
        self.vente = caisse.vente
        self.stock = caisse.stock
        self.session = caisse.s
        self.org = caisse.org
        self.site = caisse.site
        self.control = control

    def _session_active(self, session_id):
        session = self.caisse.session(session_id, "caisse.encaisser", True)
        if session.site_id != self.site:
            raise PermissionError("Session de caisse hors du site courant.")
        return session

    def _dossier(self, dossier_id, revision=None, *, brouillon=True, modifier=False):
        dossier = self.stock.obtenir(EncaissementGroupeModel, dossier_id)
        if dossier.site_id != self.site:
            raise PermissionError("Dossier hors du site courant.")
        if revision is not None and dossier.revision != revision:
            raise ConflitStock("Dossier modifié : actualiser avant de poursuivre.")
        if brouillon and dossier.etat != "BROUILLON":
            raise ConflitStock("Seul un brouillon peut être modifié.")
        session = self.caisse.session(
            dossier.session_id,
            "caisse.encaisser" if modifier else "caisse.consulter",
            modifier,
        )
        if session.site_id != self.site:
            raise PermissionError("Session de caisse hors du site courant.")
        return dossier

    def _lignes_vente(self, dossier_id):
        return self.stock.lignes(
            EncaissementGroupeVenteModel, dossier_id=dossier_id
        )

    def _reglements(self, dossier_id):
        return self.stock.lignes(ReglementGroupeModel, dossier_id=dossier_id)

    def _allocations(self, dossier_id):
        return self.stock.lignes(AllocationReglementGroupeModel, dossier_id=dossier_id)

    def _valeurs_domaine(self, dossier_id):
        sales = [
            VenteGroupe(row.vente_id, row.ordre, row.revision_vente, row.montant_du)
            for row in sorted(self._lignes_vente(dossier_id), key=lambda x: x.ordre)
        ]
        payments = [
            ReglementGroupe(
                row.id,
                row.ordre,
                row.mode,
                row.montant,
                row.rendu,
                row.confirmation_id,
            )
            for row in sorted(self._reglements(dossier_id), key=lambda x: x.ordre)
        ]
        return sales, payments

    def _detail(self, dossier):
        sales = sorted(self._lignes_vente(dossier.id), key=lambda x: x.ordre)
        payments = sorted(self._reglements(dossier.id), key=lambda x: x.ordre)
        allocations = self._allocations(dossier.id)
        total_due = sum((francs(row.montant_du, zero=True) for row in sales), Decimal(0))
        total_net = sum((francs(row.montant - row.rendu, zero=True) for row in payments), Decimal(0))
        allocated = sum((francs(row.montant, zero=True) for row in allocations), Decimal(0))
        return {
            "dossier": serial(dossier),
            "ventes": [serial(row) for row in sales],
            "reglements": [serial(row) for row in payments],
            "allocations": [serial(row) for row in allocations],
            "totaux": {
                "du_xaf": str(total_due),
                "net_regle_xaf": str(total_net),
                "alloue_xaf": str(allocated),
                "reste_xaf": str(total_due - total_net),
                "allocation_valide": self._allocations_valides(dossier.id),
            },
        }

    def _allocations_valides(self, dossier_id):
        sales, payments = self._valeurs_domaine(dossier_id)
        if not sales:
            return False
        if not payments and sum((sale.montant_du for sale in sales), Decimal(0)) != 0:
            return False
        try:
            valider_allocations(sales, payments, [
                AllocationReglement(row.reglement_id, row.vente_id, row.montant)
                for row in self._allocations(dossier_id)
            ])
        except ValueError:
            return False
        return True

    def obtenir(self, dossier_id):
        dossier = self._dossier(dossier_id, brouillon=False)
        result = self._detail(dossier)
        if dossier.etat == "FINALISE":
            result["resultat"] = self._resultat(dossier)
        return result

    def _resultat(self, dossier):
        sales = sorted(self._lignes_vente(dossier.id), key=lambda row: row.ordre)
        return {
            "recu_collectif": {
                "id": str(dossier.id),
                "numero": dossier.numero,
                "reference": dossier.reference,
                "total_xaf": str(dossier.total_xaf),
                "pdf_sha256": dossier.pdf_sha256,
            },
            "recus_individuels": [
                serial(self.stock.obtenir(EncaissementModel, row.encaissement_id))
                for row in sales if row.encaissement_id
            ],
        }

    def recu_collectif_pdf(self, dossier_id):
        dossier = self._dossier(dossier_id, brouillon=False)
        if dossier.etat != "FINALISE" or not dossier.pdf:
            raise ConflitStock("Le reçu collectif n'est disponible qu'après finalisation.")
        return dossier.pdf

    def _obtenir_vente_autorisee(self, vente_id):
        sale = self.stock.obtenir(VenteModel, vente_id)
        if sale.site_id != self.site:
            raise PermissionError("Vente hors du site courant.")
        location = self.stock.emplacement(sale.emplacement_id, None)
        if self.control is not None:
            self.control.verifier("caisse.encaisser", self.site, location.id_emplacement)
        else:
            self.stock.access("caisse.encaisser", self.site, location.id_emplacement)
        return sale

    def creer(self, session_id):
        session = self._session_active(session_id)
        row = self.stock.ajouter(
            EncaissementGroupeModel,
            site_id=self.site,
            session_id=session.id,
            auteur_id=self.stock.user,
            etat="BROUILLON",
            revision=1,
        )
        self.caisse.trace("DOSSIER_GROUPE_CREE", dossier_id=row.id, session_id=session.id)
        return self._detail(row)

    def remplacer_ventes(self, dossier_id, revision, ventes, *, reinitialiser_allocations=False):
        dossier = self._dossier(dossier_id, revision, modifier=True)
        if len({row["vente_id"] for row in ventes}) != len(ventes):
            raise ValueError("Une vente ne peut apparaître qu'une fois dans le dossier.")
        existing_allocations = self._allocations(dossier.id)
        if existing_allocations and not reinitialiser_allocations:
            raise ConflitStock("La ventilation existe : confirmer explicitement sa réinitialisation.")

        self._session_active(dossier.session_id)
        session = self.session.scalar(
            select(SessionCaisseModel)
            .where(SessionCaisseModel.organisation_id == self.org,
                   SessionCaisseModel.id == dossier.session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not session:
            raise ConflitStock("Session de caisse introuvable.")
        validated = []
        for item in ventes:
            sale = self._obtenir_vente_autorisee(item["vente_id"])
            self.vente.revision(sale, item["revision"])
            if sale.etat != "TRANSMISE" or sale.mode != "SANS_TIERS":
                raise ConflitStock("Seules les ventes comptant transmises sont admissibles.")
            if sale.site_id != self.site or sale.caisse_id != session.caisse_id:
                raise PermissionError("La vente doit appartenir au même site et à la caisse de la session.")
            self.stock.emplacement(sale.emplacement_id, "caisse.encaisser")
            paid = self.session.scalar(select(EncaissementModel.id).where(
                EncaissementModel.organisation_id == self.org,
                EncaissementModel.vente_id == sale.id,
            ))
            if paid:
                raise ConflitStock("Cette vente a déjà été encaissée.")
            amount = francs(self.vente.finance(sale)["totaux"]["ttc"], zero=True)
            validated.append((sale, amount))

        selected_ids = {sale.id for sale, _ in validated}
        dangling_confirmations = [
            payment.confirmation_id
            for payment in self._reglements(dossier.id)
            if payment.confirmation_id is not None
            and self.stock.obtenir(
                ConfirmationReglementModel, payment.confirmation_id
            ).vente_id not in selected_ids
        ]
        if dangling_confirmations:
            raise ConflitStock(
                "Retirer d'abord les règlements dont la confirmation dépend d'une vente supprimée."
            )

        if existing_allocations:
            self.session.execute(delete(AllocationReglementGroupeModel).where(
                AllocationReglementGroupeModel.organisation_id == self.org,
                AllocationReglementGroupeModel.dossier_id == dossier.id,
            ))
        self.session.execute(delete(EncaissementGroupeVenteModel).where(
            EncaissementGroupeVenteModel.organisation_id == self.org,
            EncaissementGroupeVenteModel.dossier_id == dossier.id,
        ))
        for order, (sale, amount) in enumerate(validated, 1):
            self.stock.ajouter(
                EncaissementGroupeVenteModel,
                dossier_id=dossier.id,
                site_id=self.site,
                vente_id=sale.id,
                encaissement_id=None,
                ordre=order,
                revision_vente=sale.revision,
                montant_du=amount,
            )
        dossier.revision += 1
        self.caisse.trace(
            "DOSSIER_GROUPE_VENTES_MODIFIE",
            dossier_id=dossier.id,
            ventes=[str(row[0].id) for row in validated],
            allocations_reinitialisees=bool(existing_allocations),
        )
        return self._detail(dossier)

    def remplacer_reglements(self, dossier_id, revision, reglements, *, reinitialiser_allocations=False):
        dossier = self._dossier(dossier_id, revision, modifier=True)
        if len(reglements) > 20:
            raise ValueError("Un dossier accepte au maximum 20 règlements.")
        old_allocations = self._allocations(dossier.id)
        if old_allocations and not reinitialiser_allocations:
            raise ConflitStock("La ventilation existe : confirmer explicitement sa réinitialisation.")
        sale_ids = {row.vente_id for row in self._lignes_vente(dossier.id)}
        modes = set(self.caisse.config()["modes"])
        parsed = []
        confirmation_ids = set()
        for order, item in enumerate(reglements, 1):
            if item["mode"] not in modes:
                raise ValueError("Moyen de règlement non activé pour cette caisse.")
            confirmation_id = item.get("confirmation_id")
            if item["mode"] == "ESPECES":
                if confirmation_id is not None:
                    raise ValueError("Un règlement espèces ne porte pas de confirmation externe.")
            else:
                if confirmation_id is None:
                    raise ValueError("Confirmation externe requise pour un règlement non espèces.")
                if confirmation_id in confirmation_ids:
                    raise ValueError("Une confirmation ne peut couvrir deux règlements.")
                confirmation_ids.add(confirmation_id)
                confirmation = self.stock.obtenir(ConfirmationReglementModel, confirmation_id)
                if confirmation.session_id != dossier.session_id or confirmation.mode != item["mode"]:
                    raise ConflitStock("Confirmation liée à une autre session ou à un autre moyen.")
                if confirmation.montant != francs(item["montant"]):
                    raise ConflitStock("Montant de confirmation différent du règlement.")
                if confirmation.vente_id not in sale_ids:
                    raise PermissionError("La confirmation doit concerner une vente du dossier.")
                if self.session.scalar(select(ReglementModel.id).where(
                    ReglementModel.organisation_id == self.org,
                    ReglementModel.confirmation_id == confirmation.id,
                )):
                    raise ConflitStock("Confirmation déjà consommée par un encaissement individuel.")
            parsed.append(ReglementGroupe(
                UUID(int=0), order, item["mode"], item["montant"],
                item.get("rendu", 0), confirmation_id,
            ))

        if old_allocations:
            self.session.execute(delete(AllocationReglementGroupeModel).where(
                AllocationReglementGroupeModel.organisation_id == self.org,
                AllocationReglementGroupeModel.dossier_id == dossier.id,
            ))
        self.session.execute(delete(ReglementGroupeModel).where(
            ReglementGroupeModel.organisation_id == self.org,
            ReglementGroupeModel.dossier_id == dossier.id,
        ))
        rows = []
        for order, payment in enumerate(parsed, 1):
            row = self.stock.ajouter(
                ReglementGroupeModel,
                dossier_id=dossier.id,
                ordre=order,
                mode=payment.mode,
                montant=payment.montant,
                rendu=payment.rendu,
                confirmation_id=payment.confirmation_id,
            )
            rows.append(row)
        dossier.revision += 1
        self.caisse.trace(
            "DOSSIER_GROUPE_REGLEMENTS_MODIFIES",
            dossier_id=dossier.id,
            reglements=[str(row.id) for row in rows],
            allocations_reinitialisees=bool(old_allocations),
        )
        return self._detail(dossier)

    def proposer_allocations(self, dossier_id, revision):
        dossier = self._dossier(dossier_id, revision, modifier=True)
        sales, payments = self._valeurs_domaine(dossier.id)
        allocations = repartir_automatiquement(sales, payments)
        return [{
            "reglement_id": str(row.reglement_id),
            "vente_id": str(row.vente_id),
            "montant": str(row.montant),
        } for row in allocations]

    def definir_allocations(self, dossier_id, revision, rows):
        dossier = self._dossier(dossier_id, revision, modifier=True)
        sales, payments = self._valeurs_domaine(dossier.id)
        allocations = [AllocationReglement(
            row["reglement_id"], row["vente_id"], row["montant"]
        ) for row in rows]
        valider_allocations(sales, payments, allocations)
        self.session.execute(delete(AllocationReglementGroupeModel).where(
            AllocationReglementGroupeModel.organisation_id == self.org,
            AllocationReglementGroupeModel.dossier_id == dossier.id,
        ))
        for row in allocations:
            self.stock.ajouter(
                AllocationReglementGroupeModel,
                reglement_id=row.reglement_id,
                dossier_id=dossier.id,
                vente_id=row.vente_id,
                montant=row.montant,
            )
        dossier.revision += 1
        self.caisse.trace("DOSSIER_GROUPE_ALLOCATION_VALIDEE", dossier_id=dossier.id)
        return self._detail(dossier)

    def abandonner(self, dossier_id, revision):
        dossier = self._dossier(dossier_id, revision, modifier=True)
        # Une confirmation non espèces ne doit pas rester bloquée par un brouillon abandonné.
        self.session.execute(delete(AllocationReglementGroupeModel).where(
            AllocationReglementGroupeModel.organisation_id == self.org,
            AllocationReglementGroupeModel.dossier_id == dossier.id,
        ))
        self.session.execute(delete(ReglementGroupeModel).where(
            ReglementGroupeModel.organisation_id == self.org,
            ReglementGroupeModel.dossier_id == dossier.id,
        ))
        dossier.etat = "ABANDONNE"
        dossier.revision += 1
        self.caisse.trace("DOSSIER_GROUPE_ABANDONNE", dossier_id=dossier.id)
        return self._detail(dossier)

    def _verifier_remises(self, sale):
        requests = self.stock.lignes(DemandeRemiseModel, vente_id=sale.id)
        if any(row.statut == "DEMANDEE" for row in requests):
            raise ConflitStock("Remise en attente : encaissement interdit.")
        from neosys_pharma.domain.remises import montant_remise
        for row in requests:
            if row.statut != "AUTORISEE":
                continue
            eligible = self.vente.eligible(sale, row)
            cap = self.vente.plafond_applicable(
                sale,
                UUID(row.autorisation["auteur_id"]),
                row,
                montant_remise(row.type, row.valeur, eligible),
                eligible,
            )
            if (str(cap.id) != row.autorisation["plafond"]["id"]
                    or cap.revision != row.autorisation["plafond"]["revision"]):
                raise ConflitStock("Autorisation de remise à revalider.")

    def _reservations(self, sale, *, consommer=False):
        for line in self.vente.lignes(sale):
            if not line.actif:
                continue
            links = self.stock.lignes(ReservationVenteModel, ligne_id=line.id)
            reservations = [
                self.stock.obtenir(ReservationStockModel, link.reservation_id)
                for link in links
            ]
            active = [row for row in reservations if row.statut == "ACTIVE"]
            quantity = sum(
                allocation["quantite"]
                for reservation in active
                for allocation in self.stock.reservation_detail(reservation)["allocations"]
            )
            if quantity != line.quantite:
                raise ConflitStock("Réservation incomplète.")
            for reservation in active:
                for allocation in self.stock.lignes(
                    AllocationReservationModel, reservation_id=reservation.id
                ):
                    balance = self.stock.obtenir(StockEmplacementModel, allocation.stock_id)
                    lot = self.stock.obtenir(LotModel, balance.lot_id)
                    _, rules = self.stock.conditionnement(lot.conditionnement_id)
                    if (rules["gestion_peremption"]
                            and (lot.peremption is None or perime(lot.peremption, self.stock.jour))):
                        raise ConflitStock("Lot réservé devenu périmé : libérer et réallouer.")
            if consommer:
                for reservation in active:
                    self.stock.terminer_reservation(
                        reservation.id, True, "VENTE", "caisse.encaisser", True
                    )

    def finaliser(self, dossier_id, data, cle_idempotence):
        """Finalise toutes les ventes dans la transaction portée par StockService.operation."""
        dossier = self.session.scalar(
            select(EncaissementGroupeModel)
            .where(
                EncaissementGroupeModel.id == dossier_id,
                EncaissementGroupeModel.organisation_id == self.org,
            )
            .with_for_update()
        )
        if not dossier:
            raise LookupError("Dossier d'encaissement groupé absent de cette organisation.")
        if dossier.site_id != self.site:
            raise PermissionError("Dossier hors du site courant.")
        request_digest = hashlib.sha256(json.dumps(
            jsonable_encoder(data), sort_keys=True, ensure_ascii=False
        ).encode()).hexdigest()
        if dossier.etat == "FINALISE":
            if (dossier.cle_idempotence == str(cle_idempotence)
                    and dossier.empreinte_requete == request_digest):
                return self._detail(dossier) | {"resultat": self._resultat(dossier)}
            raise ConflitStock("Dossier déjà finalisé avec une autre clé ou un autre contenu.")
        if dossier.etat != "BROUILLON":
            raise ConflitStock("Seul un brouillon peut être finalisé.")
        if dossier.revision != data["revision"]:
            raise ConflitStock("Dossier modifié : actualiser avant de finaliser.")

        self._session_active(dossier.session_id)
        session = self.session.scalar(
            select(SessionCaisseModel)
            .where(SessionCaisseModel.organisation_id == self.org,
                   SessionCaisseModel.id == dossier.session_id)
            .with_for_update()
        )
        if not session:
            raise ConflitStock("Session de caisse introuvable.")
        if (session.etat != "OUVERTE" or session.caissier_id != self.stock.user):
            raise PermissionError("La session doit rester ouverte et appartenir au caissier courant.")
        if session.revision != data["revision_session"]:
            raise ConflitStock("Session modifiée : actualiser avant de finaliser.")
        if session.site_id != dossier.site_id:
            raise PermissionError("Session et dossier de sites différents.")

        sale_links = sorted(self._lignes_vente(dossier.id), key=lambda row: (str(row.vente_id), row.ordre))
        if not sale_links:
            raise ValueError("Le dossier doit contenir au moins une vente.")
        sale_ids = [row.vente_id for row in sale_links]
        locked_sales = list(self.session.scalars(
            select(VenteModel)
            .where(VenteModel.organisation_id == self.org, VenteModel.id.in_(sale_ids))
            .order_by(VenteModel.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ))
        sales_by_id = {row.id: row for row in locked_sales}
        if len(sales_by_id) != len(sale_links):
            raise ConflitStock("Une vente du dossier a disparu ou n'est plus accessible.")

        finance_by_sale = {}
        due_by_sale = {}
        for link in sorted(sale_links, key=lambda row: (str(row.vente_id), row.ordre)):
            sale = sales_by_id[link.vente_id]
            if sale.revision != link.revision_vente:
                raise ConflitStock("Une vente a changé depuis sa sélection dans le dossier.")
            if sale.etat != "TRANSMISE" or sale.mode != "SANS_TIERS":
                raise ConflitStock("Chaque vente doit être comptant et transmise.")
            if sale.site_id != self.site or sale.caisse_id != session.caisse_id:
                raise PermissionError("Toutes les ventes doivent correspondre au site et à la caisse de la session.")
            self._obtenir_vente_autorisee(sale.id)
            if self.session.scalar(select(EncaissementModel.id).where(
                EncaissementModel.organisation_id == self.org,
                EncaissementModel.vente_id == sale.id,
            )):
                raise ConflitStock("Une vente du dossier a déjà été encaissée.")
            self._verifier_remises(sale)
            finance = self.vente.finance(sale)
            due = francs(finance["totaux"]["ttc"], zero=True)
            if due != francs(link.montant_du, zero=True):
                raise ConflitStock("Le montant dû d'une vente diffère de son instantané.")
            self._reservations(sale)
            finance_by_sale[sale.id] = finance
            due_by_sale[sale.id] = due

        payment_rows = sorted(self._reglements(dossier.id), key=lambda row: row.ordre)
        if len(payment_rows) > 20:
            raise ValueError("Un dossier accepte au maximum 20 règlements.")
        configured_modes = set(self.caisse.config()["modes"])
        payment_domain = []
        confirmation_ids = set()
        confirmation_rows = list(self.session.scalars(
            select(ConfirmationReglementModel)
            .where(ConfirmationReglementModel.organisation_id == self.org,
                   ConfirmationReglementModel.id.in_([
                       row.confirmation_id for row in payment_rows if row.confirmation_id
                   ]))
            .order_by(ConfirmationReglementModel.id)
            .with_for_update()
        )) if any(row.confirmation_id for row in payment_rows) else []
        confirmations = {row.id: row for row in confirmation_rows}
        for order, row in enumerate(payment_rows, 1):
            if row.mode not in configured_modes:
                raise ValueError("Moyen de paiement non activé.")
            confirmation = None
            if row.mode == "ESPECES":
                if row.confirmation_id is not None:
                    raise ValueError("Une ligne espèces ne porte pas de confirmation externe.")
            else:
                if row.confirmation_id is None or row.confirmation_id in confirmation_ids:
                    raise ValueError("Une confirmation distincte est requise par règlement non espèces.")
                confirmation_ids.add(row.confirmation_id)
                confirmation = confirmations.get(row.confirmation_id)
                if confirmation is None:
                    raise ConflitStock("Confirmation absente ou hors de l'organisation.")
                if (confirmation.session_id != session.id or confirmation.mode != row.mode
                        or confirmation.montant != francs(row.montant)):
                    raise ConflitStock("Confirmation de paiement incompatible avec la session, le mode ou le montant.")
                if confirmation.vente_id not in sales_by_id:
                    raise PermissionError("La confirmation doit être rattachée à une vente du groupe.")
                confirmed_sale = sales_by_id[confirmation.vente_id]
                if not self.caisse.rapprochement_compatible(confirmation, confirmed_sale, session):
                    raise ConflitStock("Confirmation obsolète : rapprocher le paiement avec la vente et la session courantes.")
                if self.session.scalar(select(ReglementModel.id).where(
                    ReglementModel.organisation_id == self.org,
                    ReglementModel.confirmation_id == confirmation.id,
                )):
                    raise ConflitStock("Confirmation déjà consommée par un encaissement individuel.")
                if self.stock.lignes(RemboursementModel, confirmation_id=confirmation.id):
                    raise ConflitStock("Confirmation déjà engagée dans une restitution.")
                confirmations[confirmation.id] = confirmation
            payment_domain.append(ReglementGroupe(
                row.id, order, row.mode, row.montant, row.rendu, row.confirmation_id
            ))

        # Every acquired confirmation for each sale must be accounted for exactly once.
        for sale in locked_sales:
            pending = {
                confirmation.id
                for confirmation in self.stock.lignes(ConfirmationReglementModel, vente_id=sale.id)
                if not self.stock.lignes(ReglementModel, confirmation_id=confirmation.id)
                and not self.stock.lignes(RemboursementModel, confirmation_id=confirmation.id)
            }
            assigned = {
                confirmation_id for confirmation_id in confirmation_ids
                if confirmations[confirmation_id].vente_id == sale.id
            }
            if pending != assigned:
                raise ConflitStock("Toutes les confirmations acquises d'une vente doivent être intégrées ou résolues.")

        allocations_rows = self._allocations(dossier.id)
        sales_domain = [
            VenteGroupe(link.vente_id, link.ordre, link.revision_vente, link.montant_du)
            for link in sorted(sale_links, key=lambda row: row.ordre)
        ]
        allocations_domain = [
            AllocationReglement(row.reglement_id, row.vente_id, row.montant)
            for row in allocations_rows
        ]
        valider_allocations(sales_domain, payment_domain, allocations_domain)
        by_payment = {row.id: row for row in payment_rows}
        allocations_by_sale = {sale_id: [] for sale_id in sale_ids}
        for allocation in allocations_rows:
            allocations_by_sale[allocation.vente_id].append(allocation)

        loyalty = {}
        for item in data.get("fidelite", []):
            sale_id = UUID(str(item["vente_id"]))
            item = {**item, "compte_id": UUID(str(item["compte_id"]))}
            if sale_id not in sales_by_id or sale_id in loyalty:
                raise ValueError("L'affectation de fidélité doit désigner une vente unique du dossier.")
            loyalty[sale_id] = item
        account_ids = sorted({item["compte_id"] for item in loyalty.values()}, key=str)
        accounts = {}
        if account_ids:
            list(self.session.scalars(
                select(CompteFideliteModel)
                .where(CompteFideliteModel.organisation_id == self.org,
                       CompteFideliteModel.id.in_(account_ids))
                .order_by(CompteFideliteModel.id)
                .with_for_update()
            ))
        for sale_id, item in loyalty.items():
            sale = sales_by_id[sale_id]
            account = self.stock.obtenir(CompteFideliteModel, item["compte_id"])
            if account.revision != item["revision_compte"]:
                raise ConflitStock("Compte fidélité modifié : actualiser avant l'encaissement groupé.")
            if account.dette:
                raise ConflitStock("Dette de points : acquisition et utilisation indisponibles.")
            self.stock.access("fidelite.consulter", self.site, sale.emplacement_id)
            profile = self.stock.obtenir(ClientFideliteModel, account.client_id)
            if sale.client_id and profile.profil_client_id and sale.client_id != profile.profil_client_id:
                raise PermissionError("Le compte fidélité ne correspond pas au client de la vente.")
            accounts[sale_id] = account

        # Lock the sequence row before allocating individual and collective receipt numbers.
        period = self.session.scalar(select(PeriodeCaisseSiteModel).where(
            PeriodeCaisseSiteModel.organisation_id == self.org,
            PeriodeCaisseSiteModel.site_id == self.site,
            PeriodeCaisseSiteModel.etat == "OUVERTE",
        ).with_for_update())
        if period is None:
            period = self.caisse.periode()
        org = self.session.get(OrganisationModel, self.org)
        site = self.session.get(SiteModel, self.site)
        if not org or not site or not site.actif:
            raise PermissionError("Organisation ou site inactif.")

        # A group confirmation is represented once by its group movement. Its exact sale
        # shares remain in AllocationReglementGroupeModel for receipt and refund tracing.
        for row in payment_rows:
            net = francs(row.montant) - francs(row.rendu, zero=True)
            if net:
                self.stock.ajouter(
                    MouvementCaisseGroupeModel,
                    dossier_id=dossier.id,
                    reglement_id=row.id,
                    session_id=session.id,
                    auteur_id=self.stock.user,
                    mode=row.mode,
                    montant_net=net,
                )

        period_number = period.prochain_encaissement_groupe
        group_number = period_number
        period.prochain_encaissement_groupe += 1
        reference = f"G-{site.code}-{period.numero:03d}-{group_number:06d}"
        group_meta = {
            "id": str(dossier.id),
            "numero": group_number,
            "reference": reference,
            "periode_z": period.numero,
        }

        receipts = []
        for link in sorted(sale_links, key=lambda row: row.ordre):
            sale = sales_by_id[link.vente_id]
            number = period.prochain_encaissement
            period.prochain_encaissement += 1
            sale_payments = []
            for allocation in sorted(
                allocations_by_sale[sale.id], key=lambda row: (by_payment[row.reglement_id].ordre, str(row.reglement_id))
            ):
                grouped_payment = by_payment[allocation.reglement_id]
                confirmation = confirmations.get(grouped_payment.confirmation_id)
                sale_payments.append({
                    "mode": grouped_payment.mode,
                    "montant": str(allocation.montant),
                    "rendu": "0",
                    "confirmation": serial(confirmation) if confirmation else None,
                    "reglement_groupe_id": str(grouped_payment.id),
                    "allocation_id": str(allocation.id),
                })
            snapshot = self.vente.detail(sale) | {
                "organisation": org.nom_commercial,
                "site": site.nom,
                "date": now().isoformat(),
                "numero_encaissement": str(number).zfill(4),
                "periode_z": period.numero,
                "reglements": sale_payments,
                "caissier_id": str(self.stock.user),
                "fidelite": None,
                "etat": "ENCAISSEE",
                "encaissement_groupe": group_meta,
            }
            account = accounts.get(sale.id)
            if account:
                gain = self.caisse.gagner(sale, account, finance_by_sale[sale.id])
                if "bareme" in gain:
                    snapshot["fidelite"] = gain | {
                        "client": serial(self.stock.obtenir(ClientFideliteModel, account.client_id))
                    }
            from neosys_pharma.infrastructure.caisse_pdf import recu_pdf
            pdf = recu_pdf(snapshot)
            enc = self.stock.ajouter(
                EncaissementModel,
                vente_id=sale.id,
                session_id=session.id,
                periode_id=period.id,
                numero=number,
                total_xaf=due_by_sale[sale.id],
                compte_id=account.id if account else None,
                instantane=snapshot,
                pdf=pdf,
                pdf_sha256=hashlib.sha256(pdf).hexdigest(),
            )
            if account and snapshot["fidelite"] and "bareme" in snapshot["fidelite"]:
                gain = snapshot["fidelite"]
                self.stock.ajouter(
                    JournalFideliteModel,
                    compte_id=account.id,
                    encaissement_id=enc.id,
                    auteur_id=self.stock.user,
                    type="ACQUISITION",
                    delta_points=gain["points_acquis"] - gain["dette_compensee"],
                    delta_dette=-gain["dette_compensee"],
                    details=gain,
                )
            link.encaissement_id = enc.id
            sale.etat = "ENCAISSEE"
            sale.revision += 1
            self.vente.evenement(
                sale,
                "ENCAISSEMENT_GROUPE",
                dossier_id=dossier.id,
                reference_groupe=reference,
                encaissement_id=enc.id,
                numero=number,
                totaux=finance_by_sale[sale.id]["totaux"],
                pdf_sha256=enc.pdf_sha256,
            )
            receipts.append({
                "vente_id": str(sale.id),
                "encaissement_id": str(enc.id),
                "numero": number,
                "total_xaf": str(due_by_sale[sale.id]),
                "pdf_sha256": enc.pdf_sha256,
            })

        for sale in locked_sales:
            self._reservations(sale, consommer=True)

        from neosys_pharma.infrastructure.caisse_pdf import recu_groupe_pdf
        collective = {
            "organisation": org.nom_commercial,
            "site": site.nom,
            "reference": reference,
            "numero": group_number,
            "periode_z": period.numero,
            "date": now().isoformat(),
            "total_xaf": str(sum(due_by_sale.values(), Decimal(0))),
            "ventes": receipts,
            "reglements": [
                {
                    "mode": row.mode,
                    "montant": str(row.montant),
                    "rendu": str(row.rendu),
                    "net": str(row.montant - row.rendu),
                    "confirmation": serial(confirmations[row.confirmation_id]) if row.confirmation_id else None,
                }
                for row in payment_rows
            ],
        }
        group_pdf = recu_groupe_pdf(collective)
        dossier.etat = "FINALISE"
        dossier.revision += 1
        dossier.periode_id = period.id
        dossier.numero = group_number
        dossier.reference = reference
        dossier.total_xaf = sum(due_by_sale.values(), Decimal(0))
        dossier.pdf = group_pdf
        dossier.pdf_sha256 = hashlib.sha256(group_pdf).hexdigest()
        dossier.cle_idempotence = str(cle_idempotence)
        dossier.empreinte_requete = request_digest
        session.revision += 1
        self.caisse.trace(
            "DOSSIER_GROUPE_FINALISE",
            dossier_id=dossier.id,
            reference=reference,
            encaissements=receipts,
            reglements=[str(row.id) for row in payment_rows],
            pdf_sha256=dossier.pdf_sha256,
        )
        for sale in locked_sales:
            self.caisse.trace(
                "VENTE_ENCAISSEE_GROUPEE",
                dossier_id=dossier.id,
                vente_id=sale.id,
                revision=sale.revision,
            )
        self.session.flush()
        return self._detail(dossier) | {"resultat": self._resultat(dossier)}
