"""Administration P1 en développement. Authentification HTTP à intégrer séparément."""
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from neosys_pharma.application.securite_service import SecuriteService, obligatoire
from neosys_pharma.domain.organisation.securite import Utilisateur, AffectationSite, Role, TypeRole
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository

router = APIRouter(prefix='/api/organisation', tags=['Utilisateurs et droits P1'])


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class UtilisateurInput(Input):
    identifiant: str = Field(min_length=1, max_length=80)
    nom: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    actif: bool = True


class UtilisateurModification(Input):
    nom: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    actif: bool


class PeriodeInput(Input):
    date_debut: date
    date_fin: date | None = None
    actif: bool = True


class AffectationInput(PeriodeInput):
    site_id: UUID


class LiensInput(Input):
    ids: list[UUID] = Field(max_length=500)


class RoleInput(Input):
    code: str = Field(min_length=1, max_length=80)
    nom: str = Field(min_length=1, max_length=200)
    permission_ids: list[UUID] = Field(default_factory=list, max_length=500)


def repository(session: Session = Depends(get_db_session)):
    return SqlAlchemySecuriteRepository(session)


def executer(action):
    try:
        result = action()
        return asdict(result) if is_dataclass(result) else result
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        status = 409 if 'Doublon' in str(error) else 422
        raise HTTPException(status, str(error)) from error


@router.get('/organisations/{organisation_id}/utilisateurs')
def utilisateurs(organisation_id: UUID, repo=Depends(repository)):
    def action():
        obligatoire(repo.organisation(organisation_id), 'Organisation')
        return [asdict(item) for item in repo.utilisateurs(organisation_id)]
    return executer(action)


@router.post('/organisations/{organisation_id}/utilisateurs', status_code=201)
def creer_utilisateur(organisation_id: UUID, data: UtilisateurInput, repo=Depends(repository)):
    return executer(lambda: SecuriteService(repo).creer_utilisateur(Utilisateur(organisation_id=organisation_id, **data.model_dump())))


@router.put('/utilisateurs/{utilisateur_id}')
def modifier_utilisateur(utilisateur_id: UUID, data: UtilisateurModification, repo=Depends(repository)):
    return executer(lambda: SecuriteService(repo).modifier_utilisateur(utilisateur_id, **data.model_dump()))


@router.get('/utilisateurs/{utilisateur_id}/affectations')
def affectations(utilisateur_id: UUID, repo=Depends(repository)):
    def action():
        obligatoire(repo.utilisateur(utilisateur_id), 'Utilisateur')
        return [SecuriteService(repo).details_affectation(item) for item in repo.affectations(utilisateur_id)]
    return executer(action)


@router.post('/utilisateurs/{utilisateur_id}/affectations', status_code=201)
def creer_affectation(utilisateur_id: UUID, data: AffectationInput, repo=Depends(repository)):
    return executer(lambda: SecuriteService(repo).creer_affectation(AffectationSite(utilisateur_id=utilisateur_id, **data.model_dump())))


@router.put('/affectations/{affectation_id}')
def modifier_affectation(affectation_id: UUID, data: PeriodeInput, repo=Depends(repository)):
    return executer(lambda: SecuriteService(repo).modifier_affectation(affectation_id, **data.model_dump()))


@router.put('/affectations/{affectation_id}/emplacements')
def emplacements(affectation_id: UUID, data: LiensInput, repo=Depends(repository)):
    return executer(lambda: SecuriteService(repo).definir_emplacements(affectation_id, data.ids))


@router.put('/affectations/{affectation_id}/roles')
def affecter_roles(affectation_id: UUID, data: LiensInput, repo=Depends(repository)):
    return executer(lambda: SecuriteService(repo).definir_roles(affectation_id, data.ids))


@router.get('/permissions')
def permissions(repo=Depends(repository)):
    return [asdict(item) for item in repo.permissions()]


@router.get('/organisations/{organisation_id}/roles')
def roles(organisation_id: UUID, repo=Depends(repository)):
    def action():
        obligatoire(repo.organisation(organisation_id), 'Organisation')
        return [{**asdict(role), 'permissions': [asdict(p) for p in repo.permissions_role(role.id_role)]} for role in repo.roles(organisation_id)]
    return executer(action)


@router.post('/organisations/{organisation_id}/roles', status_code=201)
def creer_role(organisation_id: UUID, data: RoleInput, repo=Depends(repository)):
    return executer(lambda: SecuriteService(repo).creer_role(Role(organisation_id=organisation_id, type_role=TypeRole.PERSONNALISE, code=data.code, nom=data.nom), data.permission_ids))


@router.put('/roles/{role_id}/permissions')
def definir_permissions(role_id: UUID, data: LiensInput, repo=Depends(repository)):
    return executer(lambda: SecuriteService(repo).definir_permissions(role_id, data.ids))


@router.get('/utilisateurs/{utilisateur_id}/sites/{site_id}/permissions')
def resultantes(utilisateur_id: UUID, site_id: UUID, jour: date | None = None, repo=Depends(repository)):
    jour = jour or datetime.now(ZoneInfo('Africa/Libreville')).date()
    return executer(lambda: SecuriteService(repo).permissions_resultantes(utilisateur_id, site_id, jour))
