from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import Depends, Request, Query
from pydantic import Field
from sqlalchemy import select, func
from neosys_pharma.presentation.catalogue_api import router, Input, service, executer
from neosys_pharma.presentation.authentification_api import utilisateur_courant
from neosys_pharma.presentation.tarification_api import verifier_site, serialiser
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.application.import_catalogue_service import ImportCatalogueService
from neosys_pharma.infrastructure.import_catalogue_models import ConseilTarifSourceModel

class PreviewInput(Input):
    contenu: str = Field(min_length=1, max_length=12_000_000)
    nom_fichier: str = Field(min_length=1,max_length=250)
    source: str = Field(min_length=1,max_length=200)
    mapping: dict[str,str] = Field(default_factory=dict)

class LotInput(Input):
    offset: int = Field(default=0,ge=0)
    taille: int = Field(default=100,ge=1,le=200)
    mode: Literal['catalogue','conseils']
    categorie_id: UUID | None = None
    conditionnement_libelle: str | None = Field(default=None,max_length=200)
    devise: str = Field(min_length=3,max_length=3)
    enrichir_designation: bool = False

class ApplicationConseilInput(Input):
    ids: list[UUID] = Field(min_length=1,max_length=200)
    debut: date
    fin: date | None = None
    niveau: Literal['reference','produit_site']
    site_id: UUID | None = None
    base_prix: Literal['HT','TTC']
    confirmer: bool

@router.post('/imports/previsualisation',status_code=201)
def preview(organisation_id: UUID,data: PreviewInput,user=Depends(utilisateur_courant),s=Depends(service)):
    return executer(lambda:ImportCatalogueService(s).previsualiser(organisation_id,user.id_utilisateur,**data.model_dump()))

@router.get('/imports/{identifiant}')
def rapport(organisation_id: UUID,identifiant: UUID,page: int=Query(1,ge=1),page_size: int=Query(50,ge=1,le=100),s=Depends(service)):
    return executer(lambda:ImportCatalogueService(s).rapport(organisation_id,identifiant,page,page_size))

@router.post('/imports/{identifiant}/lots')
def lot(organisation_id: UUID,identifiant: UUID,data: LotInput,s=Depends(service)):
    return executer(lambda:ImportCatalogueService(s).executer_lot(organisation_id,identifiant,**data.model_dump()))

@router.get('/conseils')
def conseils(organisation_id: UUID,q: str=Query(default="",max_length=200),conditionnement_id: UUID | None=None,page: int=Query(1,ge=1),page_size: int=Query(50,ge=1,le=100),s=Depends(service)):
    from neosys_pharma.infrastructure.catalogue_models import ProduitModel,ConditionnementModel
    from sqlalchemy import or_
    model=ConseilTarifSourceModel
    query=select(model,ProduitModel.nom,ConditionnementModel.libelle).join(ConditionnementModel,ConditionnementModel.id_conditionnement==model.conditionnement_id).join(ProduitModel,ProduitModel.id_produit==ConditionnementModel.produit_id).where(model.organisation_id==organisation_id)
    if q.strip():query=query.where(or_(model.cip7.icontains(q.strip(),autoescape=True),ProduitModel.nom.icontains(q.strip().upper(),autoescape=True)))
    if conditionnement_id:query=query.where(model.conditionnement_id==conditionnement_id)
    total=s.repo.session.scalar(select(func.count()).select_from(query.subquery()))
    rows=s.repo.session.execute(query.order_by(model.releve_le.desc(),model.id_conseil).offset((page-1)*page_size).limit(page_size))
    return {'items':[serialiser({**{col.name:getattr(r,col.name) for col in model.__table__.columns},'designation':nom,'conditionnement':libelle}) for r,nom,libelle in rows],'total':total,'page':page,'page_size':page_size}

@router.post('/conseils/appliquer')
def appliquer(organisation_id: UUID,data: ApplicationConseilInput,request: Request,user=Depends(utilisateur_courant),session=Depends(get_db_session),s=Depends(service)):
    if data.niveau=='produit_site':
        from fastapi import HTTPException
        if not data.site_id:raise HTTPException(422,'Site obligatoire.')
        verifier_site(request,organisation_id,data.site_id,user,session)
    elif data.site_id is not None:
        from fastapi import HTTPException
        raise HTTPException(422,'Le tarif de référence est indépendant du site.')
    return executer(lambda:ImportCatalogueService(s).appliquer(organisation_id,**data.model_dump()))

@router.get('/imports')
def imports(organisation_id: UUID,page: int=Query(1,ge=1),page_size: int=Query(50,ge=1,le=100),s=Depends(service)):
    from neosys_pharma.infrastructure.import_catalogue_models import ImportCatalogueModel
    model=ImportCatalogueModel
    query=select(model).where(model.organisation_id==organisation_id)
    total=s.repo.session.scalar(select(func.count()).select_from(query.subquery()))
    rows=s.repo.session.scalars(query.order_by(model.cree_le.desc(),model.id_import).offset((page-1)*page_size).limit(page_size))
    return {'items':[serialiser({col.name:getattr(r,col.name) for col in model.__table__.columns}) for r in rows],'total':total,'page':page,'page_size':page_size}

@router.get('/imports/{identifiant}/rapport.csv')
def export_rapport(organisation_id: UUID,identifiant: UUID,s=Depends(service)):
    import csv,io
    from fastapi.responses import Response
    from neosys_pharma.infrastructure.import_catalogue_models import LigneImportCatalogueModel
    def action():
        ImportCatalogueService(s).obtenir(organisation_id,identifiant)
        output=io.StringIO();writer=csv.writer(output,delimiter=';')
        writer.writerow(['Ligne','CIP','Description','DCI','QuantiteIgnoreePourStock','PrixAchatIndicatif','PrixVenteConseille','Statut','Erreurs','ProduitUUID','ConditionnementUUID'])
        def safe(value):
            text=str(value or '')
            return "'"+text if text[:1] in ('=','+','-','@') else text
        rows=s.repo.session.scalars(select(LigneImportCatalogueModel).where(LigneImportCatalogueModel.import_id==identifiant,LigneImportCatalogueModel.organisation_id==organisation_id).order_by(LigneImportCatalogueModel.numero))
        for row in rows:
            writer.writerow([row.numero,*[safe(row.donnees[x]) for x in ('CIP','Description','DCI','Quantite','PrixAchat','PrixVente')],row.statut,safe(' / '.join(row.erreurs)),row.produit_id or '',row.conditionnement_id or ''])
        return Response('\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="rapport-import.csv"'})
    return executer(action)
