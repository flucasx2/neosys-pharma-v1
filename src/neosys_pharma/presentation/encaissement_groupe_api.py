"""Contrats P4.6/3.3. Le parcours reste fermé jusqu’à validation fonctionnelle."""
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from neosys_pharma.application.encaissement_groupe_service import EncaissementGroupeService
from neosys_pharma.presentation.vente_api import POLICY, contexte
from neosys_pharma.presentation.caisse_api import service as cash_service
from neosys_pharma.presentation.stock_api import execute


# Activation volontairement impossible par configuration utilisateur dans cette étape.
GROUPED_ENCASHMENT_ENABLED = False

POLICY.update({
    'groupe_previsualiser': 'caisse.encaisser',
    'groupe_creer': 'caisse.encaisser',
    'groupe_lire': 'caisse.encaisser',
    'groupe_selection': 'caisse.encaisser',
    'groupe_confirmer': 'caisse.encaisser',
    'groupe_rapprocher': 'caisse.encaisser',
    'groupe_finaliser': 'caisse.encaisser',
    'groupe_annuler': 'caisse.encaisser',
})

router = APIRouter(prefix='/api/caisses/organisations/{organisation_id}',
                   tags=['Encaissement groupé — étape 3.3'], dependencies=[Depends(contexte)])


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Selection(Input):
    vente_id: UUID
    revision: int = Field(strict=True, ge=1)
    # Beneficiary is bound to this sale, never inferred from another sale.
    compte_id: UUID | None = None
    revision_compte: int | None = Field(default=None, strict=True, ge=1)


class Preview(Input):
    session_id: UUID
    revision_session: int = Field(strict=True, ge=1)
    ventes: list[Selection] = Field(min_length=2, max_length=20)
    compte_id: UUID | None = None
    revision_compte: int | None = Field(default=None, strict=True, ge=1)
    identite_commune_confirmee: bool = False


class Create(Preview):
    cle: UUID


class Mutation(Input):
    cle: UUID


class ChangeSelection(Mutation):
    revision: int = Field(strict=True, ge=1)
    revision_session: int = Field(strict=True, ge=1)
    revision_compte: int | None = Field(default=None, strict=True, ge=1)
    ventes: list[Selection] = Field(min_length=2, max_length=20)
    identite_commune_confirmee: bool = False


class Confirmation(Mutation):
    revision: int = Field(strict=True, ge=1)
    revision_session: int = Field(strict=True, ge=1)
    session_id: UUID
    mode: Literal['CARTE', 'MOBILE_MONEY', 'CHEQUE', 'VIREMENT']
    montant: Decimal = Field(gt=0, max_digits=18, decimal_places=0)
    reference: str = Field(min_length=1, max_length=200)
    source: Literal['MANUEL_TERMINAL', 'MANUEL_JUSTIFICATIF', 'TECHNIQUE_PRESTATAIRE']
    preuve: str = Field(min_length=1, max_length=2000)


class Reconciliation(Mutation):
    revision: int = Field(strict=True, ge=1)
    revision_session: int = Field(strict=True, ge=1)
    session_id: UUID
    justification: str = Field(min_length=1, max_length=2000)


class Payment(Input):
    mode: Literal['ESPECES', 'CARTE', 'MOBILE_MONEY', 'CHEQUE', 'VIREMENT']
    montant: Decimal = Field(gt=0, max_digits=18, decimal_places=0)
    confirmation_id: UUID | None = None


class Finalisation(Mutation):
    revision: int = Field(strict=True, ge=1)
    empreinte: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    revision_session: int = Field(strict=True, ge=1)
    session_id: UUID
    ventes: list[Selection] = Field(min_length=2, max_length=20)
    reglements: list[Payment] = Field(max_length=40)
    compte_id: UUID | None = None
    revision_compte: int | None = Field(default=None, strict=True, ge=1)


class Cancellation(Mutation):
    revision: int = Field(strict=True, ge=1)
    justification: str = Field(min_length=1, max_length=2000)


def service(c=Depends(cash_service)):
    return EncaissementGroupeService(c)


def _enabled():
    if not GROUPED_ENCASHMENT_ENABLED:
        raise HTTPException(404, 'Encaissement groupé non activé pour les utilisateurs.')


def _authorize_selection(s, session_id, selections):
    """Contrôle les deux droits avant un éventuel rejeu idempotent."""
    session = execute(lambda: s.cash.session(session_id, 'caisse.encaisser'))
    execute(lambda: s.stock.access('caisse.encaisser.groupe', s.site, session.emplacement_id))
    for item in selections:
        sale = execute(lambda item=item: s.cash.vente.obtenir(item.vente_id, 'caisse.encaisser'))
        execute(lambda sale=sale: s.stock.access('caisse.encaisser.groupe', s.site, sale.emplacement_id))
        if sale.site_id != s.site or sale.emplacement_id != session.emplacement_id or sale.caisse_id != session.caisse_id:
            raise HTTPException(403, 'Vente hors du périmètre de la session.')


def _authorize_dossier(s, key):
    entity = execute(lambda: s.autoriser_dossier(key))
    session = execute(lambda: s.cash.session(entity.session_id, 'caisse.encaisser'))
    execute(lambda: s.stock.access('caisse.encaisser.groupe', s.site, session.emplacement_id))
    for item in entity.selections:
        sale = execute(lambda item=item: s.cash.vente.obtenir(item.vente_id, 'caisse.encaisser'))
        execute(lambda sale=sale: s.stock.access('caisse.encaisser.groupe', s.site, sale.emplacement_id))
    return entity


def _mutate(s, body, kind, action):
    payload = body.model_dump(mode='json', exclude={'cle'})
    return execute(lambda: s.stock.operation(body.cle, 'P4.6.3.3:' + kind, payload, action))


@router.post('/encaissements-groupes/previsualiser', name='groupe_previsualiser')
def groupe_previsualiser(d: Preview, s=Depends(service)):
    _enabled()
    _authorize_selection(s, d.session_id, d.ventes)
    return execute(lambda: s.previsualiser(d.session_id, d.revision_session,
        [x.model_dump() for x in d.ventes], d.compte_id, d.revision_compte, d.identite_commune_confirmee))


@router.post('/encaissements-groupes', status_code=201, name='groupe_creer')
def groupe_creer(d: Create, s=Depends(service)):
    _enabled()
    _authorize_selection(s, d.session_id, d.ventes)
    return _mutate(s, d, 'CREER', lambda: s.creer(d.model_dump(exclude={'cle'})))


@router.get('/encaissements-groupes/{key}', name='groupe_lire')
def groupe_lire(key: UUID, s=Depends(service)):
    _enabled()
    _authorize_dossier(s, key)
    return execute(lambda: s.dossier(key))


@router.put('/encaissements-groupes/{key}/selection', name='groupe_selection')
def groupe_selection(key: UUID, d: ChangeSelection, s=Depends(service)):
    _enabled()
    _authorize_dossier(s, key)
    entity = execute(lambda: s._dossier(key)[0])
    _authorize_selection(s, entity.session_id, d.ventes)
    return _mutate(s, d, 'SELECTION:' + str(key), lambda: s.modifier_selection(key, d.model_dump(exclude={'cle'})))


@router.post('/encaissements-groupes/{key}/confirmations', status_code=201, name='groupe_confirmer')
def groupe_confirmer(key: UUID, d: Confirmation, s=Depends(service)):
    _enabled()
    _authorize_dossier(s, key)
    return _mutate(s, d, 'CONFIRMER:' + str(key), lambda: s.confirmer(key, d.model_dump(exclude={'cle'})))


@router.post('/encaissements-groupes/{key}/confirmations/{confirmation_id}/rapprocher', name='groupe_rapprocher')
def groupe_rapprocher(key: UUID, confirmation_id: UUID, d: Reconciliation, s=Depends(service)):
    _enabled()
    _authorize_dossier(s, key)
    return _mutate(s, d, 'RAPPROCHER:' + str(confirmation_id), lambda: s.rapprocher(key, confirmation_id, d.model_dump(exclude={'cle'})))


@router.post('/encaissements-groupes/{key}/finaliser', name='groupe_finaliser')
def groupe_finaliser(key: UUID, d: Finalisation, s=Depends(service)):
    _enabled()
    entity = _authorize_dossier(s, key)
    _authorize_selection(s, entity.session_id, d.ventes)
    return _mutate(s, d, 'FINALISER:' + str(key), lambda: s.finaliser(key, d.model_dump(exclude={'cle'})))


@router.post('/encaissements-groupes/{key}/annuler', name='groupe_annuler')
def groupe_annuler(key: UUID, d: Cancellation, s=Depends(service)):
    _enabled()
    _authorize_dossier(s, key)
    return _mutate(s, d, 'ANNULER:' + str(key), lambda: s.annuler(key, d.model_dump(exclude={'cle'})))
