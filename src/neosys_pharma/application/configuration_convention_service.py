"""Administration raccordée aux conventions et au calcul P5-B existants."""
from uuid import UUID
from sqlalchemy import func, select
from neosys_pharma.application.stock_service import serial
from neosys_pharma.application.projection_prise_en_charge import projeter_convention
from neosys_pharma.domain.configuration_convention import configuration_validee, verifier_preuve, texte
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.vente_models import VenteModel
from neosys_pharma.infrastructure.prise_en_charge_models import CalculPriseEnChargeVenteModel
from neosys_pharma.infrastructure.catalogue_models import ProduitModel, CategorieProduitModel
from neosys_pharma.infrastructure.tiers_payants_models import (
    ConventionOrganismeModel, ConfigurationConventionModel, VerificationConventionModel,
    AdhesionOrganismeModel, AdhesionBeneficiaireModel, BeneficiaireCouvertureModel,
)


class ConfigurationConventionService:
    def __init__(self, tiers):
        self.tiers, self.s, self.org = tiers, tiers.session, tiers.organisation_id

    def convention(self, ident):
        row = self.s.get(ConventionOrganismeModel, ident)
        if row is None or row.organisation_id != self.org:
            raise LookupError('Convention introuvable.')
        return row

    def detail(self, ident):
        row = self.convention(ident)
        config = self.s.scalar(select(ConfigurationConventionModel).where(
            ConfigurationConventionModel.convention_id == row.id,
            ConfigurationConventionModel.organisation_id == self.org))
        return serial(row) | {'configuration': serial(config) if config else None}

    def creer(self, data):
        self.tiers._organisation_verrouillee()
        organisme = self.tiers._organisme(data['organisme_id'])
        if organisme.revision != data['revision_organisme']:
            raise ConflitStock('Organisme modifié : rechargez avant de créer la convention.')
        code = texte(data['code'], 'Code convention', 80).upper()
        latest = self.s.scalar(select(func.max(ConventionOrganismeModel.version)).where(
            ConventionOrganismeModel.organisation_id == self.org,
            ConventionOrganismeModel.organisme_id == organisme.id,
            ConventionOrganismeModel.code == code)) or 0
        if latest != data['version_attendue']:
            raise ConflitStock('Une version de convention a été ajoutée : rechargez son historique.')
        config = configuration_validee(data['configuration'])
        # Le moteur historique est la seule autorité de taux/plafond/arrondi.
        probe = ConventionOrganismeModel(id=UUID(int=0), organisation_id=self.org,
            organisme_id=organisme.id, code=code, version=latest+1,
            date_debut=data['date_debut'], date_fin=data.get('date_fin'),
            statut=data['statut'], reference_contractuelle=data.get('reference_contractuelle'),
            conditions=data.get('conditions', {'schema_version': 1}), extensions_p5b=data['extensions_p5b'])
        extension = data['extensions_p5b']
        if type(extension.get('schema_version')) is not int or extension.get('schema_version') != 1:
            raise ValueError('Version de barèmes invalide.')
        if not isinstance(extension.get('baremes'), list) or len(extension['baremes']) > 100:
            raise ValueError('Liste de barèmes requise (100 maximum par version).')
        for rule in extension['baremes']:
            if not isinstance(rule, dict):
                raise ValueError('Structure de barème invalide.')
            texte(rule.get('code'), 'Code barème', 80)
        calculated = projeter_convention(probe)
        if not calculated.baremes:
            raise ValueError('Au moins un barème explicite est requis.')
        if len({r.code for r in calculated.baremes}) != len(calculated.baremes):
            raise ValueError('Codes de barèmes dupliqués.')
        for i, rule in enumerate(calculated.baremes):
            for other in calculated.baremes[i+1:]:
                products_overlap = not rule.produits_ids or not other.produits_ids or bool(set(rule.produits_ids)&set(other.produits_ids))
                categories_overlap = not rule.categories_ids or not other.categories_ids or bool(set(rule.categories_ids)&set(other.categories_ids))
                if products_overlap and categories_overlap:
                    raise ValueError('Deux barèmes peuvent couvrir la même ligne : préciser des sélecteurs disjoints.')
        for cls, ids in ((ProduitModel, {x for r in calculated.baremes for x in r.produits_ids} | set(calculated.exclusions_produits)),
                         (CategorieProduitModel, {UUID(x) for r in calculated.baremes for x in r.categories_ids} | {UUID(x) for x in calculated.exclusions_categories})):
            for ident in ids:
                obj = self.s.get(cls, ident)
                if obj is None or obj.organisation_id != self.org:
                    raise ValueError('Produit ou catégorie absent de cette organisation.')
        payload = {k: data[k] for k in ('organisme_id', 'date_debut', 'date_fin', 'statut', 'reference_contractuelle', 'extensions_p5b')}
        row = self.tiers.creer_convention(payload | {'code': code, 'conditions': data.get('conditions', {'schema_version': 1})})
        configuration = ConfigurationConventionModel(organisation_id=self.org, convention_id=UUID(row['id']),
            schema_version=1, definition=config, auteur_id=self.tiers.auteur_id)
        self.s.add(configuration); self.s.flush()
        self.tiers._audit('CONFIGURATION_CONVENTION', configuration.id, 'CONFIGURATION_CREEE',
                          {'convention_id': row['id'], 'schema_version': 1})
        return self.detail(UUID(row['id']))

    def verifier(self, vente, adhesion_id, data):
        self.tiers._organisation_verrouillee()
        vente = self.s.scalar(select(VenteModel).where(VenteModel.id == vente.id, VenteModel.organisation_id == self.org).with_for_update().execution_options(populate_existing=True))
        if self.s.scalar(select(CalculPriseEnChargeVenteModel.id).where(CalculPriseEnChargeVenteModel.vente_id == vente.id, CalculPriseEnChargeVenteModel.organisation_id == self.org)):
            raise ConflitStock('La prise en charge est déjà confirmée; son dossier documentaire est figé.')
        if vente.organisation_id != self.org or vente.etat not in ('PREPARATION', 'EN_ATTENTE', 'VALIDEE_PREPARATION', 'TRANSMISE'):
            raise ValueError('La vente doit être ouverte et appartenir à cette organisation.')
        adhesion = self.s.get(AdhesionOrganismeModel, adhesion_id)
        if adhesion is None or adhesion.organisation_id != self.org:
            raise LookupError('Adhésion introuvable.')
        if adhesion.revision != data['revision_adhesion']:
            raise ConflitStock('Adhésion modifiée : rechargez avant de vérifier.')
        convention = self.convention(adhesion.convention_id)
        organisme = self.tiers._organisme(convention.organisme_id)
        if not organisme.actif or convention.statut != 'ACTIVE' or adhesion.statut != 'ACTIVE':
            raise ValueError('Organisme, convention et adhésion doivent être actifs.')
        config = self.s.scalar(select(ConfigurationConventionModel).where(
            ConfigurationConventionModel.convention_id == convention.id,
            ConfigurationConventionModel.organisation_id == self.org))
        if config is None:
            raise ValueError('Cette convention ne possède pas de configuration documentaire.')
        link = self.s.scalar(select(AdhesionBeneficiaireModel).where(
            AdhesionBeneficiaireModel.organisation_id == self.org,
            AdhesionBeneficiaireModel.adhesion_id == adhesion.id,
            AdhesionBeneficiaireModel.beneficiaire_id == data['beneficiaire_id']))
        beneficiary = self.s.get(BeneficiaireCouvertureModel, data['beneficiaire_id'])
        if not link or not beneficiary or beneficiary.organisation_id != self.org or not beneficiary.actif:
            raise ValueError('Bénéficiaire actif et lien à cette adhésion requis.')
        if link.relation not in config.definition['types_beneficiaires']:
            raise ValueError('Type de bénéficiaire non admis par cette convention.')
        texte(data['reference'], 'Référence de vérification', 200)
        texte(data['motif'], 'Motif de vérification', 1000)
        start, end = data['date_verification'], data['date_fin']
        if start > self.tiers.jour or end < start:
            raise ValueError('Vérification future ou période inversée interdite.')
        for obj in (convention, adhesion, link):
            if start < obj.date_debut or (obj.date_fin and end > obj.date_fin):
                raise ValueError('La vérification doit rester dans les périodes contractuelles et les droits du bénéficiaire.')
        if data['resultat'] == 'CONFIRME':
            verifier_preuve(config.definition, data['valeurs'], data['documents'], data['source'], data['reference'])
        else:
            # Un refus est une preuve négative, pas une validation fictive de pièces manquantes.
            if data['valeurs'] or data['documents']:
                raise ValueError('Un refus conserve son motif sans déclarer des justificatifs validés.')
            if data['source'] not in {'LISTE':('LISTE',), 'IDENTIFICATION':('IDENTIFICATION',), 'EXTERNE':('EXTERNE',), 'MIXTE':('LISTE','EXTERNE')}[config.definition['mode_verification']]:
                raise ValueError('Source incompatible.')
        row = VerificationConventionModel(organisation_id=self.org, vente_id=vente.id, site_id=vente.site_id, configuration_id=config.id,
            convention_id=convention.id, adhesion_id=adhesion.id,
            revision_adhesion=adhesion.revision, auteur_id=self.tiers.auteur_id,
            **{k:data[k] for k in ('beneficiaire_id','source','reference','resultat','motif','date_verification','date_fin','valeurs','documents')})
        self.s.add(row); self.s.flush()
        self.tiers._audit('VERIFICATION_CONVENTION', row.id, 'VERIFICATION_ENREGISTREE',
                          {'adhesion_id': str(adhesion.id), 'beneficiaire_id': str(beneficiary.id), 'resultat': row.resultat})
        # Aucun changement implicite du statut des droits P5-A.
        return serial(row)
