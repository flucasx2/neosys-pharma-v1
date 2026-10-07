from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from neosys_pharma.application.authentification_service import AuthentificationService, empreinte
from neosys_pharma.application.securite_service import SecuriteService
from neosys_pharma.domain.organisation.authentification import IdentiteNonAuthentifiee
from neosys_pharma.infrastructure.authentification_repository import SqlAlchemyAuthRepository
from neosys_pharma.infrastructure.passwords import passwords
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.config import get_settings
from neosys_pharma.infrastructure.organisation_models import SiteModel

router = APIRouter(prefix='/api/auth', tags=['Authentification'])
COOKIE = 'neosys_session'
CSRF_COOKIE = 'neosys_csrf'


def maintenant():
    return datetime.now(timezone.utc)


def jour_courant():
    return maintenant().astimezone(ZoneInfo('Africa/Libreville')).date()


def service(session):
    return AuthentificationService(SqlAlchemyAuthRepository(session), passwords, get_settings().auth_session_minutes)


def verifier_origine(request):
    origin = request.headers.get('origin')
    if origin and origin != str(request.base_url).rstrip('/'):
        raise HTTPException(403, 'Origine de requête interdite.')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Requête inter-sites interdite.')


def utilisateur_courant(request: Request, session: Session = Depends(get_db_session)):
    mutation = request.method not in ('GET', 'HEAD', 'OPTIONS')
    if mutation:
        verifier_origine(request)
    try:
        return service(session).courant(request.cookies.get(COOKIE), maintenant(), request.headers.get('X-CSRF-Token'), mutation)
    except IdentiteNonAuthentifiee as exc:
        raise HTTPException(401, str(exc), headers={'WWW-Authenticate':'Session'}) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


class ConnexionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    organisation_id: UUID
    identifiant: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128, repr=False)


@router.post('/login')
def connexion(data: ConnexionInput, request: Request, response: Response, session: Session = Depends(get_db_session)):
    verifier_origine(request)
    if request.headers.get('X-NeoSys-Request') != '1':
        raise HTTPException(403, 'En-tête de connexion requis.')
    repo = SqlAlchemyAuthRepository(session)
    now = maintenant()
    # Network identity is taken from the connection, never an arbitrary Forwarded header.
    ip = request.client.host if request.client else 'unknown'
    for cle, maximum in [(empreinte('ip:' + ip), 60), (empreinte('compte:' + str(data.organisation_id) + ':' + data.identifiant.strip().lower()), 10)]:
        if not repo.tentative(cle, now, maximum=maximum):
            raise HTTPException(429, 'Trop de tentatives. Réessayez dans cinq minutes.', headers={'Retry-After':'300'})
    try:
        user, token, csrf = service(session).connecter(data.organisation_id, data.identifiant, data.password, now)
    except IdentiteNonAuthentifiee as exc:
        raise HTTPException(401, str(exc), headers={'WWW-Authenticate':'Session'}) from exc
    previous = request.cookies.get(COOKIE)
    if previous:
        service(session).deconnecter(previous)
    settings = get_settings()
    for name, value, http_only in [(COOKIE, token, True), (CSRF_COOKIE, csrf, False)]:
        response.set_cookie(name, value, httponly=http_only, secure=settings.auth_cookie_secure, samesite='strict', path='/')
    return {'utilisateur': asdict(user), 'csrf_token': csrf}


@router.post('/logout', status_code=204)
def deconnexion(request: Request, response: Response, user=Depends(utilisateur_courant), session: Session = Depends(get_db_session)):
    service(session).deconnecter(request.cookies[COOKIE])
    for name in (COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path='/', secure=get_settings().auth_cookie_secure, samesite='strict')


@router.get('/me')
def identite(user=Depends(utilisateur_courant), session: Session = Depends(get_db_session)):
    repo = SqlAlchemyAuthRepository(session).securite
    organisation = repo.organisation(user.organisation_id)
    contexts = []
    for site in repo.parents.lister(SiteModel, organisation_id=user.organisation_id):
        result = SecuriteService(repo).permissions_resultantes(user.id_utilisateur, site["id_site"], jour_courant())
        if result['permissions_site']:
            contexts.append({'site_id': site["id_site"], 'nom': site["nom"], 'code': site["code"], **result})
    return {'utilisateur':asdict(user), 'organisation':{'id_organisation':organisation.id_organisation, 'nom_commercial':organisation.nom_commercial}, 'contextes':contexts}


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=12, max_length=128, repr=False)


@router.put('/utilisateurs/{utilisateur_id}/password', status_code=204)
def definir_password(utilisateur_id: UUID, data: PasswordInput, request: Request, user=Depends(utilisateur_courant), session: Session = Depends(get_db_session)):
    from neosys_pharma.application.controle_acces import ControleAcces
    repo = SqlAlchemyAuthRepository(session)
    target = repo.utilisateur(utilisateur_id)
    try:
        site_id = UUID(request.headers.get('X-Site-ID', ''))
        if not target or target.organisation_id != user.organisation_id:
            raise PermissionError('Utilisateur non autorisé.')
        ControleAcces(repo.securite, user, jour_courant()).verifier('utilisateur.gerer', site_id)
        service(session).definir_password(utilisateur_id, data.password)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(403, str(exc)) from exc
