"""Complétude administrative P5-FAC-02 ; aucun calcul de parts ni de créances."""
from neosys_pharma.domain.configuration_convention import structure, verifier_preuve
ETATS_DOSSIER = ('A_COMPLETER','A_CONTROLER','VALIDE_POUR_FACTURATION','EN_ANOMALIE','FACTURE')
ENGAGEMENTS = ('PRESENTER','GENERER_FACTURE','VALIDER_FACTURE','EMETTRE_FACTURE')


def controle_administratif(exigences, complements):
    if not isinstance(complements, dict) or set(complements) - {x['id'] for x in exigences}:
        raise ValueError('Configuration administrative inconnue.')
    if not exigences:
        return ['EXIGENCES_DOCUMENTAIRES_NON_DEFINIES']
    anomalies = []
    for item in exigences:
        payload = complements.get(item['id'], {})
        structure(payload, {'valeurs','documents'}, 'Complément administratif')
        valeurs, ajouts = payload.get('valeurs', {}), payload.get('documents', [])
        if not isinstance(valeurs, dict) or not isinstance(ajouts, list) or len(ajouts) > 100:
            raise ValueError('Valeurs ou liste documentaire invalides.')
        for field in item['definition']['champs']:
            code = field['code']
            if field.get('finalite','FINANCIERE') == 'FINANCIERE' and code in valeurs and valeurs[code] != item['valeurs'].get(code):
                raise ValueError('Une preuve financière figée ne se corrige pas par un complément administratif.')
        documents = {d['code']:d for d in item['documents']}
        seen = set()
        for doc in ajouts:
            structure(doc, {'code','reference','verifie'}, 'Document', {'code','reference','verifie'})
            code = doc['code']
            if not isinstance(code,str) or code in seen or type(doc['verifie']) is not bool:
                raise ValueError('Justificatif dupliqué ou invalide.')
            seen.add(code)
            definition = next((d for d in item['definition']['justificatifs'] if d['code'] == code),None)
            if not definition:
                raise ValueError('Justificatif inconnu.')
            if definition.get('finalite','FINANCIERE') == 'FINANCIERE' and documents.get(code) != doc:
                raise ValueError('Justificatif financier figé : correction administrative interdite.')
            documents[code] = doc
        try:
            verifier_preuve(item['definition'], dict(item['valeurs']) | valeurs, list(documents.values()),
                item['source'], item['reference'], phase='FACTURATION')
        except (ValueError,TypeError) as exc:
            anomalies.append(f"{item['id']} : {exc}")
    return anomalies
