"""Fixture de la base navigateur jetable CI ; aucun secret de développement."""
import json
from datetime import date
from pathlib import Path
from secrets import token_urlsafe
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.organisation_repository import SqlAlchemyOrganisationRepository
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.authentification_repository import SqlAlchemyAuthRepository
from neosys_pharma.infrastructure.provisionnement import provisionner
from neosys_pharma.infrastructure.passwords import passwords
from neosys_pharma.domain.organisation.entities import Organisation,Site,Emplacement
from neosys_pharma.domain.organisation.securite import Utilisateur
from neosys_pharma.domain.organisation.permissions_systeme import role_id

password=token_urlsafe(24)
with SessionLocal() as session:
    repo=SqlAlchemyOrganisationRepository(session)
    org=Organisation(nom_commercial='NeoPharma navigateur',raison_sociale='NeoPharma SARL')
    site=Site(organisation_id=org.id_organisation,code='LBV-QA',nom='Libreville QA')
    other=Site(organisation_id=org.id_organisation,code='OW-QA',nom='Owendo QA')
    location=Emplacement(site_id=site.id_site,code='RES-QA',nom='Réserve QA')
    denied=Emplacement(site_id=site.id_site,code='INTERDIT',nom='Comptoir non autorisé')
    second=Emplacement(site_id=other.id_site,code='R-OW',nom='Réserve Owendo')
    for item in (org,site,other,location,denied,second):repo.ajouter(item)
    admin=Utilisateur(organisation_id=org.id_organisation,identifiant='gestion.qa',nom='Gestion QA')
    provisionner(session,admin,[site.id_site,other.id_site],[location.id_emplacement,denied.id_emplacement,second.id_emplacement],[role_id('GESTION_ORGANISATION')],password)
    observer=Utilisateur(organisation_id=org.id_organisation,identifiant='lecture.qa',nom='Lecture QA')
    provisionner(session,observer,[site.id_site],[location.id_emplacement],[role_id('OBSERVATEUR')],password)
    without=Utilisateur(organisation_id=org.id_organisation,identifiant='sans.qa',nom='Sans affectation QA')
    SqlAlchemySecuriteRepository(session).ajouter(without)
    SqlAlchemyAuthRepository(session).definir_password(without.id_utilisateur,passwords.hacher(password))
    session.commit()
Path('/tmp/p1-browser-fixture.json').write_text(json.dumps({'organisation_id':str(org.id_organisation),'site_id':str(site.id_site),'other_id':str(other.id_site),'location_id':str(location.id_emplacement),'denied_id':str(denied.id_emplacement),'password':password,'date':date.today().isoformat()}))
