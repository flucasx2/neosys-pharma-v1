from dataclasses import asdict as raw_asdict
from fastapi.encoders import jsonable_encoder
from datetime import date
from decimal import Decimal
from uuid import UUID
from fastapi import Depends, Request, Query, HTTPException
from pydantic import Field
from neosys_pharma.presentation.catalogue_api import router, Input, executer, service
from neosys_pharma.presentation.authentification_api import utilisateur_courant, jour_courant
from neosys_pharma.application.controle_acces import ControleAcces
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.application.tarification_service import TarificationService, TARIFS


def serialiser(value):
    return jsonable_encoder(value, custom_encoder={Decimal: str})

def asdict(value):
    return serialiser(raw_asdict(value))

def verifier_site(request, org, site, user, session):
    try:
        permission = 'catalogue.consulter' if request.method == 'GET' else 'catalogue.gerer'
        ControleAcces(SqlAlchemySecuriteRepository(session), user, jour_courant()).organisation(permission, org, site)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(403, str(exc)) from exc


class TarifInput(Input):
    debut: date
    fin: date | None = None
    devise: str = Field(min_length=3, max_length=3)
    montant_ht: Decimal | None = None
    coefficient: Decimal | None = None
    site_id: UUID | None = None
    categorie_id: UUID | None = None
    produit_id: UUID | None = None
    conditionnement_id: UUID | None = None
    provenance: str | None = Field(default=None, max_length=500)


class TVAInput(Input):
    code: str = Field(min_length=1, max_length=80)
    nom: str = Field(min_length=1, max_length=200)
    taux: Decimal
    debut: date
    fin: date | None = None


class ClotureInput(Input):
    fin: date


def classe_tarif(type_tarif):
    if type_tarif not in TARIFS:
        raise HTTPException(404, 'Type de tarif inconnu.')
    return TARIFS[type_tarif]


@router.get('/tarification/{type_tarif}')
def historique(organisation_id: UUID, type_tarif: str, request: Request, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), site_id: UUID | None = None, conditionnement_id: UUID | None = None, s=Depends(service), user=Depends(utilisateur_courant), session=Depends(get_db_session)):
    cls = classe_tarif(type_tarif)
    if type_tarif in ('sites','categories','produits'):
        site_id = site_id or UUID(request.headers['X-Site-ID'])
        verifier_site(request, organisation_id, site_id, user, session)
    filters = {'site_id': site_id} if type_tarif in ('sites','categories','produits') else {}
    if conditionnement_id and type_tarif in ('references','produits'):
        filters['conditionnement_id'] = conditionnement_id
    # History is paginated in SQL, including large imported catalogues.
    from sqlalchemy import select, func
    from neosys_pharma.infrastructure.catalogue_repository import MODELES
    model = MODELES[cls]
    query = select(model).where(model.organisation_id == organisation_id)
    for k, v in filters.items(): query = query.where(getattr(model,k)==v)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(query.order_by(model.debut.desc(), *model.__table__.primary_key.columns).offset((page-1)*page_size).limit(page_size))
    return {'items': [asdict(s.repo.entity(cls,r)) for r in rows], 'total': total, 'page': page, 'page_size': page_size}


@router.post('/tarification/tva', status_code=201)
def creer_tva(organisation_id: UUID, data: TVAInput, s=Depends(service)):
    return executer(lambda: asdict(TarificationService(s).enregistrer(TARIFS['tva'](organisation_id=organisation_id, **data.model_dump()))))


@router.post('/tarification/{type_tarif}', status_code=201)
def creer_tarif(organisation_id: UUID, type_tarif: str, data: TarifInput, request: Request, s=Depends(service), user=Depends(utilisateur_courant), session=Depends(get_db_session)):
    cls = classe_tarif(type_tarif)
    if type_tarif=='tva': raise HTTPException(422,'Utiliser le formulaire TVA.')
    from dataclasses import fields
    required = {f.name for f in fields(cls)}
    attrs = data.model_dump()
    if any(v is not None and k not in required for k,v in attrs.items()):
        raise HTTPException(422, 'Champ incompatible avec ce niveau tarifaire.')
    attrs = {k:v for k,v in attrs.items() if k in required}
    for key in ('site_id','categorie_id','produit_id','conditionnement_id'):
        if key in required and attrs.get(key) is None: raise HTTPException(422, f'{key} obligatoire.')
    if type_tarif=='references' and attrs['montant_ht'] is None: raise HTTPException(422,'Montant HT obligatoire.')
    if attrs.get('site_id'): verifier_site(request, organisation_id, attrs['site_id'], user, session)
    return executer(lambda: asdict(TarificationService(s).enregistrer(cls(organisation_id=organisation_id, **attrs))))


@router.put('/tarification/{type_tarif}/{identifiant}/cloture')
def cloturer_tarif(organisation_id: UUID, type_tarif: str, identifiant: UUID, data: ClotureInput, request: Request, s=Depends(service), user=Depends(utilisateur_courant), session=Depends(get_db_session)):
    cls = classe_tarif(type_tarif)
    old = executer(lambda: s.obtenir(cls, identifiant, organisation_id))
    if hasattr(old, 'site_id'): verifier_site(request, organisation_id, old.site_id, user, session)
    return executer(lambda: asdict(TarificationService(s).cloturer(cls,identifiant,organisation_id,data.fin)))


@router.get('/prix/{identifiant}')
def prix(organisation_id: UUID, identifiant: UUID, request: Request, jour: date | None = None, site_id: UUID | None = None, s=Depends(service), user=Depends(utilisateur_courant), session=Depends(get_db_session)):
    site_id = site_id or UUID(request.headers['X-Site-ID'])
    verifier_site(request, organisation_id, site_id, user, session)
    return executer(lambda: serialiser(TarificationService(s).resoudre(organisation_id,site_id,identifiant,jour or jour_courant())))
