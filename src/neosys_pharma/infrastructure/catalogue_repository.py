from contextlib import contextmanager
from dataclasses import asdict, fields
from sqlalchemy import select
from neosys_pharma.domain.catalogue import CategorieProduit, FormePharmaceutique, Laboratoire, Produit, Conditionnement, ReferenceProduit
from neosys_pharma.infrastructure.catalogue_models import CategorieProduitModel, FormePharmaceutiqueModel, LaboratoireModel, ProduitModel, ConditionnementModel, ReferenceProduitModel
from neosys_pharma.infrastructure.organisation_models import OrganisationModel

MODELES = dict(zip((CategorieProduit, FormePharmaceutique, Laboratoire, Produit, Conditionnement, ReferenceProduit), (CategorieProduitModel, FormePharmaceutiqueModel, LaboratoireModel, ProduitModel, ConditionnementModel, ReferenceProduitModel)))


class SqlAlchemyCatalogueRepository:
    def __init__(self, session):
        self.session = session

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
