# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestUsager(common.TransactionCase):

    def setUp(self):
        super(TestUsager, self).setUp()

        self.type_activite_tap = self.env['manureva.type_activite'].create({
            'name': 'Transport aérien public',
        })

        self.type_activite_ag = self.env['manureva.type_activite'].create({
            'name': 'Aviation générale',
        })

    def test_01_create_usager_tap(self):
        """Test création usager transport aérien public"""
        partner = self.env['res.partner'].create({
            'name': 'Air Tahiti',
            'is_company': True,
            'street': 'BP 314',
            'city': 'PAPEETE',
        })

        usager = self.env['manureva.usager'].create({
            'cie_oaci': 'VTA',
            'partner_id': partner.id,
            'type_activite_id': self.type_activite_tap.id,
        })

        self.assertEqual(usager.cie_oaci, 'VTA')
        self.assertEqual(usager.name, 'Air Tahiti')
        self.assertEqual(usager.type_activite_id, self.type_activite_tap)

    def test_02_create_usager_aviation_generale(self):
        """Test création usager aviation générale"""
        partner = self.env['res.partner'].create({
            'name': 'Pilot Privé',
            'is_company': False,
        })

        usager = self.env['manureva.usager'].create({
            'partner_id': partner.id,
            'type_activite_id': self.type_activite_ag.id,
        })

        self.assertEqual(usager.type_activite_id, self.type_activite_ag)
        self.assertFalse(usager.cie_oaci)

    def test_03_usager_inherits_partner(self):
        """Test héritage des champs du partner"""
        partner = self.env['res.partner'].create({
            'name': 'Air Archipels',
            'is_company': True,
            'street': 'BP 6019',
            'city': 'FAAA',
            'email': 'contact@airarchipels.pf',
            'phone': '40864263',
        })

        usager = self.env['manureva.usager'].create({
            'cie_oaci': 'RHL',
            'partner_id': partner.id,
            'type_activite_id': self.type_activite_tap.id,
        })

        self.assertEqual(usager.street, 'BP 6019')
        self.assertEqual(usager.city, 'FAAA')
        self.assertEqual(usager.email, 'contact@airarchipels.pf')
        self.assertEqual(usager.phone, '40864263')

    def test_04_usager_rec_name(self):
        """Test champ d'affichage (rec_name)"""
        partner = self.env['res.partner'].create({
            'name': 'Tahiti Nui Helicopters',
            'is_company': True,
        })

        usager = self.env['manureva.usager'].create({
            'cie_oaci': 'TNH',
            'partner_id': partner.id,
            'type_activite_id': self.type_activite_tap.id,
        })

        # Le _rec_name est 'cie_oaci'
        self.assertEqual(usager.display_name, 'TNH')

    def test_05_relation_usager_aeronefs(self):
        """Test relation usager - aéronefs"""
        partner = self.env['res.partner'].create({
            'name': 'Air Tetiaroa',
            'is_company': True,
        })

        usager = self.env['manureva.usager'].create({
            'cie_oaci': 'ATE',
            'partner_id': partner.id,
            'type_activite_id': self.type_activite_tap.id,
        })

        constructeur_partner = self.env['res.partner'].create({
            'name': 'Britten-Norman',
            'is_company': True,
        })

        constructeur = self.env['manureva.constructeur'].create({
            'partner_id': constructeur_partner.id,
        })

        type_aeronef = self.env['manureva.type_aeronef'].create({
            'name': 'BN2T',
            'typ_oaci': 'BN2T',
            'constructeur_id': constructeur.id,
            'tonnage': 3.2,
        })

        aeronef1 = self.env['manureva.aeronef'].create({
            'name': 'FOKAB',
            'usager_id': usager.id,
            'type_aeronef_id': type_aeronef.id,
        })

        aeronef2 = self.env['manureva.aeronef'].create({
            'name': 'FOKKB',
            'usager_id': usager.id,
            'type_aeronef_id': type_aeronef.id,
        })

        self.assertEqual(len(usager.aeronef_ids), 2)
        self.assertIn(aeronef1, usager.aeronef_ids)
        self.assertIn(aeronef2, usager.aeronef_ids)

    def test_06_relation_usager_factures(self):
        """Test relation usager - factures"""
        country_pf = self.env.ref('base.pf')

        type_aerodrome = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        aerodrome = self.env['manureva.aerodrome'].create({
            'name': 'NTAA',
            'apt_oaci': 'NTAA',
            'apt_nom': 'TAHITI',
            'aerodrome': 'TAHITI',
            'type_aerodrome_id': type_aerodrome.id,
            'country_id': country_pf.id,
        })

        partner = self.env['res.partner'].create({
            'name': 'Air Tahiti',
            'is_company': True,
        })

        usager = self.env['manureva.usager'].create({
            'cie_oaci': 'VTA',
            'partner_id': partner.id,
            'type_activite_id': self.type_activite_tap.id,
        })

        periode = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': usager.id,
        })

        facture = self.env['manureva.facture'].create({
            'facture': 2306001,
            'name': '06/23_VTA_NTAA',
            'aerodrome_id': aerodrome.id,
            'usager_id': usager.id,
            'periode_id': periode.id,
        })

        self.assertEqual(len(usager.facture_ids), 1)
        self.assertIn(facture, usager.facture_ids)

    def test_07_usager_cie_pays(self):
        """Test champ pays du transporteur"""
        country_pf = self.env.ref('base.pf')

        partner = self.env['res.partner'].create({
            'name': 'Air Caledonie International',
            'is_company': True,
        })

        usager = self.env['manureva.usager'].create({
            'cie_oaci': 'ACI',
            'partner_id': partner.id,
            'type_activite_id': self.type_activite_tap.id,
            'cie_pays': country_pf.id,
        })

        self.assertEqual(usager.cie_pays, country_pf)
