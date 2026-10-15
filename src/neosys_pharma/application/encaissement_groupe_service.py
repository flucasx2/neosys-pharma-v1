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
    value = {
        'session_id': str(session_id),
        'compte_id': str(account_id) if account_id else None,
        'ventes': [{'vente_id': str(row['vente_id']), 'revision': int(row['revision'])} for row in selections],
    }
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

    def previsualiser(self, session_id, revision_session, selections, compte_id=None, revision_compte=None, identite_commune_confirmee=False):
        session = self._session(session_id, revision=revision_session)
        sales = self._ventes_autorisees(session, selections)
        account = self._verifier_identite(sales, compte_id, revision_compte, identite_commune_confirmee)
        items = []
        total = Decimal(0)
        for sale in sales:
            finance = self.cash.vente.finance(sale)
            amount = francs(finance['totaux']['ttc'], True)
            total += amount
            items.append({'vente_id': str(sale.id), 'revision': sale.revision,
                          'numero_appel': self.cash.appel(sale).get('affichage'),
                          'totaux': finance['totaux']})
        return {'session_id': str(session.id), 'revision_session': session.revision,
                'compte_id': str(account.id) if account else None,
                'ventes': items, 'total_xaf': str(total),
                'empreinte': empreinte_selection(session.id, account.id if account else None, selections)}

    def creer(self, data):
        session = self._session(data['session_id'], revision=data['revision_session'])
        sales = self._ventes_autorisees(session, data['ventes'])
        account = self._verifier_identite(sales, data.get('compte_id'), data.get('revision_compte'), data.get('identite_commune_confirmee'))
        fingerprint = empreinte_selection(session.id, account.id if account else None, data['ventes'])
        entity = DossierEncaissementGroupe(
            organisation_id=self.org, site_id=self.site, emplacement_id=session.emplacement_id,
            caisse_id=session.caisse_id, session_id=session.id, auteur_id=self.stock.user,
            compte_id=account.id if account else None, selections=tuple(
                SelectionGroupe(vente_id=UUID(str(row['vente_id'])), revision_vente=row['revision'], ordre=index)
                for index, row in enumerate(data['ventes'], 1)), empreinte_selection=fingerprint)
        self.repo.ajouter_dossier(entity)
        self.cash.trace('DOSSIER_ENCAISSEMENT_GROUPE_CREE', dossier_id=entity.id,
                        ventes=[str(x.vente_id) for x in entity.selections], empreinte=fingerprint,
                        identite_commune_confirmee=True)
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
                'ventes': [{'vente_id': str(x.vente_id), 'revision': x.revision_vente, 'ordre': x.ordre} for x in entity.selections],
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
        account = self._verifier_identite(sales, entity.compte_id, data.get('revision_compte'), data.get('identite_commune_confirmee'))
        fingerprint = empreinte_selection(session.id, account.id if account else None, data['ventes'])
        updated = entity.changer_selection(tuple(
            SelectionGroupe(vente_id=UUID(str(item['vente_id'])), revision_vente=item['revision'], ordre=index)
            for index, item in enumerate(data['ventes'], 1)), fingerprint)
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

    def _fidelite_groupe(self, sales, finances, account):
        if not account:
            return None
        rule = self.cash.bareme('ACQUISITION')
        if not rule:
            return {'points_acquis': 0, 'motif': 'Aucun barème d’acquisition applicable.', 'ventes': []}
        by_sale, all_lines = [], []
        total_points = 0
        for sale in sales:
            eligible = []
            for line in self.cash.vente.lignes(sale):
                if not line.actif:
                    continue
                product = self.cash.s.get(ProduitModel, line.produit_id)
                if self.cash.categorie_eligible(product.categorie_id, rule):
                    paid = str(finances[sale.id]['lignes'][str(line.id)]['ttc'])
                    eligible.append({'ligne_id': str(line.id), 'ttc_paye': paid})
                    all_lines.append({'vente_id': str(sale.id), **eligible[-1]})
            base = sum((Decimal(x['ttc_paye']) for x in eligible), Decimal(0))
            points = acquisition(base, rule.points, rule.montant_xaf)
            total_points += points
            by_sale.append({'vente_id': str(sale.id), 'eligible_paye': str(base), 'lignes': eligible, 'points_acquis': points})
        debt_paid = min(total_points, account.dette)
        account.dette -= debt_paid
        account.points += total_points - debt_paid
        account.revision += 1
        return {'bareme': serial(rule), 'eligible_paye': str(sum((Decimal(x['eligible_paye']) for x in by_sale), Decimal(0))),
            'lignes': all_lines, 'ventes': by_sale, 'points_acquis': total_points,
            'dette_compensee': debt_paid, 'fractions_reportees': False,
            'solde': account.points, 'dette': account.dette}

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
        account = None
        if entity.compte_id:
            self.stock.access('fidelite.consulter', self.site, entity.emplacement_id)
            account = self.stock.obtenir(CompteFideliteModel, entity.compte_id)
            if data.get('compte_id') != entity.compte_id or data.get('revision_compte') != account.revision:
                raise ConflitStock('Compte fidélité modifié : actualiser et reconfirmer le titulaire.')
        elif data.get('compte_id') or data.get('revision_compte') is not None:
            raise ValueError('Compte fidélité différent de celui du dossier.')

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

        fidelity = self._fidelite_groupe(sales, finances, account) if account else None
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
            numero=number, total_xaf=total, compte_id=account.id if account else None,
            instantane=snapshot, pdf=pdf, pdf_sha256=hashlib.sha256(pdf).hexdigest())

        ventilations = {}
        for sale in sales:
            finance = finances[sale.id]
            detail = self.cash.vente.detail(sale)
            vent = VentilationEncaissement(organisation_id=self.org, encaissement_id=enc.id,
                vente_id=sale.id, revision_vente=sale.revision,
                montant_ht=Decimal(finance['totaux']['ht']), montant_tva=Decimal(finance['totaux']['tva']),
                net_ttc=sale_totals[sale.id], remise_ligne=Decimal(finance['totaux'].get('remise_ligne', 0)),
                remise_globale=Decimal(finance['totaux'].get('remise_globale', 0)), instantane=detail)
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

        if account and fidelity and 'bareme' in fidelity:
            self.stock.ajouter(JournalFideliteModel, compte_id=account.id, encaissement_id=enc.id,
                auteur_id=self.stock.user, type='ACQUISITION',
                delta_points=fidelity['points_acquis']-fidelity['dette_compensee'],
                delta_dette=-fidelity['dette_compensee'], details=fidelity)
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
