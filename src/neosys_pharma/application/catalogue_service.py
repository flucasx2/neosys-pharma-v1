from neosys_pharma.domain.catalogue import NatureMedicament, PrincipeActif, ClasseTherapeutique, GroupeSubstitution, ModeDelivrance, CompositionProduit, ClassificationProduit, SubstitutionProduit
from neosys_pharma.domain.tarification import RegimeTVA
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
    def rechercher_produits(self, organisation_id: UUID, recherche: str, page: int, taille: int): ...
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
            for cls, ident in ((CategorieProduit, item.categorie_id), (FormePharmaceutique, item.forme_id), (Laboratoire, item.laboratoire_id), (NatureMedicament, item.nature_id), (ModeDelivrance, item.mode_delivrance_id)):
                if ident:
                    self.obtenir(cls, ident, org)
            if item.regime_tva_code and not self.repo.lister(RegimeTVA, org, code=item.regime_tva_code):
                raise LookupError("Régime TVA introuvable dans cette organisation.")
        elif isinstance(item, (CompositionProduit, ClassificationProduit, SubstitutionProduit)):
            self.obtenir(Produit, item.produit_id, org)
            cls, key = {CompositionProduit: (PrincipeActif, "principe_id"), ClassificationProduit: (ClasseTherapeutique, "classe_id"), SubstitutionProduit: (GroupeSubstitution, "groupe_id")}[type(item)]
            self.obtenir(cls, getattr(item, key), org)
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
        for key, cls in (("compositions", CompositionProduit), ("classifications", ClassificationProduit), ("substitutions", SubstitutionProduit)):
            result[key] = [asdict(x) for x in self.repo.lister(cls, org, produit_id=identifiant)]
        category = self.obtenir(CategorieProduit, result['categorie_id'], org)
        result['regles_effectives'] = {key: result[key] if result[key] is not None else getattr(category, key) for key in ('gestion_lot', 'gestion_peremption', 'fefo', 'promotion_autorisee')}
        return result
