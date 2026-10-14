from dataclasses import replace, FrozenInstanceError
from decimal import Decimal
from uuid import uuid4
import pytest
from neosys_pharma.domain.encaissement_groupe import (
    DossierEncaissementGroupe, EtatDossierGroupe, SelectionGroupe,
    VentilationEncaissement, AllocationReglement, verifier_allocations,
)


def dossier():
    return DossierEncaissementGroupe(**{k:uuid4() for k in ('organisation_id','site_id','emplacement_id','caisse_id','session_id','auteur_id')},
        selections=tuple(SelectionGroupe(vente_id=uuid4(),revision_vente=1,ordre=i) for i in (1,2)), empreinte_selection='a'*64)


def matrix():
    org, enc, reg = uuid4(),uuid4(),uuid4()
    vals=[VentilationEncaissement(organisation_id=org,encaissement_id=enc,vente_id=uuid4(),revision_vente=1,
        montant_ht=Decimal(n),montant_tva=Decimal(0),net_ttc=Decimal(n),instantane={'lignes':[{'designation':'FICTIF'}]}) for n in (101,99)]
    allocations=[AllocationReglement(organisation_id=org,encaissement_id=enc,reglement_id=reg,
        ventilation_id=v.id,vente_id=v.vente_id,ligne_vente_id=uuid4(),montant_net=v.net_ttc) for v in vals]
    return vals,allocations,{reg:Decimal(200)},{(a.vente_id,a.ligne_vente_id):a.montant_net for a in allocations}


def test_selection_distincte_et_transition_sans_fausse_restitution():
    d=dossier();assert d.changer_selection(d.selections,'b'*64).revision==2
    with pytest.raises(ValueError):replace(d,selections=(d.selections[0],d.selections[0]))
    with pytest.raises(ValueError):replace(d,selections=d.selections[:1])
    paid=d.transition(EtatDossierGroupe.EN_REGLEMENT)
    with pytest.raises(ValueError):paid.changer_selection(d.selections,'b'*64)
    with pytest.raises(ValueError):paid.transition(EtatDossierGroupe.ANNULE)
    assert paid.transition(EtatDossierGroupe.ANNULE,paiements_acquis_resolus=True).etat==EtatDossierGroupe.ANNULE
    with pytest.raises(ValueError):d.transition(EtatDossierGroupe.ENCAISSE).transition(EtatDossierGroupe.BROUILLON)


def test_instantane_et_entites_immutables():
    vals,*_=matrix();v=vals[0]
    with pytest.raises(FrozenInstanceError):v.net_ttc=Decimal(0)
    with pytest.raises(TypeError):v.instantane['lignes'][0]['designation']='MODIFIE'
    with pytest.raises(ValueError):replace(v,montant_tva=Decimal(1))
    with pytest.raises(ValueError):replace(v,instantane={})


@pytest.mark.parametrize('value',[Decimal('-1'),Decimal('0.5'),Decimal('NaN'),Decimal('Infinity'),Decimal('1000000000000000000')])
def test_montants_financiers_invalides(value):
    vals,allocations,*_=matrix()
    with pytest.raises(ValueError):replace(allocations[0],montant_net=value)


def test_matrice_exacte_et_zero_net_sans_paiement_fictif():
    data=matrix();assert verifier_allocations(*data)
    v=replace(data[0][0],montant_ht=Decimal(0),net_ttc=Decimal(0))
    assert verifier_allocations([v],[],{}, {})


@pytest.mark.parametrize('change',['somme','organisation','encaissement','vente','ligne','doublon','paiement_inconnu'])
def test_allocations_refusees(change):
    vals,allocations,reglements,lignes=matrix();a=allocations[0]
    mutations={'somme':{'montant_net':Decimal(100)},'organisation':{'organisation_id':uuid4()},'encaissement':{'encaissement_id':uuid4()},
        'vente':{'vente_id':uuid4()},'ligne':{'ligne_vente_id':uuid4()},'paiement_inconnu':{'reglement_id':uuid4()}}
    allocations=[replace(a,**mutations.get(change,{})),allocations[1]]
    if change=='doublon':allocations.append(a)
    with pytest.raises(ValueError):verifier_allocations(vals,allocations,reglements,lignes)
