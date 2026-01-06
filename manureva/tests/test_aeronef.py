# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestAeronef(common.TransactionCase):

    def setUp(self):
        super(TestAeronef, self).setUp()

        # Création des données de test
        self.partner = self.env['res.partner'].create({
            'name': 'Air Tahiti',
            'is_company': True,
        })

        self.usager = self.env['manureva.usager'].create({
            'cie_oaci': 'VTA',
            'partner_id': self.partner.id,
        })

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

    def test_01_create_aeronef(self):
        """Test création d'un aéronef"""
        aeronef = self.env['manureva.aeronef'].create({
            'name': 'FORVB',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef.id,
            'pax': 48,
        })

        self.assertEqual(aeronef.name, 'FORVB')
        self.assertEqual(aeronef.pax, 48)
        self.assertEqual(aeronef.tonnage, 18.6)
        self.assertEqual(aeronef.typ_oaci, 'AT45')

    def test_02_aeronef_unique_constraint(self):
        """Test contrainte d'unicité sur l'immatriculation"""
        self.env['manureva.aeronef'].create({
            'name': 'FORVC',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef.id,
        })

        with self.assertRaises(Exception):
            self.env['manureva.aeronef'].create({
                'name': 'FORVC',
                'usager_id': self.usager.id,
                'type_aeronef_id': self.type_aeronef.id,
            })

    def test_03_onchange_type_aeronef(self):
        """Test onchange du type d'aéronef"""
        aeronef = self.env['manureva.aeronef'].new({
            'name': 'FORVI',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef.id,
        })

        aeronef._onchange_type_aeronef_id()
        self.assertEqual(aeronef.pax, 48)

    def test_04_related_fields(self):
        """Test des champs relationnels"""
        aeronef = self.env['manureva.aeronef'].create({
            'name': 'FORVN',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef.id,
        })

        self.assertEqual(aeronef.constructeur_id.name, 'ATR')
        self.assertEqual(aeronef.typ_oaci, 'AT45')
        self.assertEqual(aeronef.tonnage, 18.6)

    def test_05_default_pax(self):
        """Test valeur par défaut du nombre de sièges"""
        aeronef = self.env['manureva.aeronef'].create({
            'name': 'FORVO',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef.id,
        })

        # Le pax devrait être celui du type d'aéronef
        self.assertEqual(aeronef.pax, 48)
