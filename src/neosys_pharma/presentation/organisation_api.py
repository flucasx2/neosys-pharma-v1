from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from neosys_pharma.application.organisation_service import OrganisationService
from neosys_pharma.domain.organisation.entities import Emplacement, Organisation, Site
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.organisation_models import EmplacementModel, OrganisationModel, SiteModel
from neosys_pharma.infrastructure.organisation_repository import SqlAlchemyOrganisationRepository

router = APIRouter(prefix="/api/organisation", tags=["Organisation"])


class EmplacementInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=80)
    nom: str = Field(min_length=1, max_length=200)

    @field_validator("code")
    @classmethod
    def normaliser_code(cls, value: str) -> str:
        value = value.upper()
        if len(value) > 80:
            raise ValueError("Le code normalisé dépasse 80 caractères.")
        return value


class SiteInput(EmplacementInput):
    adresse: str | None = Field(default=None, max_length=1000)
    telephone: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    premier_emplacement: EmplacementInput


class OrganisationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nom_commercial: str = Field(min_length=1, max_length=200)
    raison_sociale: str = Field(min_length=1, max_length=200)
    logo: str | None = Field(default=None, max_length=1000)
    coordonnees: str | None = Field(default=None, max_length=2000)
    informations_legales: str | None = Field(default=None, max_length=2000)
    premier_site: SiteInput


def repository(session: Session = Depends(get_db_session)):
    return SqlAlchemyOrganisationRepository(session)


def executer(operation):
    try:
        return asdict(operation())
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/organisations")
def organisations(request: Request, repo=Depends(repository)):
    return [item for item in repo.lister(OrganisationModel) if request.state.visible_organisation(item)]


@router.post("/organisations", status_code=201)
def creer_organisation(data: OrganisationInput, repo=Depends(repository)):
    organisation = Organisation(**data.model_dump(exclude={"premier_site"}))
    site = Site(organisation_id=organisation.id_organisation, **data.premier_site.model_dump(exclude={"premier_emplacement"}))
    emplacement = Emplacement(site_id=site.id_site, **data.premier_site.premier_emplacement.model_dump())
    return executer(lambda: OrganisationService(repo).creer_organisation(organisation, site, emplacement))


@router.get("/organisations/{organisation_id}/sites")
def sites(organisation_id: UUID, request: Request, repo=Depends(repository)):
    if repo.organisation(organisation_id) is None:
        raise HTTPException(404, "Organisation introuvable.")
    return [item for item in repo.lister(SiteModel, organisation_id=organisation_id) if request.state.visible_site(item["id_site"])]


@router.post("/organisations/{organisation_id}/sites", status_code=201)
def creer_site(organisation_id: UUID, data: SiteInput, repo=Depends(repository)):
    site = Site(organisation_id=organisation_id, **data.model_dump(exclude={"premier_emplacement"}))
    emplacement = Emplacement(site_id=site.id_site, **data.premier_emplacement.model_dump())
    return executer(lambda: OrganisationService(repo).creer_site(site, emplacement))


@router.get("/sites/{site_id}/emplacements")
def emplacements(site_id: UUID, request: Request, repo=Depends(repository)):
    if repo.site(site_id) is None:
        raise HTTPException(404, "Site introuvable.")
    return [item for item in repo.lister(EmplacementModel, site_id=site_id) if request.state.visible_emplacement(item)]


@router.post("/sites/{site_id}/emplacements", status_code=201)
def creer_emplacement(site_id: UUID, data: EmplacementInput, repo=Depends(repository)):
    emplacement = Emplacement(site_id=site_id, **data.model_dump())
    return executer(lambda: OrganisationService(repo).creer_emplacement(emplacement))
