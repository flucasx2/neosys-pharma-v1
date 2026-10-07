"""Matrice HTTP fermée : chaque route P1 doit déclarer sa permission."""
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.application.controle_acces import ControleAcces
from neosys_pharma.application.securite_service import SecuriteService
from neosys_pharma.infrastructure.organisation_models import SiteModel
from neosys_pharma.presentation.authentification_api import utilisateur_courant, jour_courant

# Route suffix, method -> required permission. Absence is a refusal.
MATRICE = {
 ('/organisations','GET'):'organisation.consulter',
 ('/organisations/{organisation_id}/sites','GET'):'organisation.consulter',
 ('/organisations/{organisation_id}/sites','POST'):'organisation.gerer',
 ('/sites/{site_id}/emplacements','GET'):'organisation.consulter',
 ('/sites/{site_id}/emplacements','POST'):'organisation.gerer',
 ('/organisations/{organisation_id}/utilisateurs','GET'):'utilisateur.consulter',
 ('/organisations/{organisation_id}/utilisateurs','POST'):'utilisateur.gerer',
 ('/utilisateurs/{utilisateur_id}','PUT'):'utilisateur.gerer',
 ('/utilisateurs/{utilisateur_id}/affectations','GET'):'utilisateur.consulter',
 ('/utilisateurs/{utilisateur_id}/affectations','POST'):'affectation.gerer',
 ('/affectations/{affectation_id}','PUT'):'affectation.gerer',
 ('/affectations/{affectation_id}/emplacements','PUT'):'affectation.gerer',
 ('/affectations/{affectation_id}/roles','PUT'):'affectation.gerer',
 ('/permissions','GET'):'role.consulter',
 ('/organisations/{organisation_id}/roles','GET'):'role.consulter',
 ('/organisations/{organisation_id}/roles','POST'):'role.gerer',
 ('/roles/{role_id}/permissions','PUT'):'role.gerer',
 ('/utilisateurs/{utilisateur_id}/sites/{site_id}/permissions','GET'):'utilisateur.consulter',
}
for category in ('postes-vente','caisses'):
    for method in ('GET','POST'):
        MATRICE[(f'/emplacements/{{emplacement_id}}/{category}',method)] = 'organisation.consulter' if method=='GET' else 'organisation.gerer'
for method in ('GET','POST'):
    MATRICE[('/sites/{site_id}/coffres',method)] = 'organisation.consulter' if method=='GET' else 'organisation.gerer'


# Administration de la structure : droits explicites dans un site effectif de
# l'organisation, sans accorder de contexte opérationnel dans le site cible.
ADMIN_PATHS = {
 '/organisations/{organisation_id}/sites': ('GET',),
 '/sites/{site_id}/emplacements': ('GET', 'POST'),
 '/utilisateurs/{utilisateur_id}/affectations': ('GET', 'POST'),
 '/affectations/{affectation_id}': ('PUT',),
 '/affectations/{affectation_id}/emplacements': ('PUT',),
 '/affectations/{affectation_id}/roles': ('PUT',),
 '/utilisateurs/{utilisateur_id}/sites/{site_id}/permissions': ('GET',),
}
for admin_path, methods in ADMIN_PATHS.items():
    for method in methods:
        MATRICE[('/administration' + admin_path, method)] = MATRICE[(admin_path, method)]


async def require_access(request: Request, user=Depends(utilisateur_courant), session: Session = Depends(get_db_session)):
    repo = SqlAlchemySecuriteRepository(session)
    path = request.scope['route'].path.removeprefix('/api/organisation')
    permission = MATRICE.get((path,request.method))
    if not permission:
        raise HTTPException(403, 'Action non autorisée par la politique P1.')
    request.state.visible_organisation = lambda item: item["id_organisation"] == user.organisation_id
    def visible_site(site_id, permission='organisation.consulter'):
        site = repo.site(site_id)
        return bool(site and site.organisation_id == user.organisation_id and SecuriteService(repo).autorise(user.id_utilisateur,site_id,permission,jour_courant()))
    request.state.visible_site = visible_site
    request.state.visible_emplacement = lambda item: SecuriteService(repo).autorise(user.id_utilisateur,item['site_id'],'organisation.consulter',jour_courant(),item['id_emplacement'])
    administrative = path.startswith('/administration/')
    if administrative:
        path = path.removeprefix('/administration')
    params = request.path_params
    try:
        controle = ControleAcces(repo, user, jour_courant())
        if not administrative and path in ('/organisations','/organisations/{organisation_id}/sites') and request.method=='GET':
            org = UUID(params['organisation_id']) if 'organisation_id' in params else user.organisation_id
            if org != user.organisation_id:
                raise PermissionError('Organisation non autorisée.')
            if not any(SecuriteService(repo).autorise(user.id_utilisateur,site["id_site"],permission,jour_courant()) for site in repo.parents.lister(SiteModel,organisation_id=org)):
                raise PermissionError('Aucune affectation active avec la permission nécessaire.')
            return
        context = UUID(request.headers.get('X-Site-ID',''))
        target_org = user.organisation_id
        target_site = UUID(params['site_id']) if 'site_id' in params else None
        emplacement = UUID(params['emplacement_id']) if 'emplacement_id' in params else None
        if emplacement:
            item = repo.emplacement(emplacement)
            if not item:
                raise PermissionError('Emplacement non autorisé.')
            target_site = item.site_id
        if 'organisation_id' in params:
            target_org = UUID(params['organisation_id'])
        if 'utilisateur_id' in params:
            target = repo.utilisateur(UUID(params['utilisateur_id']))
            if not target:
                raise PermissionError('Utilisateur non autorisé.')
            target_org = target.organisation_id
        if 'affectation_id' in params:
            target = repo.affectation(UUID(params['affectation_id']))
            if not target:
                raise PermissionError('Affectation non autorisée.')
            target_site = target.site_id
        if 'role_id' in params:
            role = repo.role(UUID(params['role_id']))
            if not role:
                raise PermissionError('Rôle non autorisé.')
            target_org = role.organisation_id or user.organisation_id
        if path=='/utilisateurs/{utilisateur_id}/affectations' and request.method=='POST':
            body=await request.json()
            target_site=UUID(body.get('site_id',''))
        if administrative:
            if target_site:
                site = repo.site(target_site)
                if not site or site.organisation_id != user.organisation_id:
                    raise PermissionError('Site non autorisé.')
            controle.organisation('organisation.gerer', target_org, context)
            controle.organisation(permission, target_org, context)
            location_header = request.headers.get('X-Emplacement-ID')
            if location_header:
                controle.verifier(permission, context, UUID(location_header))
                controle.verifier('organisation.gerer', context, UUID(location_header))
            # Consultable ne signifie jamais utilisable comme contexte de travail.
            request.state.visible_site = lambda site_id, permission='organisation.consulter': bool(repo.site(site_id) and repo.site(site_id).organisation_id == user.organisation_id)
            request.state.visible_emplacement = lambda item: bool(repo.site(item['site_id']) and repo.site(item['site_id']).organisation_id == user.organisation_id)
            return
        if target_site and target_site != context:
            raise PermissionError('Le site demandé ne correspond pas au site courant.')
        controle.organisation(permission,target_org,context)
        if emplacement:
            controle.verifier(permission,context,emplacement)
        # A supplied location context also narrows site-level operations.
        location_header=request.headers.get('X-Emplacement-ID')
        if location_header:
            location_context=UUID(location_header)
            if emplacement and location_context!=emplacement:
                raise PermissionError('Emplacement différent du contexte courant.')
            controle.verifier(permission,context,location_context)
    except (ValueError, PermissionError, TypeError) as exc:
        raise HTTPException(403,str(exc) or 'Contexte de site requis.') from exc
