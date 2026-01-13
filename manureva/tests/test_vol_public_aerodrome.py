# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from datetime import date


@tagged('post_install', '-at_install')
class TestVolPublicAerodrome(common.TransactionCase):

    def setUp(self):
        super(TestVolPublicAerodrome, self).setUp()

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

        self.type_activite = self.env['manureva.type_activite'].create({
            'name': 'Transport aérien public',
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Air Tahiti',
            'is_company': True,
        })

        self.usager = self.env['manureva.usager'].create({
            'cie_oaci': 'VTA',
            'partner_id': self.partner.id,
            'type_activite_id': self.type_activite.id,
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

    def test_01_create_vol_public_depart(self):
        """Test création vol public aérodrome - départ"""
        vol = self.env['manureva.vol_public_aerodrome'].create({
            'fc02': self.aerodrome_ntaa.id,
            'fc03': self.usager.id,
            'fc13': 'VT101',
            'fc14': 'N',
            'fc15': 'D',
            'fc16': self.aerodrome_nttm.id,
            'fc27': self.aeronef.id,
            'fc32': date.today(),
            'fc33': '10:00:00',
            'fc34': date.today(),
            'fc35': '10:05:00',
            'fc42': '04',
            'fc43': 'N',
        })

        self.assertEqual(vol.fc15, 'D')
        self.assertEqual(vol.fc13, 'VT101')
        self.assertEqual(vol.fc43, 'N')

    def test_02_create_vol_public_arrivee(self):
        """Test création vol public aérodrome - arrivée"""
        vol = self.env['manureva.vol_public_aerodrome'].create({
            'fc02': self.aerodrome_ntaa.id,
            'fc03': self.usager.id,
            'fc13': 'VT102',
            'fc14': 'N',
            'fc15': 'A',
            'fc16': self.aerodrome_nttm.id,
            'fc27': self.aeronef.id,
            'fc32': date.today(),
            'fc33': '14:30:00',
            'fc34': date.today(),
            'fc35': '14:35:00',
            'fc42': '22',
            'fc43': 'S',
        })

        self.assertEqual(vol.fc15, 'A')
        self.assertEqual(vol.fc43, 'S')

    def test_03_vol_public_deroute(self):
        """Test vol public dérouté"""
        vol = self.env['manureva.vol_public_aerodrome'].create({
            'fc02': self.aerodrome_ntaa.id,
            'fc03': self.usager.id,
            'fc13': 'VT103',
            'fc14': 'D',  # Dérouté
            'fc15': 'A',
            'fc16': self.aerodrome_nttm.id,
            'fc27': self.aeronef.id,
            'fc32': date.today(),
            'fc33': '16:00:00',
        })

        self.assertEqual(vol.fc14, 'D')

    def test_04_vol_public_interrompu(self):
        """Test vol public interrompu"""
        vol = self.env['manureva.vol_public_aerodrome'].create({
            'fc02': self.aerodrome_ntaa.id,
            'fc03': self.usager.id,
            'fc13': 'VT104',
            'fc14': 'I',  # Interrompu
            'fc15': 'D',
            'fc16': self.aerodrome_nttm.id,
            'fc27': self.aeronef.id,
            'fc32': date.today(),
            'fc33': '18:00:00',
        })

        self.assertEqual(vol.fc14, 'I')

    def test_05_domain_aeronef(self):
        """Test domain sur aeronef (fc27)"""
        # Créer un autre usager avec son aéronef
        partner2 = self.env['res.partner'].create({
            'name': 'Air Archipels',
            'is_company': True,
        })

        usager2 = self.env['manureva.usager'].create({
            'cie_oaci': 'RHL',
            'partner_id': partner2.id,
            'type_activite_id': self.type_activite.id,
        })

        aeronef2 = self.env['manureva.aeronef'].create({
            'name': 'FOIQF',
            'usager_id': usager2.id,
            'type_aeronef_id': self.type_aeronef.id,
        })

        # Le domain devrait filtrer les aéronefs par usager
        vol = self.env['manureva.vol_public_aerodrome'].new({
            'fc02': self.aerodrome_ntaa.id,
            'fc03': self.usager.id,
        })

        # Vérifier que seul l'aéronef du bon usager est disponible
        domain = vol._fields['fc27'].get_domain(vol)
        aeronefs_allowed = self.env['manureva.aeronef'].search(domain)

        self.assertIn(self.aeronef, aeronefs_allowed)
        self.assertNotIn(aeronef2, aeronefs_allowed)

    def test_06_balisage_en_service(self):
        """Test balisage en service pour vol public"""
        vol = self.env['manureva.vol_public_aerodrome'].create({
            'fc02': self.aerodrome_ntaa.id,
            'fc03': self.usager.id,
            'fc13': 'VT105',
            'fc15': 'D',
            'fc16': self.aerodrome_nttm.id,
            'fc27': self.aeronef.id,
            'fc32': date.today(),
            'fc33': '19:30:00',
            'fc43': 'S',  # Balisage en service
        })

        self.assertEqual(vol.fc43, 'S')

    def test_07_vol_public_default_values(self):
        """Test valeurs par défaut"""
        vol = self.env['manureva.vol_public_aerodrome'].create({
            'fc02': self.aerodrome_ntaa.id,
            'fc03': self.usager.id,
            'fc27': self.aeronef.id,
            'fc32': date.today(),
            'fc33': '12:00:00',
        })

        # Vérifier les valeurs par défaut
        self.assertEqual(vol.fc15, 'D')  # Départ par défaut
        self.assertEqual(vol.fc14, 'N')  # Non dérouté par défaut
        self.assertEqual(vol.fc43, 'N')  # Balisage non en service par défaut
