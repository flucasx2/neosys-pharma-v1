"""Fixtures P4-B dédiées : recherche client, historique et sélection en préparation."""
import json
from pathlib import Path
from uuid import UUID, uuid4

from neosys_pharma.application.stock_service import StockService
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.domain.organisation.permissions_systeme import P4_PERMISSIONS, permission_id
from neosys_pharma.infrastructure.client_models import ClientModel
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.provisionnement import provisionner
from neosys_pharma.domain.organisation.securite import Role, RolePermission, TypeRole, Utilisateur


fixture_path = Path('/tmp/p1-browser-fixture.json')
fixture = json.loads(fixture_path.read_text())
org, site, location = (UUID(fixture[key]) for key in ('organisation_id', 'site_id', 'location_id'))

with SessionLocal() as session:
    # P4-B owns its browser identities. Do not depend on roles created by the
    # earlier P4 journey still being present after its intervening recipes.
    security = SqlAlchemySecuriteRepository(session)
    cashier = Role(organisation_id=org, code='clients.qa', nom='Clients QA', type_role=TypeRole.PERSONNALISE)
    security.ajouter(cashier)
    cashier_permissions = tuple(p for p, _ in P4_PERMISSIONS if p != 'vente.remise.autoriser')
    for code in cashier_permissions + ('stock.reserver', 'stock.consulter', 'organisation.consulter',
                                       'client.consulter', 'client.gerer', 'fidelite.gerer', 'fidelite.consulter'):
        security.ajouter(RolePermission(role_id=cashier.id_role, permission_id=permission_id(code)))
    reader = Role(organisation_id=org, code='clients.lecture.qa', nom='Clients lecture QA',
                  type_role=TypeRole.PERSONNALISE)
    security.ajouter(reader)
    for code in ('organisation.consulter', 'vente.consulter'):
        security.ajouter(RolePermission(role_id=reader.id_role, permission_id=permission_id(code)))
    session.commit()

    operator = Utilisateur(organisation_id=org, identifiant='clients.qa', nom='Clients QA')
    provisionner(session, operator, [site], [location], [cashier.id_role], fixture['password'])
    reader_user = Utilisateur(organisation_id=org, identifiant='clients.lecture.qa', nom='Clients lecture QA')
    provisionner(session, reader_user, [site], [location], [reader.id_role], fixture['password'])
    history_client = ClientModel(organisation_id=org, nom='Historique P4B QA', telephone='070987654', courriel='historique.p4b@example.test')
    session.add(history_client)
    session.commit()

    stock = StockService(session, org, operator.id_utilisateur, lambda *args: None)
    sales = VenteService(stock, site)

    def create_sale(key, client_id=None):
        return stock.operation(
            uuid4(), 'P4B:RECETTE:' + key, {},
            lambda: sales.creer({
                'emplacement_id': location,
                'poste_id': UUID(fixture['p4_poste']),
                'mode': 'SANS_TIERS',
                'client_id': client_id,
            }),
        )

    history_sale = create_sale('HISTORIQUE', history_client.id)
    selectable_sale = create_sale('SELECTION')
    fixture.update(
        p4b_history_client=str(history_client.id),
        p4b_history_sale=str(history_sale['id']),
        p4b_selectable_sale=str(selectable_sale['id']),
    )

fixture_path.write_text(json.dumps(fixture))
