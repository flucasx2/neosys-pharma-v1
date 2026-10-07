from neosys_pharma.application.securite_service import SecuriteService


class ControleAcces:
    """Refus par défaut, mêmes droits que l'aperçu, date réelle imposée par le serveur."""
    def __init__(self, repository, utilisateur, jour):
        self.repo, self.utilisateur, self.jour = repository, utilisateur, jour
        self.droits = SecuriteService(repository)

    def verifier(self, permission, site_id, emplacement_id=None):
        site = self.repo.site(site_id)
        if not site or site.organisation_id != self.utilisateur.organisation_id:
            raise PermissionError('Site non autorisé.')
        if emplacement_id:
            emplacement = self.repo.emplacement(emplacement_id)
            if not emplacement or emplacement.site_id != site_id:
                raise PermissionError('Emplacement incompatible avec le site courant.')
        if not self.droits.autorise(self.utilisateur.id_utilisateur, site_id, permission, self.jour, emplacement_id):
            raise PermissionError('Accès interdit : aucune affectation, permission ou emplacement compatible.')

    def organisation(self, permission, organisation_id, site_id):
        if organisation_id != self.utilisateur.organisation_id:
            raise PermissionError('Organisation non autorisée.')
        self.verifier(permission, site_id)
