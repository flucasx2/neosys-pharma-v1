from dataclasses import asdict
from typing import Protocol
from uuid import UUID
from neosys_pharma.domain.catalogue import (
    CategorieProduit, FormePharmaceutique, Laboratoire, Produit, Conditionnement,
    ReferenceProduit, verifier_hierarchie,
)


class CatalogueRepository(Protocol):
    def obtenir(self, classe, identifiant: UUID, organisation_id: UUID): ...
    def lister(self, classe, organisation_id: UUID, **filters): ...
    def enregistrer(self, entity): ...
    def transaction(self): ...
    def verrouiller_organisation(self, organisation_id: UUID): ...


class CatalogueService:
    def __init__(self, repository: CatalogueRepository):
        self.repo = repository

    def obtenir(self, classe, identifiant, org):
        item = self.repo.obtenir(classe, identifiant, org)
        if not item:
            raise LookupError("Objet du catalogue introuvable.")
        return item

    def valider(self, item):
        org = item.organisation_id
        if isinstance(item, CategorieProduit):
            verifier_hierarchie(item, lambda ident: self.repo.obtenir(CategorieProduit, ident, org))
        elif isinstance(item, Produit):
            for cls, ident in ((CategorieProduit, item.categorie_id), (FormePharmaceutique, item.forme_id), (Laboratoire, item.laboratoire_id)):
                if ident:
                    self.obtenir(cls, ident, org)
        elif isinstance(item, Conditionnement):
            self.obtenir(Produit, item.produit_id, org)
        elif isinstance(item, ReferenceProduit):
            self.obtenir(Conditionnement, item.conditionnement_id, org)

    def enregistrer(self, item, *, nouveau=False, premier_conditionnement=None):
        # Category writes share an organization lock on PostgreSQL: two concurrent
        # reparentings cannot each validate an old tree and introduce a cycle.
        with self.repo.transaction():
            self.repo.verrouiller_organisation(item.organisation_id)
            self.valider(item)
            if isinstance(item, Produit) and (nouveau or not self.repo.obtenir(Produit, item.id_produit, item.organisation_id)):
                if not isinstance(premier_conditionnement, Conditionnement) or premier_conditionnement.produit_id != item.id_produit or premier_conditionnement.organisation_id != item.organisation_id:
                    raise ValueError("Le premier conditionnement compatible est obligatoire.")
            self.repo.enregistrer(item)
            if premier_conditionnement:
                self.repo.enregistrer(premier_conditionnement)
        return item

    def detail_produit(self, identifiant, org):
        result = asdict(self.obtenir(Produit, identifiant, org))
        result['conditionnements'] = []
        for item in self.repo.lister(Conditionnement, org, produit_id=identifiant):
            row = asdict(item)
            row['references'] = [asdict(ref) for ref in self.repo.lister(ReferenceProduit, org, conditionnement_id=item.id_conditionnement)]
            result['conditionnements'].append(row)
        current = result['categorie_id']
        result['categories'] = []
        while current:
            category = self.obtenir(CategorieProduit, current, org)
            result['categories'].append(asdict(category))
            current = category.parent_id
        return result
