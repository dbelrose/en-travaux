# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from datetime import date


@tagged('post_install', '-at_install')
class TestSEAC(common.TransactionCase):

    def setUp(self):
        super(TestSEAC, self).setUp()

        # Création des données de test
        self.country_pf = self.env.ref('base.pf')

        self.type_aerodrome = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        self.aerodrome_ntaa = self.env['manureva.aerodrome'].create({
            'name': 'NTAA',
            'apt_oaci': 'NTAA',
            'apt_nom': 'TAHITI',
            'aerodrome': 'TAHITI',
            'type_aerodrome_id': self.type_aerodrome.id,
            'country_id': self.country_pf.id,
        })

        self.aerodrome_nttm = self.env['manureva.aerodrome'].create({
            'name': 'NTTM',
            'apt_oaci': 'NTTM',
            'apt_nom': 'MOOREA',
            'aerodrome': 'MOOREA',
            'type_aerodrome_id': self.type_aerodrome.id,
            'country_id': self.country_pf.id,
        })

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

        self.aeronef = self.env['manureva.aeronef'].create({
            'name': 'FORVB',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef.id,
        })

    def test_01_create_seac_arrivee(self):
        """Test création d'un mouvement arrivée"""
        seac = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'vol': 'VT101',
            'mouvement': 'A',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date': date.today(),
            'heure_texte': '10:30',
            'pax_plus': 45,
            'pax_moins': 0,
            'circonstance': 'N',
            'balisage': 'N',
        })

        self.assertEqual(seac.mouvement, 'A')
        self.assertEqual(seac.pax_plus, 45)
        self.assertEqual(seac.aerodrome_id, self.aerodrome_ntaa)

    def test_02_create_seac_depart(self):
        """Test création d'un mouvement départ"""
        seac = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'vol': 'VT102',
            'mouvement': 'D',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date': date.today(),
            'heure_texte': '14:45',
            'pax_plus': 48,
            'pax_moins': 2,
            'circonstance': 'N',
            'balisage': 'S',
        })

        self.assertEqual(seac.mouvement, 'D')
        self.assertEqual(seac.pax_plus, 48)
        self.assertEqual(seac.pax_moins, 2)
        self.assertEqual(seac.balisage, 'S')

    def test_03_seac_unique_constraint(self):
        """Test contrainte d'unicité sur les mouvements"""
        date_vol = date.today()

        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'mouvement': 'A',
            'date': date_vol,
            'heure_texte': '10:30',
        })

        with self.assertRaises(Exception):
            self.env['manureva.seac'].create({
                'aerodrome_id': self.aerodrome_ntaa.id,
                'usager_id': self.usager.id,
                'aeronef_id': self.aeronef.id,
                'mouvement': 'A',
                'date': date_vol,
                'heure_texte': '10:30',
            })

    def test_04_compute_annee(self):
        """Test calcul de l'année"""
        date_vol = date(2023, 6, 15)

        seac = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'mouvement': 'A',
            'date': date_vol,
            'heure_texte': '10:30',
        })

        self.assertEqual(seac.annee, 2023)

    def test_05_compute_heure_decimale(self):
        """Test calcul de l'heure décimale"""
        seac = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'mouvement': 'A',
            'date': date.today(),
            'heure_texte': '14:30',
        })

        self.assertEqual(seac.heure_decimale, 14.30)

    def test_06_passagers_locaux_non_payants(self):
        """Test prise en compte des passagers locaux non-payants"""
        seac = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'mouvement': 'D',
            'date': date.today(),
            'heure_texte': '10:30',
            'pax_plus': 48,
            'pax_moins': 2,
            'paxlnp1': 1,
            'paxlnp2': 0,
            'paxlnp3': 0,
            'paxlnp4': 0,
            'paxlnp5': 0,
        })

        # Passagers payants = 48 - 2 - 1 = 45
        passagers_payants = (seac.pax_plus - seac.pax_moins -
                             seac.paxlnp1 - seac.paxlnp2 - seac.paxlnp3 -
                             seac.paxlnp4 - seac.paxlnp5)
        self.assertEqual(passagers_payants, 45)
