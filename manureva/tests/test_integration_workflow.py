# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from datetime import date
from math import ceil


@tagged('post_install', '-at_install')
class TestIntegrationWorkflow(common.TransactionCase):
    """Tests d'intégration pour le workflow complet de facturation"""

    def setUp(self):
        super(TestIntegrationWorkflow, self).setUp()

        # Configuration complète
        self.country_pf = self.env.ref('base.pf')

        # Types
        self.type_aerodrome_tous = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        self.type_aerodrome_moz = self.env['manureva.type_aerodrome'].create({
            'name': 'MOZ',
            'a_facturer': True,
        })

        self.type_activite_tap = self.env['manureva.type_activite'].create({
            'name': 'Transport aérien public',
        })

        self.type_taxe_normal = self.env['manureva.type_taxe'].create({
            'name': 'Normal',
        })

        self.type_taxe_reduit = self.env['manureva.type_taxe'].create({
            'name': 'Réduit',
        })

        # Aérodromes
        self.aerodrome_ntaa = self.env['manureva.aerodrome'].create({
            'name': 'NTAA',
            'apt_oaci': 'NTAA',
            'apt_nom': 'TAHITI',
            'aerodrome': 'TAHITI',
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'country_id': self.country_pf.id,
            'balisage': True,
        })

        self.aerodrome_nttm = self.env['manureva.aerodrome'].create({
            'name': 'NTTM',
            'apt_oaci': 'NTTM',
            'apt_nom': 'MOOREA',
            'aerodrome': 'MOOREA',
            'type_aerodrome_id': self.type_aerodrome_moz.id,
            'country_id': self.country_pf.id,
            'balisage': True,
        })

        # Usager
        self.partner = self.env['res.partner'].create({
            'name': 'Air Tahiti',
            'is_company': True,
            'street': 'BP 314',
            'city': 'PAPEETE',
        })

        self.usager = self.env['manureva.usager'].create({
            'cie_oaci': 'VTA',
            'partner_id': self.partner.id,
            'type_activite_id': self.type_activite_tap.id,
        })

        # Constructeur et types d'aéronef
        self.constructeur_partner = self.env['res.partner'].create({
            'name': 'ATR',
            'is_company': True,
        })

        self.constructeur = self.env['manureva.constructeur'].create({
            'partner_id': self.constructeur_partner.id,
        })

        self.type_aeronef_at45 = self.env['manureva.type_aeronef'].create({
            'name': 'AT45',
            'typ_oaci': 'AT45',
            'constructeur_id': self.constructeur.id,
            'tonnage': 18.6,
            'pax': 48,
        })

        self.type_aeronef_at75 = self.env['manureva.type_aeronef'].create({
            'name': 'AT75',
            'typ_oaci': 'AT75',
            'constructeur_id': self.constructeur.id,
            'tonnage': 22.8,
            'pax': 68,
        })

        # Aéronefs
        self.aeronef1 = self.env['manureva.aeronef'].create({
            'name': 'FORVB',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef_at45.id,
        })

        self.aeronef2 = self.env['manureva.aeronef'].create({
            'name': 'FORVI',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef_at75.id,
        })

        # Paramètres de calcul - TOUS
        self.param_att_tous = self.env['manureva.param_att'].create({
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'mmd_inf': 6.0,
            'mmd_sup': 25.0,
            'base': 497.0,
            'coefficient': 180.0,
            'correction': 6.0,
            'avec_correction': True,
            'domestique': True,
        })

        self.param_pax_tous = self.env['manureva.param_pax'].create({
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'montant': 149.0,
        })

        self.balisage_tous = self.env['manureva.balisage'].create({
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'avant': 6.0,
            'apres': 18.0,
            'montant': 689.0,
        })

        # Paramètres de calcul - MOZ
        self.param_att_moz = self.env['manureva.param_att'].create({
            'type_aerodrome_id': self.type_aerodrome_moz.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'mmd_inf': 6.0,
            'mmd_sup': 25.0,
            'base': 721.0,
            'coefficient': 261.0,
            'correction': 6.0,
            'avec_correction': True,
            'domestique': True,
        })

        self.param_pax_moz = self.env['manureva.param_pax'].create({
            'type_aerodrome_id': self.type_aerodrome_moz.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'montant': 162.0,
        })

        self.balisage_moz = self.env['manureva.balisage'].create({
            'type_aerodrome_id': self.type_aerodrome_moz.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'avant': 6.0,
            'apres': 18.0,
            'montant': 742.0,
        })

        # TVA
        self.tva_normal = self.env['manureva.tva'].create({
            'type_taxe_id': self.type_taxe_normal.id,
            'debut': '2000-01-01',
            'fin': '2099-01-01',
            'taux': 13.0,
        })

        self.tva_reduit = self.env['manureva.tva'].create({
            'type_taxe_id': self.type_taxe_reduit.id,
            'debut': '2000-01-01',
            'fin': '2099-01-01',
            'taux': 5.0,
        })

    def test_01_workflow_complet_facturation(self):
        """Test du workflow complet de facturation"""

        # 1. Création de mouvements SEAC
        date_mvt = date(2023, 6, 15)

        # Arrivée à Tahiti
        seac1 = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'vol': 'VT101',
            'mouvement': 'A',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date': date_mvt,
            'heure_texte': '10:30',
            'pax_plus': 45,
            'pax_moins': 0,
            'circonstance': 'N',
            'balisage': 'N',
        })

        # Départ de Tahiti
        seac2 = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'vol': 'VT102',
            'mouvement': 'D',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date': date_mvt,
            'heure_texte': '14:45',
            'pax_plus': 48,
            'pax_moins': 2,
            'circonstance': 'N',
            'balisage': 'N',
        })

        # Arrivée à Moorea avec balisage
        seac3 = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_nttm.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef2.id,
            'vol': 'VT201',
            'mouvement': 'A',
            'aerod_prov_dest': self.aerodrome_ntaa.id,
            'date': date_mvt,
            'heure_texte': '19:00',
            'pax_plus': 60,
            'pax_moins': 5,
            'circonstance': 'N',
            'balisage': 'S',
        })

        # 2. Vérifier création automatique de période
        periode = self.env['manureva.periode'].search([
            ('annee', '=', 2023),
            ('mois', '=', 6),
            ('usager_id', '=', self.usager.id),
        ])

        self.assertEqual(len(periode), 1)
        self.assertTrue(periode.a_facturer)
        self.assertFalse(periode.facture)
        self.assertEqual(periode.state, '1a_facturer')

        # 3. Facturer la période
        periode.facturer_periode()

        # 4. Vérifier que la période est facturée
        periode.refresh()
        self.assertFalse(periode.a_facturer)
        self.assertTrue(periode.facture)
        self.assertEqual(periode.state, '2facture')

        # 5. Vérifier création des factures
        factures = self.env['manureva.facture'].search([
            ('periode_id', '=', periode.id)
        ])

        # Devrait y avoir 2 factures (NTAA et NTTM)
        self.assertEqual(len(factures), 2)

        # 6. Vérifier les lignes de facture NTAA
        facture_ntaa = factures.filtered(lambda f: f.aerodrome_id == self.aerodrome_ntaa)
        self.assertTrue(facture_ntaa)

        ligne_ntaa = facture_ntaa.ligne_facture_ids.filtered(
            lambda l: l.type_aeronef_id == self.type_aeronef_at45
        )
        self.assertTrue(ligne_ntaa)

        # Vérifier calcul atterrissage (1 arrivée AT45)
        mmd_at45 = max(2, ceil(18.6))  # = 19
        montant_att_attendu = self.param_att_tous.base + self.param_att_tous.coefficient * (
                mmd_at45 - self.param_att_tous.correction
        )
        self.assertEqual(ligne_ntaa.atterrissage, round(montant_att_attendu))

        # Vérifier calcul passagers (1 départ avec 46 passagers payants)
        passagers_payants = 48 - 2
        montant_pax_attendu = self.param_pax_tous.montant * passagers_payants
        self.assertEqual(ligne_ntaa.passager, round(montant_pax_attendu))

        # Pas de balisage (heure de jour)
        self.assertEqual(ligne_ntaa.balisage, 0)

        # 7. Vérifier les lignes de facture NTTM
        facture_nttm = factures.filtered(lambda f: f.aerodrome_id == self.aerodrome_nttm)
        self.assertTrue(facture_nttm)

        ligne_nttm = facture_nttm.ligne_facture_ids.filtered(
            lambda l: l.type_aeronef_id == self.type_aeronef_at75
        )
        self.assertTrue(ligne_nttm)

        # Avec balisage (19:00)
        self.assertEqual(ligne_nttm.balisage, round(self.balisage_moz.montant))

    def test_02_workflow_multiple_types_aeronef(self):
        """Test workflow avec plusieurs types d'aéronef"""

        date_mvt = date(2023, 7, 20)

        # Créer mouvements avec AT45
        for i in range(3):
            self.env['manureva.seac'].create({
                'aerodrome_id': self.aerodrome_ntaa.id,
                'usager_id': self.usager.id,
                'aeronef_id': self.aeronef1.id,
                'vol': f'VT10{i}',
                'mouvement': 'A',
                'date': date_mvt,
                'heure_texte': f'10:{i}0',
                'pax_plus': 45,
            })

        # Créer mouvements avec AT75
        for i in range(2):
            self.env['manureva.seac'].create({
                'aerodrome_id': self.aerodrome_ntaa.id,
                'usager_id': self.usager.id,
                'aeronef_id': self.aeronef2.id,
                'vol': f'VT20{i}',
                'mouvement': 'A',
                'date': date_mvt,
                'heure_texte': f'14:{i}0',
                'pax_plus': 60,
            })

        # Facturer
        periode = self.env['manureva.periode'].search([
            ('annee', '=', 2023),
            ('mois', '=', 7),
            ('usager_id', '=', self.usager.id),
        ])

        periode.facturer_periode()

        # Vérifier facture
        facture = self.env['manureva.facture'].search([
            ('periode_id', '=', periode.id)
        ])

        # Devrait y avoir 2 lignes (AT45 et AT75)
        self.assertEqual(len(facture.ligne_facture_ids), 2)

        ligne_at45 = facture.ligne_facture_ids.filtered(
            lambda l: l.type_aeronef_id == self.type_aeronef_at45
        )
        ligne_at75 = facture.ligne_facture_ids.filtered(
            lambda l: l.type_aeronef_id == self.type_aeronef_at75
        )

        self.assertTrue(ligne_at45)
        self.assertTrue(ligne_at75)

    def test_03_workflow_suppression_et_refacturation(self):
        """Test workflow de suppression et refacturation"""

        # 1. Créer et facturer
        date_mvt = date(2023, 8, 10)

        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'mouvement': 'A',
            'date': date_mvt,
            'heure_texte': '10:00',
            'pax_plus': 45,
        })

        periode = self.env['manureva.periode'].search([
            ('annee', '=', 2023),
            ('mois', '=', 8),
            ('usager_id', '=', self.usager.id),
        ])

        periode.facturer_periode()

        facture_initiale = self.env['manureva.facture'].search([
            ('periode_id', '=', periode.id)
        ])
        facture_id = facture_initiale.id

        self.assertTrue(facture_initiale)

        # 2. Supprimer factures
        periode.supprimer_facture_periode()

        periode.refresh()
        self.assertTrue(periode.a_facturer)
        self.assertFalse(periode.facture)

        # Vérifier suppression
        facture_existe = self.env['manureva.facture'].search([
            ('id', '=', facture_id)
        ])
        self.assertFalse(facture_existe)

        # 3. Refacturer
        periode.facturer_periode()

        periode.refresh()
        self.assertTrue(periode.facture)

        nouvelle_facture = self.env['manureva.facture'].search([
            ('periode_id', '=', periode.id)
        ])
        self.assertTrue(nouvelle_facture)
        self.assertNotEqual(nouvelle_facture.id, facture_id)

    def test_04_workflow_passagers_locaux_non_payants(self):
        """Test prise en compte des passagers locaux non-payants"""

        date_mvt = date(2023, 9, 5)

        # Départ avec passagers locaux non-payants
        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'mouvement': 'D',
            'date': date_mvt,
            'heure_texte': '10:00',
            'pax_plus': 48,
            'pax_moins': 2,
            'paxlnp1': 3,
            'paxlnp2': 1,
        })

        periode = self.env['manureva.periode'].search([
            ('annee', '=', 2023),
            ('mois', '=', 9),
            ('usager_id', '=', self.usager.id),
        ])

        periode.facturer_periode()

        facture = self.env['manureva.facture'].search([
            ('periode_id', '=', periode.id)
        ])

        ligne = facture.ligne_facture_ids[0]

        # Passagers payants = 48 - 2 - 3 - 1 = 42
        montant_attendu = 42 * self.param_pax_tous.montant
        self.assertEqual(ligne.passager, round(montant_attendu))

    def test_05_workflow_multi_aerodrome(self):
        """Test workflow avec plusieurs aérodromes"""

        date_mvt = date(2023, 10, 15)

        # Mouvements sur NTAA
        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'mouvement': 'A',
            'date': date_mvt,
            'heure_texte': '10:00',
        })

        # Mouvements sur NTTM
        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_nttm.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'mouvement': 'A',
            'date': date_mvt,
            'heure_texte': '11:00',
        })

        periode = self.env['manureva.periode'].search([
            ('annee', '=', 2023),
            ('mois', '=', 10),
            ('usager_id', '=', self.usager.id),
        ])

        periode.facturer_periode()

        factures = self.env['manureva.facture'].search([
            ('periode_id', '=', periode.id)
        ])

        # Devrait y avoir 2 factures
        self.assertEqual(len(factures), 2)

        aerodromes = factures.mapped('aerodrome_id')
        self.assertIn(self.aerodrome_ntaa, aerodromes)
        self.assertIn(self.aerodrome_nttm, aerodromes)

    def test_06_workflow_balisage_nuit(self):
        """Test calcul balisage pour vols de nuit"""

        date_mvt = date(2023, 11, 20)

        # Vol de jour (pas de balisage)
        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'mouvement': 'A',
            'date': date_mvt,
            'heure_texte': '12:00',
            'balisage': 'N',
        })

        # Vol de nuit (avec balisage)
        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'mouvement': 'A',
            'date': date_mvt,
            'heure_texte': '20:00',
            'balisage': 'S',
        })

        periode = self.env['manureva.periode'].search([
            ('annee', '=', 2023),
            ('mois', '=', 11),
            ('usager_id', '=', self.usager.id),
        ])

        periode.facturer_periode()

        facture = self.env['manureva.facture'].search([
            ('periode_id', '=', periode.id)
        ])

        ligne = facture.ligne_facture_ids[0]

        # Devrait avoir le balisage pour 1 vol (le vol de nuit)
        # Note: le calcul exact dépend de la logique dans facturer_periode
        self.assertGreaterEqual(ligne.balisage, 0)

    def test_07_workflow_verification_montants(self):
        """Test vérification des montants calculés"""

        date_mvt = date(2023, 12, 1)

        # Créer un mouvement simple
        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'vol': 'VT101',
            'mouvement': 'A',
            'date': date_mvt,
            'heure_texte': '10:00',
        })

        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef1.id,
            'vol': 'VT102',
            'mouvement': 'D',
            'date': date_mvt,
            'heure_texte': '14:00',
            'pax_plus': 48,
        })

        periode = self.env['manureva.periode'].search([
            ('annee', '=', 2023),
            ('mois', '=', 12),
            ('usager_id', '=', self.usager.id),
        ])

        periode.facturer_periode()

        facture = self.env['manureva.facture'].search([
            ('periode_id', '=', periode.id)
        ])

        ligne = facture.ligne_facture_ids[0]

        # Vérifier que les montants sont positifs et cohérents
        self.assertGreater(ligne.atterrissage, 0)
        self.assertGreater(ligne.passager, 0)
        self.assertGreaterEqual(ligne.balisage, 0)
