"""Tests unitaires P4-C sans base de données ni dépendance d'infrastructure."""
from decimal import Decimal
import unittest
from uuid import uuid4

from neosys_pharma.domain.encaissement_groupe import (
    AllocationReglement,
    DossierEncaissementGroupe,
    EtatDossierEncaissementGroupe as Etat,
    ReglementGroupe,
    VenteGroupe,
    repartir_automatiquement,
    valider_allocations,
)


def ventes(*dues):
    return [VenteGroupe(uuid4(), order, 1, Decimal(due)) for order, due in enumerate(dues, 1)]


class TestEncaissementGroupeDomain(unittest.TestCase):
    def test_ventilation_automatique_deterministe_par_ordre_ticket_puis_reglement(self):
        sale1, sale2 = ventes(100, 200)
        payment1 = ReglementGroupe(uuid4(), 1, "CARTE", 150, confirmation_id=uuid4())
        payment2 = ReglementGroupe(uuid4(), 2, "ESPECES", 170, rendu=20)

        rows = repartir_automatiquement([sale2, sale1], [payment2, payment1])

        self.assertEqual(
            [(row.reglement_id, row.vente_id, row.montant) for row in rows],
            [
                (payment1.reglement_id, sale1.vente_id, Decimal(100)),
                (payment1.reglement_id, sale2.vente_id, Decimal(50)),
                (payment2.reglement_id, sale2.vente_id, Decimal(150)),
            ],
        )
        self.assertTrue(valider_allocations([sale1, sale2], [payment1, payment2], rows))

    def test_allocation_manuelle_equilibree_est_acceptee_et_non_reparee(self):
        sale1, sale2 = ventes(100, 200)
        payment = ReglementGroupe(uuid4(), 1, "ESPECES", 300)
        first = ReglementGroupe(uuid4(), 1, "ESPECES", 150)
        second = ReglementGroupe(uuid4(), 2, "ESPECES", 150)
        rows = [
            AllocationReglement(first.reglement_id, sale1.vente_id, 80),
            AllocationReglement(first.reglement_id, sale2.vente_id, 70),
            AllocationReglement(second.reglement_id, sale1.vente_id, 20),
            AllocationReglement(second.reglement_id, sale2.vente_id, 130),
        ]
        self.assertTrue(valider_allocations([sale1, sale2], [first, second], rows))

    def test_allocation_manuelle_incorrecte_est_refusee(self):
        for builder in (
            lambda p, a, b: [AllocationReglement(p.reglement_id, a.vente_id, 90), AllocationReglement(p.reglement_id, b.vente_id, 210)],
            lambda p, a, b: [AllocationReglement(p.reglement_id, a.vente_id, 110), AllocationReglement(p.reglement_id, b.vente_id, 190)],
            lambda p, a, b: [AllocationReglement(p.reglement_id, a.vente_id, 100)],
        ):
            sale1, sale2 = ventes(100, 200)
            payment = ReglementGroupe(uuid4(), 1, "ESPECES", 300)
            with self.subTest(builder=builder), self.assertRaises(ValueError):
                valider_allocations([sale1, sale2], [payment], builder(payment, sale1, sale2))

    def test_reglement_refuse_fractionnaire_rendu_non_especes_et_confirmation_absente(self):
        with self.assertRaises(ValueError):
            ReglementGroupe(uuid4(), 1, "ESPECES", Decimal("1.5"))
        with self.assertRaises(ValueError):
            ReglementGroupe(uuid4(), 1, "CARTE", 100, rendu=1, confirmation_id=uuid4())
        with self.assertRaises(ValueError):
            ReglementGroupe(uuid4(), 1, "VIREMENT", 100)
        with self.assertRaises(ValueError):
            ReglementGroupe(uuid4(), 1, "ESPECES", 100, confirmation_id=uuid4())

    def test_excedent_non_especes_et_net_insuffisant_sont_refuses(self):
        sale = ventes(100)[0]
        with self.assertRaisesRegex(ValueError, "excédent non espèces"):
            repartir_automatiquement([sale], [ReglementGroupe(uuid4(), 1, "CARTE", 101, confirmation_id=uuid4())])
        with self.assertRaisesRegex(ValueError, "couvrir exactement"):
            repartir_automatiquement([sale], [ReglementGroupe(uuid4(), 1, "ESPECES", 99)])

    def test_dossier_brouillon_peut_etre_finalise_ou_abandonne_une_seule_fois(self):
        dossier = DossierEncaissementGroupe(uuid4(), uuid4(), uuid4(), uuid4(), uuid4())
        finalise = dossier.transitionner(Etat.FINALISE, cle_idempotence="k1", empreinte_requete="a" * 64)
        abandonne = dossier.transitionner(Etat.ABANDONNE)
        self.assertEqual((finalise.etat, finalise.revision), (Etat.FINALISE, 2))
        self.assertEqual((abandonne.etat, abandonne.revision), (Etat.ABANDONNE, 2))
        with self.assertRaises(ValueError):
            finalise.transitionner(Etat.ABANDONNE)
        with self.assertRaises(ValueError):
            dossier.transitionner(Etat.FINALISE)
        with self.assertRaises(ValueError):
            dossier.transitionner(Etat.FINALISE, cle_idempotence="k1", empreinte_requete="different")


if __name__ == "__main__":
    unittest.main()
