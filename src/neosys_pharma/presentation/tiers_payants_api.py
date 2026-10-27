"""API P5-A : référentiel, conventions, adhésions et ordre contractuel."""
from datetime import date, datetime
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy import or_, select

from neosys_pharma.application.configuration_convention_service import ConfigurationConventionService
from neosys_pharma.application.tiers_payants_service import TiersPayantsService
from neosys_pharma.infrastructure.client_models import OrganismePriseEnChargeModel
from neosys_pharma.infrastructure.tiers_payants_models import (
    AdhesionOrganismeModel, BeneficiaireCouvertureModel, ConventionOrganismeModel,
    ParametragePrioriteTiersPayantModel, VerificationConventionModel,
)
from neosys_pharma.application.prise_en_charge_persistante_service import PriseEnChargePersistanteService
from neosys_pharma.presentation import vente_api
from neosys_pharma.presentation.stock_api import execute
from neosys_pharma.application.stock_service import serial


POLICY = {
    "beneficiaires_import_prevoir":"tiers_payant.adhesion.gerer",
    "beneficiaires_import_confirmer":"tiers_payant.adhesion.gerer",
    "conventions_configurees_creer": "tiers_payant.convention.gerer",
    "conventions_configurees_detail": ("tiers_payant.consulter", "tiers_payant.convention.gerer"),
    "conventions_preuve_creer": "tiers_payant.adhesion.gerer",
    "conventions_preuves_lire": "tiers_payant.adhesion.consulter",
    "tiers_payants_organismes": ("tiers_payant.consulter", "tiers_payant.organisme.gerer"),
    "tiers_payants_organisme_detail": ("tiers_payant.consulter", "tiers_payant.organisme.gerer"),
    "tiers_payants_organisme_creer": "tiers_payant.organisme.gerer",
    "tiers_payants_organisme_modifier": "tiers_payant.organisme.gerer",
    "tiers_payants_conventions": ("tiers_payant.consulter", "tiers_payant.convention.gerer"),
    "tiers_payants_convention_creer": "tiers_payant.convention.gerer",
    "tiers_payants_beneficiaires": "tiers_payant.adhesion.consulter",
    "tiers_payants_beneficiaire_creer": "tiers_payant.adhesion.gerer",
    "tiers_payants_adhesions": "tiers_payant.adhesion.consulter",
    "tiers_payants_adhesion_creer": "tiers_payant.adhesion.gerer",
    "tiers_payants_adhesion_modifier": "tiers_payant.adhesion.gerer",
    "tiers_payants_priorites": ("tiers_payant.consulter", "tiers_payant.priorites.gerer"),
    "tiers_payants_priorites_creer": "tiers_payant.priorites.gerer",
    "prise_en_charge_simuler": "vente.consulter",
    "prise_en_charge_confirmer": "vente.transmettre",
    "prise_en_charge_consulter": "vente.consulter",
}
vente_api.POLICY.update(POLICY)

router = APIRouter(
    prefix="/api/tiers-payants/organisations/{organisation_id}",
    tags=["Tiers payants - référentiel P5-A"],
    dependencies=[Depends(vente_api.contexte)],
)

Input = vente_api.Input
Mutation = vente_api.Mutation


class OrganismeInput(Mutation):
    code: str = Field(min_length=1, max_length=80)
    nom: str = Field(min_length=1, max_length=200)


class OrganismeModification(OrganismeInput):
    revision: int = Field(strict=True, ge=1)
    actif: bool = Field(strict=True)


class ConventionInput(Mutation):
    organisme_id: UUID
    code: str = Field(min_length=1, max_length=80)
    reference_contractuelle: str | None = Field(default=None, max_length=200)
    date_debut: date
    date_fin: date | None = None
    statut: str = Field(default="ACTIVE", pattern="^(ACTIVE|INACTIVE)$")
    conditions: dict = Field(default_factory=dict)
    extensions_p5b: dict = Field(default_factory=dict)


class BeneficiaireInput(Mutation):
    client_id: UUID | None = None
    nom: str = Field(min_length=1, max_length=200)
    date_naissance: date | None = None
    reference_externe: str | None = Field(default=None, max_length=200)


class AdhesionInput(Mutation):
    convention_id: UUID
    titulaire_id: UUID
    beneficiaire_ids: list[UUID] = Field(min_length=1, max_length=100)
    reference_adhesion: str = Field(min_length=1, max_length=200)
    date_debut: date
    date_fin: date | None = None
    statut: str = Field(default="ACTIVE", pattern="^(ACTIVE|INACTIVE|SUSPENDUE)$")
    droits_statut: str = Field(default="A_VERIFIER", pattern="^(A_VERIFIER|CONFIRMES|REFUSES|SUSPENDUS)$")
    reference_verification_droits: str | None = Field(default=None, max_length=200)
    droits_verifies_le: datetime | None = None


class AdhesionModification(Mutation):
    revision: int = Field(strict=True, ge=1)
    date_fin: date | None = None
    statut: str = Field(pattern="^(ACTIVE|INACTIVE|SUSPENDUE)$")
    droits_statut: str = Field(pattern="^(A_VERIFIER|CONFIRMES|REFUSES|SUSPENDUS)$")
    reference_verification_droits: str | None = Field(default=None, max_length=200)
    droits_verifies_le: datetime | None = None


class PrioriteInput(Input):
    organisme_id: UUID
    convention_id: UUID
    rang: int = Field(strict=True, gt=0, le=100)
    role: str = Field(pattern="^(PRINCIPAL|SECONDAIRE)$")


class PrioritesInput(Mutation):
    date_debut: date
    date_fin: date | None = None
    statut: str = Field(default="ACTIVE", pattern="^(ACTIVE|INACTIVE)$")
    motif: str = Field(min_length=1, max_length=2000)
    priorites: list[PrioriteInput] = Field(min_length=1, max_length=100)


class CalculPriseEnChargeInput(Input):
    beneficiaire_id: UUID | None = None


class ConfirmationPriseEnChargeInput(Mutation):
    revision: int = Field(strict=True, ge=1)
    beneficiaire_id: UUID


def service(base=Depends(vente_api.service)):
    return TiersPayantsService(base.stock)


def mutate(s: TiersPayantsService, data: Mutation, kind: str, action):
    body = data.model_dump(mode="json", exclude={"cle"})
    return execute(lambda: s.stock.operation(data.cle, "P5A:" + kind, body, action))


def _vente_access(request, s, vente_id, permissions):
    sale = execute(lambda: vente_api.vente(s, request, vente_id))
    try:
        for permission in permissions:
            request.state.vente_controle.organisation(permission, s.org, s.site)
            request.state.vente_controle.verifier(permission, s.site, sale.emplacement_id)
    except PermissionError as exc:
        from fastapi import HTTPException
        raise HTTPException(403, "Permissions Vente et tiers payant requises.") from exc
    return sale


@router.post("/ventes/{vente_id}/prise-en-charge/simuler", name="prise_en_charge_simuler")
def prise_en_charge_simuler(vente_id: UUID, data: CalculPriseEnChargeInput, request: Request, s=Depends(vente_api.service)):
    _vente_access(request, s, vente_id, ("vente.consulter", "tiers_payant.consulter"))
    app_service = PriseEnChargePersistanteService(s.stock, s.site)
    return execute(lambda: app_service.simuler(vente_id, data.beneficiaire_id))


@router.post("/ventes/{vente_id}/prise-en-charge/confirmer", status_code=201, name="prise_en_charge_confirmer")
def prise_en_charge_confirmer(vente_id: UUID, data: ConfirmationPriseEnChargeInput, request: Request, s=Depends(vente_api.service)):
    sale = _vente_access(request, s, vente_id, ("vente.transmettre", "tiers_payant.consulter"))
    body = data.model_dump(mode="json", exclude={"cle"})
    service = PriseEnChargePersistanteService(s.stock, s.site)
    return execute(lambda: s.stock.operation(
        data.cle, "P5B2:CONFIRMER:" + str(vente_id), body,
        lambda: service.confirmer(vente_id, data.beneficiaire_id, data.revision),
    ))


@router.get("/ventes/{vente_id}/prise-en-charge", name="prise_en_charge_consulter")
def prise_en_charge_consulter(vente_id: UUID, request: Request, s=Depends(vente_api.service)):
    _vente_access(request, s, vente_id, ("vente.consulter", "tiers_payant.consulter"))
    return execute(lambda: PriseEnChargePersistanteService(s.stock, s.site).consulter(vente_id))


@router.get("/conventions", name="tiers_payants_conventions")
def conventions(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), organisme_id: UUID | None = None, s=Depends(service)):
    query = select(ConventionOrganismeModel).where(ConventionOrganismeModel.organisation_id == s.organisation_id)
    if organisme_id:
        query = query.where(ConventionOrganismeModel.organisme_id == organisme_id)
    total, rows = s.stock.repo.paginer(query.order_by(ConventionOrganismeModel.organisme_id, ConventionOrganismeModel.code, ConventionOrganismeModel.version.desc()), page, page_size)
    return {"items": [serial(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/conventions", status_code=201, name="tiers_payants_convention_creer")
def convention_creer(data: ConventionInput, s=Depends(service)):
    return mutate(s, data, "CONVENTION", lambda: s.creer_convention(data.model_dump(exclude={"cle"})))


@router.get("/beneficiaires", name="tiers_payants_beneficiaires")
def beneficiaires(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), client_id: UUID | None = None, q: str = Query("", max_length=200), s=Depends(service)):
    query = select(BeneficiaireCouvertureModel).where(BeneficiaireCouvertureModel.organisation_id == s.organisation_id)
    if q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(or_(BeneficiaireCouvertureModel.nom.ilike("%"+term+"%", escape="\\"), BeneficiaireCouvertureModel.reference_externe.ilike("%"+term+"%", escape="\\")))
    if client_id:
        query = query.where(BeneficiaireCouvertureModel.client_id == client_id)
    total, rows = s.stock.repo.paginer(query.order_by(BeneficiaireCouvertureModel.nom, BeneficiaireCouvertureModel.id), page, page_size)
    return {"items": [serial(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/beneficiaires", status_code=201, name="tiers_payants_beneficiaire_creer")
def beneficiaire_creer(data: BeneficiaireInput, s=Depends(service)):
    return mutate(s, data, "BENEFICIAIRE", lambda: s.creer_beneficiaire(data.model_dump(exclude={"cle"})))


@router.get("/adhesions", name="tiers_payants_adhesions")
def adhesions(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), titulaire_id: UUID | None = None, convention_id: UUID | None = None, q: str = Query("", max_length=200), s=Depends(service)):
    query = select(AdhesionOrganismeModel).where(AdhesionOrganismeModel.organisation_id == s.organisation_id)
    if convention_id:
        query = query.where(AdhesionOrganismeModel.convention_id == convention_id)
    if q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(AdhesionOrganismeModel.reference_adhesion.ilike("%"+term+"%", escape="\\"))
    if titulaire_id:
        query = query.where(AdhesionOrganismeModel.titulaire_id == titulaire_id)
    total, rows = s.stock.repo.paginer(query.order_by(AdhesionOrganismeModel.date_debut.desc(), AdhesionOrganismeModel.id), page, page_size)
    return {"items": [s.detail_adhesion(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/adhesions", status_code=201, name="tiers_payants_adhesion_creer")
def adhesion_creer(data: AdhesionInput, s=Depends(service)):
    return mutate(s, data, "ADHESION", lambda: s.creer_adhesion(data.model_dump(exclude={"cle"})))


@router.put("/adhesions/{adhesion_id}", name="tiers_payants_adhesion_modifier")
def adhesion_modifier(adhesion_id: UUID, data: AdhesionModification, s=Depends(service)):
    return mutate(s, data, "ADHESION_MODIFIER", lambda: s.modifier_adhesion(adhesion_id, data.model_dump(exclude={"cle"})))


@router.get("/priorites", name="tiers_payants_priorites")
def priorites(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), s=Depends(service)):
    query = select(ParametragePrioriteTiersPayantModel).where(ParametragePrioriteTiersPayantModel.organisation_id == s.organisation_id)
    total, rows = s.stock.repo.paginer(query.order_by(ParametragePrioriteTiersPayantModel.version.desc()), page, page_size)
    return {"items": [s.detail_priorites(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/priorites", status_code=201, name="tiers_payants_priorites_creer")
def priorites_creer(data: PrioritesInput, s=Depends(service)):
    payload = data.model_dump(exclude={"cle"})
    return mutate(s, data, "PRIORITES", lambda: s.creer_priorites(payload))


@router.get("/organismes", name="tiers_payants_organismes")
def organismes(q: str = Query("", max_length=200), actif: bool | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
               s=Depends(service)):
    query = select(OrganismePriseEnChargeModel).where(
        OrganismePriseEnChargeModel.organisation_id == s.organisation_id)
    if actif is not None:
        query = query.where(OrganismePriseEnChargeModel.actif == actif)
    if q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(or_(OrganismePriseEnChargeModel.code.ilike("%" + term + "%", escape="\\"),
                               OrganismePriseEnChargeModel.nom.ilike("%" + term + "%", escape="\\")))
    total, rows = s.stock.repo.paginer(query.order_by(
        OrganismePriseEnChargeModel.nom, OrganismePriseEnChargeModel.id), page, page_size)
    return {"items": [serial(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/organismes/{organisme_id}", name="tiers_payants_organisme_detail")
def organisme_detail(organisme_id: UUID, s=Depends(service)):
    return execute(lambda: serial(s._organisme(organisme_id)))


@router.post("/organismes", status_code=201, name="tiers_payants_organisme_creer")
def organisme_creer(data: OrganismeInput, s=Depends(service)):
    return mutate(s, data, "ORGANISME_CREE", lambda: s.creer_organisme(data.code, data.nom))


@router.put("/organismes/{organisme_id}", name="tiers_payants_organisme_modifier")
def organisme_modifier(organisme_id: UUID, data: OrganismeModification, s=Depends(service)):
    return mutate(s, data, "ORGANISME_MODIFIE:" + str(organisme_id),
                  lambda: s.modifier_organisme(organisme_id, data.revision, data.code, data.nom, data.actif))


class ConventionConfigureeInput(ConventionInput):
    revision_organisme: int = Field(strict=True, ge=1)
    version_attendue: int = Field(strict=True, ge=0)
    configuration: dict
    conditions: dict = Field(default_factory=lambda: {"schema_version": 1})


class VerificationConventionInput(Mutation):
    adhesion_id: UUID
    beneficiaire_id: UUID
    revision_adhesion: int = Field(strict=True, ge=1)
    source: str = Field(pattern="^(LISTE|IDENTIFICATION|EXTERNE)$")
    reference: str = Field(min_length=1, max_length=200)
    resultat: str = Field(pattern="^(CONFIRME|REFUSE)$")
    motif: str = Field(min_length=1, max_length=1000)
    date_verification: date
    date_fin: date
    valeurs: dict = Field(default_factory=dict)
    documents: list[dict] = Field(default_factory=list, max_length=100)


@router.post("/conventions-configurees", status_code=201, name="conventions_configurees_creer")
def convention_configuree_creer(data: ConventionConfigureeInput, s=Depends(service)):
    if data.conditions != {"schema_version": 1} or type(data.conditions.get("schema_version")) is not int:
        from fastapi import HTTPException
        raise HTTPException(422, "Conditions non prises en charge; aucun champ contractuel ne peut être ignoré.")
    return mutate(s, data, "CONVENTION_CONFIGUREE", lambda: ConfigurationConventionService(s).creer(data.model_dump(exclude={"cle"})))


@router.get("/conventions/{convention_id}", name="conventions_configurees_detail")
def convention_configuree_detail(convention_id: UUID, s=Depends(service)):
    return execute(lambda: ConfigurationConventionService(s).detail(convention_id))


@router.post("/ventes/{vente_id}/verifications", status_code=201, name="conventions_preuve_creer")
def convention_preuve_creer(vente_id: UUID, data: VerificationConventionInput, request: Request, s=Depends(vente_api.service)):
    sale = _vente_access(request, s, vente_id, ("vente.consulter", "tiers_payant.adhesion.gerer"))
    body = data.model_dump(mode="json", exclude={"cle"})
    config_service = ConfigurationConventionService(TiersPayantsService(s.stock))
    return execute(lambda: s.stock.operation(data.cle, "P5CONF:PREUVE:"+str(vente_id), body,
        lambda: config_service.verifier(sale, data.adhesion_id, data.model_dump(exclude={"cle", "adhesion_id"}))))


@router.get("/ventes/{vente_id}/verifications", name="conventions_preuves_lire")
def convention_preuves_lire(vente_id: UUID, request: Request, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), s=Depends(vente_api.service)):
    _vente_access(request, s, vente_id, ("vente.consulter", "tiers_payant.adhesion.consulter"))
    total, rows = s.stock.repo.paginer(select(VerificationConventionModel).where(
        VerificationConventionModel.organisation_id == s.org,
        VerificationConventionModel.vente_id == vente_id,
        VerificationConventionModel.site_id == s.site).order_by(VerificationConventionModel.cree_le.desc(), VerificationConventionModel.id), page, page_size)
    return {"items": [serial(row) for row in rows], "total": total, "page": page, "page_size": page_size}


class ImportBeneficiaires(Mutation):
    organisme_id:UUID
    nom_fichier:str=Field(min_length=1,max_length=200)
    format:Literal['CSV','XLSX']
    contenu_base64:str=Field(min_length=1,max_length=5_400_000)
    feuille:str|None=Field(default=None,max_length=200)
class ImportBeneficiairesConfirmer(ImportBeneficiaires):
    empreinte_attendue:str=Field(pattern=r'^[a-f0-9]{64}$')
    confirmer:bool=Field(strict=True)

@router.post('/imports/beneficiaires/previsualiser',name='beneficiaires_import_prevoir')
def beneficiaires_import_prevoir(data:ImportBeneficiaires,s=Depends(service)):
    from neosys_pharma.application.import_beneficiaires_service import ImportBeneficiairesService
    return execute(lambda:ImportBeneficiairesService(s).analyser(data.model_dump()))

@router.post('/imports/beneficiaires/confirmer',name='beneficiaires_import_confirmer')
def beneficiaires_import_confirmer(data:ImportBeneficiairesConfirmer,s=Depends(service)):
    from neosys_pharma.application.import_beneficiaires_service import ImportBeneficiairesService
    return mutate(s,data,'IMPORT_BENEFICIAIRES',lambda:ImportBeneficiairesService(s).confirmer(data.model_dump()))
