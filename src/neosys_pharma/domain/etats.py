"""Contrat transversal de valorisation : aucun prix de vente ne vaut un coût."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

@dataclass(frozen=True)
class CoutHistorique:
    montant_unitaire: Decimal
    devise: str
    methode: str
    provenance: str
    def __post_init__(self):
        if not self.montant_unitaire.is_finite() or self.montant_unitaire < 0 or not all((self.devise,self.methode,self.provenance)):
            raise ValueError('Coût documenté, devise, méthode et provenance requis.')

class SourceCouts(Protocol):
    def obtenir(self, organisation_id: UUID, stock_id: UUID, date_operation: datetime | None) -> CoutHistorique | None: ...

class CoutsIndisponibles:
    def obtenir(self, organisation_id, stock_id, date_operation): return None

def valoriser(source, org, stock_id, quantite, date_operation=None):
    cout=source.obtenir(org,stock_id,date_operation)
    if cout is None or quantite is None:
        return dict(cout_unitaire=None,montant=None,devise=None,methode=None,provenance_cout=None,valorisation='NON VALORISABLE',motif_valorisation='Coût historique absent' if cout is None else 'Quantité non comptée')
    return dict(cout_unitaire=str(cout.montant_unitaire),montant=str(cout.montant_unitaire*quantite),devise=cout.devise,methode=cout.methode,provenance_cout=cout.provenance,valorisation='VALORISÉ',motif_valorisation=None)

def synthese(rows):
    inconnues=sum(r.get('montant') is None for r in rows)
    devises={r['devise'] for r in rows if r.get('montant') is not None}
    complet=bool(rows) and not inconnues and len(devises)==1
    # Un sous-total connu n'est jamais publié comme valorisation définitive.
    return dict(lignes_non_valorisables=inconnues,valorisation_complete=complet,
                total_valorisation=str(sum((Decimal(r['montant']) for r in rows),Decimal(0))) if complet else None,
                devise=next(iter(devises)) if complet else None)
