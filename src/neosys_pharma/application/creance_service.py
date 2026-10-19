"""Constitution depuis les seules réalisations confirmées et contrôle avant facturation."""
from hashlib import sha256
from copy import deepcopy
import json
from sqlalchemy import select
from neosys_pharma.application.stock_service import serial
from neosys_pharma.application.tiers_payants_service import TiersPayantsService
from neosys_pharma.domain.creances import controle_administratif, ENGAGEMENTS
from neosys_pharma.domain.configuration_convention import texte
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.creance_models import CreanceOrganismeModel, VersionDossierCreanceModel
from neosys_pharma.infrastructure.prise_en_charge_models import (RealisationPriseEnChargeModel, CalculPriseEnChargeVenteModel,
    LigneCalculPriseEnChargeModel, PartCalculPriseEnChargeModel, EtapeCalculPriseEnChargeModel)
from neosys_pharma.infrastructure.regularisation_models import RetourVenteModel
from neosys_pharma.infrastructure.vente_models import VenteModel


class CreanceService:
    def __init__(self, stock, site):
        self.stock,self.s,self.org,self.site=stock,stock.s,stock.org,site
        self.tiers=TiersPayantsService(stock)

    def vente(self, ident, permission):
        row=self.s.scalar(select(VenteModel).where(VenteModel.id==ident,VenteModel.organisation_id==self.org,VenteModel.site_id==self.site))
        if row is None:raise LookupError('Vente introuvable dans ce site.')
        self.stock.access(permission,self.site,row.emplacement_id)
        return row

    def source(self, ident, permission='tiers_payant.creance.constituer'):
        row=self.s.scalar(select(RealisationPriseEnChargeModel).where(RealisationPriseEnChargeModel.id==ident,
            RealisationPriseEnChargeModel.organisation_id==self.org,RealisationPriseEnChargeModel.site_id==self.site))
        if row is None:raise LookupError('Réalisation financière confirmée introuvable ; une simulation ne crée aucune créance.')
        self.vente(row.vente_id,permission)
        return row

    def obtenir(self, ident, permission='tiers_payant.creance.consulter'):
        row=self.s.scalar(select(CreanceOrganismeModel).where(CreanceOrganismeModel.id==ident,
            CreanceOrganismeModel.organisation_id==self.org,CreanceOrganismeModel.site_id==self.site))
        if row is None:raise LookupError('Créance introuvable.')
        self.vente(row.vente_id,permission)
        return row

    def version(self, row):
        return self.s.scalar(select(VersionDossierCreanceModel).where(VersionDossierCreanceModel.creance_id==row.id,
            VersionDossierCreanceModel.organisation_id==self.org).order_by(VersionDossierCreanceModel.revision.desc()))

    def retours(self, row):
        real=self.s.get(RealisationPriseEnChargeModel,row.realisation_id)
        return self.s.scalars(select(RetourVenteModel).where(RetourVenteModel.organisation_id==self.org,
            RetourVenteModel.encaissement_id==real.encaissement_id).order_by(RetourVenteModel.date,RetourVenteModel.id)).all()

    def detail(self, ident):
        row=self.obtenir(ident);version=self.version(row);retours=self.retours(row)
        anomalies=list(version.anomalies)
        if retours:anomalies.append('RETOUR_A_REGULARISER : aucune réduction silencieuse de la créance.')
        return serial(row)|{'dossier':serial(version),'etat_effectif':'EN_ANOMALIE' if retours else version.etat,
            'facturable':version.etat=='VALIDE_POUR_FACTURATION' and not anomalies,
            'anomalies_effectives':anomalies,'retours':[serial(x) for x in retours]}

    def _version(self, row, revision, etat, complements, anomalies, motif):
        return self.stock.ajouter(VersionDossierCreanceModel,creance_id=row.id,revision=revision,etat=etat,
            complements=deepcopy(complements),anomalies=list(anomalies),motif=motif,auteur_id=self.stock.user)

    def constituer(self, realisation_id):
        # L'appelant utilise StockService.operation : verrou organisationnel + commit unique.
        self.tiers._organisation_verrouillee()
        real=self.source(realisation_id)
        calc=self.s.get(CalculPriseEnChargeVenteModel,real.calcul_id)
        if (calc.organisation_id,calc.site_id,calc.vente_id,calc.total_organismes_xaf)!=(self.org,self.site,real.vente_id,real.total_organismes_xaf):
            raise ConflitStock('Réalisation et calcul incohérents.')
        grouped={}
        for line in self.s.scalars(select(LigneCalculPriseEnChargeModel).where(
                LigneCalculPriseEnChargeModel.calcul_id==calc.id,LigneCalculPriseEnChargeModel.organisation_id==self.org)):
            for part in self.s.scalars(select(PartCalculPriseEnChargeModel).where(
                    PartCalculPriseEnChargeModel.ligne_calcul_id==line.id,PartCalculPriseEnChargeModel.organisation_id==self.org,
                    PartCalculPriseEnChargeModel.type_part=='ORGANISME',PartCalculPriseEnChargeModel.montant_xaf>0)):
                stage=self.s.scalar(select(EtapeCalculPriseEnChargeModel).where(
                    EtapeCalculPriseEnChargeModel.ligne_calcul_id==line.id,EtapeCalculPriseEnChargeModel.organisme_id==part.organisme_id,
                    EtapeCalculPriseEnChargeModel.organisation_id==self.org))
                if stage is None or stage.montant_couvert_xaf!=part.montant_xaf:
                    raise ConflitStock('Étape financière absente ou montant incohérent.')
                grouped.setdefault(part.organisme_id,[]).append({'ligne':serial(line),'part':serial(part),'etape':serial(stage)})
        if sum(x['part']['montant_xaf'] for rows in grouped.values() for x in rows)!=real.total_organismes_xaf:
            raise ConflitStock('Le total des créances diffère de la réalisation.')
        result=[]
        for organisme_id,rows in sorted(grouped.items(),key=lambda item:str(item[0])):
            existing=self.s.scalar(select(CreanceOrganismeModel).where(CreanceOrganismeModel.realisation_id==real.id,
                CreanceOrganismeModel.organisme_id==organisme_id,CreanceOrganismeModel.organisation_id==self.org))
            if existing:
                result.append(self.detail(existing.id));continue
            exigences={}
            for line in rows:
                raw=line['etape']['snapshot_droits'].get('dossier_documentaire_json')
                dossier=json.loads(raw) if raw else {}
                config,proof=dossier.get('configuration'),dossier.get('verification')
                if config and proof:
                    exigences[config['id']]={'id':config['id'],'definition':config['definition'],
                        'valeurs':proof['valeurs'],'documents':proof['documents'],'source':proof['source'],'reference':proof['reference']}
            snapshot={'schema_version':1,'realisation':serial(real),'calcul':serial(calc),'organisme_id':str(organisme_id),'lignes':rows}
            digest=sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            row=self.stock.ajouter(CreanceOrganismeModel,realisation_id=real.id,vente_id=real.vente_id,site_id=self.site,
                organisme_id=organisme_id,montant_xaf=sum(x['part']['montant_xaf'] for x in rows),snapshot=snapshot,
                snapshot_hash=digest,exigences=list(exigences.values()),auteur_id=self.stock.user)
            anomalies=controle_administratif(row.exigences,{})
            self._version(row,1,'A_COMPLETER' if anomalies else 'A_CONTROLER',{},anomalies,'Constitution depuis réalisation confirmée')
            self.tiers._audit('CREANCE',row.id,'CREANCE_CONSTITUEE',{'realisation_id':str(real.id),'snapshot_hash':digest})
            result.append(self.detail(row.id))
        return {'realisation_id':str(real.id),'creances':result}

    def courant(self, ident, revision, permission):
        self.tiers._organisation_verrouillee()
        row=self.obtenir(ident,permission);previous=self.version(row)
        if previous.revision!=revision:raise ConflitStock('Dossier modifié : rechargez sa révision.')
        if previous.etat=='FACTURE':raise ConflitStock('Dossier facturé : correction compensatoire requise.')
        return row,previous

    def completer(self, ident, revision, complements, motif):
        row,previous=self.courant(ident,revision,'tiers_payant.creance.completer')
        anomalies=controle_administratif(row.exigences,complements)
        self._version(row,revision+1,'A_COMPLETER' if anomalies else 'A_CONTROLER',complements,anomalies,texte(motif,'Motif',2000))
        self.tiers._audit('CREANCE',row.id,'DOSSIER_COMPLETE',{'revision':revision+1})
        return self.detail(row.id)

    def verifier(self, ident, revision, motif, conforme):
        row,previous=self.courant(ident,revision,'tiers_payant.creance.verifier')
        anomalies=controle_administratif(row.exigences,previous.complements)
        if conforme and (anomalies or self.retours(row)):
            raise ConflitStock('Dossier incomplet ou retour à régulariser : validation pour facturation interdite.')
        self._version(row,revision+1,'VALIDE_POUR_FACTURATION' if conforme else 'EN_ANOMALIE',previous.complements,
            anomalies,texte(motif,'Motif de contrôle',2000))
        self.tiers._audit('CREANCE',row.id,'DOSSIER_CONTROLE',{'revision':revision+1,'conforme':conforme})
        return self.detail(row.id)

    def autoriser_engagement(self, ident, revision, operation):
        """Garde à appeler DANS la transaction de tout futur module de facturation.

        Aucun jeton durable : un contrôle HTTP n'autorise pas une facture future.
        Le verrou commun aux retours/compléments doit rester tenu jusqu'au commit.
        """
        if operation not in ENGAGEMENTS:raise ValueError('Engagement inconnu.')
        self.tiers._organisation_verrouillee()
        row=self.obtenir(ident,'tiers_payant.creance.verifier');result=self.detail(row.id)
        if result['dossier']['revision']!=revision or not result['facturable']:
            raise ConflitStock('Engagement refusé : dossier incomplet, non vérifié, modifié ou retour à régulariser.')
        return {'autorise':True,'operation':operation,'creance_id':str(row.id),'revision':revision,
            'snapshot_hash':row.snapshot_hash,'controle_seulement':True}
