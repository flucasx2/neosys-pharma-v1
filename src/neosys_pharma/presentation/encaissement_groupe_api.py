"""API P4-C.3a des brouillons et allocations; aucune route de finalisation ici."""
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from neosys_pharma.application.caisse_service import CaisseService
from neosys_pharma.application.encaissement_groupe_service import EncaissementGroupeService
from neosys_pharma.presentation.vente_api import POLICY, contexte, service as vente_service, Input, Mutation, Revision
from neosys_pharma.presentation.stock_api import execute


# L'interface de finalisation reste volontairement indisponible dans P4-C.3a.
GROUPED_ENCASHMENT_ENABLED = False

POLICY.update({
    "groupe_creer": "caisse.encaisser",
    "groupe_lire": "caisse.consulter",
    "groupe_ventes_remplacer": "caisse.encaisser",
    "groupe_reglements_remplacer": "caisse.encaisser",
    "groupe_allocations_proposer": "caisse.encaisser",
    "groupe_allocations_definir": "caisse.encaisser",
    "groupe_abandonner": "caisse.encaisser",
})

router = APIRouter(
    prefix="/api/caisses/organisations/{organisation_id}/groupes",
    tags=["Encaissement groupé — brouillons"],
    dependencies=[Depends(contexte)],
)


def service(base=Depends(vente_service)):
    return EncaissementGroupeService(CaisseService(base))


def mutate(s, data, kind, action):
    body = data.model_dump(mode="json", exclude={"cle"})
    return execute(lambda: s.stock.operation(data.cle, "P4C:BROUILLON:" + kind, body, action))


class CreationGroupe(Mutation):
    session_id: UUID


class VenteSelection(Input):
    vente_id: UUID
    revision: int = Field(strict=True, ge=1)


class VentesGroupe(Revision):
    ventes: list[VenteSelection] = Field(max_length=50)
    reinitialiser_allocations: bool = False


class ReglementGroupe(Input):
    mode: str = Field(min_length=1, max_length=30)
    montant: Decimal = Field(gt=0, max_digits=18, decimal_places=0)
    rendu: Decimal = Field(default=Decimal(0), ge=0, max_digits=18, decimal_places=0)
    confirmation_id: UUID | None = None


class ReglementsGroupe(Revision):
    reglements: list[ReglementGroupe] = Field(max_length=20)
    reinitialiser_allocations: bool = False


class AllocationGroupe(Input):
    reglement_id: UUID
    vente_id: UUID
    montant: Decimal = Field(gt=0, max_digits=18, decimal_places=0)


class AllocationsGroupe(Revision):
    allocations: list[AllocationGroupe] = Field(max_length=100)


@router.post("", status_code=201, name="groupe_creer")
def groupe_creer(data: CreationGroupe, s=Depends(service)):
    return mutate(s, data, "CREER", lambda: s.creer(data.session_id))


@router.get("/{dossier_id}", name="groupe_lire")
def groupe_lire(dossier_id: UUID, s=Depends(service)):
    return execute(lambda: s.obtenir(dossier_id))


@router.put("/{dossier_id}/ventes", name="groupe_ventes_remplacer")
def groupe_ventes_remplacer(dossier_id: UUID, data: VentesGroupe, s=Depends(service)):
    return mutate(s, data, "VENTES:" + str(dossier_id), lambda: s.remplacer_ventes(
        dossier_id, data.revision,
        [row.model_dump() for row in data.ventes],
        reinitialiser_allocations=data.reinitialiser_allocations,
    ))


@router.put("/{dossier_id}/reglements", name="groupe_reglements_remplacer")
def groupe_reglements_remplacer(dossier_id: UUID, data: ReglementsGroupe, s=Depends(service)):
    return mutate(s, data, "REGLEMENTS:" + str(dossier_id), lambda: s.remplacer_reglements(
        dossier_id, data.revision,
        [row.model_dump() for row in data.reglements],
        reinitialiser_allocations=data.reinitialiser_allocations,
    ))


@router.get("/{dossier_id}/allocations/proposition", name="groupe_allocations_proposer")
def groupe_allocations_proposer(dossier_id: UUID, revision: int, s=Depends(service)):
    return execute(lambda: s.proposer_allocations(dossier_id, revision))


@router.put("/{dossier_id}/allocations", name="groupe_allocations_definir")
def groupe_allocations_definir(dossier_id: UUID, data: AllocationsGroupe, s=Depends(service)):
    return mutate(s, data, "ALLOCATIONS:" + str(dossier_id), lambda: s.definir_allocations(
        dossier_id, data.revision, [row.model_dump() for row in data.allocations]
    ))


@router.post("/{dossier_id}/abandonner", name="groupe_abandonner")
def groupe_abandonner(dossier_id: UUID, data: Revision, s=Depends(service)):
    return mutate(s, data, "ABANDONNER:" + str(dossier_id), lambda: s.abandonner(
        dossier_id, data.revision
    ))
