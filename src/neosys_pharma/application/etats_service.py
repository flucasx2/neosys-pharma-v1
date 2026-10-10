"""États en lecture seule, une extraction bornée et un même périmètre écran/export."""
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, or_, and_, func
from neosys_pharma.domain.etats import CoutsIndisponibles, valoriser, synthese
from neosys_pharma.infrastructure.stock_models import StockEmplacementModel as B, LotModel as L, MouvementStockModel as M, LigneInventaireModel as I, ZoneInventaireModel as Z, InventaireModel, MotifEcartInventaireModel
from neosys_pharma.infrastructure.catalogue_models import ProduitModel as P, ConditionnementModel as C, ReferenceProduitModel as R, CategorieProduitModel as K
from neosys_pharma.infrastructure.organisation_models import OrganisationModel, SiteModel, EmplacementModel as E
from neosys_pharma.infrastructure.securite_models import UtilisateurModel as U

MAX_LIGNES=20_000
TITRES={'stocks':'État des stocks','valorisation':'Valorisation des stocks','mouvements':'Journal des mouvements','peremptions':'Lots proches de la péremption ou périmés','inventaire':'Procès-verbal d’inventaire','ecarts':'Écarts d’inventaire','comptabilite':'Mouvements et écarts — préparation comptable'}
BASE=[('produit','Produit'),('conditionnement','Conditionnement'),('emplacement','Emplacement'),('lot','Lot'),('peremption','Péremption')]
FINANCE=[('cout_unitaire','Coût unitaire'),('montant','Montant'),('devise','Devise'),('valorisation','Valorisation'),('motif_valorisation','Motif'),('methode','Méthode'),('provenance_cout','Provenance coût')]
TECH=[('id','Référence ligne'),('produit_id','UUID produit'),('conditionnement_id','UUID conditionnement'),('lot_id','UUID lot'),('emplacement_id','UUID emplacement'),('stock_id','UUID stock')]

class EtatsService:
    def __init__(self, stock, site, couts=None):
        self.stock=stock; self.site=site; self.couts=couts or CoutsIndisponibles()

    def lire(self, genre, allowed, *, emplacement_id=None, produit_id=None, conditionnement_id=None, lot_id=None, inventaire_id=None, q='', debut=None, fin=None, reference=None, horizon=90):
        s=self.stock
        if genre not in TITRES: raise ValueError('État inconnu.')
        inventaire=genre in ('inventaire','ecarts')
        permission='stock.inventaire.valider' if inventaire else 'stock.consulter'
        s.access(permission,self.site)
        if debut and fin and debut>fin: raise ValueError('La date de début doit précéder la date de fin.')
        if (debut or fin) and genre not in ('mouvements','comptabilite'):raise ValueError('La période est réservée au journal des mouvements. Les soldes sont actuels.')
        if reference and genre!='peremptions':raise ValueError('La date de référence est réservée aux péremptions.')
        if emplacement_id:
            s.emplacement(emplacement_id,permission);allowed=[emplacement_id]
        # Même si un site est autorisé, aucune ligne sans AffectationEmplacement.
        if not allowed: raise PermissionError('Affectation à un emplacement requise pour cet état.')
        inv=None
        if inventaire:
            if not inventaire_id: raise ValueError('Choisir un inventaire.')
            inv=s.inventaire_scope(inventaire_id,permission)
            if inv.site_id!=self.site: raise PermissionError('Inventaire hors du site courant.')
            # Un PV conserve toutes ses zones : pas de PV officiel partiellement filtré.
            if genre=='inventaire' and any((emplacement_id,produit_id,conditionnement_id,lot_id,q,debut,fin)):
                raise ValueError('Le procès-verbal doit contenir toutes les lignes de l’inventaire. Utiliser l’état des écarts pour filtrer.')
        query=select(B,L,C,P,E).join(L,L.id==B.lot_id).join(C,C.id_conditionnement==L.conditionnement_id).join(P,P.id_produit==C.produit_id).join(E,E.id_emplacement==B.emplacement_id)
        query=query.where(B.organisation_id==s.org,B.site_id==self.site,B.emplacement_id.in_(allowed))
        if produit_id:query=query.where(P.id_produit==produit_id)
        if conditionnement_id:query=query.where(C.id_conditionnement==conditionnement_id)
        if lot_id:query=query.where(L.id==lot_id)
        if q:
            refs=select(R.id_reference).where(R.organisation_id==s.org,R.conditionnement_id==C.id_conditionnement,s.repo.upper(R.valeur).contains(s.repo.terme(q),autoescape=True)).exists()
            query=query.where(or_(s.repo.upper(P.nom).contains(s.repo.terme(q),autoescape=True),s.repo.upper(L.numero).contains(s.repo.terme(q),autoescape=True),refs))
        movement=genre in ('mouvements','comptabilite')
        if movement:
            query=query.add_columns(M,U.nom).join(M,M.stock_id==B.id).join(U,U.id_utilisateur==M.auteur_id).where(M.organisation_id==s.org)
            if debut:query=query.where(M.date>=datetime.combine(debut,time.min,timezone.utc))
            if fin:query=query.where(M.date<datetime.combine(fin+timedelta(days=1),time.min,timezone.utc))
            if genre=='comptabilite':query=query.where(M.delta_physique!=0)
            query=query.order_by(M.sequence,M.id)
        elif inventaire:
            query=query.add_columns(I,Z.nom,MotifEcartInventaireModel.nom).join(I,I.stock_id==B.id).join(Z,Z.id==I.zone_id).outerjoin(MotifEcartInventaireModel,MotifEcartInventaireModel.id==I.motif_id).where(Z.inventaire_id==inv.id,I.organisation_id==s.org).order_by(Z.nom,P.nom,I.id)
        else:
            query=query.order_by(P.nom,C.libelle,E.nom,B.id)
            if genre=='peremptions':
                reference=reference or s.jour
                # Les dates absentes sont explicitement signalées, jamais devinées.
                query=query.join(K,K.id_categorie==P.categorie_id).where(B.physique>0,or_(and_(L.peremption.is_(None),func.coalesce(P.gestion_peremption,K.gestion_peremption).is_(True)),L.peremption<=reference+timedelta(days=horizon)))
        data=s.s.execute(query.limit(MAX_LIGNES+1)).all()
        if len(data)>MAX_LIGNES:raise ValueError('Plus de 20 000 lignes : préciser les filtres. Aucun export partiel n’est généré.')
        rows=[]
        for values in data:
            b,l,c,p,e=values[:5]
            row=dict(id=str(b.id),stock_id=str(b.id),produit_id=str(p.id_produit),conditionnement_id=str(c.id_conditionnement),lot_id=str(l.id),emplacement_id=str(e.id_emplacement),produit=p.nom,conditionnement=c.libelle,emplacement=e.nom,lot=l.numero,peremption=l.peremption.isoformat() if l.peremption else None,physique=b.physique,reserve=b.reserve,vendable=b.physique-b.reserve)
            quantity=b.physique;at=None
            if movement:
                m,auteur=values[5:];quantity=m.delta_physique;at=m.date
                row.update(id=str(m.id),date=m.date.isoformat(),type=m.type,sequence=m.sequence,delta_physique=m.delta_physique,delta_reserve=m.delta_reserve,physique_apres=m.physique_apres,reserve_apres=m.reserve_apres,origine=m.origine,justification=m.justification,auteur=auteur,auteur_id=str(m.auteur_id),operation_id=str(m.operation_id),statut_comptable='À QUALIFIER — AUCUNE ÉCRITURE')
            elif inventaire:
                line,zone,motif=values[5:];delta=line.ecart if inv.statut=='VALIDE' else s.ecart(line,inv) if line.compte is not None else None
                quantity=delta;row.update(id=str(line.id),zone=zone,theorique=line.theorique,compte=line.compte,ecart=delta,theorique_au_comptage=line.compte-delta if delta is not None else None,motif=motif,justification=line.justification,comptage_sequence=line.comptage_sequence)
            elif genre=='peremptions':
                row['etat_peremption']='DATE ABSENTE' if not l.peremption else 'PÉRIMÉ' if l.peremption<reference else 'PROCHE';row['jours_restants']=(l.peremption-reference).days if l.peremption else None
            row.update(valoriser(self.couts,s.org,b.id,quantity,at));rows.append(row)
        columns=BASE.copy()
        if movement:columns=[('date','Date UTC'),('type','Type')]+columns+[('delta_physique','Physique Δ'),('delta_reserve','Réservé Δ'),('physique_apres','Physique après'),('reserve_apres','Réservé après'),('origine','Origine'),('auteur','Auteur'),('justification','Justification')]
        elif inventaire:columns=[('zone','Zone')]+columns+[('theorique','Photographie'),('theorique_au_comptage','Théorique au comptage'),('compte','Compté'),('ecart','Écart'),('motif','Motif'),('justification','Justification')]
        else:columns += [('physique','Physique'),('reserve','Réservé'),('vendable','Vendable')]
        if genre=='peremptions':columns += [('etat_peremption','État'),('jours_restants','Jours restants')]
        if genre in ('valorisation','ecarts','comptabilite'):columns += FINANCE
        if genre=='comptabilite':columns += [('statut_comptable','Statut comptable'),('operation_id','Référence opération'),('sequence','Séquence')]
        org=s.s.get(OrganisationModel,s.org);site=s.s.get(SiteModel,self.site)
        responsable=None
        if inv and inv.valide_par:
            responsable=s.s.scalar(select(U.nom).where(U.id_utilisateur==inv.valide_par,U.organisation_id==s.org))
        summary=synthese(rows)
        numeric=['delta_physique','delta_reserve'] if movement else ['theorique','compte','ecart'] if inventaire else ['physique','reserve','vendable']
        summary['totaux_quantites']={k:sum(r[k] for r in rows if r.get(k) is not None) for k in numeric}
        summary['lignes_non_comptees']=sum(r.get('compte') is None for r in rows) if inventaire else 0
        notes=['Quantités exprimées en unités de conditionnement, sans conversion. Les totaux de conditionnements différents ne sont pas des unités homogènes.','Coûts d’acquisition historiques indisponibles : aucun prix fournisseur conseillé ou prix de vente utilisé. Aucune écriture comptable générée.']
        if genre in ('stocks','valorisation','peremptions'):notes.append('Soldes actuels extraits à la génération ; aucune reconstitution historique à une date passée.')
        if inventaire:notes.append('Écart = compté − (photographie + mouvements jusqu’au comptage). Les mouvements postérieurs au comptage restent conservés.')
        return dict(responsable_validation=responsable,reference=str(uuid4()),titre=TITRES[genre],genre=genre,organisation_id=str(s.org),organisation=org.nom_commercial,site_id=str(self.site),site=site.code+' — '+site.nom,genere_le=datetime.now(timezone.utc).isoformat(),filtres={k:str(v) for k,v in dict(emplacement_id=emplacement_id,produit_id=produit_id,conditionnement_id=conditionnement_id,lot_id=lot_id,q=q,debut=debut if movement else None,fin=fin if movement else None,reference=reference if genre=='peremptions' else None,horizon=horizon if genre=='peremptions' else None).items() if v not in (None,'')},inventaire=dict(id=str(inv.id),nom=inv.nom,type=inv.type,statut=inv.statut,date=inv.date.isoformat(),snapshot_sequence=inv.snapshot_sequence,valide_par=str(inv.valide_par) if inv.valide_par else None,valide_le=inv.valide_le.isoformat() if inv.valide_le else None) if inv else None,columns=[dict(key=k,label=v) for k,v in columns+TECH],items=rows,total=len(rows),synthese=summary,notes=notes)
