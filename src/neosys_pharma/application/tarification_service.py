from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from neosys_pharma.domain.catalogue import Produit, Conditionnement, CategorieProduit
from neosys_pharma.domain.tarification import RegimeTVA, TarifReference, ParametrageTarifSite, TarifCategorieSite, TarifProduitSite, chevauche
from neosys_pharma.infrastructure.tarification_models import RegimeTVAModel, TarifReferenceModel, ParametrageTarifSiteModel, TarifCategorieSiteModel, TarifProduitSiteModel
from neosys_pharma.infrastructure.catalogue_repository import MODELES
from neosys_pharma.infrastructure.organisation_models import SiteModel

TARIFS = {'references': TarifReference, 'sites': ParametrageTarifSite, 'categories': TarifCategorieSite, 'produits': TarifProduitSite, 'tva': RegimeTVA}
MODELES.update({RegimeTVA: RegimeTVAModel, TarifReference: TarifReferenceModel, ParametrageTarifSite: ParametrageTarifSiteModel, TarifCategorieSite: TarifCategorieSiteModel, TarifProduitSite: TarifProduitSiteModel})


class TarificationService:
    def __init__(self, catalogue):
        self.catalogue = catalogue
        self.repo = catalogue.repo

    def scope(self, item):
        return {key: getattr(item, key) for key in ('site_id', 'categorie_id', 'conditionnement_id', 'produit_id', 'code') if hasattr(item, key)}

    def valider(self, item):
        org = item.organisation_id
        if hasattr(item, 'site_id'):
            site = self.repo.session.scalar(select(SiteModel).where(SiteModel.id_site == item.site_id, SiteModel.organisation_id == org))
            if not site:
                raise LookupError('Site du tarif introuvable dans cette organisation.')
        for cls, key in ((CategorieProduit, 'categorie_id'), (Produit, 'produit_id'), (Conditionnement, 'conditionnement_id')):
            if hasattr(item, key):
                parent = self.catalogue.obtenir(cls, getattr(item, key), org)
                if key == 'conditionnement_id' and hasattr(item, 'produit_id') and parent.produit_id != item.produit_id:
                    raise ValueError('Conditionnement appartenant à un autre produit.')
        for old in self.repo.lister(type(item), org, **self.scope(item)):
            if old.id_regime == item.id_regime if isinstance(item, RegimeTVA) else old.id_tarif == item.id_tarif:
                continue
            if chevauche(old, item):
                raise ValueError('Chevauchement de périodes : clôturez explicitement la période existante ou choisissez une autre date.')

    def enregistrer(self, item):
        with self.repo.transaction():
            self.repo.verrouiller_organisation(item.organisation_id)
            self.valider(item)
            self.repo.enregistrer(item)
        return item

    def cloturer(self, classe, identifiant, org, fin):
        with self.repo.transaction():
            self.repo.verrouiller_organisation(org)
            old = self.catalogue.obtenir(classe, identifiant, org)
            if old.fin is not None:
                raise ValueError('Période déjà clôturée ; son historique est conservé.')
            if fin < old.debut:
                raise ValueError('La fin précède le début de période.')
            item = replace(old, fin=fin)
            self.repo.enregistrer(item)
        return item

    def actif(self, classe, org, jour, **scope):
        values = [x for x in self.repo.lister(classe, org, **scope) if x.debut <= jour <= (x.fin or date.max)]
        if len(values) > 1:
            raise ValueError('Historique tarifaire incohérent : plusieurs périodes applicables.')
        return values[0] if values else None

    def resoudre(self, org, site, conditionnement, jour):
        pack = self.catalogue.obtenir(Conditionnement, conditionnement, org)
        product = self.catalogue.obtenir(Produit, pack.produit_id, org)
        reference = self.actif(TarifReference, org, jour, conditionnement_id=conditionnement)
        choices = [
            ('PRODUIT_SITE', self.actif(TarifProduitSite, org, jour, site_id=site, produit_id=product.id_produit, conditionnement_id=conditionnement)),
            ('CATEGORIE_SITE', self.actif(TarifCategorieSite, org, jour, site_id=site, categorie_id=product.categorie_id)),
            ('SITE', self.actif(ParametrageTarifSite, org, jour, site_id=site)),
            ('REFERENCE', reference),
        ]
        origine, rule = next(((o, r) for o, r in choices if r), (None, None))
        if not rule:
            return {'disponible': False, 'motif': 'Aucun tarif applicable.', 'jour': jour, 'site_id': site, 'conditionnement_id': conditionnement}
        dependencies = [rule]
        montant = rule.montant_ht
        if montant is None:
            if not reference or reference.devise != rule.devise:
                return {'disponible': False, 'motif': 'La règle prioritaire exige un tarif de référence dans la même devise.', 'origine': origine, 'jour': jour}
            montant = reference.montant_ht * rule.coefficient
            dependencies.append(reference)
        tax = self.actif(RegimeTVA, org, jour, code=product.regime_tva_code) if product.regime_tva_code else None
        if product.regime_tva_code and not tax:
            return {'disponible': False, 'motif': 'Régime TVA sans période applicable.', 'origine': origine, 'jour': jour}
        if tax:
            dependencies.append(tax)
        taux = tax.taux if tax else Decimal('0')
        ht = montant.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        tva = (ht * taux / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        return {'disponible': True, 'site_id': site, 'conditionnement_id': conditionnement, 'jour': jour,
            'origine': origine, 'tarif_id': rule.id_tarif, 'devise': rule.devise, 'montant_ht': ht, 'taux_tva': taux,
            'montant_tva': tva, 'montant_ttc': ht+tva, 'debut': max(x.debut for x in dependencies),
            'fin': min((x.fin for x in dependencies if x.fin), default=None),
            'regime_tva': asdict(tax) if tax else None, 'regle': asdict(rule),
            'reference': asdict(reference) if reference else None}
