"""API P5-A : référentiel, conventions, adhésions et ordre contractuel."""
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import select

from neosys_pharma.application.tiers_payants_service import TiersPayantsService
from neosys_pharma.infrastructure.tiers_payants_models import (
    AdhesionOrganismeModel, BeneficiaireCouvertureModel, ConventionOrganismeModel,
    ParametragePrioriteTiersPayantModel,
)
from neosys_pharma.presentation import vente_api
from neosys_pharma.presentation.stock_api import execute
from neosys_pharma.application.stock_service import serial


POLICY = {
    "tiers_payants_conventions": ("tiers_payant.consulter", "tiers_payant.convention.gerer"),
    "tiers_payants_convention_creer": "tiers_payant.convention.gerer",
    "tiers_payants_beneficiaires": "tiers_payant.adhesion.consulter",
    "tiers_payants_beneficiaire_creer": "tiers_payant.adhesion.gerer",
    "tiers_payants_adhesions": "tiers_payant.adhesion.consulter",
    "tiers_payants_adhesion_creer": "tiers_payant.adhesion.gerer",
    "tiers_payants_adhesion_modifier": "tiers_payant.adhesion.gerer",
    "tiers_payants_priorites": ("tiers_payant.consulter", "tiers_payant.priorites.gerer"),
    "tiers_payants_priorites_creer": "tiers_payant.priorites.gerer",
}
vente_api.POLICY.update(POLICY)

router = APIRouter(
    prefix="/api/tiers-payants/organisations/{organisation_id}",
    tags=["Tiers payants - référentiel P5-A"],
    dependencies=[Depends(vente_api.contexte)],
)

Input = vente_api.Input
Mutation = vente_api.Mutation


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


def service(base=Depends(vente_api.service)):
    return TiersPayantsService(base.stock)


def mutate(s: TiersPayantsService, data: Mutation, kind: str, action):
    body = data.model_dump(mode="json", exclude={"cle"})
    return execute(lambda: s.stock.operation(data.cle, "P5A:" + kind, body, action))


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
def beneficiaires(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), client_id: UUID | None = None, s=Depends(service)):
    query = select(BeneficiaireCouvertureModel).where(BeneficiaireCouvertureModel.organisation_id == s.organisation_id)
    if client_id:
        query = query.where(BeneficiaireCouvertureModel.client_id == client_id)
    total, rows = s.stock.repo.paginer(query.order_by(BeneficiaireCouvertureModel.nom, BeneficiaireCouvertureModel.id), page, page_size)
    return {"items": [serial(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/beneficiaires", status_code=201, name="tiers_payants_beneficiaire_creer")
def beneficiaire_creer(data: BeneficiaireInput, s=Depends(service)):
    return mutate(s, data, "BENEFICIAIRE", lambda: s.creer_beneficiaire(data.model_dump(exclude={"cle"})))


@router.get("/adhesions", name="tiers_payants_adhesions")
def adhesions(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), titulaire_id: UUID | None = None, s=Depends(service)):
    query = select(AdhesionOrganismeModel).where(AdhesionOrganismeModel.organisation_id == s.organisation_id)
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
