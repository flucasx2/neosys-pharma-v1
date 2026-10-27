"""Contrat explicite de configuration documentaire, sans calcul financier parallèle."""
from datetime import date, datetime
import re


def structure(value, allowed, label, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or not set(required) <= set(value):
        raise ValueError(f"{label} : champs inconnus ou manquants.")


def texte(value, label, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} : texte obligatoire ou invalide.")
    return value.strip()


def configuration_validee(data):
    structure(data, {'regime', 'mode_verification', 'types_beneficiaires', 'champs', 'justificatifs'}, 'Configuration',
              {'regime', 'mode_verification', 'types_beneficiaires', 'champs', 'justificatifs'})
    regime = data['regime']
    if regime is not None:
        structure(regime, {'code', 'libelle'}, 'Régime', {'code', 'libelle'})
        regime = {'code': texte(regime['code'], 'Code régime', 80).upper(), 'libelle': texte(regime['libelle'], 'Régime')}
    mode = data['mode_verification']
    if mode not in ('LISTE', 'IDENTIFICATION', 'EXTERNE', 'MIXTE'):
        raise ValueError('Mode de vérification invalide.')
    types = data['types_beneficiaires']
    if not isinstance(types, list) or not types or any(t not in ('TITULAIRE', 'AYANT_DROIT', 'AUTRE') for t in types) or len(set(types)) != len(types):
        raise ValueError('Types de bénéficiaires explicites et uniques requis.')
    fields, documents = [], []
    for key in ('champs', 'justificatifs'):
        if not isinstance(data[key], list) or len(data[key]) > 100:
            raise ValueError(f'{key} : liste bornée requise.')
    for item in data['champs']:
        structure(item, {'code', 'libelle', 'type', 'obligatoire', 'format', 'finalite'}, 'Champ', {'code', 'libelle', 'type', 'obligatoire', 'format'})
        if item['type'] not in ('TEXTE', 'ENTIER', 'DATE') or type(item['obligatoire']) is not bool:
            raise ValueError('Type ou obligation du champ invalide.')
        if item['format'] not in (None, 'CHIFFRES', 'ALPHANUMERIQUE') or (item['format'] is not None and item['type'] != 'TEXTE'):
            raise ValueError('Format du champ non pris en charge.')
        fields.append(dict(item, code=texte(item['code'], 'Code champ', 80).upper(), libelle=texte(item['libelle'], 'Libellé champ')))
    for item in data['justificatifs']:
        structure(item, {'code', 'libelle', 'obligatoire', 'groupe_alternative', 'finalite'}, 'Justificatif', {'code', 'libelle', 'obligatoire', 'groupe_alternative'})
        if type(item['obligatoire']) is not bool:
            raise ValueError('Obligation documentaire explicite requise.')
        group = item['groupe_alternative']
        if group is not None:
            group = texte(group, 'Groupe alternatif', 80).upper()
            if not item['obligatoire']:
                raise ValueError('Un groupe alternatif appartient aux justificatifs obligatoires.')
        documents.append(dict(item, code=texte(item['code'], 'Code justificatif', 80).upper(), libelle=texte(item['libelle'], 'Libellé justificatif'), groupe_alternative=group))
    for item in fields + documents:
        if item.get('finalite', 'FINANCIERE') not in ('FINANCIERE', 'FACTURATION'):
            raise ValueError('Finalité documentaire inconnue.')
    for group in {d['groupe_alternative'] for d in documents if d['groupe_alternative']}:
        if len({d.get('finalite', 'FINANCIERE') for d in documents if d['groupe_alternative'] == group}) != 1:
            raise ValueError('Un groupe alternatif ne peut pas mélanger les finalités.')
    for items in (fields, documents):
        if any(not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]*', x['code']) for x in items):
            raise ValueError('Codes de champs et justificatifs : lettres, chiffres, tiret et soulignement uniquement.')
        if len({x['code'] for x in items}) != len(items):
            raise ValueError('Codes de champs ou justificatifs dupliqués.')
    return dict(regime=regime, mode_verification=mode, types_beneficiaires=types, champs=fields, justificatifs=documents)


def verifier_preuve(config, valeurs, documents, source, reference_source, *, phase='FINANCIERE'):
    if phase not in ('FINANCIERE', 'FACTURATION'):
        raise ValueError('Phase de contrôle inconnue.')
    if not isinstance(valeurs, dict) or set(valeurs) - {f['code'] for f in config['champs']}:
        raise ValueError('Champs de vérification inconnus.')
    for field in config['champs']:
        value = valeurs.get(field['code'])
        if value is None or value == '':
            if field['obligatoire'] and (phase == 'FACTURATION' or field.get('finalite', 'FINANCIERE') == 'FINANCIERE'):
                raise ValueError(f"Champ obligatoire manquant : {field['libelle']}.")
            continue
        if field['type'] == 'ENTIER':
            if type(value) is not int or value < 0:
                raise ValueError(f"Entier non négatif requis : {field['libelle']}.")
        elif field['type'] == 'DATE':
            if not isinstance(value, str):
                raise ValueError('Date ISO requise.')
            date.fromisoformat(value)
        else:
            texte(value, field['libelle'], 500)
            pattern = {'CHIFFRES': r'[0-9]+', 'ALPHANUMERIQUE': r'[A-Za-z0-9-]+'}.get(field['format'])
            if pattern and not re.fullmatch(pattern, value):
                raise ValueError(f"Format invalide : {field['libelle']}.")
    if not isinstance(documents, list) or len(documents) > 100:
        raise ValueError('Liste des justificatifs invalide.')
    definitions = {d['code']: d for d in config['justificatifs']}
    seen = set()
    for doc in documents:
        structure(doc, {'code', 'reference', 'verifie'}, 'Document fourni', {'code', 'reference', 'verifie'})
        if not isinstance(doc['code'], str) or doc['code'] not in definitions or doc['code'] in seen or doc['verifie'] is not True:
            raise ValueError('Justificatif inconnu, dupliqué ou non vérifié.')
        texte(doc['reference'], 'Référence documentaire', 200)
        seen.add(doc['code'])
    groups = {}
    for doc in config['justificatifs']:
        if not doc['obligatoire'] or (phase == 'FINANCIERE' and doc.get('finalite', 'FINANCIERE') == 'FACTURATION'):
            continue
        group = doc['groupe_alternative']
        if group:
            groups.setdefault(group, set()).add(doc['code'])
        elif doc['code'] not in seen:
            raise ValueError(f"Justificatif obligatoire manquant : {doc['libelle']}.")
    if any(not (codes & seen) for codes in groups.values()):
        raise ValueError('Un groupe de justificatifs alternatifs est incomplet.')
    modes = {'LISTE': {'LISTE'}, 'IDENTIFICATION': {'IDENTIFICATION'}, 'EXTERNE': {'EXTERNE'}, 'MIXTE': {'LISTE', 'EXTERNE'}}
    if source not in modes[config['mode_verification']]:
        raise ValueError('Source de vérification incompatible avec la convention.')
    texte(reference_source, 'Référence de vérification', 200)
