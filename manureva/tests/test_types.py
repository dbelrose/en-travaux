# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestTypes(common.TransactionCase):

    def setUp(self):
        super(TestTypes, self).setUp()

    def test_01_create_type_activite(self):
        """Test création type d'activité"""
        type_activite = self.env['manureva.type_activite'].create({
            'name': 'Transport aérien public',
        })

        self.assertEqual(type_activite.name, 'Transport aérien public')

    def test_02_type_activite_unique(self):
        """Test contrainte d'unicité type d'activité"""
        self.env['manureva.type_activite'].create({
            'name': 'Aviation générale',
        })

        with self.assertRaises(Exception):
            self.env['manureva.type_activite'].create({
                'name': 'Aviation générale',
            })

    def test_03_create_type_aerodrome(self):
        """Test création type d'aérodrome"""
        type_aerodrome = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        self.assertEqual(type_aerodrome.name, 'Tous')
        self.assertTrue(type_aerodrome.a_facturer)

    def test_04_type_aerodrome_a_facturer(self):
        """Test type d'aérodrome à facturer"""
        type_facturable = self.env['manureva.type_aerodrome'].create({
            'name': 'MOZ',
            'a_facturer': True,
        })

        type_non_facturable = self.env['manureva.type_aerodrome'].create({
            'name': 'Privé',
            'a_facturer': False,
        })

        self.assertTrue(type_facturable.a_facturer)
        self.assertFalse(type_non_facturable.a_facturer)

    def test_05_type_aerodrome_unique(self):
        """Test contrainte d'unicité type d'aérodrome"""
        self.env['manureva.type_aerodrome'].create({
            'name': 'Etat',
            'a_facturer': False,
        })

        with self.assertRaises(Exception):
            self.env['manureva.type_aerodrome'].create({
                'name': 'Etat',
                'a_facturer': True,
            })

    def test_06_create_type_aeronef(self):
        """Test création type d'aéronef"""
        constructeur_partner = self.env['res.partner'].create({
            'name': 'ATR',
            'is_company': True,
        })

        constructeur = self.env['manureva.constructeur'].create({
            'partner_id': constructeur_partner.id,
        })

        type_aeronef = self.env['manureva.type_aeronef'].create({
            'name': 'AT45',
            'typ_oaci': 'AT45',
            'constructeur_id': constructeur.id,
            'tonnage': 18.6,
            'pax': 48,
        })

        self.assertEqual(type_aeronef.name, 'AT45')
        self.assertEqual(type_aeronef.typ_oaci, 'AT45')
        self.assertEqual(type_aeronef.tonnage, 18.6)
        self.assertEqual(type_aeronef.pax, 48)

    def test_07_type_aeronef_unique(self):
        """Test contrainte d'unicité type d'aéronef"""
        constructeur_partner = self.env['res.partner'].create({
            'name': 'ATR',
            'is_company': True,
        })

        constructeur = self.env['manureva.constructeur'].create({
            'partner_id': constructeur_partner.id,
        })

        self.env['manureva.type_aeronef'].create({
            'name': 'AT75',
            'typ_oaci': 'AT75',
            'constructeur_id': constructeur.id,
            'tonnage': 22.8,
            'pax': 68,
        })

        with self.assertRaises(Exception):
            self.env['manureva.type_aeronef'].create({
                'name': 'AT75',
                'typ_oaci': 'AT75',
                'constructeur_id': constructeur.id,
                'tonnage': 22.8,
                'pax': 68,
            })

    def test_08_onchange_oaci_type_aeronef(self):
        """Test onchange du code OACI pour type d'aéronef"""
        constructeur_partner = self.env['res.partner'].create({
            'name': 'Beechcraft',
            'is_company': True,
        })

        constructeur = self.env['manureva.constructeur'].create({
            'partner_id': constructeur_partner.id,
        })

        type_aeronef = self.env['manureva.type_aeronef'].new({
            'typ_oaci': 'BE20',
            'constructeur_id': constructeur.id,
        })

        type_aeronef._onchange_oaci()
        self.assertEqual(type_aeronef.name, 'BE20')

    def test_09_create_constructeur(self):
        """Test création constructeur"""
        partner = self.env['res.partner'].create({
            'name': 'De Havilland',
            'is_company': True,
        })

        constructeur = self.env['manureva.constructeur'].create({
            'partner_id': partner.id,
        })

        self.assertEqual(constructeur.name, 'De Havilland')
        self.assertTrue(constructeur.is_company)

    def test_10_relation_constructeur_types(self):
        """Test relation constructeur - types d'aéronef"""
        partner = self.env['res.partner'].create({
            'name': 'Airbus',
            'is_company': True,
        })

        constructeur = self.env['manureva.constructeur'].create({
            'partner_id': partner.id,
        })

        type1 = self.env['manureva.type_aeronef'].create({
            'name': 'A320',
            'typ_oaci': 'A320',
            'constructeur_id': constructeur.id,
            'tonnage': 78.0,
            'pax': 180,
        })

        type2 = self.env['manureva.type_aeronef'].create({
            'name': 'A321',
            'typ_oaci': 'A321',
            'constructeur_id': constructeur.id,
            'tonnage': 93.5,
            'pax': 220,
        })

        self.assertEqual(len(constructeur.type_aeronef_ids), 2)
        self.assertIn(type1, constructeur.type_aeronef_ids)
        self.assertIn(type2, constructeur.type_aeronef_ids)
