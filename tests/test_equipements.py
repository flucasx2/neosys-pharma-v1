from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from neosys_pharma.domain.organisation.entities import Organisation, Site, Emplacement
from neosys_pharma.domain.organisation.equipements import PosteVente, Caisse, Coffre
from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.organisation_models import SiteModel, EmplacementModel, PosteVenteModel, CaisseModel, CoffreModel
from neosys_pharma.infrastructure.organisation_repository import SqlAlchemyOrganisationRepository
from test_p1_vertical import client, structure


def test_entites_independantes_domaine_et_persistance():
    engine = create_engine("sqlite+pysqlite://")
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as session:
        repo = SqlAlchemyOrganisationRepository(session)
        org = Organisation(nom_commercial="Neo", raison_sociale="Neo SARL")
        repo.ajouter(org)
        repo.enregistrer()
        assert repo.organisation(org.id_organisation) == org
        assert repo.lister(SiteModel) == []
        site = Site(organisation_id=org.id_organisation, code="lbv", nom="Libreville")
        repo.ajouter(site)
        repo.enregistrer()
        assert repo.site(site.id_site) == site
        assert repo.lister(EmplacementModel) == []
        emplacement = Emplacement(site_id=site.id_site, code="r", nom="Réserve")
        repo.ajouter(emplacement)
        repo.enregistrer()
        assert repo.emplacement(emplacement.id_emplacement) == emplacement
    engine.dispose()


@pytest.mark.parametrize("classe,parent", [(PosteVente,"emplacement_id"),(Caisse,"emplacement_id"),(Coffre,"site_id")])
def test_equipement_domaine(classe,parent):
    identifiant=uuid4()
    a=classe(**{parent:identifiant},code=" p01 ",nom=" Comptoir ")
    b=classe(**{parent:identifiant},code="p02",nom="Autre")
    assert a.code=="P01" and a.nom=="Comptoir" and a.actif
    assert a != b
    for data in ({parent:None,"code":"p","nom":"Poste"},{parent:identifiant,"code":" ","nom":"Poste"},{parent:identifiant,"code":"p","nom":" "}):
        with pytest.raises(ValueError):
            classe(**data)


@pytest.mark.parametrize("chemin,identifiant,parent", [("postes-vente","id_poste_vente","emplacement_id"),("caisses","id_caisse","emplacement_id"),("coffres","id_coffre","site_id")])
def test_equipements_vertical_contextes_et_doublons(client,chemin,identifiant,parent):
    org,site=structure(client)
    empl=client.get(f"/api/organisation/sites/{site}/emplacements").json()[0]["id_emplacement"]
    rattachement=site if parent=="site_id" else empl
    categorie="sites" if parent=="site_id" else "emplacements"
    path=f"/api/organisation/{categorie}/{rattachement}/{chemin}"
    assert client.get(path).json()==[]
    response=client.post(path,json={"code":"e01","nom":"Équipement"})
    assert response.status_code==201,response.text
    assert response.json()[parent]==rattachement and response.json()[identifiant]
    assert client.post(path,json={"code":" E01 ","nom":"Doublon"}).status_code==409
    assert len(client.get(path).json())==1
    assert client.post(path,json={"code":" ","nom":"Invalide"}).status_code==422
    assert client.post(path,json={"code":"e02","nom":"Invalide",parent:str(uuid4())}).status_code==422
    absent=f"/api/organisation/{categorie}/{uuid4()}/{chemin}"
    assert client.get(absent).status_code==404
    assert client.post(absent,json={"code":"e01","nom":"Orphelin"}).status_code==404
    # Le même code est permis dans un autre parent et ne fuit pas dans le contexte courant.
    _,autre_site=structure(client)
    autre_empl=client.get(f"/api/organisation/sites/{autre_site}/emplacements").json()[0]["id_emplacement"]
    autre=autre_site if parent=="site_id" else autre_empl
    autre_path=f"/api/organisation/{categorie}/{autre}/{chemin}"
    assert client.get(autre_path).json()==[]
    assert client.post(autre_path,json={"code":"e01","nom":"Autre contexte"}).status_code==201
    assert client.get(path).json()[0]["nom"]=="Équipement"


def test_interface_equipements(client):
    page=client.get("/").text
    for label in ("Postes de vente","Caisses","Coffres du site","equipement-emplacement"):
        assert label in page


@pytest.mark.parametrize("model,parent,identifiant", [(PosteVenteModel,"emplacement_id","id_poste_vente"),(CaisseModel,"emplacement_id","id_caisse"),(CoffreModel,"site_id","id_coffre")])
def test_database_refuse_equipement_orphelin(model,parent,identifiant):
    engine=create_engine("sqlite+pysqlite://")
    @event.listens_for(engine,"connect")
    def foreign_keys(connection,_):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as session:
        session.add(model(**{parent:uuid4(),identifiant:uuid4()},code="X",nom="Orphelin",actif=True))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
    engine.dispose()
