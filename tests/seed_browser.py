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
from neosys_pharma.domain.organisation.entities import Site,Emplacement
from neosys_pharma.domain.organisation.securite import Utilisateur, AffectationSite, AffectationEmplacement, AffectationRole
from neosys_pharma.application.bootstrap_service import BootstrapService, InstallationInitiale
from neosys_pharma.infrastructure.bootstrap import SqlAlchemyBootstrapRepository, verifier_migrations
from sqlalchemy import select
from neosys_pharma.infrastructure.securite_models import UtilisateurModel
from neosys_pharma.infrastructure.organisation_models import SiteModel, EmplacementModel
from neosys_pharma.domain.organisation.permissions_systeme import role_id

password=token_urlsafe(24)
with SessionLocal() as session:
    verifier_migrations(session)
    initial=BootstrapService(SqlAlchemyBootstrapRepository(session),passwords).initialiser(
        InstallationInitiale(nom_commercial='NeoPharma navigateur',raison_sociale='NeoPharma SARL',
            site_code='LBV-QA',site_nom='Libreville QA',emplacement_code='RES-QA',emplacement_nom='Réserve QA',
            identifiant='gestion.qa',utilisateur_nom='Gestion QA'),password,date.today())
    repo=SqlAlchemyOrganisationRepository(session)
    security=SqlAlchemySecuriteRepository(session)
    org=repo.organisation(initial.organisation_id)
    site=repo.site(session.scalar(select(SiteModel.id_site)))
    location=repo.emplacement(session.scalar(select(EmplacementModel.id_emplacement)))
    admin=security.utilisateur(session.scalar(select(UtilisateurModel.id_utilisateur)))
    other=Site(organisation_id=org.id_organisation,code='OW-QA',nom='Owendo QA')
    denied=Emplacement(site_id=site.id_site,code='INTERDIT',nom='Comptoir non autorisé')
    second=Emplacement(site_id=other.id_site,code='R-OW',nom='Réserve Owendo')
    for item in (other,denied,second):repo.ajouter(item)
    first_assignment=security.affectations(admin.id_utilisateur)[0]
    security.ajouter(AffectationEmplacement(affectation_site_id=first_assignment.id_affectation_site,emplacement_id=denied.id_emplacement))
    other_assignment=AffectationSite(utilisateur_id=admin.id_utilisateur,site_id=other.id_site,date_debut=date.today())
    for item in (other_assignment,
                 AffectationEmplacement(affectation_site_id=other_assignment.id_affectation_site,emplacement_id=second.id_emplacement),
                 AffectationRole(affectation_site_id=other_assignment.id_affectation_site,role_id=role_id('GESTION_ORGANISATION'))):security.ajouter(item)
    session.commit()
    observer=Utilisateur(organisation_id=org.id_organisation,identifiant='lecture.qa',nom='Lecture QA')
    provisionner(session,observer,[site.id_site],[location.id_emplacement],[role_id('OBSERVATEUR')],password)
    without=Utilisateur(organisation_id=org.id_organisation,identifiant='sans.qa',nom='Sans affectation QA')
    SqlAlchemySecuriteRepository(session).ajouter(without)
    SqlAlchemyAuthRepository(session).definir_password(without.id_utilisateur,passwords.hacher(password))
    session.commit()
Path('/tmp/p1-browser-fixture.json').write_text(json.dumps({'organisation_id':str(org.id_organisation),'site_id':str(site.id_site),'other_id':str(other.id_site),'location_id':str(location.id_emplacement),'denied_id':str(denied.id_emplacement),'password':password,'date':date.today().isoformat()}))
