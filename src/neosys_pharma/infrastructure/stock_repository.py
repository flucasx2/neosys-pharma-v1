"""Transactions P3 : un verrou d'organisation commun évite allocations et snapshots concurrents."""
from uuid import UUID
from unicodedata import normalize
from sqlalchemy import select, func, update
from neosys_pharma.infrastructure.stock_models import MouvementStockModel
from neosys_pharma.infrastructure.organisation_models import OrganisationModel

class StockRepository:
    def __init__(self,session):
        self.session=session
        if session.get_bind().dialect.name=='sqlite':
            session.connection().connection.driver_connection.create_function('stock_upper',1,lambda value:normalize('NFC',value).upper() if value is not None else None,deterministic=True)

    def upper(self,value):
        return func.stock_upper(value) if self.session.get_bind().dialect.name=='sqlite' else func.upper(value)

    @staticmethod
    def terme(value):return normalize('NFC',value.strip()).upper()


    def verrouiller(self,org):
        # SQLite : verrou d'écriture (tests). PostgreSQL : verrou de ligne transactionnel.
        self.session.execute(update(OrganisationModel).where(OrganisationModel.id_organisation==org).values(actif=OrganisationModel.actif))
        self.session.expire_all()

    def obtenir(self,model,ident,org):
        row=self.session.scalar(select(model).where(model.id==ident,model.organisation_id==org).execution_options(populate_existing=True))
        if not row: raise LookupError('Entité Stock absente de cette organisation.')
        return row

    def lignes(self,model,org,**filters):
        return list(self.session.scalars(select(model).filter_by(organisation_id=org,**filters)))

    def sequence(self,org):
        return self.session.scalar(select(func.coalesce(func.max(MouvementStockModel.sequence),0)).where(MouvementStockModel.organisation_id==org))

    def ajouter(self,row):
        self.session.add(row);self.session.flush();return row

    def paginer(self,query,page,size):
        total=self.session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        return total,list(self.session.scalars(query.offset((page-1)*size).limit(size)))
