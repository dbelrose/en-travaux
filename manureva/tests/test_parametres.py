# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from datetime import date


@tagged('post_install', '-at_install')
class TestParametres(common.TransactionCase):

    def setUp(self):
        super(TestParametres, self).setUp()

        self.type_aerodrome = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        self.type_taxe_normal = self.env['manureva.type_taxe'].create({
            'name': 'Normal',
        })

        self.type_taxe_reduit = self.env['manureva.type_taxe'].create({
            'name': 'Réduit',
        })

    def test_01_create_tva_normal(self):
        """Test création TVA normale"""
        tva = self.env['manureva.tva'].create({
            'type_taxe_id': self.type_taxe_normal.id,
            'debut': '2000-01-01',
            'fin': '2099-01-01',
            'taux': 13.0,
        })

        self.assertEqual(tva.taux, 13.0)
        self.assertEqual(tva.name, 'Normal')
        self.assertTrue(tva.active)

    def test_02_create_tva_reduit(self):
        """Test création TVA réduite"""
        tva = self.env['manureva.tva'].create({
            'type_taxe_id': self.type_taxe_reduit.id,
            'debut': '2000-01-01',
            'fin': '2099-01-01',
            'taux': 5.0,
        })

        self.assertEqual(tva.taux, 5.0)
        self.assertEqual(tva.name, 'Réduit')

    def test_03_tva_constraint_dates(self):
        """Test contrainte dates TVA"""
        with self.assertRaises(Exception):
            self.env['manureva.tva'].create({
                'type_taxe_id': self.type_taxe_normal.id,
                'debut': '2023-12-31',
                'fin': '2023-01-01',
                'taux': 13.0,
            })

    def test_04_create_balisage(self):
        """Test création paramètre balisage"""
        balisage = self.env['manureva.balisage'].create({
            'type_aerodrome_id': self.type_aerodrome.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'avant': 6.0,
            'apres': 18.0,
            'montant': 689.0,
        })

        self.assertEqual(balisage.montant, 689.0)
        self.assertEqual(balisage.avant, 6.0)
        self.assertEqual(balisage.apres, 18.0)
        self.assertTrue(balisage.active)

    def test_05_create_param_att(self):
        """Test création paramètre atterrissage"""
        param = self.env['manureva.param_att'].create({
            'type_aerodrome_id': self.type_aerodrome.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'mmd_inf': 2.0,
            'mmd_sup': 6.0,
            'base': 165.0,
            'coefficient': 83.0,
            'correction': 2.0,
            'avec_correction': True,
            'domestique': True,
        })

        self.assertEqual(param.base, 165.0)
        self.assertEqual(param.coefficient, 83.0)
        self.assertTrue(param.avec_correction)
        self.assertTrue(param.active)

    def test_06_create_param_pax(self):
        """Test création paramètre passager"""
        param = self.env['manureva.param_pax'].create({
            'type_aerodrome_id': self.type_aerodrome.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'montant': 149.0,
        })

        self.assertEqual(param.montant, 149.0)
        self.assertTrue(param.active)

    def test_07_param_att_unique_constraint(self):
        """Test contrainte d'unicité paramètre atterrissage"""
        self.env['manureva.param_att'].create({
            'type_aerodrome_id': self.type_aerodrome.id,
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

        with self.assertRaises(Exception):
            self.env['manureva.param_att'].create({
                'type_aerodrome_id': self.type_aerodrome.id,
                'debut': '2000-01-01',
                'fin': '2099-12-31',
                'mmd_inf': 6.0,
                'mmd_sup': 25.0,
                'base': 500.0,
                'coefficient': 180.0,
                'correction': 6.0,
                'avec_correction': True,
                'domestique': True,
            })

    def test_08_compute_active_tva(self):
        """Test calcul du statut actif pour TVA"""
        # TVA future
        tva_future = self.env['manureva.tva'].create({
            'type_taxe_id': self.type_taxe_normal.id,
            'debut': '2099-01-01',
            'fin': '2099-12-31',
            'taux': 15.0,
        })

        self.assertFalse(tva_future.active)

        # TVA en cours
        tva_actuelle = self.env['manureva.tva'].create({
            'type_taxe_id': self.type_taxe_normal.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'taux': 13.0,
        })

        self.assertTrue(tva_actuelle.active)

    def test_09_compute_active_param_att(self):
        """Test calcul du statut actif pour paramètre atterrissage"""
        # Paramètre passé
        param_passe = self.env['manureva.param_att'].create({
            'type_aerodrome_id': self.type_aerodrome.id,
            'debut': '2000-01-01',
            'fin': '2020-12-31',
            'mmd_inf': 2.0,
            'mmd_sup': 6.0,
            'base': 165.0,
            'coefficient': 83.0,
            'correction': 2.0,
            'avec_correction': True,
            'domestique': True,
        })

        self.assertFalse(param_passe.active)

    def test_10_type_taxe_unique(self):
        """Test contrainte d'unicité type de taxe"""
        with self.assertRaises(Exception):
            self.env['manureva.type_taxe'].create({
                'name': 'Normal',
            })
