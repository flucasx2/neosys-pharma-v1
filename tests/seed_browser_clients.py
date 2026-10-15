"""Fixtures P4-B dédiées : recherche client, historique et sélection en préparation."""
import json
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select

from neosys_pharma.application.stock_service import StockService
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.client_models import ClientModel
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.securite_models import RoleModel, RolePermissionModel, UtilisateurModel


fixture_path = Path('/tmp/p1-browser-fixture.json')
fixture = json.loads(fixture_path.read_text())
org, site, location = (UUID(fixture[key]) for key in ('organisation_id', 'site_id', 'location_id'))

with SessionLocal() as session:
    cashier_role = session.scalar(select(RoleModel).where(RoleModel.organisation_id == org, RoleModel.code == 'vente.qa'))
    if not cashier_role:
        raise RuntimeError('Le rôle de recette vente.qa est requis avant P4-B.')
    existing = set(session.scalars(select(RolePermissionModel.permission_id).where(RolePermissionModel.role_id == cashier_role.id_role)))
    for code in ('client.consulter', 'client.gerer', 'fidelite.gerer', 'fidelite.consulter'):
        pid = permission_id(code)
        if pid not in existing:
            session.add(RolePermissionModel(role_id=cashier_role.id_role, permission_id=pid))
    session.commit()

    operator = session.scalar(select(UtilisateurModel).where(UtilisateurModel.organisation_id == org, UtilisateurModel.identifiant == 'vente.qa'))
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
