"""Cycle de brouillon P4-C.3a, sans écriture financière ni finalisation."""
from decimal import Decimal
from uuid import UUID

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
    EncaissementModel,
    EncaissementGroupeModel,
    EncaissementGroupeVenteModel,
    ReglementGroupeModel,
    ReglementModel,
    ConfirmationReglementModel,
    SessionCaisseModel,
)
from neosys_pharma.infrastructure.vente_models import VenteModel


class EncaissementGroupeService:
    """Prépare et valide des brouillons ; la finalisation est un incrément séparé."""

    def __init__(self, caisse):
        self.caisse = caisse
        self.vente = caisse.vente
        self.stock = caisse.stock
        self.session = caisse.s
        self.org = caisse.org
        self.site = caisse.site

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
        if not sales or not payments:
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
        return self._detail(self._dossier(dossier_id, brouillon=False))

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

        session = self._session_active(dossier.session_id)
        validated = []
        for item in ventes:
            sale = self.vente.obtenir(item["vente_id"], "caisse.encaisser")
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
        dossier.etat = "ABANDONNE"
        dossier.revision += 1
        self.caisse.trace("DOSSIER_GROUPE_ABANDONNE", dossier_id=dossier.id)
        return self._detail(dossier)
