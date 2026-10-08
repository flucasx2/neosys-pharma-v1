"""Prévisualisation persistée, reprise par lots et conseils distincts des tarifs."""
import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from sqlalchemy import select, func
from neosys_pharma.domain.catalogue import Produit, Conditionnement, ReferenceProduit, CategorieProduit, texte
from neosys_pharma.domain.tarification import TarifReference, TarifProduitSite, decimal_valide, RegimeTVA
from neosys_pharma.infrastructure.catalogue_models import ReferenceProduitModel, ConditionnementModel
from neosys_pharma.infrastructure.import_catalogue_models import ImportCatalogueModel, LigneImportCatalogueModel, ConseilTarifSourceModel
from neosys_pharma.application.tarification_service import TarificationService

COLONNES = ('CIP', 'Quantite', 'Description', 'DCI', 'PrixAchat', 'PrixVente')


def lignes_csv(reader):
    try:
        yield from reader
    except csv.Error as exc:
        raise ValueError("Structure CSV invalide : " + str(exc)) from exc


def montant(raw):
    if not raw.strip(): return None
    try:
        return decimal_valide(raw.replace('\u00a0','').replace(' ','').replace(',','.'))
    except Exception as exc:
        raise ValueError('Montant invalide.') from exc


class ImportCatalogueService:
    def __init__(self, catalogue):
        self.catalogue = catalogue
        self.repo = catalogue.repo
        self.session = self.repo.session

    def obtenir(self, org, ident):
        item = self.session.scalar(select(ImportCatalogueModel).where(ImportCatalogueModel.id_import==ident,ImportCatalogueModel.organisation_id==org))
        if not item: raise LookupError('Import introuvable.')
        return item

    def rapprocher(self, org, cip):
        return self.session.scalar(select(ConditionnementModel).join(ReferenceProduitModel,ReferenceProduitModel.conditionnement_id==ConditionnementModel.id_conditionnement).where(ReferenceProduitModel.organisation_id==org, ReferenceProduitModel.type_reference=='CIP7',ReferenceProduitModel.valeur==cip))

    def previsualiser(self, org, utilisateur, contenu, nom_fichier, source, mapping):
        if len(contenu.encode('utf-8')) > 12_000_000: raise ValueError('Fichier limité à 12 Mo.')
        sample=contenu.lstrip('\ufeff')
        delimiter = ';' if ';' in sample.partition('\n')[0] else ','
        reader=csv.DictReader(io.StringIO(sample,newline=''),delimiter=delimiter,strict=True)
        headers=reader.fieldnames or []
        mapping=mapping or {x:x for x in COLONNES if x in headers}
        if set(mapping)-set(COLONNES) or not {'CIP','Description'} <= set(mapping) or any(v not in headers for v in mapping.values()) or len(set(mapping.values()))!=len(mapping):
            raise ValueError('Correspondance unique des colonnes CIP et Description obligatoire ; autres colonnes facultatives.')
        if len(headers)!=len(set(headers)): raise ValueError('En-têtes de colonnes dupliqués.')
        job=ImportCatalogueModel(id_import=uuid4(),organisation_id=org,utilisateur_id=utilisateur,nom_fichier=nom_fichier,source=texte(source,200,code=False),empreinte=hashlib.sha256(contenu.encode('utf-8')).hexdigest(),mapping=mapping,cree_le=datetime.now(timezone.utc),total=0)
        with self.repo.transaction():
            self.session.add(job);self.session.flush()
            # Fetch references once rather than issuing thousands of preview queries.
            refs=dict(self.session.execute(select(ReferenceProduitModel.valeur,ReferenceProduitModel.conditionnement_id).where(ReferenceProduitModel.organisation_id==org,ReferenceProduitModel.type_reference=='CIP7')).all())
            seen=set()
            for numero, raw in enumerate(lignes_csv(reader),1):
                if numero>20000: raise ValueError('Limite de 20 000 lignes par fichier.')
                data={x:(raw.get(mapping.get(x,'')) or '').strip() for x in COLONNES}
                data['Description']=data['Description'].upper()
                errors=[]
                if None in raw or any(v is None for v in raw.values()): errors.append("Nombre de champs incohérent avec l’en-tête CSV.")
                if not re.fullmatch('[0-9]{7}',data['CIP']): errors.append('CIP7 : exactement sept chiffres, zéros initiaux conservés.')
                if not data['Description'] or len(data['Description'])>200: errors.append('Désignation obligatoire, au plus 200 caractères.')
                if len(data['DCI'])>2000: errors.append('DCI brute limitée à 2000 caractères.')
                if data['CIP'] in seen: errors.append('CIP7 dupliqué dans le fichier.')
                seen.add(data['CIP'])
                for col in ('PrixAchat','PrixVente'):
                    try: montant(data[col])
                    except ValueError: errors.append(f'{col} invalide.')
                self.session.add(LigneImportCatalogueModel(id_ligne=uuid4(),organisation_id=org,import_id=job.id_import,numero=numero,donnees=data,erreurs=errors,statut='INVALIDE' if errors else ('EXISTANT' if data['CIP'] in refs else 'INCONNU'),conditionnement_id=refs.get(data['CIP'])))
                if numero%200==0:self.session.flush()
                job.total=numero
            if not job.total:raise ValueError('Le fichier ne contient aucune ligne.')
        return {'id_import':job.id_import,'total':job.total,'colonnes':headers,'mapping':mapping,'empreinte':job.empreinte}

    def rapport(self, org, ident, page, taille):
        job=self.obtenir(org,ident)
        filtres=(LigneImportCatalogueModel.import_id==ident,LigneImportCatalogueModel.organisation_id==org)
        counts=dict(self.session.execute(select(LigneImportCatalogueModel.statut,func.count()).where(*filtres).group_by(LigneImportCatalogueModel.statut)).all())
        rows=self.session.scalars(select(LigneImportCatalogueModel).where(*filtres).order_by(LigneImportCatalogueModel.numero).offset((page-1)*taille).limit(taille))
        return {'id_import':ident,'nom_fichier':job.nom_fichier,'source':job.source,'options':job.options,'total':job.total,'compteurs':counts,'page':page,'page_size':taille,'items':[{'id_ligne':r.id_ligne,'numero':r.numero,'donnees':r.donnees,'erreurs':r.erreurs,'statut':r.statut,'produit_id':r.produit_id,'conditionnement_id':r.conditionnement_id} for r in rows]}

    def executer_lot(self, org, ident, *, offset, taille, mode, categorie_id, conditionnement_libelle, devise, enrichir_designation):
        job=self.obtenir(org,ident)
        devise=devise.strip().upper()
        if len(devise)!=3 or not devise.isascii() or not devise.isalpha():raise ValueError('Devise ISO requise.')
        rows=list(self.session.scalars(select(LigneImportCatalogueModel).where(LigneImportCatalogueModel.import_id==ident,LigneImportCatalogueModel.organisation_id==org).order_by(LigneImportCatalogueModel.numero).offset(offset).limit(taille)))
        with self.repo.transaction():
            self.repo.verrouiller_organisation(org)
            self.session.refresh(job)
            options={'mode':mode,'devise':devise,'enrichir_designation':enrichir_designation,'categorie_id':str(categorie_id) if categorie_id else None,'conditionnement_libelle':conditionnement_libelle}
            if job.options is not None and any(job.options.get(k)!=options[k] for k in ('mode','devise','enrichir_designation')):
                raise ValueError('Usage, devise et choix d’enrichissement sont figés pour cet import ; créez une nouvelle prévisualisation pour les modifier.')
            job.options=options
            if categorie_id: self.catalogue.obtenir(CategorieProduit,categorie_id,org)
            for line in rows:
                self.session.refresh(line)
                if line.statut in ('INVALIDE','IMPORTE','CONSEIL','IGNORE'):continue
                data=line.donnees
                pack=self.rapprocher(org,data['CIP'])
                if not pack:
                    if mode=='conseils':line.statut='IGNORE';continue
                    if not categorie_id or not conditionnement_libelle:
                        line.erreurs=['Produit inconnu : catégorie et libellé commercial du conditionnement obligatoires.'];continue
                    prod=Produit(organisation_id=org,nom=data['Description'],categorie_id=categorie_id)
                    packaging=Conditionnement(organisation_id=org,produit_id=prod.id_produit,code='IMPORT-'+data['CIP'],libelle=conditionnement_libelle)
                    self.repo.enregistrer(prod);self.repo.enregistrer(packaging)
                    self.repo.enregistrer(ReferenceProduit(organisation_id=org,conditionnement_id=packaging.id_conditionnement,type_reference='CIP7',valeur=data['CIP']))
                    pack=self.rapprocher(org,data['CIP'])
                elif enrichir_designation and mode=='catalogue':
                    from dataclasses import replace
                    prod=self.catalogue.obtenir(Produit,pack.produit_id,org)
                    self.repo.enregistrer(replace(prod,nom=data['Description']))
                line.produit_id=pack.produit_id;line.conditionnement_id=pack.id_conditionnement
                # File+mapping+row+currency identifies a source observation, not an operational price.
                empreinte=hashlib.sha256(json.dumps([job.empreinte,job.mapping,line.numero,devise,job.source],sort_keys=True).encode()).hexdigest()
                existing=self.session.scalar(select(ConseilTarifSourceModel.id_conseil).where(ConseilTarifSourceModel.organisation_id==org,ConseilTarifSourceModel.empreinte_ligne==empreinte))
                if not existing:
                    self.session.add(ConseilTarifSourceModel(id_conseil=uuid4(),organisation_id=org,conditionnement_id=pack.id_conditionnement,import_id=ident,empreinte_ligne=empreinte,source=job.source,cip7=data['CIP'],dci_brute=data['DCI'] or None,prix_achat_indicatif=montant(data['PrixAchat']),prix_vente_conseille=montant(data['PrixVente']),devise=devise.upper(),releve_le=datetime.now(timezone.utc)))
                line.statut='IMPORTE' if mode=='catalogue' else 'CONSEIL';line.erreurs=[]
                self.session.flush()
        return {'id_import':ident,'traitees':len(rows),'offset_suivant':offset+len(rows),'termine':offset+len(rows)>=job.total}

    def appliquer(self, org, ids, *, debut, fin, niveau, site_id, base_prix, confirmer):
        if not confirmer:raise ValueError('Validation explicite des modifications tarifaires requise.')
        tariffs=TarificationService(self.catalogue)
        with self.repo.transaction():
            self.repo.verrouiller_organisation(org)
            result=[]
            for ident in ids:
                quote=self.session.scalar(select(ConseilTarifSourceModel).where(ConseilTarifSourceModel.id_conseil==ident,ConseilTarifSourceModel.organisation_id==org))
                if not quote:raise LookupError('Conseil tarifaire introuvable.')
                if quote.prix_vente_conseille is None:raise ValueError('Prix conseillé absent.')
                pack=self.catalogue.obtenir(Conditionnement,quote.conditionnement_id,org)
                value=quote.prix_vente_conseille
                if base_prix=='TTC':
                    prod=self.catalogue.obtenir(Produit,pack.produit_id,org)
                    tax=tariffs.actif(RegimeTVA,org,debut,code=prod.regime_tva_code) if prod.regime_tva_code else None
                    if prod.regime_tva_code and not tax:raise ValueError('TVA inconnue à la date choisie.')
                    # A TTC conversion cannot cover changing TVA rates with one HT value.
                    if tax and (tax.fin is not None and (fin is None or fin>tax.fin)):raise ValueError('La période TTC doit rester dans la période TVA connue.')
                    value=(value/(1+(tax.taux if tax else Decimal(0))/100)).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP)
                attrs={'organisation_id':org,'conditionnement_id':pack.id_conditionnement,'montant_ht':value,'devise':quote.devise,'debut':debut,'fin':fin,'provenance':'CONSEIL VALIDÉ '+str(quote.id_conseil)}
                if niveau=='produit_site':item=TarifProduitSite(**attrs,site_id=site_id,produit_id=pack.produit_id)
                else:item=TarifReference(**attrs)
                # Exact re-approval is idempotent; a conflicting price/period is rejected.
                old=next((x for x in self.repo.lister(type(item),org,**tariffs.scope(item)) if x.debut==debut and x.fin==fin and x.montant_ht==value and x.devise==quote.devise and x.provenance==item.provenance),None)
                if old:result.append(old.id_tarif);continue
                tariffs.valider(item);self.repo.enregistrer(item);result.append(item.id_tarif)
        return {'tarifs_crees_ou_existants':result}
