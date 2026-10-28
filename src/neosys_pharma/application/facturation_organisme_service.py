"""Bordereaux/factures : contrôles transactionnels, aucune écriture de caisse."""
from datetime import date,timezone
from hashlib import sha256
import os
import re
import json
from uuid import UUID
from sqlalchemy import delete, select, text
from fastapi.encoders import jsonable_encoder
from neosys_pharma.application.stock_service import serial
from neosys_pharma.application.creance_service import CreanceService
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.domain.documents_organismes import total_xaf
from neosys_pharma.domain.configuration_convention import texte
from neosys_pharma.infrastructure.facturation_organisme_models import (
    PreparationOrganismeModel,VersionPreparationOrganismeModel,EngagementCreanceModel,
    DocumentOrganismeModel,LigneDocumentOrganismeModel,RegroupementDocumentsModel,MembreRegroupementModel,SelectionVersionPreparationModel)
from neosys_pharma.infrastructure.facturation_organisme_pdf import document_pdf
from neosys_pharma.infrastructure.tiers_payants_models import ConventionOrganismeModel
from neosys_pharma.infrastructure.organisation_models import OrganisationModel,SiteModel


def emission_isolee_autorisee(stock):
    """Aucune activation ordinaire ; le moteur doit réellement viser la base marquée."""
    if os.getenv('CI','').lower()!='true' or os.getenv('P5C2_DISPOSABLE_EMISSION')!='1':return False
    url=stock.s.get_bind().engine.url
    if url.get_backend_name()!='postgresql' or url.host not in ('localhost','127.0.0.1','::1'):return False
    if not (url.database or '').startswith('neosys_p4p5_') or os.getenv('P4P5_CONFIRM_DATABASE')!=url.database:return False
    actual,marker=stock.s.execute(text("select current_database(), shobj_description(oid,'pg_database') from pg_database where datname=current_database()")).one()
    return actual==url.database and marker=='NEOSYS_P4P5_DISPOSABLE'


class FacturationOrganismeService:
    def __init__(self,stock,site):
        self.stock,self.s,self.org,self.site=stock,stock.s,stock.org,site
        self.creances=CreanceService(stock,site)

    def obtenir(self,ident,permission='tiers_payant.document.consulter'):
        row=self.s.scalar(select(PreparationOrganismeModel).where(PreparationOrganismeModel.id==ident,
            PreparationOrganismeModel.organisation_id==self.org,PreparationOrganismeModel.site_id==self.site))
        if row is None:raise LookupError('Préparation introuvable dans ce site.')
        self.stock.access(permission,self.site)
        self.stock.access('tiers_payant.document.consulter',self.site)
        # L'historique peut contenir des dossiers retirés : vérifier aussi leur périmètre.
        versions=self.s.scalars(select(VersionPreparationOrganismeModel).where(VersionPreparationOrganismeModel.preparation_id==row.id,VersionPreparationOrganismeModel.organisation_id==self.org)).all()
        sources={x['creance_id'] for version in versions for x in version.selection}
        for ident in sources:
            c=self.creances.obtenir(UUID(ident))
            self.creances.vente(c.vente_id,permission)
            self.creances.vente(c.vente_id,'tiers_payant.document.consulter')
        return row

    def version(self,row):
        return self.s.scalar(select(VersionPreparationOrganismeModel).where(VersionPreparationOrganismeModel.preparation_id==row.id,
            VersionPreparationOrganismeModel.organisation_id==self.org).order_by(VersionPreparationOrganismeModel.revision.desc()))

    def _version(self,row,revision,etat,selection,motif):
        version=self.stock.ajouter(VersionPreparationOrganismeModel,preparation_id=row.id,revision=revision,etat=etat,
            selection=selection,motif=texte(motif,'Motif',2000),auteur_id=self.stock.user)
        for item in selection:self.stock.ajouter(SelectionVersionPreparationModel,version_id=version.id,creance_id=UUID(item['creance_id']))
        return version

    def _convention(self,ident,organisme_id):
        row=self.s.get(ConventionOrganismeModel,ident)
        if row is None or row.organisation_id!=self.org or row.organisme_id!=organisme_id:
            raise ValueError('Convention absente ou incompatible avec cet organisme.')
        return row

    def _presentation(self,row):
        if row.presentation_id is None:return None
        source=self.obtenir(row.presentation_id)
        doc=self.s.scalar(select(DocumentOrganismeModel).where(DocumentOrganismeModel.preparation_id==source.id,
            DocumentOrganismeModel.organisation_id==self.org))
        if source.genre!='BORDEREAU' or doc is None or source.organisme_id!=row.organisme_id or source.convention_id!=row.convention_id:
            raise ValueError('Bordereau émis compatible requis.')
        return doc

    def _selection(self,row,selection,operation,permission='tiers_payant.document.preparer'):
        if not selection or len(selection)>100 or len({str(x['creance_id']) for x in selection})!=len(selection):
            raise ValueError('Sélection explicite de 1 à 100 créances distinctes requise.')
        output=[];presentation=self._presentation(row)
        presented=set(presentation.snapshot['creance_ids']) if presentation else None
        for item in sorted(selection,key=lambda x:str(x['creance_id'])):
            ident=UUID(str(item['creance_id']));revision=item['revision']
            if type(revision) is not int or revision<1:raise ValueError('Révision de dossier requise.')
            claim=self.creances.obtenir(ident)
            self.creances.vente(claim.vente_id,permission)
            if claim.organisme_id!=row.organisme_id:raise ValueError('Un document ne mélange jamais les organismes.')
            stages=claim.snapshot['lignes']
            if {x['etape']['convention_id'] for x in stages}!={str(row.convention_id)}:
                raise ValueError('Une seule version de convention compatible par préparation est prise en charge.')
            real=self.creances.source(claim.realisation_id,'tiers_payant.creance.consulter')
            instant=real.realisee_le
            day=instant.astimezone(timezone.utc).date() if instant.tzinfo else instant.date()
            if not row.date_debut<=day<=row.date_fin:
                raise ValueError('Réalisation hors période sélectionnée (date UTC de réalisation).')
            self.creances.autoriser_engagement(ident,revision,operation)
            used=self.s.scalar(select(LigneDocumentOrganismeModel).where(LigneDocumentOrganismeModel.creance_id==ident,
                LigneDocumentOrganismeModel.organisation_id==self.org,LigneDocumentOrganismeModel.genre=='FACTURE'))
            if used:raise ConflitStock('Créance déjà facturée : aucune seconde facturation.')
            if presented is not None and str(ident) not in presented:raise ValueError('Créance absente du bordereau lié.')
            reservation=self.s.scalar(select(EngagementCreanceModel).where(EngagementCreanceModel.creance_id==ident,
                EngagementCreanceModel.genre==row.genre,EngagementCreanceModel.organisation_id==self.org))
            if reservation is not None and reservation.preparation_id!=row.id:
                raise ConflitStock('Créance déjà engagée dans une préparation incompatible.')
            if self.creances.solde_effectif(claim)<=0:
                raise ConflitStock('Créance entièrement compensée : aucun solde à présenter.')
            output.append({'creance_id':str(ident),'revision':revision})
        return output

    def creer(self,data):
        self.creances.tiers._organisation_verrouillee();self.stock.access('tiers_payant.document.preparer',self.site)
        if data['date_fin']<data['date_debut']:raise ValueError('Période inversée.')
        self._convention(data['convention_id'],data['organisme_id'])
        self.creances.tiers._organisme(data['organisme_id'])
        if data['genre']=='BORDEREAU' and data.get('presentation_id'):raise ValueError('Un bordereau ne dépend pas d’un autre bordereau.')
        row=self.stock.ajouter(PreparationOrganismeModel,site_id=self.site,organisme_id=data['organisme_id'],
            convention_id=data['convention_id'],genre=data['genre'],date_debut=data['date_debut'],date_fin=data['date_fin'],
            presentation_id=data.get('presentation_id'),auteur_id=self.stock.user)
        selection=self._selection(row,data['selection'],'PRESENTER' if row.genre=='BORDEREAU' else 'GENERER_FACTURE')
        self._reserver(row,selection);self._version(row,1,'PREPARATION',selection,data['motif'])
        self.creances.tiers._audit('PREPARATION_DOCUMENT',row.id,'PREPARATION_CREEE',{'genre':row.genre})
        return self.detail(row.id)

    def _reserver(self,row,selection):
        # Suppression transactionnelle uniquement pour une préparation non émise.
        if self.s.scalar(select(DocumentOrganismeModel.id).where(DocumentOrganismeModel.preparation_id==row.id)):
            raise ConflitStock('Document émis : engagement irréversible, régularisation nécessaire.')
        self.s.execute(delete(EngagementCreanceModel).where(EngagementCreanceModel.preparation_id==row.id,
            EngagementCreanceModel.organisation_id==self.org));self.s.flush()
        for item in selection:self.stock.ajouter(EngagementCreanceModel,preparation_id=row.id,
            creance_id=UUID(item['creance_id']),genre=row.genre)

    def courant(self,ident,revision,permission):
        self.creances.tiers._organisation_verrouillee();row=self.obtenir(ident,permission);v=self.version(row)
        if v.revision!=revision:raise ConflitStock('Préparation modifiée : rechargez sa révision.')
        if v.etat in ('ABANDONNEE','EMISE'):raise ConflitStock('Préparation terminée ; aucune modification possible.')
        return row,v

    def modifier(self,ident,revision,selection,motif):
        row,v=self.courant(ident,revision,'tiers_payant.document.preparer')
        # Une préparation peut devenir vide après retrait ; validation/émission restent interdites.
        selection=self._selection(row,selection,'PRESENTER' if row.genre=='BORDEREAU' else 'GENERER_FACTURE') if selection else []
        self._reserver(row,selection);self._version(row,revision+1,'PREPARATION',selection,motif)
        self.creances.tiers._audit('PREPARATION_DOCUMENT',row.id,'SELECTION_MODIFIEE',{'revision':revision+1})
        return self.detail(row.id)

    def abandonner(self,ident,revision,motif):
        row,v=self.courant(ident,revision,'tiers_payant.document.preparer')
        self._reserver(row,[]);self._version(row,revision+1,'ABANDONNEE',v.selection,motif)
        self.creances.tiers._audit('PREPARATION_DOCUMENT',row.id,'PREPARATION_ABANDONNEE',{'revision':revision+1})
        return self.detail(row.id)

    def valider(self,ident,revision,motif):
        row,v=self.courant(ident,revision,'tiers_payant.document.valider')
        self._selection(row,v.selection,'PRESENTER' if row.genre=='BORDEREAU' else 'VALIDER_FACTURE','tiers_payant.document.valider')
        self._version(row,revision+1,'VALIDEE',v.selection,motif)
        self.creances.tiers._audit('PREPARATION_DOCUMENT',row.id,'PREPARATION_VALIDEE',{'revision':revision+1})
        return self.detail(row.id)

    def snapshot(self,row,selection,reference=None,reference_validation=None):
        org=self.s.get(OrganisationModel,self.org);site=self.s.get(SiteModel,self.site)
        payer=self.creances.tiers._organisme(row.organisme_id);convention=self._convention(row.convention_id,row.organisme_id)
        lines=[];dossiers=[]
        for item in selection:
            c=self.creances.obtenir(UUID(item['creance_id']));v=self.creances.version(c)
            beneficiary=c.snapshot['calcul'].get('beneficiaire_id')
            for part in c.snapshot['lignes']:
                raw=part['etape']['snapshot_droits'].get('dossier_documentaire_json')
                if raw:beneficiary=json.loads(raw).get('beneficiaire',{}).get('nom') or beneficiary
            effective=self.creances.solde_effectif(c)
            lines.append({'reference':str(c.id),'detail':f"Vente {c.vente_id} / bénéficiaire {beneficiary} / convention {convention.code} v{convention.version}",
                'montant_xaf':effective})
            dossiers.append({'creance':serial(c),'version_administrative':serial(v),
                'compensations':[serial(x) for x in self.creances.compensations(c)],
                'solde_effectif_xaf':effective})
        presentation=self._presentation(row)
        return {'genre':row.genre,'reference':reference,'reference_validation':reference_validation,
            'emetteur':{'organisation_id':str(self.org),'nom':org.nom_commercial,'raison_sociale':org.raison_sociale,
                'coordonnees':org.coordonnees,'informations_legales_declarees':org.informations_legales,'site':serial(site)},
            'destinataire':serial(payer),'convention':serial(convention),'periode':f'{row.date_debut} / {row.date_fin} (UTC réalisation)',
            'auteur_id':str(self.stock.user),'date':str(self.stock.jour),'lignes':lines,'total_xaf':total_xaf(x['montant_xaf'] for x in lines),
            'creance_ids':[x['creance_id'] for x in selection],'dossiers':dossiers,
            'presentation_id':str(presentation.id) if presentation else None,'preparation_id':str(row.id)}

    def detail(self,ident):
        row=self.obtenir(ident);v=self.version(row)
        doc=self.s.scalar(select(DocumentOrganismeModel).where(DocumentOrganismeModel.preparation_id==row.id,
            DocumentOrganismeModel.organisation_id==self.org))
        return {'preparation':serial(row),'version':serial(v),'document':self.document_info(doc) if doc else None}

    @staticmethod
    def document_info(row):
        return jsonable_encoder({c.name:getattr(row,c.name) for c in row.__table__.columns if c.name!='pdf'})

    def previsualiser(self,ident,revision):
        row,v=self.courant(ident,revision,'tiers_payant.document.consulter')
        self._selection(row,v.selection,'PRESENTER' if row.genre=='BORDEREAU' else 'GENERER_FACTURE','tiers_payant.document.consulter')
        return document_pdf(self.snapshot(row,v.selection),definitif=False)

    def emettre(self,ident,revision,reference,reference_validation,motif):
        row,v=self.courant(ident,revision,'tiers_payant.document.emettre')
        if v.etat!='VALIDEE':raise ConflitStock('Validation de la préparation requise avant émission.')
        self._selection(row,v.selection,'PRESENTER' if row.genre=='BORDEREAU' else 'EMETTRE_FACTURE','tiers_payant.document.emettre')
        if not emission_isolee_autorisee(self.stock):
            raise PermissionError('Émission désactivée hors recette native jetable ; politique de numérotation et conformité à arbitrer.')
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9/-]{0,79}',reference):raise ValueError('Référence manuelle de recette invalide.')
        validation=texte(reference_validation,'Référence du protocole de recette',200)
        if self.s.scalar(select(DocumentOrganismeModel.id).where(DocumentOrganismeModel.organisation_id==self.org,
                DocumentOrganismeModel.genre==row.genre,DocumentOrganismeModel.reference==reference)):
            raise ConflitStock('Référence déjà utilisée ; aucun renumérotage silencieux.')
        snap=self.snapshot(row,v.selection,reference,validation);pdf=document_pdf(snap,definitif=True)
        doc=self.stock.ajouter(DocumentOrganismeModel,preparation_id=row.id,site_id=self.site,organisme_id=row.organisme_id,
            genre=row.genre,reference=reference,reference_validation=validation,total_xaf=snap['total_xaf'],snapshot=snap,
            pdf=pdf,pdf_sha256=sha256(pdf).hexdigest(),auteur_id=self.stock.user)
        for item in v.selection:
            claim=self.creances.obtenir(UUID(item['creance_id']))
            self.stock.ajouter(LigneDocumentOrganismeModel,document_id=doc.id,creance_id=claim.id,genre=row.genre,
                montant_xaf=self.creances.solde_effectif(claim))
            if row.genre=='FACTURE':
                dossier=self.creances.version(claim)
                self.creances._version(claim,dossier.revision+1,'FACTURE',dossier.complements,dossier.anomalies,'Facture de recette '+reference)
        self._version(row,revision+1,'EMISE',v.selection,motif)
        self.creances.tiers._audit('DOCUMENT_ORGANISME',doc.id,'DOCUMENT_EMIS_RECETTE',{'reference':reference,'genre':row.genre,'pdf_sha256':doc.pdf_sha256})
        return self.detail(row.id)

    def document(self,ident):
        doc=self.s.scalar(select(DocumentOrganismeModel).where(DocumentOrganismeModel.id==ident,
            DocumentOrganismeModel.organisation_id==self.org,DocumentOrganismeModel.site_id==self.site))
        if doc is None:raise LookupError('Document introuvable.')
        self.obtenir(doc.preparation_id)
        return doc

    def _controler_facture_regroupable(self,document):
        for line in self.s.scalars(select(LigneDocumentOrganismeModel).where(
                LigneDocumentOrganismeModel.document_id==document.id,LigneDocumentOrganismeModel.organisation_id==self.org)):
            claim=self.creances.obtenir(line.creance_id)
            self.creances.vente(claim.vente_id,'tiers_payant.document.regrouper')
            result=self.creances.detail(claim.id)
            if result['retours_a_regulariser'] or result['retours_ambigus']:
                raise ConflitStock('Facture affectée par un retour non régularisé : regroupement interdit.')
            if self.creances.version(claim).etat!='FACTURE' or result['solde_effectif_xaf']!=line.montant_xaf:
                raise ConflitStock('Facture et créance incohérentes ; engagement interdit.')

    def regrouper(self,genre,ids,motif):
        self.creances.tiers._organisation_verrouillee();self.stock.access('tiers_payant.document.regrouper',self.site)
        texte(motif,'Motif',2000)
        if genre not in ('RECAPITULATIF','LOT'):raise ValueError('Type de regroupement inconnu.')
        if not ids or len(ids)>100 or len(set(ids))!=len(ids):raise ValueError('1 à 100 pièces distinctes requises.')
        rows=[];payer=None;members=[]
        for ident in sorted(ids,key=str):
            if genre=='RECAPITULATIF':
                source=self.document(ident)
                if source.genre!='FACTURE':raise ValueError('Seules les factures émises entrent dans un récapitulatif.')
                used=self.s.scalar(select(MembreRegroupementModel.id).where(MembreRegroupementModel.document_id==ident))
                self._controler_facture_regroupable(source)
                members.append({'document_id':ident,'recapitulatif_id':None})
            else:
                source=self.regroupement(ident)
                if source.genre!='RECAPITULATIF':raise ValueError('Un lot contient des récapitulatifs, jamais un autre lot.')
                used=self.s.scalar(select(MembreRegroupementModel.id).where(MembreRegroupementModel.recapitulatif_id==ident))
                for member in self.s.scalars(select(MembreRegroupementModel).where(MembreRegroupementModel.regroupement_id==source.id,MembreRegroupementModel.organisation_id==self.org)):
                    self._controler_facture_regroupable(self.document(member.document_id))
                members.append({'document_id':None,'recapitulatif_id':ident})
            if used:raise ConflitStock('Pièce déjà regroupée ; aucun double comptage.')
            if payer is not None and source.organisme_id!=payer:raise ValueError('Un regroupement ne mélange pas les organismes.')
            payer=source.organisme_id;rows.append(source)
        snap={'genre':genre,'lignes':[{'reference':str(x.id),'detail':getattr(x,'reference','Récapitulatif'),'montant_xaf':x.total_xaf} for x in rows],
            'total_xaf':total_xaf(x.total_xaf for x in rows),'auteur_id':str(self.stock.user),'date':str(self.stock.jour),'motif':motif,
            'sources':[self.document_info(x) for x in rows]}
        pdf=document_pdf(snap,definitif=True)
        grouped=self.stock.ajouter(RegroupementDocumentsModel,site_id=self.site,organisme_id=payer,genre=genre,
            total_xaf=snap['total_xaf'],snapshot=snap,pdf=pdf,pdf_sha256=sha256(pdf).hexdigest(),auteur_id=self.stock.user)
        for member in members:self.stock.ajouter(MembreRegroupementModel,regroupement_id=grouped.id,**member)
        self.creances.tiers._audit('REGROUPEMENT_DOCUMENT',grouped.id,'REGROUPEMENT_CREE',{'genre':genre,'sources':[str(x.id) for x in rows]})
        return self.document_info(grouped)

    def regroupement(self,ident):
        row=self.s.scalar(select(RegroupementDocumentsModel).where(RegroupementDocumentsModel.id==ident,
            RegroupementDocumentsModel.organisation_id==self.org,RegroupementDocumentsModel.site_id==self.site))
        if row is None:raise LookupError('Regroupement introuvable.')
        self.stock.access('tiers_payant.document.consulter',self.site)
        # Vérifier récursivement les emplacements via les seuls niveaux autorisés.
        for member in self.s.scalars(select(MembreRegroupementModel).where(MembreRegroupementModel.regroupement_id==ident,
                MembreRegroupementModel.organisation_id==self.org)):
            if member.document_id:self.document(member.document_id)
            else:self.regroupement(member.recapitulatif_id)
        return row
