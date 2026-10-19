"""Prévisualisation puis import atomique de personnes, jamais de droits ou créances."""
from datetime import date
import hashlib
import json
from uuid import UUID
from sqlalchemy import select
from neosys_pharma.domain.import_beneficiaires import lire_liste
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.client_models import ClientModel
from neosys_pharma.infrastructure.tiers_payants_models import BeneficiaireCouvertureModel,OrigineImportBeneficiaireModel


class ImportBeneficiairesService:
    def __init__(self,tp):self.tp=tp;self.s=tp.session;self.stock=tp.stock

    def analyser(self,data):
        source=self.tp._organisme(data['organisme_id'])
        if not source.actif:raise ValueError('Organisme inactif : import refusé.')
        digest,rows=lire_liste(data['contenu_base64'],data['format'],data.get('feuille'))
        result=[];counts={'NOUVEAU':0,'RATTACHEMENT':0,'DEJA_IMPORTE':0,'INVALIDE':0}
        for row in rows:
            d=row['donnees'];errors=list(row['erreurs']);status='NOUVEAU'
            fingerprint=hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            origin=self.s.scalar(select(OrigineImportBeneficiaireModel).where(
                OrigineImportBeneficiaireModel.organisation_id==self.tp.organisation_id,
                OrigineImportBeneficiaireModel.organisme_id==source.id,
                OrigineImportBeneficiaireModel.reference_externe==d['reference_externe'])) if not errors else None
            if origin:
                if origin.empreinte_ligne!=fingerprint:errors.append('Référence déjà importée avec des données différentes : revue explicite nécessaire, aucun écrasement.')
                else:status='DEJA_IMPORTE'
            elif not errors:
                if not d['beneficiaire_id'] and self.s.scalar(select(BeneficiaireCouvertureModel.id).where(BeneficiaireCouvertureModel.organisation_id==self.tp.organisation_id,BeneficiaireCouvertureModel.reference_externe==d['reference_externe']).limit(1)):
                    errors.append('Référence déjà présente sans cette provenance : identifier explicitement le bénéficiaire et sa révision, sans fusion automatique.')
                if d['client_id']:
                    client=self.s.get(ClientModel,UUID(d['client_id']))
                    if not client or client.organisation_id!=self.tp.organisation_id or not client.actif:errors.append('Client absent, inactif ou hors organisation.')
                if d['beneficiaire_id']:
                    target=self.s.get(BeneficiaireCouvertureModel,UUID(d['beneficiaire_id']))
                    if not target or target.organisation_id!=self.tp.organisation_id or not target.actif:errors.append('Bénéficiaire absent, inactif ou hors organisation.')
                    elif (target.revision!=d['revision_beneficiaire'] or target.nom!=d['nom'] or
                        (d['date_naissance'] and target.date_naissance!=date.fromisoformat(d['date_naissance'])) or
                        (d['client_id'] and target.client_id!=UUID(d['client_id']))):errors.append('Identité ou révision du bénéficiaire à revérifier ; aucune modification implicite.')
                    else:status='RATTACHEMENT'
            if errors:status='INVALIDE'
            counts[status]+=1;result.append(row|{'erreurs':errors,'statut':status,'empreinte_ligne':fingerprint,'beneficiaire_importe_id':str(origin.beneficiaire_id) if origin else None})
        return {'organisme_id':str(source.id),'empreinte':digest,'total':len(rows),'compteurs':counts,'lignes':result,'confirmation_possible':counts['INVALIDE']==0}

    def confirmer(self,data):
        self.tp._organisation_verrouillee()
        if not data['confirmer']:raise ValueError('Confirmation explicite de l’import requise ; aucun droit ne sera confirmé.')
        result=self.analyser(data)
        if result['empreinte']!=data['empreinte_attendue']:raise ConflitStock('Le fichier a changé depuis la prévisualisation.')
        if not result['confirmation_possible']:raise ValueError('Import bloqué : corriger toutes les lignes signalées dans la prévisualisation.')
        created=[];linked=[];ignored=[]
        for line in result['lignes']:
            d=line['donnees']
            if line['statut']=='DEJA_IMPORTE':ignored.append(line['beneficiaire_importe_id']);continue
            if d['beneficiaire_id']:ident=UUID(d['beneficiaire_id']);linked.append(str(ident))
            else:
                person=self.tp.creer_beneficiaire({'nom':d['nom'],'reference_externe':d['reference_externe'],
                    'client_id':UUID(d['client_id']) if d['client_id'] else None,
                    'date_naissance':date.fromisoformat(d['date_naissance']) if d['date_naissance'] else None})
                ident=UUID(person['id']);created.append(str(ident))
            self.stock.ajouter(OrigineImportBeneficiaireModel,organisme_id=data['organisme_id'],beneficiaire_id=ident,
                reference_externe=d['reference_externe'],empreinte_ligne=line['empreinte_ligne'],empreinte_fichier=result['empreinte'],
                nom_fichier=data['nom_fichier'],donnees=d,auteur_id=self.tp.auteur_id)
        self.tp._audit('ORGANISME',data['organisme_id'],'LISTE_BENEFICIAIRES_IMPORTEE',
            {'empreinte_fichier':result['empreinte'],'nom_fichier':data['nom_fichier'],'crees':len(created),'rattaches':len(linked),'deja_importes':len(ignored),'droits_confirmes':False})
        return {'empreinte':result['empreinte'],'crees':created,'rattaches':linked,'deja_importes':ignored,'droits_confirmes':False}
