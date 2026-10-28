"""Simulation et confirmation du snapshot P5-B.2 dans la transaction appelante."""
from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from neosys_pharma.application.prise_en_charge_service import SimulationPriseEnChargeService
from neosys_pharma.application.projection_prise_en_charge import construire_demande
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.domain.prise_en_charge import StatutCalcul
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.prise_en_charge_models import (
    CalculPriseEnChargeVenteModel, EtapeCalculPriseEnChargeModel,
    LigneCalculPriseEnChargeModel, PartCalculPriseEnChargeModel,
)
from neosys_pharma.infrastructure.vente_models import VenteModel


def _xaf_value(raw) -> int:
    value = Decimal(str(raw))
    if value != value.to_integral_value() or value < 0:
        raise ValueError("Le montant net de vente doit être un entier XAF positif ou nul.")
    return int(value)


class PriseEnChargePersistanteService:
    def __init__(self, stock, site_id: UUID):
        self.stock, self.session = stock, stock.s
        self.organisation_id, self.site_id = stock.org, site_id
        self.simulator = SimulationPriseEnChargeService()

    def _calculate(self, vente_id, beneficiaire_id=None, *, confirmation=False):
        sale = self.session.scalar(select(VenteModel).where(
            VenteModel.id == vente_id,
            VenteModel.organisation_id == self.organisation_id,
            VenteModel.site_id == self.site_id,
        ))
        if not sale:
            raise PermissionError("Vente absente du site ou de l'organisation courante.")
        if sale.etat in ("ENCAISSEE", "ANNULEE"):
            raise ValueError("Vente terminale : consulter le snapshot historique sans recalcul.")
        finance = VenteService(self.stock, self.site_id).finance(sale)
        net_by_line = {UUID(line_id): values["ttc"] for line_id, values in finance["lignes"].items()}
        request = construire_demande(
            self.session, sale.id, self.organisation_id, self.site_id,
            self.stock.jour, beneficiaire_id, net_by_line,
        )
        if confirmation:
            request = replace(request, exiger_v1=True)
        return sale, self.simulator.simuler(request)

    def simuler(self, vente_id, beneficiaire_id=None):
        _, result = self._calculate(vente_id, beneficiaire_id)
        return {
            "statut": result.statut.value,
            "total_xaf": result.total_net_xaf,
            "total_organismes_xaf": result.total_organismes_xaf,
            "part_client_xaf": result.part_client_xaf,
            "lignes": result.snapshot.en_json()["lignes"],
            "blocages": [{"code": b.code.value, "message": b.message,
                          "ligne_id": str(b.ligne_id) if b.ligne_id else None,
                          "organisme_id": str(b.organisme_id) if b.organisme_id else None}
                         for b in result.blocages],
            "snapshot_hash": result.snapshot.hash_contenu,
            "simulation_seulement": True,
            "creance_creee": False,
        }

    def confirmer(self, vente_id, beneficiaire_id, revision):
        sale = self.session.scalar(select(VenteModel).where(
            VenteModel.id == vente_id,
            VenteModel.organisation_id == self.organisation_id,
            VenteModel.site_id == self.site_id,
        ).with_for_update())
        if not sale:
            raise PermissionError("Vente absente du site ou de l'organisation courante.")
        if sale.etat != "TRANSMISE":
            raise ValueError("La prise en charge financière se confirme après transmission à la caisse.")
        if sale.mode in ("SANS_TIERS", "CREDIT"):
            raise ValueError("Le mode de cette vente ne prévoit pas une prise en charge organisme.")
        if sale.revision != revision:
            raise ConflitStock("Vente modifiée : actualisez avant de confirmer la prise en charge.")
        existing = self.session.scalar(select(CalculPriseEnChargeVenteModel).where(
            CalculPriseEnChargeVenteModel.vente_id == sale.id,
            CalculPriseEnChargeVenteModel.organisation_id == self.organisation_id,
        ))
        if existing:
            raise ConflitStock("Une prise en charge est déjà confirmée pour cette vente.")
        _, result = self._calculate(vente_id, beneficiaire_id, confirmation=True)
        if result.statut != StatutCalcul.ADMISSIBLE:
            raise ValueError("Prise en charge bloquée : " + "; ".join(b.message for b in result.blocages))
        snapshot = result.snapshot.en_json()
        total_org = int(result.total_organismes_xaf or 0)
        part_client = int(result.part_client_xaf or 0)
        if total_org + part_client != int(result.total_net_xaf):
            raise ConflitStock("Le calcul ne satisfait pas l'invariant financier de vente.")
        header = self.stock.ajouter(
            CalculPriseEnChargeVenteModel,
            id=uuid4(), vente_id=sale.id, site_id=sale.site_id,
            beneficiaire_id=beneficiaire_id, date_calcul=self.stock.jour,
            revision_vente=sale.revision, parametrage_id=result.snapshot.parametrage_id,
            parametrage_version=result.snapshot.parametrage_version,
            moteur_version=result.snapshot.moteur_version,
            snapshot_hash=result.snapshot.hash_contenu, total_xaf=result.total_net_xaf,
            total_organismes_xaf=total_org, part_client_xaf=part_client,
            snapshot=snapshot, auteur_id=self.stock.user,
        )
        for line_result in result.lignes:
            line_id = uuid4()
            org_total = sum(amount for _, amount in line_result.parts_organismes_xaf)
            self.stock.ajouter(LigneCalculPriseEnChargeModel,
                id=line_id, calcul_id=header.id, vente_id=sale.id,
                ligne_vente_id=line_result.ligne_id, net_xaf=line_result.net_xaf,
                part_client_xaf=int(line_result.part_client_xaf or 0),
                total_organismes_xaf=org_total)
            self.stock.ajouter(PartCalculPriseEnChargeModel,
                ligne_calcul_id=line_id, type_part="CLIENT", organisme_id=None,
                montant_xaf=int(line_result.part_client_xaf or 0), rang=None)
            for organisme_id, amount in line_result.parts_organismes_xaf:
                rank = next(stage.rang for stage in line_result.etapes if stage.organisme_id == organisme_id)
                self.stock.ajouter(PartCalculPriseEnChargeModel,
                    ligne_calcul_id=line_id, type_part="ORGANISME",
                    organisme_id=organisme_id, montant_xaf=amount, rang=rank)
            for stage in line_result.etapes:
                self.stock.ajouter(EtapeCalculPriseEnChargeModel,
                    ligne_calcul_id=line_id, organisme_id=stage.organisme_id,
                    rang=stage.rang, role=stage.role,
                    convention_id=stage.convention_id,
                    convention_version=stage.convention_version,
                    adhesion_id=stage.adhesion_id,
                    adhesion_revision=stage.adhesion_revision,
                    base_initiale_xaf=stage.base_initiale_xaf,
                    base_eligible_xaf=stage.base_eligible_xaf,
                    montant_couvert_xaf=stage.montant_couvert_xaf,
                    reste_apres_xaf=stage.reste_apres_xaf,
                    code=stage.code, regle_code=stage.regle_code,
                    snapshot_convention=jsonable_encoder(dict(stage.snapshot_convention)),
                    snapshot_droits=jsonable_encoder(dict(stage.snapshot_droits)))
        return self.consulter(sale.id)

    def consulter(self, vente_id):
        row = self.session.scalar(select(CalculPriseEnChargeVenteModel).where(
            CalculPriseEnChargeVenteModel.vente_id == vente_id,
            CalculPriseEnChargeVenteModel.organisation_id == self.organisation_id,
            CalculPriseEnChargeVenteModel.site_id == self.site_id,
        ))
        if not row:
            return None
        return {
            "id": str(row.id), "vente_id": str(row.vente_id),
            "organisation_id": str(row.organisation_id), "site_id": str(row.site_id),
            "beneficiaire_id": str(row.beneficiaire_id) if row.beneficiaire_id else None,
            "date_calcul": row.date_calcul.isoformat(), "revision_vente": row.revision_vente,
            "parametrage_id": str(row.parametrage_id), "parametrage_version": row.parametrage_version,
            "moteur_version": row.moteur_version, "snapshot_hash": row.snapshot_hash,
            "total_xaf": row.total_xaf, "total_organismes_xaf": row.total_organismes_xaf,
            "part_client_xaf": row.part_client_xaf, "confirme_le": row.confirme_le.isoformat(),
            "snapshot": row.snapshot, "creance_creee": False,
        }
