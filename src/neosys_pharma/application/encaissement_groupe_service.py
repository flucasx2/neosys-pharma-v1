"""Orchestration transactionnelle de l’étape P4.6/3.3.

Toutes les mutations sont appelées depuis StockService.operation : verrou
d’organisation, clé d’idempotence, une transaction et un commit uniques.
"""
import hashlib
import json
import unicodedata
from decimal import Decimal, ROUND_FLOOR
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from neosys_pharma.application.caisse_service import CaisseService, serial
from neosys_pharma.domain.caisse import MODES, acquisition, francs, repartir_paiements
from neosys_pharma.domain.encaissement_groupe import (
    AllocationReglement,
    DossierEncaissementGroupe,
    EtatDossierGroupe,
    SelectionGroupe,
    VentilationEncaissement,
    verifier_allocations,
)
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.caisse_models import (
    CompteFideliteModel,
    ConfirmationReglementModel,
    EncaissementModel,
    EvenementCaisseModel,
    JournalFideliteModel,
    MouvementCaisseModel,
    ReglementModel,
    SessionCaisseModel,
)
from neosys_pharma.infrastructure.encaissement_groupe_models import (
    DossierEncaissementGroupeModel,
)
from neosys_pharma.infrastructure.encaissement_groupe_repository import (
    SqlAlchemyEncaissementGroupeRepository,
)
from neosys_pharma.infrastructure.organisation_models import OrganisationModel, SiteModel
from neosys_pharma.infrastructure.catalogue_models import ProduitModel
from neosys_pharma.infrastructure.regularisation_models import RemboursementModel
from neosys_pharma.infrastructure.vente_models import VenteModel


def empreinte_selection(session_id, account_id, selections):
    rows = [{'vente_id': str(row['vente_id']), 'revision': int(row['revision'])} for row in selections]
    beneficiary_ids = [str(row['compte_id']) if row.get('compte_id') else None for row in selections]
    # Keep fingerprints of legacy single-account drafts byte-for-byte stable.
    uniform = not any(beneficiary_ids) or (len(set(beneficiary_ids)) == 1 and beneficiary_ids[0] == (str(account_id) if account_id else None))
    value = {'session_id': str(session_id), 'compte_id': str(account_id) if account_id else None, 'ventes': rows}
    if not uniform:
        value['fidelite_par_vente'] = [
            {'vente_id': str(row['vente_id']), 'compte_id': str(row['compte_id']) if row.get('compte_id') else None,
             'revision_compte': row.get('revision_compte')}
            for row in selections]
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def repartir_allocations(reglements, lignes):
    """Prorata entier à plus grand reste, avec départage UUID déterministe.

    Une confirmation historique individuelle reste rattachée à sa vente ; les
    paiements de groupe et les espèces sont répartis sur les soldes communs.
    """
    remaining = {(UUID(str(row['vente_id'])), UUID(str(row['ligne_id']))): francs(row['montant'], True) for row in lignes}
    result = []
    for payment_index, payment in enumerate(reglements):
        amount = francs(payment['montant'] - payment['rendu'], True)
        if amount == 0:
            continue
        anchor = payment.get('vente_ancree')
        candidates = [key for key, value in remaining.items() if value > 0 and (anchor is None or key[0] == anchor)]
        available = sum((remaining[key] for key in candidates), Decimal(0))
        if amount > available:
            raise ConflitStock('Un paiement acquis dépasse le solde de la vente à laquelle il est rattaché.')
        if not candidates:
            raise ConflitStock('Aucun solde de vente disponible pour ventiler le règlement.')
        floors = {}
        remainders = {}
        for key in candidates:
            raw = amount * remaining[key] / available
            floor = raw.to_integral_value(rounding=ROUND_FLOOR)
            floors[key] = floor
            remainders[key] = raw - floor
        residual = int(amount - sum(floors.values(), Decimal(0)))
        for key in sorted(candidates, key=lambda k: (-remainders[k], str(k[0]), str(k[1])))[:residual]:
            floors[key] += 1
        for key in sorted(candidates, key=lambda k: (str(k[0]), str(k[1]))):
            allocated = floors[key]
            if not allocated:
                continue
            remaining[key] -= allocated
            result.append({'payment_index': payment_index, 'vente_id': key[0], 'ligne_id': key[1], 'montant': allocated})
    if any(value for value in remaining.values()):
        raise ConflitStock('Les règlements ne couvrent pas exactement les lignes de toutes les ventes.')
    return result


class EncaissementGroupeService:
    def __init__(self, caisse: CaisseService):
        self.cash = caisse
        self.stock = caisse.stock
        self.s = caisse.s
        self.org = caisse.org
        self.site = caisse.site
        self.repo = SqlAlchemyEncaissementGroupeRepository(self.s, self.org)

    def _access(self, permission, location):
        self.stock.access(permission, self.site, location)

    def _session(self, key, *, revision=None, active=True):
        session = self.cash.session(key, 'caisse.encaisser', active)
        self._access('caisse.encaisser.groupe', session.emplacement_id)
        if revision is not None and session.revision != revision:
            raise ConflitStock('Session de caisse modifiée : actualiser avant de continuer.')
        return session

    @staticmethod
    def _normaliser_identite(value):
        if not value:
            return None
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        return unicodedata.normalize('NFC', encoded).casefold()

    def _ventes_autorisees(self, session, selections):
        if len(selections) < 2 or len({str(x['vente_id']) for x in selections}) != len(selections):
            raise ValueError('Sélectionner au moins deux ventes distinctes.')
        rows = []
        for item in selections:
            sale = self.cash.verifier_vente(item['vente_id'], session, item['revision'], 'caisse.encaisser')
            self._access('caisse.encaisser.groupe', sale.emplacement_id)
            if sale.site_id != self.site or sale.caisse_id != session.caisse_id or sale.emplacement_id != session.emplacement_id:
                raise PermissionError('Toutes les ventes doivent appartenir au site, à la caisse et à l’emplacement autorisés.')
            if sale.mode != 'SANS_TIERS':
                raise ValueError('Crédit et tiers payant ne sont pas finalisables en groupe.')
            if self.repo.encaissement_de_vente(sale.id):
                raise ConflitStock('Une vente sélectionnée est déjà encaissée.')
            rows.append(sale)
        return rows

    def _verifier_identite(self, ventes, compte_id, revision_compte, attestation):
        if attestation is not True:
            raise ValueError('Confirmation explicite de l’identité commune requise.')
        recipients = [self._normaliser_identite(v.destinataire) for v in ventes]
        recipients_non_vides = [x for x in recipients if x]
        if recipients_non_vides and (len(recipients_non_vides) != len(ventes) or len(set(recipients_non_vides)) != 1):
            raise ValueError('Les préparations n’identifient pas le même destinataire.')
        account = None
        if compte_id:
            self.stock.access('fidelite.consulter', self.site, ventes[0].emplacement_id)
            account = self.stock.obtenir(CompteFideliteModel, compte_id)
            if revision_compte != account.revision:
                raise ConflitStock('Compte fidélité modifié : actualiser et reconfirmer le titulaire.')
        elif not recipients_non_vides:
            raise ValueError('Aucun destinataire commun identifié : sélectionner explicitement un compte fidélité ou préparer les ventes avec le même destinataire.')
        return account

    def _comptes_par_vente(self, ventes, selections, compte_id=None, revision_compte=None,
                           identite_commune_confirmee=False):
        """Validate explicit per-sale loyalty, retaining the old common-account contract."""
        by_sale = {str(item['vente_id']): item for item in selections}
        if set(by_sale) != {str(sale.id) for sale in ventes}:
            raise ValueError('La correspondance des ventes et des comptes fidélité est incomplète.')
        has_explicit_map = any(item.get('compte_id') is not None for item in selections)
        if has_explicit_map:
            if compte_id is not None or revision_compte is not None:
                raise ValueError('Utiliser soit le compte historique commun, soit les comptes par vente.')
            accounts = {}
            for sale in ventes:
                item = by_sale[str(sale.id)]
                account_id = item.get('compte_id')
                account_revision = item.get('revision_compte')
                if account_id is None:
                    if account_revision is not None:
                        raise ValueError('Révision de fidélité sans compte pour la vente.')
                    continue
                if account_revision is None:
                    raise ValueError('Révision du compte fidélité obligatoire pour chaque vente associée.')
                self.stock.access('fidelite.consulter', self.site, sale.emplacement_id)
                account = self.stock.obtenir(CompteFideliteModel, account_id)
                if account.revision != account_revision:
                    raise ConflitStock('Compte fidélité modifié pour une vente : actualiser et reconfirmer le titulaire.')
                # If P4-B supplied a stable client id in the sale snapshot, enforce it.
                client_id = (sale.destinataire or {}).get('client_id')
                if client_id and str(account.client_id) != str(client_id):
                    raise PermissionError('Le compte fidélité ne correspond pas au client de cette vente.')
                accounts[sale.id] = account
            return accounts, None
        if compte_id is None:
            # Loyalty remains optional; a sale without a selected beneficiary
            # neither borrows another sale's client nor blocks settlement.
            return {}, None
        account = self._verifier_identite(ventes, compte_id, revision_compte, identite_commune_confirmee)
        return ({sale.id: account for sale in ventes} if account else {}), account

    def previsualiser(self, session_id, revision_session, selections, compte_id=None, revision_compte=None, identite_commune_confirmee=False):
        session = self._session(session_id, revision=revision_session)
        sales = self._ventes_autorisees(session, selections)
        accounts, common_account = self._comptes_par_vente(
            sales, selections, compte_id, revision_compte, identite_commune_confirmee)
        items = []
        total = Decimal(0)
        for sale in sales:
            finance = self.cash.vente.finance(sale)
            amount = francs(finance['totaux']['ttc'], True)
            total += amount
            account = accounts.get(sale.id)
            items.append({'vente_id': str(sale.id), 'revision': sale.revision,
                          'compte_id': str(account.id) if account else None,
                          'revision_compte': account.revision if account else None,
                          'client_id': str(account.client_id) if account else None,
                          'numero_appel': self.cash.appel(sale).get('affichage'),
                          'totaux': finance['totaux']})
        return {'session_id': str(session.id), 'revision_session': session.revision,
                'compte_id': str(common_account.id) if common_account else None,
                'ventes': items, 'total_xaf': str(total),
                'empreinte': empreinte_selection(session.id, common_account.id if common_account else None, selections)}

    def creer(self, data):
        session = self._session(data['session_id'], revision=data['revision_session'])
        sales = self._ventes_autorisees(session, data['ventes'])
        accounts, common_account = self._comptes_par_vente(sales, data['ventes'], data.get('compte_id'), data.get('revision_compte'), data.get('identite_commune_confirmee'))
        enriched = [{**item, 'compte_id': str(accounts[UUID(str(item['vente_id']))].id) if UUID(str(item['vente_id'])) in accounts else None,
                     'revision_compte': accounts[UUID(str(item['vente_id']))].revision if UUID(str(item['vente_id'])) in accounts else None}
                    for item in data['ventes']]
        fingerprint = empreinte_selection(session.id, common_account.id if common_account else None, enriched)
        entity = DossierEncaissementGroupe(
            organisation_id=self.org, site_id=self.site, emplacement_id=session.emplacement_id,
            caisse_id=session.caisse_id, session_id=session.id, auteur_id=self.stock.user,
            compte_id=common_account.id if common_account else None, selections=tuple(
                SelectionGroupe(vente_id=UUID(str(row['vente_id'])), revision_vente=row['revision'], ordre=index,
                    compte_id=UUID(row['compte_id']) if row['compte_id'] else None,
                    revision_compte=row['revision_compte'])
                for index, row in enumerate(enriched, 1)), empreinte_selection=fingerprint)
        self.repo.ajouter_dossier(entity)
        self.cash.trace('DOSSIER_ENCAISSEMENT_GROUPE_CREE', dossier_id=entity.id,
                        ventes=[str(x.vente_id) for x in entity.selections], empreinte=fingerprint,
                        identite_commune_confirmee=bool(common_account))
        self.s.flush()
        return self.dossier(entity.id)

    def _dossier(self, key):
        entity = self.repo.dossier(key)
        if entity is None:
            raise LookupError('Dossier groupé introuvable dans cette organisation.')
        return entity, self.s.scalar(select(DossierEncaissementGroupeModel).where(
            DossierEncaissementGroupeModel.id == key,
            DossierEncaissementGroupeModel.organisation_id == self.org))

    def _load_authorized(self, key):
        entity, row = self._dossier(key)
        session = self._session(entity.session_id,
            active=entity.etat in (EtatDossierGroupe.BROUILLON, EtatDossierGroupe.EN_REGLEMENT))
        if session.id != entity.session_id or session.emplacement_id != entity.emplacement_id:
            raise PermissionError('Session et emplacement incompatibles avec le dossier.')
        selections = [{'vente_id': x.vente_id, 'revision': x.revision_vente} for x in entity.selections]
        sales = self._ventes_autorisees(session, selections) if entity.etat in (EtatDossierGroupe.BROUILLON, EtatDossierGroupe.EN_REGLEMENT) else []
        if entity.etat not in (EtatDossierGroupe.BROUILLON, EtatDossierGroupe.EN_REGLEMENT):
            for item in entity.selections:
                sale = self.cash.vente.obtenir(item.vente_id, 'caisse.consulter')
                self._access('caisse.encaisser.groupe', sale.emplacement_id)
        return entity, row, session, sales

    def dossier(self, key):
        entity, row = self._dossier(key)
        receipt = self.s.scalar(select(EncaissementModel.id).where(
            EncaissementModel.organisation_id == self.org,
            EncaissementModel.dossier_groupe_id == key))
        return {'id': str(entity.id), 'organisation_id': str(entity.organisation_id),
                'site_id': str(entity.site_id), 'emplacement_id': str(entity.emplacement_id),
                'caisse_id': str(entity.caisse_id), 'session_id': str(entity.session_id),
                'auteur_id': str(entity.auteur_id), 'compte_id': str(entity.compte_id) if entity.compte_id else None,
                'etat': entity.etat.value, 'revision': entity.revision,
                'empreinte_selection': entity.empreinte_selection,
                'ventes': [{'vente_id': str(x.vente_id), 'revision': x.revision_vente, 'ordre': x.ordre,
                            'compte_id': str(x.compte_id) if x.compte_id else None,
                            'revision_compte': x.revision_compte} for x in entity.selections],
                'encaissement_id': str(receipt) if receipt else None}

    def autoriser_dossier(self, key):
        return self._load_authorized(key)[0]

    def modifier_selection(self, key, data):
        entity, row, session, sales = self._load_authorized(key)
        if entity.etat != EtatDossierGroupe.BROUILLON:
            raise ConflitStock('La sélection est figée dès le début du règlement.')
        if entity.revision != data['revision']:
            raise ConflitStock('Dossier modifié : actualiser la sélection.')
        if session.revision != data['revision_session']:
            raise ConflitStock('Session de caisse modifiée : actualiser.')
        sales = self._ventes_autorisees(session, data['ventes'])
        accounts, common_account = self._comptes_par_vente(sales, data['ventes'], entity.compte_id,
            data.get('revision_compte'), data.get('identite_commune_confirmee'))
        enriched = [{**item, 'compte_id': str(accounts[UUID(str(item['vente_id']))].id) if UUID(str(item['vente_id'])) in accounts else None,
                     'revision_compte': accounts[UUID(str(item['vente_id']))].revision if UUID(str(item['vente_id'])) in accounts else None}
                    for item in data['ventes']]
        fingerprint = empreinte_selection(session.id, common_account.id if common_account else None, enriched)
        updated = entity.changer_selection(tuple(
            SelectionGroupe(vente_id=UUID(str(item['vente_id'])), revision_vente=item['revision'], ordre=index,
                compte_id=UUID(item['compte_id']) if item['compte_id'] else None,
                revision_compte=item['revision_compte'])
            for index, item in enumerate(enriched, 1)), fingerprint)
        self.repo.modifier_selection(updated, entity.revision)
        self.cash.trace('DOSSIER_ENCAISSEMENT_GROUPE_SELECTION_MODIFIEE', dossier_id=key,
                        revision=updated.revision, empreinte=fingerprint)
        self.s.flush()
        return self.dossier(key)

    def confirmer(self, key, data):
        entity, row, session, sales = self._load_authorized(key)
        if entity.etat not in (EtatDossierGroupe.BROUILLON, EtatDossierGroupe.EN_REGLEMENT):
            raise ConflitStock('Dossier non ouvert aux confirmations.')
        if entity.revision != data['revision'] or session.revision != data['revision_session']:
            raise ConflitStock('Dossier ou session modifié : actualiser avant de confirmer.')
        mode = data['mode']
        if mode == 'ESPECES' or mode not in self.cash.config()['modes']:
            raise ValueError('Un moyen non espèces activé est requis.')
        if data['source'] == 'TECHNIQUE_PRESTATAIRE':
            raise ValueError('Aucun prestataire bancaire intégré : confirmation technique indisponible.')
        if mode in ('CARTE', 'MOBILE_MONEY') and data['source'] != 'MANUEL_TERMINAL':
            raise ValueError('Confirmation manuelle du terminal indépendant requise.')
        if mode in ('CHEQUE', 'VIREMENT') and data['source'] != 'MANUEL_JUSTIFICATIF':
            raise ValueError('Confirmation du justificatif requise.')
        reference, preuve = data['reference'].strip(), data['preuve'].strip()
        if not reference or not preuve:
            raise ValueError('Référence vérifiable et preuve de confirmation obligatoires.')
        amount = francs(data['montant'])
        confirmation = self.stock.ajouter(ConfirmationReglementModel,
            vente_id=None, dossier_groupe_id=entity.id, revision_vente=None,
            revision_groupe=entity.revision, session_id=session.id, mode=mode,
            montant=amount, reference=reference, source=data['source'], preuve=preuve,
            auteur_id=self.stock.user)
        row.etat = EtatDossierGroupe.EN_REGLEMENT.value
        row.revision += 1
        self.cash.trace('PAIEMENT_GROUPE_CONFIRME', dossier_id=entity.id,
            confirmation_id=confirmation.id, revision_groupe=entity.revision,
            empreinte=entity.empreinte_selection, session_id=session.id)
        self.s.flush()
        return serial(confirmation)

    def rapprocher(self, key, confirmation_id, data):
        entity, row, session, sales = self._load_authorized(key)
        confirmation = self.stock.obtenir(ConfirmationReglementModel, confirmation_id)
        if confirmation.dossier_groupe_id != entity.id or confirmation.vente_id is not None:
            raise PermissionError('Confirmation d’un autre dossier.')
        if entity.etat != EtatDossierGroupe.EN_REGLEMENT or entity.revision != data['revision']:
            raise ConflitStock('Dossier modifié ou sans règlement à rapprocher.')
        if session.id != data['session_id'] or session.revision != data['revision_session']:
            raise ConflitStock('Session de rapprochement incompatible.')
        if self.stock.lignes(ReglementModel, confirmation_id=confirmation.id):
            raise ConflitStock('Paiement déjà consommé.')
        if self.stock.lignes(RemboursementModel, confirmation_id=confirmation.id):
            raise ConflitStock('Paiement déjà affecté à une restitution.')
        self.cash.trace('PAIEMENT_GROUPE_RAPPROCHE', dossier_id=entity.id,
            confirmation_id=confirmation.id, session_id=session.id,
            revision_groupe=entity.revision, empreinte=entity.empreinte_selection,
            justification=data['justification'])
        return serial(confirmation) | {'revision_rapprochee': entity.revision, 'session_rapprochee': str(session.id)}

    def _confirmation_match(self, confirmation, entity, session):
        if confirmation.session_id == session.id:
            created = [event for event in self.stock.lignes(EvenementCaisseModel, type='PAIEMENT_GROUPE_CONFIRME')
                       if event.donnees.get('confirmation_id') == str(confirmation.id)
                       and event.donnees.get('empreinte') == entity.empreinte_selection]
            if created:
                return True
        for event in self.stock.lignes(EvenementCaisseModel, type='PAIEMENT_GROUPE_RAPPROCHE'):
            data = event.donnees
            if (data.get('confirmation_id') == str(confirmation.id)
                and data.get('dossier_id') == str(entity.id)
                and data.get('session_id') == str(session.id)
                and data.get('empreinte') == entity.empreinte_selection):
                return True
        return False

    def _fidelite_groupe(self, sales, finances, accounts):
        if not accounts:
            return None
        rule = self.cash.bareme('ACQUISITION')
        if not rule:
            return {'points_acquis': 0, 'motif': 'Aucun barème d’acquisition applicable.', 'ventes': [], 'comptes': []}
        by_sale, all_lines, by_account = [], [], {}
        for sale in sales:
            account = accounts.get(sale.id)
            if account is None:
                by_sale.append({'vente_id': str(sale.id), 'compte_id': None, 'points_acquis': 0,
                                'eligible_paye': '0', 'lignes': []})
                continue
            eligible = []
            for line in self.cash.vente.lignes(sale):
                if not line.actif:
                    continue
                product = self.cash.s.get(ProduitModel, line.produit_id)
                if self.cash.categorie_eligible(product.categorie_id, rule):
                    paid = str(finances[sale.id]['lignes'][str(line.id)]['ttc'])
                    eligible.append({'ligne_id': str(line.id), 'ttc_paye': paid})
            base = sum((Decimal(x['ttc_paye']) for x in eligible), Decimal(0))
            # Round once per sale, preserving the P4.5 rule at the sale boundary.
            points = acquisition(base, rule.points, rule.montant_xaf)
            sale_result = {'vente_id': str(sale.id), 'compte_id': str(account.id),
                'client_id': str(account.client_id), 'eligible_paye': str(base),
                'lignes': eligible, 'points_acquis': points}
            by_sale.append(sale_result)
            all_lines.extend({'vente_id': str(sale.id), **line} for line in eligible)
            aggregate = by_account.setdefault(account.id, {'account': account, 'points_acquis': 0,
                'eligible_paye': Decimal(0), 'ventes': []})
            aggregate['points_acquis'] += points
            aggregate['eligible_paye'] += base
            aggregate['ventes'].append(str(sale.id))
        account_results = []
        for account_id, aggregate in by_account.items():
            account = aggregate['account']
            debt_paid = min(aggregate['points_acquis'], account.dette)
            account.dette -= debt_paid
            account.points += aggregate['points_acquis'] - debt_paid
            account.revision += 1
            account_results.append({'compte_id': str(account_id), 'client_id': str(account.client_id),
                'ventes': aggregate['ventes'], 'eligible_paye': str(aggregate['eligible_paye']),
                'points_acquis': aggregate['points_acquis'], 'dette_compensee': debt_paid,
                'solde': account.points, 'dette': account.dette})
        total_points = sum(item['points_acquis'] for item in by_sale)
        return {'bareme': serial(rule), 'eligible_paye': str(sum((Decimal(x['eligible_paye']) for x in by_sale), Decimal(0))),
            'lignes': all_lines, 'ventes': by_sale, 'comptes': account_results,
            'points_acquis': total_points, 'fractions_reportees': False}

    def finaliser(self, key, data):
        entity, group_row, session, _ = self._load_authorized(key)
        if entity.etat not in (EtatDossierGroupe.BROUILLON, EtatDossierGroupe.EN_REGLEMENT):
            raise ConflitStock('Dossier déjà traité ou fermé.')
        if entity.revision != data['revision'] or entity.empreinte_selection != data['empreinte']:
            raise ConflitStock('Révision ou empreinte du dossier modifiée : actualiser.')
        if session.revision != data['revision_session'] or session.etat != 'OUVERTE':
            raise ConflitStock('Session ouverte et révision actuelle requises.')
        picks = [{'vente_id': x.vente_id, 'revision': x.revision_vente} for x in entity.selections]
        sales = self._ventes_autorisees(session, picks)
        if [{'vente_id': str(x.id), 'revision': x.revision} for x in sales] != [
            {'vente_id': str(x['vente_id']), 'revision': x['revision']} for x in data['ventes']]:
            raise ConflitStock('La sélection de ventes a changé depuis la prévisualisation.')
        requested = {str(item['vente_id']): item for item in data['ventes']}
        stored = {str(item.vente_id): item for item in entity.selections}
        if set(requested) != set(stored):
            raise ConflitStock('Les ventes ou leurs bénéficiaires fidélité diffèrent du brouillon.')
        explicit_request_map = any(item.get('compte_id') is not None for item in data['ventes'])
        accounts, account_revisions = {}, {}
        for sale in sales:
            selection = stored[str(sale.id)]
            req = requested[str(sale.id)]
            if int(req['revision']) != selection.revision_vente:
                raise ConflitStock('La révision d’une vente ne correspond plus au brouillon.')
            if explicit_request_map:
                account_id, account_revision = req.get('compte_id'), req.get('revision_compte')
            elif entity.compte_id:
                account_id, account_revision = data.get('compte_id'), data.get('revision_compte')
            else:
                account_id, account_revision = None, None
            if account_id != selection.compte_id:
                raise ConflitStock('Le compte fidélité associé à une vente diffère du brouillon.')
            if account_id is None:
                if account_revision is not None or selection.revision_compte is not None:
                    raise ConflitStock('Révision de compte présente sans bénéficiaire fidélité.')
                continue
            if account_revision is None or int(account_revision) != selection.revision_compte:
                raise ConflitStock('Révision du compte fidélité différente du brouillon.')
            self.stock.access('fidelite.consulter', self.site, sale.emplacement_id)
            account = self.stock.obtenir(CompteFideliteModel, account_id)
            if account.revision != selection.revision_compte:
                raise ConflitStock('Compte fidélité modifié pour une vente : actualiser et reconfirmer le titulaire.')
            client_id = (sale.destinataire or {}).get('client_id')
            if client_id and str(account.client_id) != str(client_id):
                raise PermissionError('Le compte fidélité ne correspond pas au client de cette vente.')
            accounts[sale.id] = account
            account_revisions[sale.id] = selection.revision_compte
        common_ids = {account.id for account in accounts.values()}
        common_account = next(iter(accounts.values())) if len(accounts) == 1 and len(accounts) == len(sales) and len(common_ids) == 1 else None

        finances = {}
        line_rows = []
        sale_totals = {}
        for sale in sales:
            self.cash.verifier_remises(sale)
            finance = self.cash.vente.finance(sale)
            finances[sale.id] = finance
            sale_totals[sale.id] = francs(finance['totaux']['ttc'], True)
            for line in self.cash.vente.lignes(sale):
                if line.actif:
                    line_rows.append({'vente_id': str(sale.id), 'ligne_id': str(line.id),
                        'montant': francs(finance['lignes'][str(line.id)]['ttc'], True)})
        total = sum(sale_totals.values(), Decimal(0))

        group_confirmations = self.stock.lignes(ConfirmationReglementModel, dossier_groupe_id=entity.id)
        individual_confirmations = [c for sale in sales for c in self.stock.lignes(ConfirmationReglementModel, vente_id=sale.id)]
        used, payment_rows = set(), []
        sale_by_id = {sale.id: sale for sale in sales}
        for item in data['reglements']:
            if item['mode'] not in self.cash.config()['modes']:
                raise ValueError('Moyen de paiement non activé.')
            amount = francs(item['montant'])
            confirmation = None
            anchor = None
            if item['mode'] != 'ESPECES':
                if not item.get('confirmation_id'):
                    raise ValueError('Confirmation indépendante obligatoire avant encaissement.')
                confirmation = self.stock.obtenir(ConfirmationReglementModel, item['confirmation_id'])
                if confirmation.id in used:
                    raise ValueError('Confirmation utilisée plusieurs fois.')
                used.add(confirmation.id)
                if confirmation.vente_id:
                    anchor = confirmation.vente_id
                    if anchor not in sale_by_id or not self.cash.rapprochement_compatible(confirmation, sale_by_id[anchor], session):
                        raise ConflitStock('Confirmation individuelle incompatible : rapprocher le paiement de sa vente d’origine.')
                elif confirmation.dossier_groupe_id != entity.id or not self._confirmation_match(confirmation, entity, session):
                    raise ConflitStock('Confirmation groupée incompatible ou non rapprochée.')
                if confirmation.mode != item['mode'] or confirmation.montant != amount:
                    raise ConflitStock('Mode ou montant différent de la confirmation acquise.')
                if self.stock.lignes(ReglementModel, confirmation_id=confirmation.id):
                    raise ConflitStock('Confirmation déjà consommée.')
                if self.stock.lignes(RemboursementModel, confirmation_id=confirmation.id):
                    raise ConflitStock('Confirmation en restitution : encaissement interdit.')
            elif item.get('confirmation_id'):
                raise ValueError('Une confirmation externe ne peut pas être associée aux espèces.')
            payment_rows.append({'mode': item['mode'], 'montant': amount,
                'confirmation_id': confirmation.id if confirmation else None,
                'confirmation': serial(confirmation) if confirmation else None,
                'vente_ancree': anchor})
        payments = repartir_paiements(total, payment_rows)

        pending_group = {c.id for c in group_confirmations if not self.stock.lignes(ReglementModel, confirmation_id=c.id)
            and not self.stock.lignes(RemboursementModel, confirmation_id=c.id, etat='EXECUTE')}
        pending_individual = {c.id for c in individual_confirmations if not self.stock.lignes(ReglementModel, confirmation_id=c.id)
            and not self.stock.lignes(RemboursementModel, confirmation_id=c.id, etat='EXECUTE')}
        if used != pending_group | pending_individual:
            raise ConflitStock('Toutes les confirmations acquises doivent être intégrées ou résolues par restitution.')

        allocated = repartir_allocations(payments, line_rows)
        period = self.cash.periode()
        number = period.prochain_encaissement
        org, site = self.s.get(OrganisationModel, self.org), self.s.get(SiteModel, self.site)
        from neosys_pharma.infrastructure.caisse_pdf import recu_groupe_pdf
        from neosys_pharma.application.caisse_service import now

        fidelity = self._fidelite_groupe(sales, finances, accounts) if accounts else None
        snapshot_sales = []
        for sale in sales:
            detail = self.cash.vente.detail(sale)
            detail['fidelite'] = next((x for x in (fidelity or {}).get('ventes', []) if x['vente_id'] == str(sale.id)), None)
            snapshot_sales.append({'vente_id': str(sale.id), 'revision_avant': sale.revision,
                'numero_appel': detail.get('numero_appel'), 'lignes': detail['lignes'],
                'totaux': detail['totaux'], 'fidelite': detail['fidelite']})
        snapshot = {'type_encaissement': 'GROUPE', 'organisation': org.nom_commercial,
            'site': site.nom, 'date': now().isoformat(), 'numero_encaissement': str(number).zfill(4),
            'periode_z': period.numero, 'caissier_id': str(self.stock.user),
            'etat': 'ENCAISSEE', 'ventes': snapshot_sales,
            'reglements': jsonable_encoder([{k: v for k, v in payment.items() if k != 'vente_ancree'} for payment in payments], custom_encoder={Decimal: str, UUID: str}),
            'fidelite': fidelity, 'total_xaf': str(total), 'ventilation_schema': 1}
        pdf = recu_groupe_pdf({'id': str(entity.id), **snapshot})
        enc = self.stock.ajouter(EncaissementModel, vente_id=None, type_encaissement='GROUPE',
            dossier_groupe_id=entity.id, session_id=session.id, periode_id=period.id,
            numero=number, total_xaf=total, compte_id=common_account.id if common_account else None,
            instantane=snapshot, pdf=pdf, pdf_sha256=hashlib.sha256(pdf).hexdigest())

        ventilations = {}
        for sale in sales:
            finance = finances[sale.id]
            detail = self.cash.vente.detail(sale)
            vent = VentilationEncaissement(organisation_id=self.org, encaissement_id=enc.id,
                vente_id=sale.id, revision_vente=sale.revision,
                montant_ht=Decimal(finance['totaux']['ht']), montant_tva=Decimal(finance['totaux']['tva']),
                net_ttc=sale_totals[sale.id], remise_ligne=Decimal(finance['totaux'].get('remise_ligne', 0)),
                remise_globale=Decimal(finance['totaux'].get('remise_globale', 0)), instantane=detail,
                compte_id=accounts[sale.id].id if sale.id in accounts else None,
                revision_compte=account_revisions.get(sale.id))
            self.repo.ajouter_ventilation(vent)
            ventilations[sale.id] = vent

        reglements = []
        for payment_index, payment in enumerate(payments):
            payment_row = self.stock.ajouter(ReglementModel, encaissement_id=enc.id, mode=payment['mode'],
                montant=payment['montant'], rendu=payment['rendu'], confirmation_id=payment['confirmation_id'])
            reglements.append(payment_row)
            self.stock.ajouter(MouvementCaisseModel, session_id=session.id, reglement_id=payment_row.id,
                auteur_id=self.stock.user, mode=payment_row.mode, montant_net=payment_row.montant-payment_row.rendu)
        reglement_by_index = {i: row for i, row in enumerate(reglements)}
        line_to_vent = {sale.id: ventilations[sale.id] for sale in sales}
        allocations_for_check = []
        for allocation in allocated:
            reglement = reglement_by_index[allocation['payment_index']]
            sale_id, line_id = allocation['vente_id'], allocation['ligne_id']
            item = AllocationReglement(organisation_id=self.org, encaissement_id=enc.id,
                reglement_id=reglement.id, ventilation_id=line_to_vent[sale_id].id,
                vente_id=sale_id, ligne_vente_id=line_id, montant_net=allocation['montant'])
            self.repo.ajouter_allocation(item)
            allocations_for_check.append(item)
        verifier_allocations(list(ventilations.values()), allocations_for_check,
            {r.id: r.montant-r.rendu for r in reglements},
            {(UUID(x['vente_id']), UUID(x['ligne_id'])): x['montant'] for x in line_rows})

        if fidelity and 'bareme' in fidelity:
            for account_result in fidelity['comptes']:
                account_id = UUID(account_result['compte_id'])
                account_sales = [row for row in fidelity['ventes'] if row.get('compte_id') == str(account_id)]
                account_points = sum(row['points_acquis'] for row in account_sales)
                self.stock.ajouter(JournalFideliteModel, compte_id=account_id, encaissement_id=enc.id,
                    auteur_id=self.stock.user, type='ACQUISITION',
                    delta_points=account_points-account_result['dette_compensee'],
                    delta_dette=-account_result['dette_compensee'],
                    details={'bareme': fidelity['bareme'], 'compte': account_result,
                             'ventes': account_sales, 'lignes': [line for line in fidelity['lignes']
                                 if line['vente_id'] in account_result['ventes']]})
        for sale in sales:
            self.cash.consommer_reservations(sale)
            sale.etat = 'ENCAISSEE'
            sale.revision += 1
            self.cash.vente.evenement(sale, 'ENCAISSEMENT_GROUPE', encaissement_id=enc.id,
                dossier_groupe_id=entity.id, numero=number, pdf_sha256=enc.pdf_sha256)
        group_row.etat = EtatDossierGroupe.ENCAISSE.value
        group_row.revision += 1
        period.prochain_encaissement += 1
        session.revision += 1
        self.cash.trace('VENTES_ENCAISSEES_GROUPE', dossier_id=entity.id,
            encaissement_id=enc.id, ventes=[str(v.id) for v in sales], session_id=session.id,
            numero=number, total_xaf=str(total), pdf_sha256=enc.pdf_sha256)
        self.s.flush()
        return serial(enc) | {'ventilations': [{'vente_id': str(sale.id),
            'net_ttc': str(ventilations[sale.id].net_ttc), 'ventilation_id': str(ventilations[sale.id].id)} for sale in sales]}

    def annuler(self, key, data):
        entity, row, session, sales = self._load_authorized(key)
        if entity.revision != data['revision']:
            raise ConflitStock('Dossier modifié : actualiser avant annulation.')
        if entity.etat == EtatDossierGroupe.EN_REGLEMENT:
            confirmations = self.stock.lignes(ConfirmationReglementModel, dossier_groupe_id=entity.id)
            confirmations.extend(c for sale in sales for c in self.stock.lignes(ConfirmationReglementModel,vente_id=sale.id))
            unresolved = [c for c in confirmations if not self.stock.lignes(ReglementModel,confirmation_id=c.id)
                and not self.stock.lignes(RemboursementModel, confirmation_id=c.id, etat='EXECUTE')]
            if unresolved:
                raise ConflitStock('Restituer et confirmer chaque paiement externe acquis avant annulation.')
        elif entity.etat != EtatDossierGroupe.BROUILLON:
            raise ConflitStock('Seul un dossier brouillon ou intégralement restitué peut être annulé.')
        cancelled = entity.transition(EtatDossierGroupe.ANNULE,
            paiements_acquis_resolus=entity.etat == EtatDossierGroupe.EN_REGLEMENT)
        row.etat = cancelled.etat.value
        row.revision = cancelled.revision
        self.cash.trace('DOSSIER_ENCAISSEMENT_GROUPE_ANNULE', dossier_id=entity.id,
            revision=cancelled.revision, justification=data['justification'])
        self.s.flush()
        return self.dossier(key)
