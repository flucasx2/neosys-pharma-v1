"""API P4-B des fiches client et des organismes de prise en charge (sans calcul P5)."""
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import or_, select

from neosys_pharma.application.caisse_service import CaisseService, serial
from neosys_pharma.infrastructure.client_models import ClientModel, ClientOrganismeModel, OrganismePriseEnChargeModel
from neosys_pharma.infrastructure.caisse_models import ClientFideliteModel, CompteFideliteModel, EncaissementModel
from neosys_pharma.infrastructure.vente_models import VenteModel
from neosys_pharma.presentation.vente_api import POLICY, Input, Mutation, Revision, contexte, service as vente_service
from neosys_pharma.presentation.stock_api import execute

POLICY.update({
    'clients_liste': ('client.consulter','client.gerer'), 'client_detail_route': ('client.consulter','client.gerer'), 'client_ventes': 'client.consulter',
    'client_creer': 'client.gerer', 'client_modifier': 'client.gerer',
    'organismes_liste': ('client.consulter','client.gerer'), 'organisme_creer': 'client.gerer', 'client_organisme_associer': 'client.gerer',
    'client_organisme_retirer': 'client.gerer', 'client_fidelite_adhesion': 'fidelite.gerer',
})
router = APIRouter(prefix='/api/clients/organisations/{organisation_id}', tags=['Clients et organismes de prise en charge'], dependencies=[Depends(contexte)])


class Fiche(Mutation):
    nom: str = Field(min_length=1, max_length=200)
    telephone: str | None = Field(default=None, max_length=80)
    courriel: str | None = Field(default=None, max_length=254)


class Modification(Revision):
    nom: str = Field(min_length=1, max_length=200)
    telephone: str | None = Field(default=None, max_length=80)
    courriel: str | None = Field(default=None, max_length=254)
    actif: bool = True


class Organisme(Mutation):
    code: str = Field(min_length=1, max_length=80)
    nom: str = Field(min_length=1, max_length=200)


class Association(Mutation):
    organisme_id: UUID
    role: str = Field(pattern='^(PRINCIPAL|COMPLEMENTAIRE)$')
    reference: str | None = Field(default=None, max_length=200)


def clean_phone(value):
    if value is None:return None
    result=re.sub(r'[\s().-]', '', value)
    return result or None


def operation(s, data, kind, fn):
    return execute(lambda:s.stock.operation(data.cle, 'P4B:' + kind, data.model_dump(mode='json', exclude={'cle'}), fn))


def get_client(s, key):
    row=s.s.get(ClientModel, key)
    if not row or row.organisation_id != s.org:raise HTTPException(404, 'Fiche client introuvable.')
    return row


def client_detail(s, row):
    fidelity=s.s.scalar(select(ClientFideliteModel).where(ClientFideliteModel.organisation_id==s.org, ClientFideliteModel.profil_client_id==row.id))
    account=s.s.scalar(select(CompteFideliteModel).where(CompteFideliteModel.organisation_id==s.org, CompteFideliteModel.client_id==fidelity.id)) if fidelity else None
    links=s.s.scalars(select(ClientOrganismeModel).where(ClientOrganismeModel.organisation_id==s.org, ClientOrganismeModel.client_id==row.id, ClientOrganismeModel.actif.is_(True))).all()
    organisms=[]
    for link in links:
        organism=s.s.get(OrganismePriseEnChargeModel, link.organisme_id)
        if organism and organism.organisation_id==s.org:
            organisms.append({'id':str(link.id),'organisme_id':str(organism.id),'code':organism.code,'nom':organism.nom,'role':link.role,'reference':link.reference})
    return serial(row)|{'organismes':organisms,'fidelite':({'compte_id':str(account.id),'points':account.points,'dette':account.dette} if account else None)}


@router.get('')
def clients_liste(q: str = Query('', max_length=200), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), s=Depends(vente_service)):
    query=select(ClientModel).where(ClientModel.organisation_id==s.org)
    if q.strip():
        like='%'+q.strip()+'%'
        filters=[ClientModel.nom.ilike(like),ClientModel.telephone.ilike(like),ClientModel.courriel.ilike(like)]
        try:filters.append(ClientModel.id==UUID(q.strip()))
        except ValueError:pass
        query=query.where(or_(*filters))
    total,rows=s.stock.repo.paginer(query.order_by(ClientModel.nom,ClientModel.id),page,page_size)
    return {'items':[client_detail(s,row) for row in rows],'total':total,'page':page,'page_size':page_size}


@router.post('', status_code=201)
def client_creer(data: Fiche, s=Depends(vente_service)):
    def create():
        row=s.stock.ajouter(ClientModel,nom=data.nom.strip(),telephone=clean_phone(data.telephone),courriel=data.courriel.strip().lower() if data.courriel else None)
        return client_detail(s,row)
    return operation(s,data,'CLIENT_CREE',create)


@router.get('/organismes')
def organismes_liste(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), s=Depends(vente_service)):
    query=select(OrganismePriseEnChargeModel).where(OrganismePriseEnChargeModel.organisation_id==s.org,OrganismePriseEnChargeModel.actif.is_(True)).order_by(OrganismePriseEnChargeModel.nom,OrganismePriseEnChargeModel.id)
    total,rows=s.stock.repo.paginer(query,page,page_size)
    return {'items':[serial(row) for row in rows],'total':total,'page':page,'page_size':page_size}


@router.post('/organismes', status_code=201)
def organisme_creer(data: Organisme, s=Depends(vente_service)):
    return operation(s,data,'ORGANISME_CREE',lambda:serial(s.stock.ajouter(OrganismePriseEnChargeModel,code=data.code.strip().upper(),nom=data.nom.strip())))


@router.get('/{client_id}')
def client_detail_route(client_id: UUID, s=Depends(vente_service)):
    return client_detail(s,get_client(s,client_id))


@router.put('/{client_id}')
def client_modifier(client_id: UUID, data: Modification, s=Depends(vente_service)):
    def update():
        row=get_client(s,client_id)
        if row.revision!=data.revision:raise ValueError('Fiche client modifiée : actualiser avant de poursuivre.')
        row.nom=data.nom.strip();row.telephone=clean_phone(data.telephone);row.courriel=data.courriel.strip().lower() if data.courriel else None;row.actif=data.actif;row.revision+=1
        # Les coordonnées de l'ancien profil fidélité sont maintenues pour compatibilité.
        legacy=s.s.scalar(select(ClientFideliteModel).where(ClientFideliteModel.organisation_id==s.org,ClientFideliteModel.profil_client_id==row.id))
        if legacy:legacy.nom=row.nom;legacy.telephone=row.telephone
        return client_detail(s,row)
    return operation(s,data,'CLIENT_MODIFIE:'+str(client_id),update)


@router.post('/{client_id}/organismes', status_code=201)
def client_organisme_associer(client_id: UUID, data: Association, s=Depends(vente_service)):
    def attach():
        row=get_client(s,client_id)
        if not row.actif:raise ValueError('Une fiche inactive ne peut pas recevoir une association.')
        organism=s.s.get(OrganismePriseEnChargeModel,data.organisme_id)
        if not organism or organism.organisation_id!=s.org or not organism.actif:raise PermissionError('Organisme absent, inactif ou hors organisation.')
        if data.role=='PRINCIPAL' and s.s.scalar(select(ClientOrganismeModel.id).where(ClientOrganismeModel.organisation_id==s.org,ClientOrganismeModel.client_id==row.id,ClientOrganismeModel.role=='PRINCIPAL',ClientOrganismeModel.actif.is_(True))):raise ValueError('Un organisme principal actif existe déjà.')
        link=s.stock.ajouter(ClientOrganismeModel,client_id=row.id,organisme_id=organism.id,role=data.role,reference=data.reference.strip() if data.reference else None)
        return client_detail(s,row)|{'association_id':str(link.id)}
    return operation(s,data,'ORGANISME_ASSOCIE:'+str(client_id),attach)


@router.delete('/{client_id}/organismes/{association_id}', status_code=200)
def client_organisme_retirer(client_id: UUID, association_id: UUID, cle: UUID, s=Depends(vente_service)):
    class Key(Mutation):pass
    data=Key(cle=cle)
    def remove():
        row=get_client(s,client_id);link=s.s.get(ClientOrganismeModel,association_id)
        if not link or link.organisation_id!=s.org or link.client_id!=row.id:raise HTTPException(404,'Association introuvable.')
        link.actif=False
        return client_detail(s,row)
    return operation(s,data,'ORGANISME_RETIRE:'+str(association_id),remove)


@router.post('/{client_id}/fidelite', status_code=201)
def client_fidelite_adhesion(client_id: UUID, data: Mutation, s=Depends(vente_service)):
    get_client(s,client_id)
    return operation(s,data,'FIDELITE_ADHESION:'+str(client_id),lambda:CaisseService(s).creer_compte_pour_client(client_id))


@router.get('/{client_id}/ventes')
def client_ventes(client_id: UUID, request: Request, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), s=Depends(vente_service)):
    get_client(s,client_id)
    from neosys_pharma.infrastructure.organisation_models import EmplacementModel
    allowed=[]
    for loc in s.s.scalars(select(EmplacementModel).where(EmplacementModel.site_id==s.site,EmplacementModel.actif.is_(True))):
        try:s.stock.emplacement(loc.id_emplacement,'vente.consulter');allowed.append(loc.id_emplacement)
        except PermissionError:pass
    # Le titulaire choisi à la caisse ne remplace jamais le client de préparation.
    # EXISTS évite de multiplier les ventes et conserve le décompte/pagination SQL.
    fidelity_locations=[]
    for loc_id in allowed:
        try:s.stock.emplacement(loc_id,'fidelite.consulter');fidelity_locations.append(loc_id)
        except PermissionError:pass
    linked_by_card=(select(EncaissementModel.id)
        .join(CompteFideliteModel,CompteFideliteModel.id==EncaissementModel.compte_id)
        .join(ClientFideliteModel,ClientFideliteModel.id==CompteFideliteModel.client_id)
        .where(EncaissementModel.organisation_id==s.org,
               CompteFideliteModel.organisation_id==s.org,
               ClientFideliteModel.organisation_id==s.org,
               ClientFideliteModel.profil_client_id==client_id,
               EncaissementModel.vente_id==VenteModel.id,
               VenteModel.emplacement_id.in_(fidelity_locations))
        .correlate(VenteModel).exists())
    query=select(VenteModel).where(
        VenteModel.organisation_id==s.org,VenteModel.site_id==s.site,
        VenteModel.emplacement_id.in_(allowed),
        or_(VenteModel.client_id==client_id,linked_by_card)
    ).order_by(VenteModel.cree_le.desc(),VenteModel.id)
    # Le repository pagine des entités ; calculer la provenance avec la même
    # expression sur les seuls identifiants de la page, sans exposer le compte.
    total,rows=s.stock.repo.paginer(query,page,page_size)
    fidelity_ids=set(s.s.scalars(select(VenteModel.id).where(
        VenteModel.id.in_([row.id for row in rows]),
        VenteModel.organisation_id==s.org,VenteModel.site_id==s.site,linked_by_card))) if rows else set()
    # Reçu details are included only where the caller also has caisse.consulter.
    cashier_locations=[]
    for loc in s.s.scalars(select(EmplacementModel).where(EmplacementModel.site_id==s.site,EmplacementModel.actif.is_(True))):
        try:s.stock.emplacement(loc.id_emplacement,'caisse.consulter');cashier_locations.append(loc.id_emplacement)
        except PermissionError:pass
    receipts={}
    if rows and cashier_locations:
        for receipt in s.s.scalars(select(EncaissementModel).join(VenteModel,VenteModel.id==EncaissementModel.vente_id).where(EncaissementModel.organisation_id==s.org,VenteModel.id.in_([row.id for row in rows]),VenteModel.emplacement_id.in_(cashier_locations))):
            receipts[receipt.vente_id]={'recu_id':str(receipt.id),'numero_recu':str(receipt.numero).zfill(4),'date_encaissement':receipt.date.isoformat()}
    return {'items':[{**serial(row),**receipts.get(row.id,{}),
        'origines_rattachement':(['PREPARATION'] if row.client_id==client_id else [])+
            (['FIDELITE_CAISSE'] if row.id in fidelity_ids else [])
        } for row in rows],'total':total,'page':page,'page_size':page_size}
