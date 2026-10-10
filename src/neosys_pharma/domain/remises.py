"""Remises TTC ; allocation au plus fort reste, départagée par UUID de ligne."""
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR

def franc(value):return Decimal(str(value)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)

def repartir(total,weights):
    total=franc(total);denominator=sum(weights.values(),Decimal(0))
    if not denominator:return {k:Decimal(0) for k in weights}
    exact={k:total*v/denominator for k,v in weights.items()}
    result={k:v.quantize(Decimal(1),rounding=ROUND_FLOOR) for k,v in exact.items()}
    remainder=int(total-sum(result.values()))
    for k in sorted(weights,key=lambda k:(-(exact[k]-result[k]),str(k)))[:remainder]:result[k]+=1
    return result

def montant_remise(kind,value,eligible):
    value=Decimal(str(value));eligible=Decimal(str(eligible))
    if not value.is_finite() or value<=0:raise ValueError('Remise positive et finie requise.')
    if kind=='POURCENTAGE':
        if value>100:raise ValueError('Remise supérieure à 100 %.')
        value=eligible*value/100
    elif kind!='MONTANT_XAF':raise ValueError('Type de remise inconnu.')
    if value>eligible:raise ValueError('Remise supérieure au montant TTC éligible.')
    return franc(value)

def calculer(lignes,demandes):
    weights={str(l.id):Decimal(l.montants['ttc']) for l in lignes}
    base=repartir(franc(sum(weights.values(),Decimal(0))),weights)
    individual={k:Decimal(0) for k in base};global_request=None
    for r in demandes:
        if r.statut!='AUTORISEE':continue
        if r.ligne_id:
            key=str(r.ligne_id)
            if key not in base:raise ValueError('Remise sur une ligne inactive.')
            if individual[key]:raise ValueError('Plusieurs remises individuelles actives sur une ligne.')
            individual[key]=montant_remise(r.type,r.valeur,base[key])
        else:
            if global_request:raise ValueError('Plusieurs remises globales actives.')
            global_request=r
    solde={k:base[k]-individual[k] for k in base}
    global_amount=montant_remise(global_request.type,global_request.valeur,sum(solde.values())) if global_request else Decimal(0)
    global_parts=repartir(global_amount,solde)
    result={}
    for l in lignes:
        key=str(l.id);ttc=solde[key]-global_parts[key];rate=Decimal(str(l.instantane_tarif['taux_tva']))
        ht=franc(ttc/(1+rate/100));tva=ttc-ht
        result[key]={k:str(v) for k,v in dict(ttc_initial=base[key],remise_ligne=individual[key],remise_globale=global_parts[key],ht=ht,tva=tva,ttc=ttc).items()}
    totals={k:str(sum((Decimal(x[k]) for x in result.values()),Decimal(0))) for k in ('ttc_initial','remise_ligne','remise_globale','ht','tva','ttc')}
    return {'lignes':result,'totaux':totals}
