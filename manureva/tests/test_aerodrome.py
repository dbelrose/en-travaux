# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestAerodrome(common.TransactionCase):

    def setUp(self):
        super(TestAerodrome, self).setUp()

        # Création des données de test
        self.country_pf = self.env.ref('base.pf')

        self.type_aerodrome_tous = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        self.type_aerodrome_etat = self.env['manureva.type_aerodrome'].create({
            'name': 'Etat',
            'a_facturer': False,
        })

        self.balisage_tous = self.env['manureva.balisage'].create({
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'avant': 6.0,
            'apres': 18.0,
            'montant': 689.0,
        })

    def test_01_create_aerodrome(self):
        """Test création d'un aérodrome"""
        aerodrome = self.env['manureva.aerodrome'].create({
            'name': 'NTAA',
            'apt_oaci': 'NTAA',
            'apt_nom': 'TAHITI',
            'aerodrome': 'TAHITI',
            'iata': 'PPT',
            'type_aerodrome_id': self.type_aerodrome_etat.id,
            'country_id': self.country_pf.id,
            'balisage': False,
            'email_ad_pro': False,
        })

        self.assertEqual(aerodrome.name, 'NTAA')
        self.assertEqual(aerodrome.aerodrome, 'TAHITI')
        self.assertFalse(aerodrome.balisage)

    def test_02_aerodrome_unique_constraint(self):
        """Test contrainte d'unicité sur le code OACI"""
        self.env['manureva.aerodrome'].create({
            'name': 'NTTM',
            'apt_oaci': 'NTTM',
            'apt_nom': 'MOOREA',
            'aerodrome': 'MOOREA',
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'country_id': self.country_pf.id,
        })

        with self.assertRaises(Exception):
            self.env['manureva.aerodrome'].create({
                'name': 'NTTM',
                'apt_oaci': 'NTTM',
                'apt_nom': 'MOOREA2',
                'aerodrome': 'MOOREA2',
                'type_aerodrome_id': self.type_aerodrome_tous.id,
                'country_id': self.country_pf.id,
            })

    def test_03_compute_email_pro(self):
        """Test calcul de l'email professionnel"""
        aerodrome = self.env['manureva.aerodrome'].create({
            'name': 'NTTH',
            'apt_oaci': 'NTTH',
            'apt_nom': 'HUAHINE',
            'aerodrome': 'HUAHINE',
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'country_id': self.country_pf.id,
            'email_ad_pro': True,
        })

        self.assertEqual(aerodrome.email_pro, 'huahine.aerodrome@mail.pf')

    def test_04_compute_red_balisage(self):
        """Test calcul de la redevance balisage"""
        aerodrome = self.env['manureva.aerodrome'].create({
            'name': 'NTGF',
            'apt_oaci': 'NTGF',
            'apt_nom': 'FAKARAVA',
            'aerodrome': 'FAKARAVA',
            'type_aerodrome_id': self.type_aerodrome_tous.id,
            'country_id': self.country_pf.id,
            'balisage': True,
        })

        self.assertEqual(aerodrome.red_balisage, 689.0)

    def test_05_aerodrome_no_balisage(self):
        """Test aérodrome sans balisage"""
        aerodrome = self.env['manureva.aerodrome'].create({
            'name': 'NTTB',
            'apt_oaci': 'NTTB',
            'apt_nom': 'BORA BORA',
            'aerodrome': 'BORA BORA',
            'type_aerodrome_id': self.type_aerodrome_etat.id,
            'country_id': self.country_pf.id,
            'balisage': False,
        })

        self.assertEqual(aerodrome.red_balisage, 0)
        self.assertFalse(aerodrome.balisage)
