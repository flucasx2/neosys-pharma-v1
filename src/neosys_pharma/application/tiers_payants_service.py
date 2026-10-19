"""Use cases P5-A. Les calculs de parts et de plafonds restent dans P5-B."""
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from neosys_pharma.domain.stock import ConflitStock

from neosys_pharma.domain.tiers_payants import EntreePriorite, RolePriorite, verifier_periode, verifier_priorites, normaliser_identite_organisme
from neosys_pharma.infrastructure.client_models import ClientModel, OrganismePriseEnChargeModel
from neosys_pharma.infrastructure.organisation_models import OrganisationModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel
from neosys_pharma.application.stock_service import serial
from neosys_pharma.infrastructure.tiers_payants_models import (
    AdhesionBeneficiaireModel, AdhesionOrganismeModel, BeneficiaireCouvertureModel,
    ConventionOrganismeModel, EvenementTiersPayantModel,
    ParametragePrioriteTiersPayantModel, PrioriteOrganismeModel,
)


class TiersPayantsService:
    def __init__(self, stock_service):
        self.stock = stock_service
        self.session = stock_service.s
        self.organisation_id = stock_service.org
        self.auteur_id = stock_service.user
        self.jour = stock_service.jour

    def _audit(self, entity_type: str, entity_id: UUID, event_type: str, data: dict):
        self.session.add(EvenementTiersPayantModel(
            organisation_id=self.organisation_id, entite_type=entity_type,
            entite_id=entity_id, type=event_type, donnees=data, auteur_id=self.auteur_id,
        ))

    def _organisation_verrouillee(self):
        row = self.session.scalar(
            select(OrganisationModel).where(
                OrganisationModel.id_organisation == self.organisation_id
            ).with_for_update()
        )
        if row is None or not row.actif:
            raise PermissionError("Organisation absente ou inactive.")
        return row

    def _organisme(self, organisme_id: UUID):
        row = self.session.get(OrganismePriseEnChargeModel, organisme_id)
        if row is None or row.organisation_id != self.organisation_id:
            raise LookupError("Organisme de prise en charge introuvable.")
        return row

    def creer_organisme(self, code: str, nom: str) -> dict:
        self._organisation_verrouillee()
        code, nom = normaliser_identite_organisme(code, nom)
        row = self.stock.ajouter(OrganismePriseEnChargeModel, code=code, nom=nom)
        self.session.flush()
        self._audit("ORGANISME", row.id, "ORGANISME_CREE", {"apres": serial(row)})
        return serial(row)

    def modifier_organisme(self, organisme_id: UUID, revision: int,
                           code: str, nom: str, actif: bool) -> dict:
        self._organisation_verrouillee()
        row = self._organisme(organisme_id)
        if row.revision != revision:
            raise ConflitStock("Organisme modifié par une autre opération : rechargez sa fiche.")
        code, nom = normaliser_identite_organisme(code, nom)
        if type(actif) is not bool:
            raise ValueError("Le statut actif doit être explicite.")
        before = serial(row)
        row.code, row.nom, row.actif = code, nom, actif
        row.revision += 1
        self.session.flush()
        self._audit("ORGANISME", row.id, "ORGANISME_MODIFIE", {"avant": before, "apres": serial(row)})
        return serial(row)

    def creer_convention(self, data: dict) -> dict:
        self._organisation_verrouillee()
        organisme = self._organisme(data["organisme_id"])
        if not organisme.actif:
            raise ValueError("Un organisme inactif ne peut recevoir une nouvelle convention active.")
        code = data["code"].strip().upper()
        if not code:
            raise ValueError("Le code de convention est obligatoire.")
        start, end = data["date_debut"], data.get("date_fin")
        verifier_periode(start, end)
        statut = data.get("statut", "ACTIVE")
        if statut not in ("ACTIVE", "INACTIVE"):
            raise ValueError("Statut de convention invalide.")
        if statut == "ACTIVE":
            existing = self.session.scalars(select(ConventionOrganismeModel).where(
                ConventionOrganismeModel.organisation_id == self.organisation_id,
                ConventionOrganismeModel.organisme_id == organisme.id,
                ConventionOrganismeModel.code == code,
                ConventionOrganismeModel.statut == "ACTIVE",
            ).with_for_update()).all()
            for row in existing:
                if (end is None or row.date_debut <= end) and (row.date_fin is None or row.date_fin >= start):
                    raise ValueError("La période recouvre une autre version active de cette convention.")
        max_version = self.session.scalar(select(func.max(ConventionOrganismeModel.version)).where(
            ConventionOrganismeModel.organisation_id == self.organisation_id,
            ConventionOrganismeModel.organisme_id == organisme.id,
            ConventionOrganismeModel.code == code,
        )) or 0
        row = ConventionOrganismeModel(
            organisation_id=self.organisation_id, organisme_id=organisme.id,
            code=code, version=max_version + 1,
            reference_contractuelle=data.get("reference_contractuelle"),
            date_debut=start, date_fin=end, statut=statut,
            conditions=data.get("conditions") or {}, extensions_p5b=data.get("extensions_p5b") or {},
            auteur_id=self.auteur_id,
        )
        self.session.add(row)
        self.session.flush()
        self._audit("CONVENTION", row.id, "CONVENTION_VERSION_CREEE", {
            "organisme_id": str(organisme.id), "code": code, "version": row.version,
            "date_debut": start.isoformat(), "date_fin": end.isoformat() if end else None,
            "statut": statut,
        })
        return serial(row)

    def creer_beneficiaire(self, data: dict) -> dict:
        self._organisation_verrouillee()
        client_id = data.get("client_id")
        if client_id:
            client = self.session.get(ClientModel, client_id)
            if client is None or client.organisation_id != self.organisation_id:
                raise LookupError("Fiche client bénéficiaire introuvable dans cette organisation.")
            if not client.actif:
                raise ValueError("Une fiche client inactive ne peut être liée à un bénéficiaire actif.")
        nom = data["nom"].strip()
        if not nom:
            raise ValueError("Le nom du bénéficiaire est obligatoire.")
        row = BeneficiaireCouvertureModel(
            organisation_id=self.organisation_id, client_id=client_id, nom=nom,
            date_naissance=data.get("date_naissance"),
            reference_externe=data.get("reference_externe"), actif=True,
            revision=1, auteur_id=self.auteur_id,
        )
        self.session.add(row)
        self.session.flush()
        self._audit("BENEFICIAIRE", row.id, "BENEFICIAIRE_CREE", {
            "client_id": str(client_id) if client_id else None,
        })
        return serial(row)

    def creer_adhesion(self, data: dict) -> dict:
        self._organisation_verrouillee()
        convention = self.session.get(ConventionOrganismeModel, data["convention_id"])
        holder = self.session.get(BeneficiaireCouvertureModel, data["titulaire_id"])
        if convention is None or convention.organisation_id != self.organisation_id:
            raise LookupError("Convention introuvable dans cette organisation.")
        if not self._organisme(convention.organisme_id).actif:
            raise ValueError('Un organisme inactif ne peut recevoir une nouvelle adhésion.')
        if holder is None or holder.organisation_id != self.organisation_id:
            raise LookupError("Titulaire de couverture introuvable dans cette organisation.")
        if not holder.actif:
            raise ValueError("Le titulaire de couverture est inactif.")
        start, end = data["date_debut"], data.get("date_fin")
        verifier_periode(start, end)
        if convention.statut != "ACTIVE" or start < convention.date_debut or (convention.date_fin and (end is None or end > convention.date_fin)):
            raise ValueError("La période d'adhésion doit être comprise dans une version active de la convention.")
        beneficiary_ids = list(dict.fromkeys(data["beneficiaire_ids"]))
        if holder.id not in beneficiary_ids:
            beneficiary_ids.insert(0, holder.id)
        beneficiaries = self.session.scalars(select(BeneficiaireCouvertureModel).where(
            BeneficiaireCouvertureModel.organisation_id == self.organisation_id,
            BeneficiaireCouvertureModel.id.in_(beneficiary_ids),
        )).all()
        if len(beneficiaries) != len(beneficiary_ids):
            raise LookupError("Un bénéficiaire est absent ou appartient à une autre organisation.")
        if any(not b.actif for b in beneficiaries):
            raise ValueError("Une adhésion ne peut inclure un bénéficiaire inactif.")
        reference = data["reference_adhesion"].strip()
        if not reference:
            raise ValueError("La référence d'adhésion est obligatoire.")
        statut = data.get("statut", "ACTIVE")
        rights = data.get("droits_statut", "A_VERIFIER")
        if statut not in ("ACTIVE", "INACTIVE", "SUSPENDUE") or rights not in ("A_VERIFIER", "CONFIRMES", "REFUSES", "SUSPENDUS"):
            raise ValueError("Statut d'adhésion ou de droits invalide.")
        if rights != "A_VERIFIER" and (not data.get("reference_verification_droits") or not data.get("droits_verifies_le")):
            raise ValueError("Une décision sur les droits doit conserver sa référence et sa date de vérification.")
        row = AdhesionOrganismeModel(
            organisation_id=self.organisation_id, convention_id=convention.id,
            titulaire_id=holder.id, reference_adhesion=reference,
            date_debut=start, date_fin=end, statut=statut, droits_statut=rights,
            reference_verification_droits=data.get("reference_verification_droits"),
            droits_verifies_le=data.get("droits_verifies_le"), revision=1,
            auteur_id=self.auteur_id,
        )
        self.session.add(row)
        self.session.flush()
        for beneficiary in beneficiaries:
            self.session.add(AdhesionBeneficiaireModel(
                organisation_id=self.organisation_id, adhesion_id=row.id,
                beneficiaire_id=beneficiary.id,
                relation="TITULAIRE" if beneficiary.id == holder.id else "AYANT_DROIT",
                date_debut=start, date_fin=end,
            ))
        self.session.flush()
        self._audit("ADHESION", row.id, "ADHESION_CREEE", {
            "convention_id": str(convention.id), "titulaire_id": str(holder.id),
            "beneficiaires_ids": [str(value) for value in beneficiary_ids],
            "droits_statut": rights,
        })
        return self.detail_adhesion(row)

    def detail_adhesion(self, row: AdhesionOrganismeModel) -> dict:
        links = self.session.scalars(select(AdhesionBeneficiaireModel).where(
            AdhesionBeneficiaireModel.organisation_id == self.organisation_id,
            AdhesionBeneficiaireModel.adhesion_id == row.id,
        ).order_by(AdhesionBeneficiaireModel.id)).all()
        return serial(row) | {"beneficiaires": [serial(link) | {"beneficiaire_nom": self.session.get(BeneficiaireCouvertureModel, link.beneficiaire_id).nom} for link in links]}

    def modifier_adhesion(self, adhesion_id: UUID, data: dict) -> dict:
        self._organisation_verrouillee()
        row = self.session.scalar(select(AdhesionOrganismeModel).where(
            AdhesionOrganismeModel.id == adhesion_id,
            AdhesionOrganismeModel.organisation_id == self.organisation_id,
        ).with_for_update())
        if row is None:
            raise LookupError("Adhésion introuvable dans cette organisation.")
        if row.revision != data["revision"]:
            raise ConflitStock("Adhésion modifiée : actualiser avant de poursuivre.")
        convention = self.session.get(ConventionOrganismeModel, row.convention_id)
        end = data.get("date_fin")
        verifier_periode(row.date_debut, end)
        if convention is None or row.date_debut < convention.date_debut or (convention.date_fin and (end is None or end > convention.date_fin)):
            raise ValueError("La période d'adhésion doit rester comprise dans la convention.")
        status = data["statut"]
        rights = data["droits_statut"]
        if status not in ("ACTIVE", "INACTIVE", "SUSPENDUE") or rights not in ("A_VERIFIER", "CONFIRMES", "REFUSES", "SUSPENDUS"):
            raise ValueError("Statut d'adhésion ou de droits invalide.")
        reference = data.get("reference_verification_droits")
        verified_at = data.get("droits_verifies_le")
        if rights != "A_VERIFIER" and (not reference or not verified_at):
            raise ValueError("Une décision sur les droits doit conserver sa référence et sa date de vérification.")
        previous = {"statut": row.statut, "droits_statut": row.droits_statut, "revision": row.revision}
        row.date_fin = end
        row.statut = status
        row.droits_statut = rights
        row.reference_verification_droits = reference if rights != "A_VERIFIER" else None
        row.droits_verifies_le = verified_at if rights != "A_VERIFIER" else None
        row.revision += 1
        self.session.flush()
        self._audit("ADHESION", row.id, "ADHESION_DROITS_MODIFIES", {
            "avant": previous,
            "apres": {"statut": status, "droits_statut": rights, "revision": row.revision},
        })
        return self.detail_adhesion(row)

    def creer_priorites(self, data: dict) -> dict:
        self._organisation_verrouillee()
        start, end = data["date_debut"], data.get("date_fin")
        verifier_periode(start, end)
        if start < self.jour:
            raise ValueError("Un nouveau paramétrage de priorité ne peut pas prendre effet rétroactivement.")
        entries = [EntreePriorite(
            organisme_id=item["organisme_id"], convention_id=item["convention_id"],
            rang=item["rang"], role=RolePriorite(item["role"]),
        ) for item in data["priorites"]]
        verifier_priorites(entries)
        statut = data.get("statut", "ACTIVE")
        if statut not in ("ACTIVE", "INACTIVE"):
            raise ValueError("Statut de paramétrage invalide.")
        version = (self.session.scalar(select(func.max(ParametragePrioriteTiersPayantModel.version)).where(
            ParametragePrioriteTiersPayantModel.organisation_id == self.organisation_id,
        )) or 0) + 1

        if statut == "ACTIVE":
            later = self.session.scalars(select(ParametragePrioriteTiersPayantModel).where(
                ParametragePrioriteTiersPayantModel.organisation_id == self.organisation_id,
                ParametragePrioriteTiersPayantModel.statut == "ACTIVE",
                ParametragePrioriteTiersPayantModel.date_debut > start,
            )).all()
            if later:
                raise ValueError("Une nouvelle priorité ne peut pas être antidatée avant une version déjà planifiée.")
            current = self.session.scalar(select(ParametragePrioriteTiersPayantModel).where(
                ParametragePrioriteTiersPayantModel.organisation_id == self.organisation_id,
                ParametragePrioriteTiersPayantModel.statut == "ACTIVE",
                ParametragePrioriteTiersPayantModel.date_debut < start,
                (ParametragePrioriteTiersPayantModel.date_fin.is_(None) | (ParametragePrioriteTiersPayantModel.date_fin >= start)),
            ).order_by(ParametragePrioriteTiersPayantModel.date_debut.desc()).with_for_update())
            if current:
                if current.date_debut >= start:
                    raise ValueError("La nouvelle priorité doit commencer après la version active.")
                current.date_fin = start - timedelta(days=1)
                self._audit("PARAMETRAGE_PRIORITE", current.id, "PARAMETRAGE_PRIORITE_CLOTURE", {
                    "date_fin": current.date_fin.isoformat(), "remplace_par_version": version + 1,
                })
        for item in data["priorites"]:
            organisme = self._organisme(item["organisme_id"])
            convention = self.session.get(ConventionOrganismeModel, item["convention_id"])
            if convention is None or convention.organisation_id != self.organisation_id or convention.organisme_id != organisme.id:
                raise ValueError("La convention doit appartenir à l'organisme et à l'organisation courants.")
            if convention.statut != "ACTIVE" or start < convention.date_debut or (convention.date_fin and (end is None or end > convention.date_fin)):
                raise ValueError("La période de priorité doit être couverte par la convention active.")
            if not organisme.actif:
                raise ValueError("Un organisme inactif ne peut être ajouté aux priorités actives.")

        header = ParametragePrioriteTiersPayantModel(
            organisation_id=self.organisation_id, version=version, date_debut=start,
            date_fin=end, statut=statut, motif=data["motif"].strip(), auteur_id=self.auteur_id,
        )
        self.session.add(header)
        self.session.flush()
        for item in entries:
            self.session.add(PrioriteOrganismeModel(
                organisation_id=self.organisation_id, parametrage_id=header.id,
                organisme_id=item.organisme_id, convention_id=item.convention_id,
                rang=item.rang, role=item.role.value,
            ))
        self.session.flush()
        self._audit("PARAMETRAGE_PRIORITE", header.id, "PARAMETRAGE_PRIORITE_CREE", {
            "version": version, "date_debut": start.isoformat(),
            "date_fin": end.isoformat() if end else None, "statut": statut,
            "priorites": [{"organisme_id": str(row.organisme_id), "convention_id": str(row.convention_id), "rang": row.rang, "role": row.role.value} for row in entries],
            "motif": data["motif"].strip(),
        })
        return self.detail_priorites(header)

    def detail_priorites(self, header: ParametragePrioriteTiersPayantModel) -> dict:
        entries = self.session.scalars(select(PrioriteOrganismeModel).where(
            PrioriteOrganismeModel.organisation_id == self.organisation_id,
            PrioriteOrganismeModel.parametrage_id == header.id,
        ).order_by(PrioriteOrganismeModel.rang)).all()
        result = serial(header)
        result["priorites"] = []
        for entry in entries:
            organismo = self._organisme(entry.organisme_id)
            convention = self.session.get(ConventionOrganismeModel, entry.convention_id)
            result["priorites"].append(serial(entry) | {
                "organisme_code": organismo.code, "organisme_nom": organismo.nom,
                "convention_code": convention.code if convention else None,
                "convention_version": convention.version if convention else None,
            })
        return result
