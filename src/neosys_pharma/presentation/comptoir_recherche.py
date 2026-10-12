"""Filtres de lecture P4.6 ; aucun élargissement du contexte P1."""
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from typing import Literal
from fastapi import Query, HTTPException
from sqlalchemy import select, cast, String, or_
from neosys_pharma.infrastructure.vente_models import VenteModel, LigneVenteModel
from neosys_pharma.infrastructure.caisse_models import AppelVenteModel, EncaissementModel
from neosys_pharma.infrastructure.organisation_models import CaisseModel

def filtres_comptoir(q: str = Query('', max_length=200),
        etat: Literal['PREPARATION','EN_ATTENTE','VALIDEE_PREPARATION','TRANSMISE','ENCAISSEE','ANNULEE'] | None = None,
        debut: date | None = None, fin: date | None = None,
        emplacement_id: UUID | None = None, caisse_id: UUID | None = None):
    if debut and fin and debut > fin:
        raise HTTPException(422, 'La date de fin doit suivre la date de début.')
    if fin == date.max:
        raise HTTPException(422, 'Date de fin hors plage.')
    return dict(q=q.strip(), etat=etat, debut=debut, fin=fin,
                emplacement_id=emplacement_id, caisse_id=caisse_id)

def filtrer(s, query, filters, permission, date_column, receipt=False):
    stock = getattr(s, 'stock', None) or s.vente.stock
    if filters['emplacement_id']:
        stock.emplacement(filters['emplacement_id'], permission)
        query = query.where(VenteModel.emplacement_id == filters['emplacement_id'])
    if filters['caisse_id']:
        caisse = stock.s.get(CaisseModel, filters['caisse_id'])
        if not caisse:
            raise PermissionError('Caisse inaccessible dans ce contexte.')
        stock.emplacement(caisse.emplacement_id, permission)
        query = query.where(VenteModel.caisse_id == filters['caisse_id'])
    if filters['etat']:
        query = query.where(VenteModel.etat == filters['etat'])
    if filters['debut']:
        query = query.where(date_column >= datetime.combine(filters['debut'], time.min, timezone.utc))
    if filters['fin']:
        query = query.where(date_column < datetime.combine(filters['fin'] + timedelta(days=1), time.min, timezone.utc))
    term = filters['q']
    if term:
        upper = stock.repo.terme(term)
        lines = select(LigneVenteModel.id).where(
            LigneVenteModel.organisation_id == s.org, LigneVenteModel.vente_id == VenteModel.id,
            LigneVenteModel.actif.is_(True),
            or_(stock.repo.upper(LigneVenteModel.designation).contains(upper, autoescape=True),
                stock.repo.upper(LigneVenteModel.reference).contains(upper, autoescape=True)))
        ids = cast(VenteModel.id, String).contains(term.replace('-', '').lower(), autoescape=True)
        # PostgreSQL displays UUIDs with hyphens; SQLite stores the hex representation.
        from sqlalchemy import func
        ids = func.replace(cast(VenteModel.id, String), '-', '').contains(term.replace('-', '').lower(), autoescape=True)
        clauses = [ids, lines.exists()]
        if receipt:
            clauses.append(func.replace(cast(EncaissementModel.id, String), '-', '').contains(term.replace('-', '').lower(), autoescape=True))
        if term.isascii() and term.isdigit() and len(term) <= 10:
            number = int(term)
            calls = select(AppelVenteModel.id).where(AppelVenteModel.organisation_id == s.org,
                AppelVenteModel.vente_id == VenteModel.id, AppelVenteModel.numero == number)
            clauses.append(calls.exists())
            if receipt:
                clauses.append(EncaissementModel.numero == number)
        query = query.where(or_(*clauses))
    return query

def appel(s, vente_id):
    a = s.s.scalar(select(AppelVenteModel).where(AppelVenteModel.organisation_id == s.org,
                                               AppelVenteModel.vente_id == vente_id))
    return {'numero_appel': str(a.numero).zfill(4) if a else None,
            'periode_appel_id': str(a.periode_id) if a else None}
