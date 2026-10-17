"""Repository organisationnel sans commit, contrôle d'accès ou finalisation implicite."""
from collections.abc import Mapping
from sqlalchemy import select, delete
from neosys_pharma.domain.encaissement_groupe import DossierEncaissementGroupe, SelectionGroupe, EtatDossierGroupe
from neosys_pharma.infrastructure.encaissement_groupe_models import (
    DossierEncaissementGroupeModel, SelectionGroupeModel, VentilationEncaissementModel,
    AllocationReglementModel, VenteEncaisseeModel,
)


def _json(value):
    if isinstance(value, Mapping):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_json(v) for v in value]
    return value


class SqlAlchemyEncaissementGroupeRepository:
    def __init__(self, session, organisation_id):
        self.session, self.organisation_id = session, organisation_id

    def _scope(self, entity):
        if entity.organisation_id != self.organisation_id:
            raise ValueError('Entité hors organisation du repository.')

    def ajouter_dossier(self, entity):
        self._scope(entity)
        self.session.add(DossierEncaissementGroupeModel(
            id=entity.id, organisation_id=entity.organisation_id, site_id=entity.site_id,
            emplacement_id=entity.emplacement_id, caisse_id=entity.caisse_id,
            session_id=entity.session_id, auteur_id=entity.auteur_id, compte_id=entity.compte_id,
            etat=entity.etat.value, revision=entity.revision, empreinte_selection=entity.empreinte_selection))
        self.session.flush()
        self.session.add_all([SelectionGroupeModel(id=s.id, organisation_id=entity.organisation_id,
            dossier_id=entity.id, vente_id=s.vente_id, revision_vente=s.revision_vente, ordre=s.ordre,
            compte_id=s.compte_id, revision_compte=s.revision_compte)
            for s in entity.selections])

    def dossier(self, key):
        row = self.session.scalar(select(DossierEncaissementGroupeModel).filter_by(id=key, organisation_id=self.organisation_id))
        if row is None:
            return None
        selections = self.session.scalars(select(SelectionGroupeModel).filter_by(dossier_id=key,
            organisation_id=self.organisation_id).order_by(SelectionGroupeModel.ordre)).all()
        return DossierEncaissementGroupe(id=row.id, organisation_id=row.organisation_id,
            site_id=row.site_id, emplacement_id=row.emplacement_id, caisse_id=row.caisse_id,
            session_id=row.session_id, auteur_id=row.auteur_id, compte_id=row.compte_id,
            etat=EtatDossierGroupe(row.etat), revision=row.revision, empreinte_selection=row.empreinte_selection,
            selections=tuple(SelectionGroupe(id=s.id, vente_id=s.vente_id,
                revision_vente=s.revision_vente, ordre=s.ordre,
                compte_id=s.compte_id, revision_compte=s.revision_compte) for s in selections))

    def modifier_selection(self, entity, revision_attendue):
        self._scope(entity)
        current = self.dossier(entity.id)
        if current is None or current.revision != revision_attendue:
            raise ValueError('Dossier absent ou révision modifiée.')
        expected = current.changer_selection(entity.selections, entity.empreinte_selection)
        if entity != expected:
            raise ValueError('Contexte ou état du dossier modifié par la sélection.')
        # Les triggers refusent aussi une modification après paiement acquis.
        self.session.execute(delete(SelectionGroupeModel).where(
            SelectionGroupeModel.dossier_id == entity.id, SelectionGroupeModel.organisation_id == self.organisation_id))
        row = self.session.scalar(select(DossierEncaissementGroupeModel).filter_by(id=entity.id, organisation_id=self.organisation_id))
        row.revision, row.empreinte_selection = entity.revision, entity.empreinte_selection
        self.session.add_all([SelectionGroupeModel(id=s.id, organisation_id=self.organisation_id,
            dossier_id=entity.id, vente_id=s.vente_id, revision_vente=s.revision_vente, ordre=s.ordre,
            compte_id=s.compte_id, revision_compte=s.revision_compte)
            for s in entity.selections])

    def ajouter_ventilation(self, entity):
        self._scope(entity)
        self.session.add(VentilationEncaissementModel(id=entity.id, organisation_id=entity.organisation_id,
            encaissement_id=entity.encaissement_id, vente_id=entity.vente_id, revision_vente=entity.revision_vente,
            montant_ht=entity.montant_ht, montant_tva=entity.montant_tva, net_ttc=entity.net_ttc,
            remise_ligne=entity.remise_ligne, remise_globale=entity.remise_globale, instantane=_json(entity.instantane),
            compte_id=entity.compte_id, revision_compte=entity.revision_compte))

    def ajouter_allocation(self, entity):
        self._scope(entity)
        self.session.add(AllocationReglementModel(**{name: getattr(entity, name) for name in
            ('id', 'organisation_id', 'encaissement_id', 'reglement_id', 'ventilation_id', 'vente_id', 'ligne_vente_id', 'montant_net')}))

    def encaissement_de_vente(self, vente_id):
        return self.session.scalar(select(VenteEncaisseeModel.encaissement_id).where(
            VenteEncaisseeModel.vente_id == vente_id, VenteEncaisseeModel.organisation_id == self.organisation_id))
