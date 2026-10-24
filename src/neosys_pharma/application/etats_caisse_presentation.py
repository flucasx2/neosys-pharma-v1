"""Projection de lecture C06 : écritures historiques, aucun solde recalculé."""
from decimal import Decimal
from datetime import datetime
from neosys_pharma.infrastructure.caisse_models import (
    MouvementCaisseModel, MouvementCaisseGroupeModel, ReglementModel,
    ReglementGroupeModel, ConfirmationReglementModel, EncaissementModel,
)
from neosys_pharma.infrastructure.regularisation_models import (
    MouvementFinancierModel, TransfertFondsModel, RetourVenteModel,
)


def detail_flux(service, sessions):
    """Périmètre identique à X/Z : sessions retenues, jamais tous les tickets du site.

    Un paiement est lu depuis son écriture nette (individuelle OU groupée).
    Les reçus individuels d'un groupe ne constituent pas de nouvelles écritures.
    Les contreparties coffre sont affichées séparément, jamais additionnées au net caisse.
    """
    stock=service.stock
    data={k:[] for k in ('encaissements','remboursements','fonds','transferts','acquis_restitues','autres','retours_information')}
    def rows(cls,**filters):
        return sorted(stock.lignes(cls,**filters),key=lambda r:(str(getattr(r,'date','')),str(r.id)))
    for session in sessions:
        for cls,payment_cls,source in ((MouvementCaisseModel,ReglementModel,'INDIVIDUEL'),(MouvementCaisseGroupeModel,ReglementGroupeModel,'GROUPE')):
            for movement in rows(cls,session_id=session.id):
                payment=stock.obtenir(payment_cls,movement.reglement_id)
                confirmation=stock.obtenir(ConfirmationReglementModel,payment.confirmation_id) if payment.confirmation_id else None
                data['encaissements'].append({'reference':str(movement.id),'reglement_id':str(payment.id),
                    'session_id':str(session.id),'source':source,'mode':movement.mode,
                    'moyen_id':str(confirmation.moyen_id) if confirmation and confirmation.moyen_id else None,
                    'libelle':confirmation.moyen_libelle if confirmation else movement.mode,
                    'date':movement.date.isoformat(),'brut_recu':str(payment.montant),
                    'rendu':str(payment.rendu),'net_regle':str(movement.montant_net)})
        # Un retour physique reste informatif : il n'est jamais déduit du solde.
        for receipt in rows(EncaissementModel,session_id=session.id):
            for returned in rows(RetourVenteModel,encaissement_id=receipt.id):
                data['retours_information'].append({'reference':str(returned.id),'session_origine_id':str(session.id),
                    'encaissement_id':str(receipt.id),'montant_client':str(returned.montant),'date':returned.date.isoformat()})
        movements=rows(MouvementFinancierModel,session_id=session.id)
        transfers=rows(TransfertFondsModel,session_id=session.id)
        for transfer in transfers:
            # Les deux jambes d'un transfert sont lisibles, y compris EN_TRANSIT.
            legs=rows(MouvementFinancierModel,origine=transfer.id)
            data['transferts'].append({'reference':str(transfer.id),'session_id':str(session.id),
                'coffre_id':str(transfer.coffre_id),'sens':transfer.sens,'etat':transfer.etat,
                'montant':str(transfer.montant),'ecritures':[{
                    'reference':str(m.id),'type':m.type,'cible':'CAISSE' if m.session_id else 'COFFRE',
                    'montant_signe':str(m.montant),'date':m.date.isoformat()} for m in legs]})
        for movement in movements:
            if movement.type.startswith('TRANSFERT_'):continue  # déjà présenté avec ses deux jambes
            category=('remboursements' if movement.type=='REMBOURSEMENT' else
                      'fonds' if movement.type in ('FONDS_ENTREE','FONDS_SORTIE') else
                      'acquis_restitues' if movement.type=='ACQUIS_RESTITUE' else 'autres')
            data[category].append({'reference':str(movement.id),'origine':str(movement.origine),
                'session_id':str(session.id),'type':movement.type,'mode':movement.mode,
                'montant_signe':str(movement.montant),'date':movement.date.isoformat(),
                'auteur_id':str(movement.auteur_id),'justification':movement.justification})
    def total(rows,key):return str(sum((Decimal(r[key]) for r in rows),Decimal(0)))
    data['totaux']={key:total(data['encaissements'],key) for key in ('brut_recu','rendu','net_regle')}
    # Agrégats de présentation uniquement ; les attendus et nets officiels restent ceux des services existants.
    data['totaux'].update(remboursements_executes=str(-Decimal(total(data['remboursements'],'montant_signe'))),
        fonds_entrees=total([r for r in data['fonds'] if r['type']=='FONDS_ENTREE'],'montant_signe'),
        fonds_sorties=str(-Decimal(total([r for r in data['fonds'] if r['type']=='FONDS_SORTIE'],'montant_signe'))))
    data['perimetre']='Sessions retenues par X/Z ; retours informatifs rattachés aux encaissements d’origine ; contreparties coffre exclues du net caisse.'
    return data


def sections_flux(data):
    """Tables documentaires, sans nouvelle règle financière."""
    totals=data['totaux']
    sections=[{'titre':'Encaissements - synthèse historique (FCFA)',
        'colonnes':['Brut reçu','Rendu monnaie','Règlements nets','Remboursements exécutés','Fonds entrants','Fonds sortants'],
        'lignes':[[totals[k] for k in ('brut_recu','rendu','net_regle','remboursements_executes','fonds_entrees','fonds_sorties')]]},
        {'titre':'Règlements historiques - une seule écriture par règlement',
         'colonnes':['Référence / session / origine','Moyen historique','Brut reçu','Rendu monnaie','Net réglé'],
         'lignes':[[r['reference']+' / '+r['session_id']+' / '+r['source'],(r['libelle'] or r['mode'])+' / '+r['mode'],r['brut_recu'],r['rendu'],r['net_regle']] for r in data['encaissements']]}]
    for key,title in (('remboursements','Remboursements exécutés - mouvements signés'),('fonds','Apports et retraits de fonds - mouvements signés'),('acquis_restitues','Acquis non finalisés - contre-écritures de restitution'),('autres','Autres écritures historiques')):
        sections.append({'titre':title,'colonnes':['Référence / origine','Session','Type / moyen','Montant signé FCFA'],
            'lignes':[[r['reference']+' / '+r['origine'],r['session_id'],r['type']+' / '+r['mode'],r['montant_signe']] for r in data[key]]})
    sections.append({'titre':'Transferts - état des dossiers (sans nouvel effet financier)',
        'colonnes':['Référence / session','Sens','État','Montant FCFA'],
        'lignes':[[r['reference']+' / '+r['session_id'],r['sens'],r['etat'],r['montant']] for r in data['transferts']]})
    sections.append({'titre':'Transferts - écritures caisse et coffre distinctes',
        'colonnes':['Référence / transfert','Cible','Écriture','Montant signé FCFA'],
        'lignes':[[m['reference']+' / '+r['reference'],m['cible'],m['type'],m['montant_signe']] for r in data['transferts'] for m in r['ecritures']]})
    sections.append({'titre':'Retours physiques par encaissement d’origine - information sans effet de caisse',
        'colonnes':['Retour / encaissement','Session d’origine','Date','Montant client FCFA'],
        'lignes':[[r['reference']+' / '+r['encaissement_id'],r['session_origine_id'],datetime.fromisoformat(r['date']).strftime('%d/%m/%Y %H:%M UTC'),r['montant_client']] for r in data['retours_information']]})
    # Les zéros restent dans la synthèse, sans multiplier les tables vides.
    return [{**section,'titre_solidaire':True} for section in sections if section['lignes']]
