from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from neosys_pharma.application.equipement_service import EquipementService
from neosys_pharma.domain.organisation.equipements import Caisse, Coffre, PosteVente
from neosys_pharma.infrastructure.organisation_models import CaisseModel, CoffreModel, PosteVenteModel
from neosys_pharma.presentation.organisation_api import EmplacementInput, executer, repository

router = APIRouter(prefix="/api/organisation", tags=["Équipements P1"])


def lister_emplacement(repo, model, emplacement_id):
    if repo.emplacement(emplacement_id) is None:
        raise HTTPException(404, "Emplacement introuvable.")
    return repo.lister(model, emplacement_id=emplacement_id)


@router.get("/emplacements/{emplacement_id}/postes-vente")
def postes(emplacement_id: UUID, repo=Depends(repository)):
    return lister_emplacement(repo, PosteVenteModel, emplacement_id)


@router.post("/emplacements/{emplacement_id}/postes-vente", status_code=201)
def creer_poste(emplacement_id: UUID, data: EmplacementInput, repo=Depends(repository)):
    return executer(lambda: EquipementService(repo).creer(PosteVente(emplacement_id=emplacement_id, **data.model_dump())))


@router.get("/emplacements/{emplacement_id}/caisses")
def caisses(emplacement_id: UUID, repo=Depends(repository)):
    return lister_emplacement(repo, CaisseModel, emplacement_id)


@router.post("/emplacements/{emplacement_id}/caisses", status_code=201)
def creer_caisse(emplacement_id: UUID, data: EmplacementInput, repo=Depends(repository)):
    return executer(lambda: EquipementService(repo).creer(Caisse(emplacement_id=emplacement_id, **data.model_dump())))


@router.get("/sites/{site_id}/coffres")
def coffres(site_id: UUID, repo=Depends(repository)):
    if repo.site(site_id) is None:
        raise HTTPException(404, "Site introuvable.")
    return repo.lister(CoffreModel, site_id=site_id)


@router.post("/sites/{site_id}/coffres", status_code=201)
def creer_coffre(site_id: UUID, data: EmplacementInput, repo=Depends(repository)):
    return executer(lambda: EquipementService(repo).creer(Coffre(site_id=site_id, **data.model_dump())))
