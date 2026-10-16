"""API P4-C.3 des brouillons et de la finalisation groupée protégée par défaut."""
from decimal import Decimal
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
from sqlalchemy.engine import make_url

from neosys_pharma.application.caisse_service import CaisseService
from neosys_pharma.application.encaissement_groupe_service import EncaissementGroupeService
from neosys_pharma.presentation.vente_api import POLICY, contexte, service as vente_service, Input, Mutation, Revision
from neosys_pharma.presentation.stock_api import execute


# Activation réservée au job Chromium sur sa base PostgreSQL locale et jetable
# nommée neosys_browser. Hors CI, sans marqueur de recette ou sur un hôte distant,
# la finalisation est fermée.
def _grouped_encashment_enabled():
    if os.getenv("GROUPED_ENCASHMENT_ENABLED", "").lower() != "true":
        return False
    if os.getenv("CI", "").lower() != "true":
        return False
    if os.getenv("P4C4_CI_DISPOSABLE_DATABASE", "") != "1":
        return False
    try:
        url = make_url(os.getenv("DATABASE_URL", ""))
    except Exception:
        return False
    return url.database == "neosys_browser" and url.host in {"localhost", "127.0.0.1", "::1"}


GROUPED_ENCASHMENT_ENABLED = _grouped_encashment_enabled()

POLICY.update({
    "groupe_creer": "caisse.encaisser",
    "groupe_lire": "caisse.consulter",
    "groupe_ventes_remplacer": "caisse.encaisser",
    "groupe_reglements_remplacer": "caisse.encaisser",
    "groupe_allocations_proposer": "caisse.encaisser",
    "groupe_allocations_definir": "caisse.encaisser",
    "groupe_abandonner": "caisse.encaisser",
    "groupe_finaliser": "caisse.encaisser",
    "groupe_recu_pdf": "caisse.consulter",
    "groupe_activation": "caisse.consulter",
})

router = APIRouter(
    prefix="/api/caisses/organisations/{organisation_id}/groupes",
    tags=["Encaissement groupé — brouillons"],
    dependencies=[Depends(contexte)],
)


@router.get("/activation", name="groupe_activation")
def groupe_activation():
    """État du verrou UI; l'autorisation réelle reste vérifiée à la finalisation."""
    return {"finalisation_active": GROUPED_ENCASHMENT_ENABLED}


def service(request: Request, base=Depends(vente_service)):
    return EncaissementGroupeService(CaisseService(base), request.state.vente_controle)


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


class FideliteVenteGroupe(Input):
    vente_id: UUID
    compte_id: UUID
    revision_compte: int = Field(strict=True, ge=1)


class FinalisationGroupe(Revision):
    revision_session: int = Field(strict=True, ge=1)
    fidelite: list[FideliteVenteGroupe] = Field(default_factory=list, max_length=50)


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


@router.post("/{dossier_id}/finaliser", name="groupe_finaliser")
def groupe_finaliser(dossier_id: UUID, data: FinalisationGroupe, s=Depends(service)):
    if not GROUPED_ENCASHMENT_ENABLED:
        raise HTTPException(503, "La finalisation groupée reste désactivée jusqu'à la recette complète.")
    body = data.model_dump(mode="json", exclude={"cle"})
    return mutate(s, data, "FINALISER:" + str(dossier_id), lambda: s.finaliser(
        dossier_id, body, data.cle
    ))


@router.get("/{dossier_id}/recu.pdf", name="groupe_recu_pdf")
def groupe_recu_pdf(dossier_id: UUID, s=Depends(service)):
    pdf = execute(lambda: s.recu_collectif_pdf(dossier_id))
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="recu-groupe-{dossier_id}.pdf"'},
    )
