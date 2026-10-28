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
from neosys_pharma.infrastructure.creance_models import (CreanceOrganismeModel, VersionDossierCreanceModel,
    CompensationCreanceOrganismeModel)
from neosys_pharma.infrastructure.prise_en_charge_models import (RealisationPriseEnChargeModel, CalculPriseEnChargeVenteModel,
    LigneCalculPriseEnChargeModel, PartCalculPriseEnChargeModel, EtapeCalculPriseEnChargeModel)
from neosys_pharma.infrastructure.regularisation_models import RetourVenteModel, LigneRetourVenteModel
from neosys_pharma.infrastructure.vente_models import VenteModel
from neosys_pharma.infrastructure.facturation_organisme_models import EngagementCreanceModel, LigneDocumentOrganismeModel
from neosys_pharma.domain.compensation_creance import organisme_unique


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

    def _ventilation_retour(self, row, retour):
        """Retourne les parts certaines par organisme; toute ambiguïté bloque."""
        real=self.s.get(RealisationPriseEnChargeModel,row.realisation_id)
        source=retour.instantane.get('prise_en_charge') or {}
        if (source.get('realisation_id'),source.get('calcul_id'))!=(str(real.id),str(real.calcul_id)):
            raise ConflitStock('Le retour ne référence pas exactement la réalisation historique.')
        if retour.montant_organismes_xaf is None:
            raise ConflitStock('Retour historique sans ventilation organismes : régularisation manuelle requise.')
        calc_lines={x.ligne_vente_id:x for x in self.s.scalars(select(LigneCalculPriseEnChargeModel).where(
            LigneCalculPriseEnChargeModel.calcul_id==real.calcul_id,
            LigneCalculPriseEnChargeModel.organisation_id==self.org)).all()}
        allocations={};total=0
        return_lines=self.s.scalars(select(LigneRetourVenteModel).where(
            LigneRetourVenteModel.retour_id==retour.id,LigneRetourVenteModel.organisation_id==self.org)).all()
        if not return_lines:
            raise ConflitStock('Détail de lignes de retour absent : ventilation impossible.')
        evidence=[]
        for returned in return_lines:
            snap=returned.instantane
            try:amount=int(snap['part_organismes_xaf'])
            except (KeyError,TypeError,ValueError):
                raise ConflitStock('Part organismes absente ou invalide dans le snapshot du retour.')
            if amount<0:raise ConflitStock('Part organismes négative dans le snapshot du retour.')
            calc_line=calc_lines.get(returned.ligne_id)
            if calc_line is None:raise ConflitStock('Ligne retournée absente du calcul financier historique.')
            parts=self.s.scalars(select(PartCalculPriseEnChargeModel).where(
                PartCalculPriseEnChargeModel.ligne_calcul_id==calc_line.id,
                PartCalculPriseEnChargeModel.organisation_id==self.org,
                PartCalculPriseEnChargeModel.type_part=='ORGANISME',
                PartCalculPriseEnChargeModel.montant_xaf>0)).all()
            try:
                payeur=organisme_unique([(part.organisme_id,part.montant_xaf) for part in parts],
                    amount,calc_line.total_organismes_xaf)
            except ValueError as exc:
                raise ConflitStock(str(exc)) from exc
            if payeur is None:
                continue
            part=next(part for part in parts if part.organisme_id==payeur)
            allocations[payeur]=allocations.get(payeur,0)+amount
            total+=amount
            evidence.append({'ligne_retour_id':str(returned.id),'ligne_vente_id':str(returned.ligne_id),
                'quantite':returned.quantite,'montant_organismes_xaf':amount,'part_calcul_id':str(part.id),
                'organisme_id':str(payeur),'snapshot_ligne':snap})
        try:source_total=int(source.get('montant_organismes_xaf',-1))
        except (TypeError,ValueError):raise ConflitStock('Total organismes absent ou invalide dans le snapshot du retour.')
        if total!=retour.montant_organismes_xaf or total!=source_total:
            raise ConflitStock('Le total du retour diffère de ses lignes ou de son snapshot financier.')
        return allocations,{'retour':serial(retour),'realisation_id':str(real.id),'calcul_id':str(real.calcul_id),
            'lignes':evidence,'total_organismes_xaf':total}

    def compensations(self,row):
        rows=self.s.scalars(select(CompensationCreanceOrganismeModel).where(
            CompensationCreanceOrganismeModel.creance_id==row.id,
            CompensationCreanceOrganismeModel.organisation_id==self.org).order_by(
                CompensationCreanceOrganismeModel.cree_le,CompensationCreanceOrganismeModel.id)).all()
        for item in rows:
            digest=sha256(json.dumps(item.snapshot,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            if digest!=item.snapshot_hash or item.snapshot.get('total_organismes_xaf')!=item.montant_xaf:
                raise ConflitStock('Intégrité du registre de compensation non vérifiable.')
        return rows

    def solde_effectif(self,row):
        amount=row.montant_xaf-sum(x.montant_xaf for x in self.compensations(row))
        if amount<0:raise ConflitStock('Les écritures dépassent le montant initial de la créance.')
        return amount

    def _retours_a_regulariser(self,row,retours,compensations):
        existing={x.retour_id:x.montant_xaf for x in compensations}
        pending=[];ambiguities=[]
        for retour in retours:
            try:allocations,_=self._ventilation_retour(row,retour)
            except ConflitStock as exc:
                ambiguities.append({'retour_id':str(retour.id),'motif':str(exc)});continue
            expected=allocations.get(row.organisme_id,0)
            recorded=existing.get(retour.id,0)
            if recorded!=expected:
                pending.append({'retour_id':str(retour.id),'montant_attendu_xaf':expected,
                    'montant_compense_xaf':recorded})
        return pending,ambiguities

    def detail(self, ident):
        row=self.obtenir(ident);version=self.version(row);retours=self.retours(row);compensations=self.compensations(row)
        anomalies=list(version.anomalies)
        pending,ambiguities=self._retours_a_regulariser(row,retours,compensations)
        if pending:anomalies.append('RETOUR_A_REGULARISER : compensation explicite requise.')
        if ambiguities:anomalies.append('RETOUR_AMBIGU : ventilation historique insuffisante; blocage conservé.')
        montant_compense=sum(x.montant_xaf for x in compensations)
        solde=self.solde_effectif(row)
        return serial(row)|{'dossier':serial(version),'etat_effectif':'EN_ANOMALIE' if pending or ambiguities else version.etat,
            'facturable':version.etat=='VALIDE_POUR_FACTURATION' and not anomalies and solde>0,
            'anomalies_effectives':anomalies,'retours':[serial(x) for x in retours],
            'compensations':[serial(x) for x in compensations],'montant_compense_xaf':montant_compense,
            'solde_effectif_xaf':solde,
            'retours_a_regulariser':pending,'retours_ambigus':ambiguities}

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
        pending,ambiguities=self._retours_a_regulariser(row,self.retours(row),self.compensations(row))
        if conforme and (anomalies or pending or ambiguities):
            raise ConflitStock('Dossier incomplet ou retour à régulariser : validation pour facturation interdite.')
        self._version(row,revision+1,'VALIDE_POUR_FACTURATION' if conforme else 'EN_ANOMALIE',previous.complements,
            anomalies,texte(motif,'Motif de contrôle',2000))
        self.tiers._audit('CREANCE',row.id,'DOSSIER_CONTROLE',{'revision':revision+1,'conforme':conforme})
        return self.detail(row.id)

    def regulariser_retour(self,ident,retour_id,motif):
        self.tiers._organisation_verrouillee()
        row=self.obtenir(ident,'tiers_payant.creance.regulariser')
        retours={x.id:x for x in self.retours(row)}
        retour=retours.get(retour_id)
        if retour is None:raise LookupError('Retour absent de la réalisation de cette créance.')
        if self.s.scalar(select(EngagementCreanceModel).where(
                EngagementCreanceModel.creance_id==row.id,
                EngagementCreanceModel.organisation_id==self.org)) is not None:
            raise ConflitStock('Créance déjà engagée : compensation C1 interdite.')
        if self.s.scalar(select(LigneDocumentOrganismeModel).where(
                LigneDocumentOrganismeModel.creance_id==row.id,
                LigneDocumentOrganismeModel.organisation_id==self.org)) is not None:
            raise ConflitStock('Créance déjà présentée ou facturée : traitement documentaire hors périmètre.')
        if self.version(row).etat=='FACTURE':
            raise ConflitStock('Créance déjà facturée : traitement documentaire hors périmètre.')
        existing=self.s.scalar(select(CompensationCreanceOrganismeModel).where(
            CompensationCreanceOrganismeModel.creance_id==row.id,
            CompensationCreanceOrganismeModel.retour_id==retour.id,
            CompensationCreanceOrganismeModel.organisation_id==self.org))
        if existing:raise ConflitStock('Ce retour a déjà été compensé pour cette créance.')
        allocations,evidence=self._ventilation_retour(row,retour)
        amount=allocations.get(row.organisme_id,0)
        if amount<=0:raise ConflitStock('Ce retour ne porte aucune part positive sur cette créance.')
        total=sum(x.montant_xaf for x in self.compensations(row))
        if total+amount>row.montant_xaf:
            raise ConflitStock('La compensation dépasserait le montant initial de la créance.')
        motif=texte(motif,'Motif de compensation',2000)
        digest=sha256(json.dumps(evidence,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        item=self.stock.ajouter(CompensationCreanceOrganismeModel,creance_id=row.id,retour_id=retour.id,
            montant_xaf=amount,snapshot=evidence,snapshot_hash=digest,motif=motif,auteur_id=self.stock.user)
        self.tiers._audit('CREANCE',row.id,'COMPENSATION_RETOUR',{'retour_id':str(retour.id),
            'montant_xaf':amount,'snapshot_hash':digest,'solde_effectif_xaf':row.montant_xaf-total-amount})
        return self.detail(row.id)|{'compensation':serial(item)}

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
            'snapshot_hash':row.snapshot_hash,'montant_effectif_xaf':result['solde_effectif_xaf'],'controle_seulement':True}
