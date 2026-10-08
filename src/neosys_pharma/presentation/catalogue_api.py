from neosys_pharma.domain.catalogue import NatureMedicament, PrincipeActif, ClasseTherapeutique, GroupeSubstitution, ModeDelivrance, CompositionProduit, ClassificationProduit, SubstitutionProduit
from dataclasses import asdict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from neosys_pharma.application.catalogue_service import CatalogueService
from neosys_pharma.application.controle_acces import ControleAcces
from neosys_pharma.domain.catalogue import CategorieProduit, FormePharmaceutique, Laboratoire, Produit, Conditionnement, ReferenceProduit, TypeReference
from neosys_pharma.infrastructure.catalogue_repository import SqlAlchemyCatalogueRepository
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.presentation.authentification_api import utilisateur_courant, jour_courant


def catalogue_access(request: Request, organisation_id: UUID, user=Depends(utilisateur_courant), session: Session = Depends(get_db_session)):
    permission = {'GET': 'catalogue.consulter', 'POST': 'catalogue.gerer', 'PUT': 'catalogue.gerer'}.get(request.method)
    try:
        if not permission:
            raise PermissionError('Action Catalogue non autorisée.')
        site = UUID(request.headers.get('X-Site-ID', ''))
        controle = ControleAcces(SqlAlchemySecuriteRepository(session), user, jour_courant())
        controle.organisation(permission, organisation_id, site)
        location = request.headers.get('X-Emplacement-ID')
        if location:
            controle.verifier(permission, site, UUID(location))
    except (ValueError, PermissionError) as exc:
        raise HTTPException(403, str(exc) or 'Site courant autorisé requis.') from exc


router = APIRouter(prefix='/api/catalogue/organisations/{organisation_id}', tags=['Catalogue'], dependencies=[Depends(catalogue_access)])


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class NommeInput(Input):
    code: str = Field(min_length=1, max_length=80)
    nom: str = Field(min_length=1, max_length=200)
    actif: bool = True


class CategorieInput(NommeInput):
    gestion_lot: bool = False
    gestion_peremption: bool = False
    fefo: bool = False
    promotion_autorisee: bool = False
    parent_id: UUID | None = None


class ConditionnementInput(Input):
    code: str = Field(min_length=1, max_length=80)
    libelle: str = Field(min_length=1, max_length=200)
    actif: bool = True


class ProduitInput(Input):
    nom: str = Field(min_length=1, max_length=200)
    categorie_id: UUID
    forme_id: UUID | None = None
    laboratoire_id: UUID | None = None
    nature_id: UUID | None = None
    mode_delivrance_id: UUID | None = None
    regime_tva_code: str | None = Field(default=None, max_length=80)
    gestion_lot: bool | None = None
    gestion_peremption: bool | None = None
    fefo: bool | None = None
    promotion_autorisee: bool | None = None
    description: str | None = Field(default=None, max_length=2000)
    actif: bool = True


class ProduitCreation(ProduitInput):
    premier_conditionnement: ConditionnementInput


class ReferenceInput(Input):
    type_reference: TypeReference
    valeur: str = Field(min_length=1, max_length=200)
    actif: bool = True


def service(session: Session = Depends(get_db_session)):
    return CatalogueService(SqlAlchemyCatalogueRepository(session))


def executer(action):
    try:
        return action()
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(409, 'Code ou référence déjà utilisé dans ce périmètre.') from exc


def sauver(s, classe, data, org, identifiant=None, id_field=None):
    def action():
        attrs = data.model_dump()
        if identifiant:
            s.obtenir(classe, identifiant, org)
            attrs[id_field] = identifiant
        item = classe(organisation_id=org, **attrs)
        return asdict(s.enregistrer(item))
    return executer(action)


@router.get('/categories')
def categories(organisation_id: UUID, s=Depends(service)):
    return [asdict(x) for x in s.repo.lister(CategorieProduit, organisation_id)]


@router.post('/categories', status_code=201)
def creer_categorie(organisation_id: UUID, data: CategorieInput, s=Depends(service)):
    return sauver(s, CategorieProduit, data, organisation_id)


@router.put('/categories/{identifiant}')
def modifier_categorie(organisation_id: UUID, identifiant: UUID, data: CategorieInput, s=Depends(service)):
    return sauver(s, CategorieProduit, data, organisation_id, identifiant, 'id_categorie')


@router.get('/formes')
def formes(organisation_id: UUID, s=Depends(service)):
    return [asdict(x) for x in s.repo.lister(FormePharmaceutique, organisation_id)]


@router.post('/formes', status_code=201)
def creer_forme(organisation_id: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, FormePharmaceutique, data, organisation_id)


@router.put('/formes/{identifiant}')
def modifier_forme(organisation_id: UUID, identifiant: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, FormePharmaceutique, data, organisation_id, identifiant, 'id_forme')


@router.get('/laboratoires')
def laboratoires(organisation_id: UUID, s=Depends(service)):
    return [asdict(x) for x in s.repo.lister(Laboratoire, organisation_id)]


@router.post('/laboratoires', status_code=201)
def creer_laboratoire(organisation_id: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, Laboratoire, data, organisation_id)


@router.put('/laboratoires/{identifiant}')
def modifier_laboratoire(organisation_id: UUID, identifiant: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, Laboratoire, data, organisation_id, identifiant, 'id_laboratoire')


@router.get('/produits')
def produits(organisation_id: UUID, q: str = Query(default='', max_length=200), page: int = Query(default=1, ge=1, le=1_000_000), page_size: int = Query(default=25, ge=1, le=100), s=Depends(service)):
    return s.repo.rechercher_produits(organisation_id, q, page, page_size)


@router.get('/produits/{identifiant}')
def produit(organisation_id: UUID, identifiant: UUID, s=Depends(service)):
    return executer(lambda: s.detail_produit(identifiant, organisation_id))


@router.post('/produits', status_code=201)
def creer_produit(organisation_id: UUID, data: ProduitCreation, s=Depends(service)):
    def action():
        item = Produit(organisation_id=organisation_id, **data.model_dump(exclude={'premier_conditionnement'}))
        packaging = Conditionnement(organisation_id=organisation_id, produit_id=item.id_produit, **data.premier_conditionnement.model_dump())
        s.enregistrer(item, nouveau=True, premier_conditionnement=packaging)
        return s.detail_produit(item.id_produit, organisation_id)
    return executer(action)


@router.put('/produits/{identifiant}')
def modifier_produit(organisation_id: UUID, identifiant: UUID, data: ProduitInput, s=Depends(service)):
    sauver(s, Produit, data, organisation_id, identifiant, 'id_produit')
    return s.detail_produit(identifiant, organisation_id)


@router.post('/produits/{identifiant}/conditionnements', status_code=201)
def creer_conditionnement(organisation_id: UUID, identifiant: UUID, data: ConditionnementInput, s=Depends(service)):
    return executer(lambda: asdict(s.enregistrer(Conditionnement(organisation_id=organisation_id, produit_id=identifiant, **data.model_dump()))))


@router.put('/conditionnements/{identifiant}')
def modifier_conditionnement(organisation_id: UUID, identifiant: UUID, data: ConditionnementInput, s=Depends(service)):
    def action():
        old = s.obtenir(Conditionnement, identifiant, organisation_id)
        item = Conditionnement(organisation_id=organisation_id, produit_id=old.produit_id, id_conditionnement=identifiant, **data.model_dump())
        return asdict(s.enregistrer(item))
    return executer(action)


@router.post('/conditionnements/{identifiant}/references', status_code=201)
def creer_reference(organisation_id: UUID, identifiant: UUID, data: ReferenceInput, s=Depends(service)):
    return executer(lambda: asdict(s.enregistrer(ReferenceProduit(organisation_id=organisation_id, conditionnement_id=identifiant, **data.model_dump()))))


@router.put('/references/{identifiant}')
def modifier_reference(organisation_id: UUID, identifiant: UUID, data: ReferenceInput, s=Depends(service)):
    def action():
        old = s.obtenir(ReferenceProduit, identifiant, organisation_id)
        item = ReferenceProduit(organisation_id=organisation_id, conditionnement_id=old.conditionnement_id, id_reference=identifiant, **data.model_dump())
        return asdict(s.enregistrer(item))
    return executer(action)


@router.get('/natures')
def lister_natures(organisation_id: UUID, s=Depends(service)):
    return [asdict(x) for x in s.repo.lister(NatureMedicament, organisation_id)]


@router.post('/natures', status_code=201)
def creer_natures(organisation_id: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, NatureMedicament, data, organisation_id)


@router.put('/natures/{identifiant}')
def modifier_natures(organisation_id: UUID, identifiant: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, NatureMedicament, data, organisation_id, identifiant, 'id_nature')


@router.get('/principes')
def lister_principes(organisation_id: UUID, s=Depends(service)):
    return [asdict(x) for x in s.repo.lister(PrincipeActif, organisation_id)]


@router.post('/principes', status_code=201)
def creer_principes(organisation_id: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, PrincipeActif, data, organisation_id)


@router.put('/principes/{identifiant}')
def modifier_principes(organisation_id: UUID, identifiant: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, PrincipeActif, data, organisation_id, identifiant, 'id_principe')


@router.get('/classes')
def lister_classes(organisation_id: UUID, s=Depends(service)):
    return [asdict(x) for x in s.repo.lister(ClasseTherapeutique, organisation_id)]


@router.post('/classes', status_code=201)
def creer_classes(organisation_id: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, ClasseTherapeutique, data, organisation_id)


@router.put('/classes/{identifiant}')
def modifier_classes(organisation_id: UUID, identifiant: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, ClasseTherapeutique, data, organisation_id, identifiant, 'id_classe')


@router.get('/groupes')
def lister_groupes(organisation_id: UUID, s=Depends(service)):
    return [asdict(x) for x in s.repo.lister(GroupeSubstitution, organisation_id)]


@router.post('/groupes', status_code=201)
def creer_groupes(organisation_id: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, GroupeSubstitution, data, organisation_id)


@router.put('/groupes/{identifiant}')
def modifier_groupes(organisation_id: UUID, identifiant: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, GroupeSubstitution, data, organisation_id, identifiant, 'id_groupe')


@router.get('/modes')
def lister_modes(organisation_id: UUID, s=Depends(service)):
    return [asdict(x) for x in s.repo.lister(ModeDelivrance, organisation_id)]


@router.post('/modes', status_code=201)
def creer_modes(organisation_id: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, ModeDelivrance, data, organisation_id)


@router.put('/modes/{identifiant}')
def modifier_modes(organisation_id: UUID, identifiant: UUID, data: NommeInput, s=Depends(service)):
    return sauver(s, ModeDelivrance, data, organisation_id, identifiant, 'id_mode')


class CompositionProduitInput(Input):
    principe_id: UUID
    actif: bool = True
    dosage: str | None = Field(default=None, min_length=1, max_length=200)


@router.post('/produits/{identifiant}/compositions', status_code=201)
def creer_composition(organisation_id: UUID, identifiant: UUID, data: CompositionProduitInput, s=Depends(service)):
    return executer(lambda: asdict(s.enregistrer(CompositionProduit(organisation_id=organisation_id, produit_id=identifiant, **data.model_dump()))))


@router.put('/compositions/{identifiant}')
def modifier_composition(organisation_id: UUID, identifiant: UUID, data: CompositionProduitInput, s=Depends(service)):
    def action():
        old = s.obtenir(CompositionProduit, identifiant, organisation_id)
        return asdict(s.enregistrer(CompositionProduit(organisation_id=organisation_id, produit_id=old.produit_id, id_composition=identifiant, **data.model_dump())))
    return executer(action)


class ClassificationProduitInput(Input):
    classe_id: UUID
    actif: bool = True


@router.post('/produits/{identifiant}/classifications', status_code=201)
def creer_classification(organisation_id: UUID, identifiant: UUID, data: ClassificationProduitInput, s=Depends(service)):
    return executer(lambda: asdict(s.enregistrer(ClassificationProduit(organisation_id=organisation_id, produit_id=identifiant, **data.model_dump()))))


@router.put('/classifications/{identifiant}')
def modifier_classification(organisation_id: UUID, identifiant: UUID, data: ClassificationProduitInput, s=Depends(service)):
    def action():
        old = s.obtenir(ClassificationProduit, identifiant, organisation_id)
        return asdict(s.enregistrer(ClassificationProduit(organisation_id=organisation_id, produit_id=old.produit_id, id_classification=identifiant, **data.model_dump())))
    return executer(action)


class SubstitutionProduitInput(Input):
    groupe_id: UUID
    actif: bool = True


@router.post('/produits/{identifiant}/substitutions', status_code=201)
def creer_substitution(organisation_id: UUID, identifiant: UUID, data: SubstitutionProduitInput, s=Depends(service)):
    return executer(lambda: asdict(s.enregistrer(SubstitutionProduit(organisation_id=organisation_id, produit_id=identifiant, **data.model_dump()))))


@router.put('/substitutions/{identifiant}')
def modifier_substitution(organisation_id: UUID, identifiant: UUID, data: SubstitutionProduitInput, s=Depends(service)):
    def action():
        old = s.obtenir(SubstitutionProduit, identifiant, organisation_id)
        return asdict(s.enregistrer(SubstitutionProduit(organisation_id=organisation_id, produit_id=old.produit_id, id_substitution=identifiant, **data.model_dump())))
    return executer(action)
