"""Clauses contractuelles synthétiques pour les tests P5 uniquement."""
def conditions_v1(organismes, *, ecart="CLIENT"):
    return {"schema_version": 2, "coordination": {
        "ordres": [{"beneficiaires_ids": [], "organismes_ids": [str(x) for x in organismes]}],
        "traitements_solde": {"DROITS": "CLIENT", "REFUS": "CLIENT", "EXCLUSION": "CLIENT",
                              "PLAFOND": ecart, "ECART": ecart}}}
