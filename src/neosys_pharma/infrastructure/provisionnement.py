"""Provisionnement local de confiance ; jamais exposé en HTTP, aucun droit implicite."""
import argparse
from datetime import date
from getpass import getpass
from uuid import UUID
from sqlalchemy import select
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.authentification_models import CredentialModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.authentification_repository import SqlAlchemyAuthRepository
from neosys_pharma.infrastructure.passwords import passwords
from neosys_pharma.domain.organisation.securite import Utilisateur, AffectationSite, AffectationRole, AffectationEmplacement


def provisionner(session, utilisateur, site_ids, emplacement_ids, role_ids, password):
    """Une transaction ; seuls les liens fournis explicitement donnent des droits."""
    repo=SqlAlchemySecuriteRepository(session)
    if not repo.organisation(utilisateur.organisation_id):
        raise ValueError('Organisation introuvable.')
    sites=[repo.site(i) for i in site_ids]
    if not sites or any(not s or s.organisation_id!=utilisateur.organisation_id for s in sites):
        raise ValueError('Sites incompatibles avec l’organisation.')
    locations=[repo.emplacement(i) for i in emplacement_ids]
    if any(not e or e.site_id not in site_ids for e in locations):
        raise ValueError('Emplacements incompatibles.')
    roles=[repo.role(i) for i in role_ids]
    if any(not r or (r.organisation_id and r.organisation_id!=utilisateur.organisation_id) for r in roles):
        raise ValueError('Rôles incompatibles.')
    encoded=passwords.hacher(password)
    try:
        repo.ajouter(utilisateur)
        for site in sites:
            assignment=AffectationSite(utilisateur_id=utilisateur.id_utilisateur,site_id=site.id_site,date_debut=date.today())
            repo.ajouter(assignment)
            for role in roles:
                repo.ajouter(AffectationRole(affectation_site_id=assignment.id_affectation_site,role_id=role.id_role))
            for location in locations:
                if location.site_id==site.id_site:
                    repo.ajouter(AffectationEmplacement(affectation_site_id=assignment.id_affectation_site,emplacement_id=location.id_emplacement))
        SqlAlchemyAuthRepository(session).definir_password(utilisateur.id_utilisateur,encoded)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return utilisateur


def main():
    parser=argparse.ArgumentParser(description='Créer un premier compte local avec ses affectations explicites. Mot de passe demandé sans affichage.')
    parser.add_argument('--organisation-id',type=UUID,required=True)
    parser.add_argument('--site-id',type=UUID,action='append',required=True)
    parser.add_argument('--emplacement-id',type=UUID,action='append',default=[])
    parser.add_argument('--role-id',type=UUID,action='append',required=True)
    parser.add_argument('--identifiant',required=True)
    parser.add_argument('--nom',required=True)
    args=parser.parse_args()
    password=getpass('Mot de passe (12–128 caractères) : ')
    if password!=getpass('Confirmation : '):
        parser.error('Confirmation différente.')
    with SessionLocal() as session:
        from neosys_pharma.infrastructure.bootstrap import verrouiller_installation
        verrouiller_installation(session)
        # First credential per organisation. Subsequent accounts use the protected UI.
        existing=session.scalar(select(CredentialModel.utilisateur_id).join(UtilisateurModel).where(UtilisateurModel.organisation_id==args.organisation_id))
        if existing:
            parser.error('Cette organisation possède déjà un compte authentifiable.')
        user=Utilisateur(organisation_id=args.organisation_id,identifiant=args.identifiant,nom=args.nom)
        provisionner(session,user,args.site_id,args.emplacement_id,args.role_id,password)
        print('Compte provisionné :',user.id_utilisateur)


if __name__=='__main__':
    main()
