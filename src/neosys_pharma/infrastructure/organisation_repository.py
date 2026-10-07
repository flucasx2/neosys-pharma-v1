from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neosys_pharma.domain.organisation.entities import Emplacement, Organisation, Site
from neosys_pharma.domain.organisation.equipements import Caisse, Coffre, PosteVente
from neosys_pharma.infrastructure.organisation_models import (
    EmplacementModel, OrganisationModel, SiteModel, PosteVenteModel, CaisseModel, CoffreModel,
)


class SqlAlchemyOrganisationRepository:
    def __init__(self, session: Session):
        self.session = session

    def organisation(self, identifiant: UUID) -> Organisation | None:
        model = self.session.get(OrganisationModel, identifiant)
        return Organisation(**self.valeurs(model)) if model else None

    def site(self, identifiant: UUID) -> Site | None:
        model = self.session.get(SiteModel, identifiant)
        return Site(**self.valeurs(model)) if model else None

    def emplacement(self, identifiant: UUID) -> Emplacement | None:
        model = self.session.get(EmplacementModel, identifiant)
        return Emplacement(**self.valeurs(model)) if model else None

    @staticmethod
    def valeurs(model) -> dict:
        return {column.key: getattr(model, column.key) for column in model.__table__.columns}

    def ajouter(self, entite: Organisation | Site | Emplacement | PosteVente | Caisse | Coffre) -> None:
        model = {Organisation: OrganisationModel, Site: SiteModel, Emplacement: EmplacementModel,
                 PosteVente: PosteVenteModel, Caisse: CaisseModel, Coffre: CoffreModel}[type(entite)]
        self.session.add(model(**asdict(entite)))
        # Flush parents before children without committing the transaction.
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ValueError("Code déjà utilisé dans ce contexte ou parent invalide.") from exc

    def enregistrer(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ValueError("La hiérarchie ne peut pas être enregistrée.") from exc

    def lister(self, model, **filtres) -> list[dict]:
        requete = select(model).filter_by(**filtres).order_by(model.nom_commercial if model is OrganisationModel else model.code)
        return [self.valeurs(item) for item in self.session.scalars(requete)]
