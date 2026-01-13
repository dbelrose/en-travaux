# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


@tagged('post_install', '-at_install')
class TestPeriodeFacturation(common.TransactionCase):

    def setUp(self):
        super(TestPeriodeFacturation, self).setUp()

        # Création des données de test
        self.country_pf = self.env.ref('base.pf')

        # Type d'aérodrome
        self.type_aerodrome_tous = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        # Aérodrome
        self.aerodrome = self.env['manureva.aerodrome'].create({
            'name': 'NTAA',
            'apt_oaci': 'NTAA',
            'apt_nom': 'TAHITI',
            'aerodrome': 'TAHITI',
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'country_id': self.country_pf.id,
            'balisage': True,
        })

        # Usager
        self.partner = self.env['res.partner'].create({
            'name': 'Air Tahiti',
            'is_company': True,
        })

        self.usager = self.env['manureva.usager'].create({
            'cie_oaci': 'VTA',
            'partner_id': self.partner.id,
        })

        # Type d'aéronef
        self.constructeur_partner = self.env['res.partner'].create({
            'name': 'ATR',
            'is_company': True,
        })

        self.constructeur = self.env['manureva.constructeur'].create({
            'partner_id': self.constructeur_partner.id,
        })

        self.type_aeronef = self.env['manureva.type_aeronef'].create({
            'name': 'AT45',
            'typ_oaci': 'AT45',
            'constructeur_id': self.constructeur.id,
            'tonnage': 18.6,
            'pax': 48,
        })

        # Aéronef
        self.aeronef = self.env['manureva.aeronef'].create({
            'name': 'FORVB',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef.id,
        })

        # Paramètres de calcul
        self.param_att = self.env['manureva.param_att'].create({
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

        self.param_pax = self.env['manureva.param_pax'].create({
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'montant': 149.0,
        })

        self.balisage = self.env['manureva.balisage'].create({
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'avant': 6.0,
            'apres': 18.0,
            'montant': 689.0,
        })

    def test_01_create_periode(self):
        """Test création d'une période"""
        periode = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': self.usager.id,
            'a_facturer': True,
            'facture': False,
        })

        self.assertEqual(periode.annee, 2023)
        self.assertEqual(periode.mois, 6)
        self.assertTrue(periode.a_facturer)
        self.assertFalse(periode.facture)
        self.assertEqual(periode.state, '1a_facturer')

    def test_02_periode_unique_constraint(self):
        """Test contrainte d'unicité sur période"""
        self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 7,
            'usager_id': self.usager.id,
        })

        with self.assertRaises(Exception):
            self.env['manureva.periode'].create({
                'annee': 2023,
                'mois': 7,
                'usager_id': self.usager.id,
            })

    def test_03_compute_name(self):
        """Test calcul du nom de la période"""
        periode = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': self.usager.id,
        })

        self.assertIn('Juin', periode.name)
        self.assertIn('2023', periode.name)
        self.assertIn('VTA', periode.name)

    def test_04_compute_date_debut(self):
        """Test calcul de la date de début"""
        periode = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': self.usager.id,
        })

        expected_date = date(2023, 6, 1)
        self.assertEqual(periode.date_debut, expected_date)

    def test_05_create_seac_creates_periode(self):
        """Test que la création d'un SEAC crée automatiquement une période"""
        date_mvt = date.today()

        seac = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'mouvement': 'A',
            'date': date_mvt,
            'heure_texte': '10:30',
            'pax_plus': 45,
            'pax_moins': 0,
        })

        # Vérifier qu'une période a été créée
        periode = self.env['manureva.periode'].search([
            ('annee', '=', date_mvt.year),
            ('mois', '=', date_mvt.month),
            ('usager_id', '=', self.usager.id),
        ])

        self.assertEqual(len(periode), 1)
        self.assertTrue(periode.a_facturer)

    def test_06_create_facture(self):
        """Test création d'une facture"""
        periode = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': self.usager.id,
        })

        facture = self.env['manureva.facture'].create({
            'facture': 2306001,
            'name': '06/23_VTA_NTAA',
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'periode_id': periode.id,
        })

        self.assertEqual(facture.facture, 2306001)
        self.assertEqual(facture.aerodrome_id, self.aerodrome)
        self.assertEqual(facture.usager_id, self.usager)

    def test_07_create_ligne_facture(self):
        """Test création d'une ligne de facture"""
        periode = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': self.usager.id,
        })

        facture = self.env['manureva.facture'].create({
            'facture': 2306001,
            'name': '06/23_VTA_NTAA',
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'periode_id': periode.id,
        })

        ligne = self.env['manureva.ligne_facture'].create({
            'facture_id': facture.id,
            'type_aeronef_id': self.type_aeronef.id,
            'atterrissage': 5000.0,
            'passager': 7450.0,
            'balisage': 689.0,
        })

        self.assertEqual(ligne.atterrissage, 5000.0)
        self.assertEqual(ligne.passager, 7450.0)
        self.assertEqual(ligne.balisage, 689.0)
        self.assertEqual(ligne.name, 'AT45')

    def test_08_supprimer_facture_periode(self):
        """Test suppression des factures d'une période"""
        periode = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': self.usager.id,
            'facture': True,
            'state': '2facture',
        })

        facture = self.env['manureva.facture'].create({
            'facture': 2306001,
            'name': '06/23_VTA_NTAA',
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'periode_id': periode.id,
        })

        periode.supprimer_facture_periode()

        self.assertTrue(periode.a_facturer)
        self.assertFalse(periode.facture)
        self.assertEqual(periode.state, '1a_facturer')
        self.assertFalse(self.env['manureva.facture'].search([('id', '=', facture.id)]))

    def test_09_compute_state(self):
        """Test calcul de l'état de la période"""
        periode = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': self.usager.id,
            'a_facturer': True,
            'facture': False,
        })

        self.assertEqual(periode.state, '1a_facturer')

        # Création d'une facture
        self.env['manureva.facture'].create({
            'facture': 2306001,
            'name': '06/23_VTA_NTAA',
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'periode_id': periode.id,
        })

        periode._compute_state()
        self.assertEqual(periode.state, '2facture')
