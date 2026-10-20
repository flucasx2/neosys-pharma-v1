"""Transaction finale P4/P3. Les confirmations externes ne consomment aucun stock."""
import hashlib,re
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import select,func
from fastapi.encoders import jsonable_encoder
from neosys_pharma.application.stock_service import ident
from neosys_pharma.domain.caisse import MODES,francs,repartir_paiements,acquisition,RegleFiscaleFidelite
from neosys_pharma.domain.catalogue import texte
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.caisse_models import *
from neosys_pharma.infrastructure.organisation_models import CaisseModel,OrganisationModel,SiteModel
from neosys_pharma.infrastructure.catalogue_models import ProduitModel,CategorieProduitModel,NatureMedicamentModel
from neosys_pharma.infrastructure.vente_models import ReservationVenteModel
from neosys_pharma.infrastructure.client_models import ClientModel
from neosys_pharma.infrastructure.stock_models import ReservationStockModel
from neosys_pharma.infrastructure.prise_en_charge_models import (
    CalculPriseEnChargeVenteModel, LigneCalculPriseEnChargeModel,
    PartCalculPriseEnChargeModel, RealisationPriseEnChargeModel,
)

def serial(row):
    return jsonable_encoder({c.name:getattr(row,c.name) for c in row.__table__.columns if c.name!='pdf'},custom_encoder={Decimal:str})

class CaisseService:
    def __init__(self,vente):
        self.vente=vente;self.stock=vente.stock;self.s=vente.s;self.org=vente.org;self.site=vente.site

    def trace(self,type,**data):
        self.stock.ajouter(EvenementCaisseModel,auteur_id=self.stock.user,type=type,donnees=jsonable_encoder({**data,'operation_id':str(self.stock.op)}))

    def periode(self):
        p=self.s.scalar(select(PeriodeCaisseSiteModel).filter_by(organisation_id=self.org,site_id=self.site,etat='OUVERTE'))
        if not p:
            if self.stock.lignes(PeriodeCaisseSiteModel,site_id=self.site):raise ConflitStock('Ouvrir une période après clôture Z effective ; aucun reset implicite.')
            p=self.stock.ajouter(PeriodeCaisseSiteModel,site_id=self.site)
        return p

    def appel(self,v):
        a=self.s.scalar(select(AppelVenteModel).filter_by(organisation_id=self.org,vente_id=v.id))
        if not a:
            p=self.periode();a=self.stock.ajouter(AppelVenteModel,vente_id=v.id,periode_id=p.id,numero=p.prochain_appel);p.prochain_appel+=1
        return serial(a)|{'affichage':str(a.numero).zfill(4)}

    def config(self):
        row=self.s.scalar(select(ParametrageCaisseModel).filter_by(organisation_id=self.org))
        return (serial(row) if row else {'modes':[],'ticket_appel':False,'revision':0})|{'moyens':[serial(m) for m in self.s.scalars(select(MoyenPaiementModel).where(MoyenPaiementModel.organisation_id==self.org).order_by(MoyenPaiementModel.code))]}

    def moyen(self,mode,key,*,actif=True):
        if not key:return None
        row=self.stock.obtenir(MoyenPaiementModel,key)
        if row.mode!=mode:raise ValueError('Moyen de paiement incompatible avec sa famille.')
        if actif and not row.actif:raise ConflitStock('Moyen de paiement désactivé : choisir un moyen autorisé.')
        return row

    def definir_moyen(self,data,key=None):
        self.stock.access('caisse.parametrer',self.site,None)
        libelle=data['libelle'].strip()
        if not libelle or any(ord(c)<32 for c in libelle):raise ValueError('Libellé de moyen invalide.')
        if key:
            row=self.stock.obtenir(MoyenPaiementModel,key)
            if row.revision!=data['revision']:raise ConflitStock('Moyen modifié : actualiser.')
            before=serial(row);row.libelle=libelle;row.actif=data['actif'];row.revision+=1
        else:
            import re
            code=data['code'].strip().upper()
            if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,79}',code):raise ValueError('Code de moyen invalide.')
            if data['mode'] not in MODES or data['mode']=='ESPECES':raise ValueError('Famille non espèces requise.')
            before=None;row=self.stock.ajouter(MoyenPaiementModel,code=code,libelle=libelle,mode=data['mode'],actif=data['actif'])
        self.trace('MOYEN_PAIEMENT_CONFIGURE',avant=before,apres=serial(row))
        return serial(row)

    def configurer(self,data):
        row=self.s.scalar(select(ParametrageCaisseModel).filter_by(organisation_id=self.org))
        if data['revision']!=(row.revision if row else 0):raise ConflitStock('Configuration modifiée : actualiser.')
        if len(set(data['modes']))!=len(data['modes']) or any(x not in MODES for x in data['modes']):raise ValueError('Moyens de paiement invalides.')
        before=serial(row) if row else None
        if row:row.modes=data['modes'];row.ticket_appel=data['ticket_appel'];row.revision+=1
        else:row=self.stock.ajouter(ParametrageCaisseModel,modes=data['modes'],ticket_appel=data['ticket_appel'])
        self.trace('PARAMETRAGE',avant=before,apres=serial(row));return serial(row)

    def renommer_caisse(self,key,data):
        row,_=self.caisse(key,'caisse.parametrer')
        if row.nom!=data['nom_attendu']:
            raise ConflitStock('Le nom de cette caisse a changé : rechargez les données.')
        nom=data['nom'].strip()
        if not nom or len(nom)>200 or any(ord(c)<32 for c in nom):
            raise ValueError('Nom de caisse invalide.')
        avant=row.nom;row.nom=nom
        self.trace('CAISSE_RENOMMEE',caisse_id=str(row.id_caisse),avant=avant,apres=nom)
        return {'id':str(row.id_caisse),'nom':row.nom,'emplacement_id':str(row.emplacement_id)}

    def caisse(self,key,permission):
        row=self.s.get(CaisseModel,ident(key))
        if not row or not row.actif:raise PermissionError('Caisse absente ou inactive.')
        loc=self.stock.emplacement(row.emplacement_id,permission)
        if loc.site_id!=self.site:raise PermissionError('Caisse hors du site courant.')
        return row,loc

    def session(self,key,permission,active=False):
        row=self.stock.obtenir(SessionCaisseModel,key)
        self.caisse(row.caisse_id,permission)
        if active and (row.etat!='OUVERTE' or row.caissier_id!=self.stock.user):raise PermissionError('Session ouverte du caissier courant requise.')
        return row

    def ouvrir(self,data):
        caisse,loc=self.caisse(data['caisse_id'],'caisse.session.gerer')
        if self.stock.lignes(SessionCaisseModel,caisse_id=caisse.id_caisse,etat='OUVERTE'):raise ConflitStock('Une session est déjà ouverte : la fermer avant changement de caissier.')
        row=self.stock.ajouter(SessionCaisseModel,caisse_id=caisse.id_caisse,site_id=self.site,emplacement_id=loc.id_emplacement,caissier_id=self.stock.user,fond_initial=francs(data['fond_initial'],True))
        self.trace('SESSION_OUVERTE',session=serial(row));return self.session_detail(row)

    def session_detail(self,row):
        cash=self.s.scalar(select(func.coalesce(func.sum(MouvementCaisseModel.montant_net),0)).where(MouvementCaisseModel.session_id==row.id,MouvementCaisseModel.organisation_id==self.org,MouvementCaisseModel.mode=='ESPECES'))
        grouped_cash=self.s.scalar(select(func.coalesce(func.sum(MouvementCaisseGroupeModel.montant_net),0)).where(MouvementCaisseGroupeModel.session_id==row.id,MouvementCaisseGroupeModel.organisation_id==self.org,MouvementCaisseGroupeModel.mode=='ESPECES'))
        from neosys_pharma.infrastructure.regularisation_models import MouvementFinancierModel
        extras=self.s.scalar(select(func.coalesce(func.sum(MouvementFinancierModel.montant),0)).where(MouvementFinancierModel.session_id==row.id,MouvementFinancierModel.organisation_id==self.org,MouvementFinancierModel.mode=='ESPECES'))
        expected=row.fond_initial+cash+grouped_cash+extras
        return serial(row)|{'especes_attendues':str(expected),'ecart_especes':str(row.comptage_final-expected) if row.comptage_final is not None else None}

    def fermer(self,key,data):
        row=self.session(key,'caisse.session.gerer',True)
        if row.revision!=data['revision']:raise ConflitStock('Session modifiée : actualiser.')
        from neosys_pharma.infrastructure.regularisation_models import TransfertFondsModel,RemboursementModel
        if any(x.etat not in ('RECU','ANNULE') for x in self.stock.lignes(TransfertFondsModel,session_id=row.id)) or any(x.etat!='EXECUTE' for x in self.stock.lignes(RemboursementModel,session_id=row.id)):raise ConflitStock('Résoudre les transferts et remboursements avant fermeture.')
        row.comptage_final=francs(data['comptage_final'],True);row.ferme_le=now();row.etat='FERMEE';row.revision+=1
        self.trace('SESSION_FERMEE',session=self.session_detail(row),justification=data['justification']);return self.session_detail(row)

    def verifier_vente(self,key,session,revision,permission='caisse.encaisser'):
        v=self.vente.obtenir(key,permission);self.vente.revision(v,revision)
        if v.etat!='TRANSMISE' or v.caisse_id!=session.caisse_id or v.emplacement_id!=session.emplacement_id:raise ConflitStock('Préparation transmise à cette caisse requise.')
        if v.mode=='CREDIT':raise ValueError('Le crédit reste indisponible dans ce parcours.')
        if v.mode!='SANS_TIERS':self._prise_en_charge(v)
        return v

    def _prise_en_charge(self,v,verrouiller=True):
        """Revalide le snapshot tiers confirmé et ses montants ligne par ligne."""
        query=select(CalculPriseEnChargeVenteModel).where(
            CalculPriseEnChargeVenteModel.vente_id==v.id,
            CalculPriseEnChargeVenteModel.organisation_id==self.org,
            CalculPriseEnChargeVenteModel.site_id==self.site,
        )
        calcul=self.s.scalar(query.with_for_update() if verrouiller else query)
        if not calcul:
            raise ConflitStock('Prise en charge non confirmée : aucun encaissement tiers autorisé.')
        if calcul.revision_vente!=v.revision:
            raise ConflitStock('Le calcul tiers ne correspond plus à la révision transmise de la vente.')
        finance=self.vente.finance(v)
        total=francs(finance['totaux']['ttc'],True)
        if calcul.total_xaf!=total or calcul.total_xaf!=calcul.total_organismes_xaf+calcul.part_client_xaf:
            raise ConflitStock('Le snapshot de prise en charge ne correspond plus au montant net de la vente.')
        lines=list(self.s.scalars(select(LigneCalculPriseEnChargeModel).where(
            LigneCalculPriseEnChargeModel.calcul_id==calcul.id,
            LigneCalculPriseEnChargeModel.vente_id==v.id,
            LigneCalculPriseEnChargeModel.organisation_id==self.org,
        ).order_by(LigneCalculPriseEnChargeModel.ligne_vente_id)))
        line_net={UUID(line_id):francs(values['ttc'],True) for line_id,values in finance['lignes'].items()}
        if {row.ligne_vente_id for row in lines}!=set(line_net):
            raise ConflitStock('Les lignes du snapshot tiers diffèrent des lignes financières de la vente.')
        for row in lines:
            if row.net_xaf!=line_net[row.ligne_vente_id] or row.net_xaf!=row.part_client_xaf+row.total_organismes_xaf:
                raise ConflitStock('Répartition tiers incohérente avec le net historique d’une ligne.')
        if sum(row.part_client_xaf for row in lines)!=calcul.part_client_xaf or sum(row.total_organismes_xaf for row in lines)!=calcul.total_organismes_xaf:
            raise ConflitStock('Les parts par ligne ne correspondent pas au total du snapshot tiers.')
        parts=list(self.s.scalars(select(PartCalculPriseEnChargeModel).join(
            LigneCalculPriseEnChargeModel,
            PartCalculPriseEnChargeModel.ligne_calcul_id==LigneCalculPriseEnChargeModel.id,
        ).where(
            LigneCalculPriseEnChargeModel.calcul_id==calcul.id,
            PartCalculPriseEnChargeModel.organisation_id==self.org,
            PartCalculPriseEnChargeModel.type_part=='ORGANISME',
        )))
        return calcul,lines,parts

    def prise_en_charge_detail(self,v):
        if v.mode=='SANS_TIERS':return None
        calcul,lines,parts=self._prise_en_charge(v)
        from neosys_pharma.infrastructure.client_models import OrganismePriseEnChargeModel
        totals={}
        for part in parts:totals[part.organisme_id]=totals.get(part.organisme_id,0)+part.montant_xaf
        names={str(row.id):row.nom for row in self.s.scalars(select(OrganismePriseEnChargeModel).where(
            OrganismePriseEnChargeModel.organisation_id==self.org,
            OrganismePriseEnChargeModel.id.in_(totals or [UUID(int=0)]),
        ))}
        org_by_line={}
        calc_line_by_id={row.id:row.ligne_vente_id for row in lines}
        for part in parts:
            sale_line=calc_line_by_id.get(part.ligne_calcul_id)
            if sale_line is not None:
                org_by_line.setdefault(sale_line,[]).append({
                    'organisme_id':str(part.organisme_id),
                    'nom':names.get(str(part.organisme_id),'Organisme'),
                    'montant_xaf':part.montant_xaf,
                })
        return {
            'calcul_id':str(calcul.id),'snapshot_hash':calcul.snapshot_hash,
            'total_xaf':calcul.total_xaf,'part_client_xaf':calcul.part_client_xaf,
            'total_organismes_xaf':calcul.total_organismes_xaf,
            'organismes':[{'organisme_id':str(key),'nom':names.get(str(key),'Organisme'),
                           'montant_xaf':amount} for key,amount in sorted(totals.items(),key=lambda item:str(item[0]))],
            'lignes':[{'ligne_vente_id':str(row.ligne_vente_id),'net_xaf':row.net_xaf,
                       'part_client_xaf':row.part_client_xaf,
                       'total_organismes_xaf':row.total_organismes_xaf,
                       'organismes':org_by_line.get(row.ligne_vente_id,[])} for row in lines],
        }

    def prise_en_charge_detail_optionnelle(self,v):
        """Permet d'afficher une vente tiers avant confirmation, sans l'autoriser à encaisser."""
        if v.mode=='SANS_TIERS':return None
        exists=self.s.scalar(select(CalculPriseEnChargeVenteModel.id).where(
            CalculPriseEnChargeVenteModel.vente_id==v.id,
            CalculPriseEnChargeVenteModel.organisation_id==self.org,
            CalculPriseEnChargeVenteModel.site_id==self.site,
        ))
        return self.prise_en_charge_detail(v) if exists else None

    def confirmer(self,key,data):
        session=self.session(data['session_id'],'caisse.paiement.confirmer',True)
        v=self.verifier_vente(key,session,data['revision'],'caisse.paiement.confirmer')
        if data['mode']=='ESPECES' or data['mode'] not in self.config()['modes']:raise ValueError('Moyen non espèces actif requis.')
        if data['source']=='TECHNIQUE_PRESTATAIRE':raise ValueError('Aucun prestataire bancaire intégré : confirmation technique indisponible.')
        if data['mode'] in ('CARTE','MOBILE_MONEY') and data['source']!='MANUEL_TERMINAL':raise ValueError('Confirmation manuelle du terminal indépendant requise.')
        if data['mode'] in ('CHEQUE','VIREMENT') and data['source']!='MANUEL_JUSTIFICATIF':raise ValueError('Confirmation du justificatif requise.')
        moyen=self.moyen(data['mode'],data.get('moyen_id'))
        if not moyen and any(m['mode']==data['mode'] for m in self.config()['moyens']):
            raise ValueError('Sélection explicite du moyen de paiement configuré requise.')
        ref=data['reference'].strip()
        if not ref or not data['preuve'].strip():raise ValueError('Référence vérifiable et preuve de confirmation obligatoires.')
        row=self.stock.ajouter(ConfirmationReglementModel,vente_id=v.id,session_id=session.id,revision_vente=v.revision,mode=data['mode'],moyen_id=moyen.id if moyen else None,moyen_libelle=moyen.libelle if moyen else None,montant=francs(data['montant']),reference=ref,source=data['source'],preuve=data['preuve'],auteur_id=self.stock.user)
        self.trace('PAIEMENT_CONFIRME',confirmation=serial(row));return serial(row)

    def rapprocher(self,key,confirmation_id,data):
        session=self.session(data['session_id'],'caisse.paiement.confirmer',True)
        v=self.verifier_vente(key,session,data['revision'],'caisse.paiement.confirmer')
        confirmation=self.stock.obtenir(ConfirmationReglementModel,confirmation_id)
        if confirmation.vente_id!=v.id:raise PermissionError('Confirmation d’une autre vente.')
        if self.stock.lignes(ReglementModel,confirmation_id=confirmation.id):raise ConflitStock('Paiement déjà utilisé.')
        self.trace('PAIEMENT_RAPPROCHE',confirmation_id=confirmation.id,vente_id=v.id,session_id=session.id,revision_vente=v.revision,justification=data['justification'])
        return serial(confirmation)|{'revision_rapprochee':v.revision,'session_rapprochee':str(session.id)}

    def rapprochement_compatible(self,confirmation,v,session):
        if confirmation.vente_id!=v.id:return False
        if confirmation.session_id==session.id and confirmation.revision_vente==v.revision:return True
        for event in self.stock.lignes(EvenementCaisseModel,type='PAIEMENT_RAPPROCHE'):
            d=event.donnees
            if d.get('confirmation_id')==str(confirmation.id) and d.get('vente_id')==str(v.id) and d.get('session_id')==str(session.id) and d.get('revision_vente')==v.revision:return True
        return False

    def compte(self,key,permission='fidelite.consulter'):
        self.stock.access(permission,self.site,None)
        row=self.stock.obtenir(CompteFideliteModel,key)
        client=self.stock.obtenir(ClientFideliteModel,row.client_id)
        return serial(row)|{'client':serial(client),'cartes':[serial(c) for c in self.stock.lignes(CarteFideliteModel,compte_id=row.id)],'utilisation_disponible':False,'motif_blocage':'Règle fiscale fidélité non validée.'}

    def creer_compte(self,data):
        phone=re.sub(r'[\s().-]','',data['telephone']) if data.get('telephone') else None
        profile=self.stock.ajouter(ClientModel,nom=texte(data['nom'],200),telephone=phone)
        client=self.stock.ajouter(ClientFideliteModel,nom=profile.nom,telephone=phone,profil_client_id=profile.id)
        row=self.stock.ajouter(CompteFideliteModel,client_id=client.id)
        self.trace('COMPTE_CREE',client=serial(client),compte_id=row.id)
        return self.compte(row.id,'fidelite.gerer')

    def creer_compte_pour_client(self,client_id):
        profile=self.stock.obtenir(ClientModel,client_id)
        if not profile.actif:raise ValueError('Une fiche client inactive ne peut pas adhérer à la fidélité.')
        old=self.s.scalar(select(ClientFideliteModel).filter_by(organisation_id=self.org,profil_client_id=profile.id))
        if old:raise ValueError('Cette fiche client possède déjà un compte fidélité.')
        client=self.stock.ajouter(ClientFideliteModel,nom=profile.nom,telephone=profile.telephone,profil_client_id=profile.id)
        row=self.stock.ajouter(CompteFideliteModel,client_id=client.id)
        self.trace('COMPTE_CREE',client=serial(client),profil_client_id=profile.id,compte_id=row.id)
        return self.compte(row.id,'fidelite.gerer')

    def carte(self,key,data):
        row=self.stock.obtenir(CompteFideliteModel,key)
        if row.revision!=data['revision']:raise ConflitStock('Compte modifié : actualiser.')
        old=None
        if data.get('remplace_id'):
            old=self.stock.obtenir(CarteFideliteModel,data['remplace_id'])
            if old.compte_id!=row.id:raise PermissionError('Carte d’un autre compte.')
            if old.etat=='REMPLACEE':raise ConflitStock('Carte déjà remplacée.')
            old.etat='REMPLACEE'
        code=data.get('code')
        if code is None and data['type']=='VIRTUELLE':code='V-'+uuid4().hex.upper()
        if not isinstance(code,str) or not code.strip() or len(code)>200 or any(ord(c)<32 for c in code):
            raise ValueError('Un identifiant physique valide est obligatoire ; les cartes virtuelles peuvent recevoir un identifiant automatique.')
        barcode=self.valider_code_barres(data.get('code_barres'),data['type'])
        card=self.stock.ajouter(CarteFideliteModel,compte_id=row.id,code=code.strip(),code_barres=barcode,type=data['type'],remplace_id=old.id if old else None)
        row.revision+=1;self.trace('CARTE_CREEE',carte=serial(card));return self.compte(row.id,'fidelite.gerer')

    @staticmethod
    def valider_code_barres(value,kind='PHYSIQUE'):
        if value is None:return None
        if kind!='PHYSIQUE' or not value or value!=value.strip() or len(value)>80 or any(ord(c)<32 or ord(c)>126 for c in value):
            raise ValueError('Code-barres physique ASCII de 1 à 80 caractères, sans espaces de bord, requis.')
        return value

    def associer_code_barres(self,key,data):
        card=self.stock.obtenir(CarteFideliteModel,key);account=self.stock.obtenir(CompteFideliteModel,card.compte_id)
        self.compte(account.id,'fidelite.gerer')
        if account.revision!=data['revision']:raise ConflitStock('Compte modifié : actualiser.')
        if card.type!='PHYSIQUE' or card.etat!='ACTIVE' or card.code_barres is not None or self.stock.lignes(DocumentCarteFideliteModel,carte_id=card.id):
            raise ConflitStock('Associer le code-barres avant impression, à une carte physique active sans code-barres.')
        card.code_barres=self.valider_code_barres(data['code_barres']);account.revision+=1;self.s.flush()
        self.trace('CARTE_CODE_BARRES_ASSOCIE',carte=serial(card))
        return self.compte(account.id,'fidelite.gerer')

    def imprimer_carte(self,key):
        card=self.stock.obtenir(CarteFideliteModel,key);account=self.compte(card.compte_id,'fidelite.gerer')
        if card.etat!='ACTIVE':raise ConflitStock('Carte opposée ou remplacée : nouvelle impression refusée.')
        rows=self.stock.lignes(DocumentCarteFideliteModel,carte_id=card.id)
        document=rows[0] if rows else None
        if document is None:
            snapshot={'carte_id':str(card.id),'compte_id':str(card.compte_id),'code':card.code,'code_barres':card.code_barres,
                'titulaire':account['client']['nom'],'organisation':self.s.get(OrganisationModel,self.org).nom_commercial}
            from neosys_pharma.infrastructure.caisse_pdf import carte_fidelite_pdf
            pdf=carte_fidelite_pdf(snapshot)
            document=self.stock.ajouter(DocumentCarteFideliteModel,carte_id=card.id,auteur_id=self.stock.user,instantane=snapshot,pdf=pdf,pdf_sha256=hashlib.sha256(pdf).hexdigest())
        self.trace('CARTE_DOCUMENT_DEMANDE',carte_id=card.id,document_id=document.id,pdf_sha256=document.pdf_sha256)
        return serial(document)

    def opposer(self,key,data):
        card=self.stock.obtenir(CarteFideliteModel,key);row=self.stock.obtenir(CompteFideliteModel,card.compte_id)
        if row.revision!=data['revision'] or card.etat!='ACTIVE':raise ConflitStock('Carte ou compte modifié.')
        card.etat='OPPOSEE';row.revision+=1
        self.trace('CARTE_OPPOSEE',carte=serial(card),justification=data['justification']);return self.compte(row.id,'fidelite.gerer')

    def bareme(self,kind):
        rows=self.s.scalars(select(BaremeFideliteModel).where(BaremeFideliteModel.organisation_id==self.org,BaremeFideliteModel.type==kind,BaremeFideliteModel.debut<=self.stock.jour,(BaremeFideliteModel.fin.is_(None))|(BaremeFideliteModel.fin>=self.stock.jour))).all()
        if len(rows)>1:raise ConflitStock('Barèmes actifs incompatibles.')
        return rows[0] if rows else None

    def ajouter_bareme(self,data):
        if data['fin'] and data['fin']<data['debut']:raise ValueError('Fin antérieure au début.')
        if len(set(data['categories']))!=len(data['categories']) or not data['categories']:raise ValueError('Catégories éligibles explicites obligatoires.')
        for cid in data['categories']:
            category=self.s.get(CategorieProduitModel,ident(cid))
            if not category or category.organisation_id!=self.org:raise PermissionError('Catégorie hors organisation.')
        if data['type']=='CONVERSION' and data['plafond_xaf'] is None and data['plafond_pourcentage'] is None:raise ValueError('Plafond de réduction explicite obligatoire.')
        end=data['fin'] or date.max
        for old in self.stock.lignes(BaremeFideliteModel,type=data['type']):
            if old.debut<=end and (old.fin or date.max)>=data['debut']:raise ConflitStock('Périodes inclusives chevauchantes : clôturer explicitement le barème précédent.')
        row=self.stock.ajouter(BaremeFideliteModel,**{**data,'categories':[str(x) for x in data['categories']]})
        self.trace('BAREME_CREE',bareme=serial(row));return serial(row)

    def clore_bareme(self,key,data):
        row=self.stock.obtenir(BaremeFideliteModel,key)
        if row.fin is not None:raise ConflitStock('Barème déjà clôturé.')
        # Ne pas retirer une date déjà utilisée dans un encaissement historique.
        if data['fin']<row.debut or data['fin']<self.stock.jour:raise ValueError('Clôture antérieure au début ou à la date courante interdite.')
        row.fin=data['fin'];self.trace('BAREME_CLOTURE',bareme=serial(row));return serial(row)

    def categorie_eligible(self,cid,bareme):
        seen=set()
        while cid and cid not in seen:
            seen.add(cid)
            if str(cid) in bareme.categories:return True
            if not bareme.sous_categories:return False
            category=self.s.get(CategorieProduitModel,cid)
            if not category or category.organisation_id!=self.org:return False
            cid=category.parent_id
        return False

    def assiette_acquisition(self,v,finance,rule,part_client_par_ligne=None):
        """Lecture commune au diagnostic et au gain ; aucun crédit de points."""
        eligible=[];diagnostics=[]
        for row in self.vente.lignes(v):
            product=self.s.get(ProduitModel,row.produit_id)
            nature=self.s.get(NatureMedicamentModel,product.nature_id) if product and product.nature_id else None
            amount=Decimal(0)
            if not row.actif:code,motif='LIGNE_INACTIVE','Ligne inactive.'
            elif not nature:code,motif='NATURE_ABSENTE','Nature du produit non renseignée ou introuvable.'
            elif nature.code.strip().upper()!='COSMETIQUE':code,motif='NATURE_NON_ADMISE','Nature du produit différente de COSMETIQUE.'
            elif not rule:code,motif='BAREME_ABSENT','Aucun barème d’acquisition applicable à la date métier.'
            elif not self.categorie_eligible(product.categorie_id,rule):code,motif='CATEGORIE_NON_ADMISE','Catégorie non admise au barème applicable.'
            else:
                amount=(part_client_par_ligne or {}).get(row.id,finance['lignes'][str(row.id)]['ttc'])
                amount=francs(amount,True)
                if amount:
                    eligible.append({'ligne_id':str(row.id),'ttc_paye':str(amount),
                                     'part_client_xaf':int(amount),'nature_code':nature.code})
                    code,motif='ELIGIBLE','Montant client éligible ; attribution après encaissement uniquement.'
                else:code,motif='MONTANT_CLIENT_NUL','Aucun montant client éligible sur cette ligne.'
            diagnostics.append({'ligne_id':str(row.id),'designation':row.designation,
                'eligible':code=='ELIGIBLE','code':code,'motif':motif,
                'montant_client_eligible_xaf':int(amount)})
        return eligible,diagnostics

    def information_fidelite(self,key):
        """Diagnostic en lecture seule : présent avant paiement, snapshot après."""
        v=self.vente.obtenir(key,'caisse.consulter')
        self.stock.access('fidelite.consulter',self.site,v.emplacement_id)
        receipt=self.s.scalar(select(EncaissementModel).where(
            EncaissementModel.organisation_id==self.org,EncaissementModel.vente_id==v.id))
        if receipt:
            gain=receipt.instantane.get('fidelite')
            result={'vente_id':str(v.id),'revision':v.revision,'phase':'ENCAISSEE',
                'source':'SNAPSHOT_ENCAISSEMENT','lignes':[],
                'points_acquis':(gain or {}).get('points_acquis',(gain or {}).get('points',0)),
                'eligible_paye':(gain or {}).get('eligible_paye'),
                'dette_compensee':(gain or {}).get('dette_compensee',0)}
            if not gain:code,motif='SANS_FIDELITE','Aucun compte fidélité enregistré pour cet encaissement.'
            elif gain.get('motif'):code,motif='BAREME_ABSENT',gain['motif']
            elif result['points_acquis']:code,motif='ACQUISITION_CONFIRMEE','Points acquis enregistrés après encaissement ; une dette éventuelle est compensée avant disponibilité.'
            elif Decimal(gain.get('eligible_paye','0'))==0:code,motif='ASSIETTE_NULLE','Aucun montant éligible enregistré. Le motif par produit n’est pas conservé dans ce snapshot historique ; aucune réévaluation rétroactive.'
            else:code,motif='SEUIL_NON_ATTEINT','Assiette éligible enregistrée, mais aucun point entier acquis selon le barème et son arrondi inférieur.'
            return result|{'code':code,'motif':motif}
        finance=self.vente.finance(v)
        coverage,coverage_lines,_=self._prise_en_charge(v,verrouiller=False) if v.mode!='SANS_TIERS' else (None,[],[])
        line_paid={row.ligne_vente_id:row.part_client_xaf for row in coverage_lines} if coverage else None
        rule=self.bareme('ACQUISITION')
        eligible,diagnostics=self.assiette_acquisition(v,finance,rule,line_paid)
        return {'vente_id':str(v.id),'revision':v.revision,'phase':'AVANT_ENCAISSEMENT',
            'source':'REGLES_ACTUELLES','points_acquis':None,'lignes':diagnostics,
            'eligible_paye':str(sum((Decimal(x['ttc_paye']) for x in eligible),Decimal(0))),
            'code':'INFORMATION_AVANT_PAIEMENT' if rule else 'BAREME_ABSENT',
            'motif':'Titulaire identifié et éligibilité des produits sont distincts. Aucun point attribué avant encaissement confirmé.' if rule else 'Aucun barème d’acquisition applicable à la date métier. Aucun point ne sera attribué en son absence.'}

    def gagner(self,v,compte,finance,part_client_par_ligne=None):
        rule=self.bareme('ACQUISITION')
        if not rule:return {'points':0,'motif':'Aucun barème d’acquisition applicable.'}
        eligible,_=self.assiette_acquisition(v,finance,rule,part_client_par_ligne)
        base=sum((Decimal(x['ttc_paye']) for x in eligible),Decimal(0))
        points=acquisition(base,rule.points,rule.montant_xaf)
        # Une éventuelle dette est compensée avant disponibilité de nouveaux points.
        compensation=min(points,compte.dette);compte.dette-=compensation;compte.points+=points-compensation;compte.revision+=1
        details={'bareme':serial(rule),'eligible_paye':str(base),'lignes':eligible,'points_acquis':points,'dette_compensee':compensation,'fractions_reportees':False}
        return details|{'solde':compte.points,'dette':compte.dette}

    def finaliser(self,key,data):
        session=self.session(data['session_id'],'caisse.encaisser',True)
        v=self.verifier_vente(key,session,data['revision'])
        coverage=None;coverage_lines=[];coverage_parts=[]
        if v.mode!='SANS_TIERS':coverage,coverage_lines,coverage_parts=self._prise_en_charge(v)
        if session.revision!=data['revision_session']:raise ConflitStock('Session modifiée : actualiser.')
        if data['points_utilises']:
            if not data['consentement']:raise ValueError('Consentement explicite du titulaire obligatoire.')
            self.stock.access('fidelite.utiliser',self.site,v.emplacement_id)
            if not data.get('compte_id'):raise ValueError('Compte fidélité obligatoire.')
            account=self.stock.obtenir(CompteFideliteModel,data['compte_id'])
            if account.dette:raise ConflitStock('Dette de points : nouvelle utilisation interdite.')
            RegleFiscaleFidelite().verifier_utilisation()
        requests=self.stock.lignes(self.vente.remise_model,vente_id=v.id)
        if any(r.statut=='DEMANDEE' for r in requests):raise ConflitStock('Remise en attente : encaissement interdit.')
        from neosys_pharma.domain.remises import montant_remise
        for r in requests:
            if r.statut=='AUTORISEE':
                eligible=self.vente.eligible(v,r);cap=self.vente.plafond_applicable(v,ident(r.autorisation['auteur_id']),r,montant_remise(r.type,r.valeur,eligible),eligible)
                if str(cap.id)!=r.autorisation['plafond']['id'] or cap.revision!=r.autorisation['plafond']['revision']:raise ConflitStock('Autorisation de remise à revalider.')
        finance=self.vente.finance(v);total_vente=francs(finance['totaux']['ttc'],True)
        total=francs(coverage.part_client_xaf,True) if coverage else total_vente
        payments=[];used=set()
        for row in data['reglements']:
            if row['mode'] not in self.config()['modes']:raise ValueError('Moyen de paiement non activé.')
            montant=francs(row['montant']);confirmation=None
            if row['mode']!='ESPECES':
                if not row.get('confirmation_id'):raise ValueError('Confirmation indépendante obligatoire avant encaissement.')
                confirmation=self.stock.obtenir(ConfirmationReglementModel,row['confirmation_id'])
                self.moyen(confirmation.mode,confirmation.moyen_id)
                if confirmation.id in used:raise ValueError('Confirmation utilisée plusieurs fois.')
                used.add(confirmation.id)
                if not self.rapprochement_compatible(confirmation,v,session) or confirmation.mode!=row['mode'] or confirmation.montant!=montant:raise ConflitStock('Confirmation incompatible ou préparation modifiée : rapprocher le paiement.')
                if self.stock.lignes(ReglementModel,confirmation_id=confirmation.id):raise ConflitStock('Confirmation déjà consommée.')
            elif row.get('confirmation_id'):raise ValueError('Référence de paiement non espèces incompatible avec espèces.')
            payments.append({'mode':row['mode'],'montant':montant,'confirmation_id':confirmation.id if confirmation else None,'confirmation':serial(confirmation) if confirmation else None})
        payments=repartir_paiements(total,payments)
        from neosys_pharma.infrastructure.regularisation_models import RemboursementModel
        if any(self.stock.lignes(RemboursementModel,confirmation_id=c,etat='EXECUTE') for c in used):raise ConflitStock('Paiement déjà restitué.')
        if any(self.stock.lignes(RemboursementModel,confirmation_id=c) for c in used):raise ConflitStock('Restitution demandée : paiement indisponible pour encaissement.')
        pending={c.id for c in self.stock.lignes(ConfirmationReglementModel,vente_id=v.id) if not self.stock.lignes(ReglementModel,confirmation_id=c.id) and not self.stock.lignes(RemboursementModel,confirmation_id=c.id,etat='EXECUTE')}
        if pending!=used:raise ConflitStock('Tous les paiements acquis confirmés doivent être rapprochés et intégrés ; ne pas laisser de règlement orphelin.')
        compte=None
        if data.get('compte_id'):
            self.stock.access('fidelite.consulter',self.site,v.emplacement_id)
            compte=self.stock.obtenir(CompteFideliteModel,data['compte_id'])
            if data['revision_compte']!=compte.revision:raise ConflitStock('Compte fidélité modifié : actualiser et reconfirmer le titulaire.')
            if coverage:
                profile=self.s.scalar(select(ClientFideliteModel).where(
                    ClientFideliteModel.id==compte.client_id,
                    ClientFideliteModel.organisation_id==self.org,
                    ClientFideliteModel.profil_client_id==v.client_id,
                )) if v.client_id else None
                client=self.s.get(ClientModel,v.client_id) if v.client_id else None
                if not profile or not client or not client.actif:
                    raise PermissionError('Pour une vente avec prise en charge, le compte fidélité doit appartenir au client actif rattaché à la vente.')
        # Revalidation des réservations et des péremptions dans la même transaction.
        for row in self.vente.lignes(v):
            if not row.actif:continue
            links=self.stock.lignes(ReservationVenteModel,ligne_id=row.id)
            active=[self.stock.obtenir(ReservationStockModel,x.reservation_id) for x in links if self.stock.obtenir(ReservationStockModel,x.reservation_id).statut=='ACTIVE']
            if sum(sum(a['quantite'] for a in self.stock.reservation_detail(r)['allocations']) for r in active)!=row.quantite:raise ConflitStock('Réservation incomplète.')
            for reservation in active:self.stock.terminer_reservation(reservation.id,True,'VENTE','caisse.encaisser',True)
        p=self.periode();numero=p.prochain_encaissement;p.prochain_encaissement+=1
        org=self.s.get(OrganisationModel,self.org);site=self.s.get(SiteModel,self.site)
        line_paid={row.ligne_vente_id:row.part_client_xaf for row in coverage_lines} if coverage else None
        coverage_detail=self.prise_en_charge_detail(v) if coverage else None
        snapshot=self.vente.detail(v)|{'organisation':org.nom_commercial,'site':site.nom,'date':now().isoformat(),'numero_encaissement':str(numero).zfill(4),'periode_z':p.numero,'reglements':jsonable_encoder(payments,custom_encoder={Decimal:str}),'caissier_id':str(self.stock.user),'fidelite':None,'etat':'ENCAISSEE'}
        if coverage_detail:
            snapshot['part_client_xaf']=int(total)
            snapshot['total_organismes_xaf']=coverage.total_organismes_xaf
            snapshot['prise_en_charge']=coverage_detail
        gain=self.gagner(v,compte,finance,line_paid) if compte else None
        if compte:snapshot['fidelite']=gain|{'client':serial(self.stock.obtenir(ClientFideliteModel,compte.client_id))}
        from neosys_pharma.infrastructure.caisse_pdf import recu_pdf
        pdf=recu_pdf(snapshot)
        enc=self.stock.ajouter(EncaissementModel,vente_id=v.id,session_id=session.id,periode_id=p.id,numero=numero,total_xaf=total,compte_id=compte.id if compte else None,instantane=snapshot,pdf=pdf,pdf_sha256=hashlib.sha256(pdf).hexdigest())
        if coverage and coverage.total_organismes_xaf:
            self.stock.ajouter(RealisationPriseEnChargeModel,
                vente_id=v.id,encaissement_id=enc.id,calcul_id=coverage.id,
                site_id=self.site,total_xaf=int(coverage.total_xaf),
                total_organismes_xaf=int(coverage.total_organismes_xaf),
                part_client_xaf=int(coverage.part_client_xaf),snapshot=snapshot['prise_en_charge'])
        if compte and 'bareme' in gain:
            self.stock.ajouter(JournalFideliteModel,compte_id=compte.id,encaissement_id=enc.id,auteur_id=self.stock.user,type='ACQUISITION',delta_points=gain['points_acquis']-gain['dette_compensee'],delta_dette=-gain['dette_compensee'],details=gain)
        for row in payments:
            payment=self.stock.ajouter(ReglementModel,encaissement_id=enc.id,mode=row['mode'],montant=row['montant'],rendu=row['rendu'],confirmation_id=row['confirmation_id'])
            self.stock.ajouter(MouvementCaisseModel,session_id=session.id,reglement_id=payment.id,auteur_id=self.stock.user,mode=payment.mode,montant_net=payment.montant-payment.rendu)
        v.etat='ENCAISSEE';v.revision+=1;session.revision+=1
        self.vente.evenement(v,'ENCAISSEMENT',encaissement_id=enc.id,numero=numero,totaux=finance['totaux'],pdf_sha256=enc.pdf_sha256)
        self.trace('VENTE_ENCAISSEE',vente_id=v.id,encaissement_id=enc.id,session_id=session.id)
        self.s.flush();return self.recu(enc)

    def recu(self,enc):return serial(enc)
