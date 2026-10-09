from neosys_pharma.domain.catalogue import NatureMedicament, PrincipeActif, ClasseTherapeutique, GroupeSubstitution, ModeDelivrance, CompositionProduit, ClassificationProduit, SubstitutionProduit
from neosys_pharma.infrastructure.catalogue_models import NatureMedicamentModel, PrincipeActifModel, ClasseTherapeutiqueModel, GroupeSubstitutionModel, ModeDelivranceModel, CompositionProduitModel, ClassificationProduitModel, SubstitutionProduitModel
from contextlib import contextmanager
from unicodedata import normalize
from dataclasses import asdict, fields
from sqlalchemy import select, func, or_, and_
from neosys_pharma.domain.catalogue import CategorieProduit, FormePharmaceutique, Laboratoire, Produit, Conditionnement, ReferenceProduit
from neosys_pharma.infrastructure.catalogue_models import CategorieProduitModel, FormePharmaceutiqueModel, LaboratoireModel, ProduitModel, ConditionnementModel, ReferenceProduitModel
from neosys_pharma.infrastructure.organisation_models import OrganisationModel

MODELES = dict(zip((CategorieProduit, FormePharmaceutique, Laboratoire, Produit, Conditionnement, ReferenceProduit), (CategorieProduitModel, FormePharmaceutiqueModel, LaboratoireModel, ProduitModel, ConditionnementModel, ReferenceProduitModel)))

MODELES.update({NatureMedicament: NatureMedicamentModel,PrincipeActif: PrincipeActifModel,ClasseTherapeutique: ClasseTherapeutiqueModel,GroupeSubstitution: GroupeSubstitutionModel,ModeDelivrance: ModeDelivranceModel,CompositionProduit: CompositionProduitModel,ClassificationProduit: ClassificationProduitModel,SubstitutionProduit: SubstitutionProduitModel})

class SqlAlchemyCatalogueRepository:
    def __init__(self, session):
        self.session = session
        if session.get_bind().dialect.name == "sqlite":
            # SQLite built-in upper/lower only handle ASCII. This read-only SQL
            # function keeps legacy accented labels searchable without rewriting them.
            session.connection().connection.driver_connection.create_function(
                "catalogue_upper", 1, lambda value: normalize("NFC", value).upper() if value is not None else None, deterministic=True)

    def entity(self, classe, row):
        return classe(**{f.name: getattr(row, f.name) for f in fields(classe)})

    def obtenir(self, classe, identifiant, organisation_id):
        model = MODELES[classe]
        pk = next(iter(model.__table__.primary_key.columns))
        row = self.session.scalar(select(model).where(pk == identifiant, model.organisation_id == organisation_id))
        return self.entity(classe, row) if row else None

    def lister(self, classe, organisation_id, **filters):
        model = MODELES[classe]
        query = select(model).where(model.organisation_id == organisation_id)
        for key, value in filters.items():
            query = query.where(getattr(model, key) == value)
        key = getattr(model, 'nom', None)
        if key is None:
            key = getattr(model, 'code', model.__table__.primary_key.columns.values()[0])
        rows = self.session.scalars(query.order_by(key, *model.__table__.primary_key.columns)).all()
        return [self.entity(classe, row) for row in rows]

    def rechercher_produits(self, organisation_id, recherche, page, taille):
        """Bounded summary: SQL search/count/page, no per-product detail loads."""
        p, c, r = ProduitModel, ConditionnementModel, ReferenceProduitModel
        filtres = [p.organisation_id == organisation_id]
        if recherche.strip():
            terme = normalize("NFC", recherche.strip()).upper()
            upper = func.catalogue_upper if self.session.get_bind().dialect.name == "sqlite" else func.upper
            reference = select(r.id_reference).join(c, and_(c.id_conditionnement == r.conditionnement_id, c.organisation_id == r.organisation_id)).where(
                c.produit_id == p.id_produit, c.organisation_id == organisation_id,
                r.organisation_id == organisation_id, upper(r.valeur).contains(terme, autoescape=True)).exists()
            filtres.append(or_(upper(p.nom).contains(terme, autoescape=True), reference))
        total = self.session.scalar(select(func.count()).select_from(p).where(*filtres))
        page_ids = select(p.id_produit).where(*filtres).order_by(p.nom, p.id_produit).limit(taille).offset((page - 1) * taille)
        # Stable display representatives, not new business "principal" flags.
        # Rank only packaging/references of products on this page.
        packs = select(c.produit_id, c.libelle, c.id_conditionnement,
            func.count().over(partition_by=c.produit_id).label('nombre'),
            func.row_number().over(partition_by=c.produit_id, order_by=(c.actif.desc(), c.code, c.id_conditionnement)).label('rang')
        ).where(c.organisation_id == organisation_id, c.produit_id.in_(page_ids)).subquery()
        refs = select(r.conditionnement_id, r.valeur, r.type_reference,
            func.row_number().over(partition_by=r.conditionnement_id, order_by=(r.actif.desc(), r.type_reference, r.valeur, r.id_reference)).label('rang')
        ).join(c, and_(c.id_conditionnement == r.conditionnement_id, c.organisation_id == r.organisation_id)).where(r.organisation_id == organisation_id, c.produit_id.in_(page_ids)).subquery()
        query = select(p.id_produit, p.nom, p.actif,
            CategorieProduitModel.nom.label('categorie'), FormePharmaceutiqueModel.nom.label('forme'), LaboratoireModel.nom.label('laboratoire'),
            packs.c.libelle.label('conditionnement'), packs.c.nombre.label('nombre_conditionnements'),
            refs.c.valeur.label('reference'), refs.c.type_reference.label('type_reference')
        ).join(CategorieProduitModel, and_(CategorieProduitModel.id_categorie == p.categorie_id, CategorieProduitModel.organisation_id == p.organisation_id))
        for model, ident in ((FormePharmaceutiqueModel, p.forme_id), (LaboratoireModel, p.laboratoire_id)):
            query = query.outerjoin(model, and_(next(iter(model.__table__.primary_key.columns)) == ident, model.organisation_id == p.organisation_id))
        query = query.outerjoin(packs, and_(packs.c.produit_id == p.id_produit, packs.c.rang == 1)).outerjoin(refs, and_(refs.c.conditionnement_id == packs.c.id_conditionnement, refs.c.rang == 1))
        rows = self.session.execute(query.where(*filtres).order_by(p.nom, p.id_produit).limit(taille).offset((page - 1) * taille)).mappings()
        items = [dict(row) for row in rows]
        for item in items:
            for key in ('nom', 'categorie', 'forme', 'laboratoire', 'conditionnement'):
                if item[key] is not None:
                    item[key] = normalize('NFC', item[key]).upper()
        return {'items': items, 'total': total, 'page': page, 'page_size': taille}

    def enregistrer(self, entity):
        self.session.merge(MODELES[type(entity)](**asdict(entity)))
        self.session.flush()

    def verrouiller_organisation(self, organisation_id):
        self.session.scalar(select(OrganisationModel).where(OrganisationModel.id_organisation == organisation_id).with_for_update())

    @contextmanager
    def transaction(self):
        try:
            yield
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
