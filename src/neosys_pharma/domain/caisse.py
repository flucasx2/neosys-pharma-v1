"""Montants XAF entiers, paiements acquis et acquisition sans taux implicite."""
from decimal import Decimal,ROUND_FLOOR
MODES=('ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')

def francs(value,zero=False):
    d=Decimal(str(value))
    if not d.is_finite() or d!=d.to_integral_value() or d<0 or (not zero and d==0):raise ValueError('Montant en francs CFA entiers requis.')
    if d>Decimal('999999999999999999'):raise ValueError('Montant trop élevé.')
    return d

def repartir_paiements(total,rows):
    total=francs(total,True)
    if not rows and total:raise ValueError('Règlements confirmés obligatoires.')
    cash=sum((francs(x['montant']) for x in rows if x['mode']=='ESPECES'),Decimal(0))
    noncash=sum((francs(x['montant']) for x in rows if x['mode']!='ESPECES'),Decimal(0))
    if noncash>total:raise ValueError('Surpaiement non espèces interdit.')
    if noncash+cash<total:raise ValueError('Le montant net doit être intégralement réglé.')
    rendu=noncash+cash-total
    result=[]
    for row in rows:
        if row['mode'] not in MODES:raise ValueError('Moyen de paiement inconnu.')
        change=min(rendu,francs(row['montant'])) if row['mode']=='ESPECES' else Decimal(0)
        rendu-=change;result.append({**row,'rendu':change})
    return result

def acquisition(montant,points,base):
    return int((francs(montant,True)*points/francs(base)).to_integral_value(rounding=ROUND_FLOOR))

def regularisation(points_utilises,points_acquis,retour_eligible,total_eligible,solde):
    """Calcul P4.5 préparatoire pur ; aucun retour ou remboursement exécuté."""
    r=francs(retour_eligible,True);t=francs(total_eligible)
    if r>t:raise ValueError('Retour supérieur à la base originale.')
    restitution=int((Decimal(points_utilises)*r/t).to_integral_value(rounding=ROUND_FLOOR))
    revocation=int((Decimal(points_acquis)*r/t).to_integral_value(rounding=ROUND_FLOOR))
    disponible=solde+restitution
    return {'restitution':restitution,'revocation':revocation,'solde':max(0,disponible-revocation),'dette':max(0,revocation-disponible)}

class RegleFiscaleFidelite:
    """Point d'extension explicite ; aucune règle fiscale gabonaise n'est validée."""
    code='GABON_FIDELITE_NON_VALIDEE'
    validee=False
    def verifier_utilisation(self):
        raise ValueError('Utilisation des points bloquée : règle fiscale gabonaise non validée.')
