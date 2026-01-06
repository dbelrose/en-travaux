# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from datetime import date


@tagged('post_install', '-at_install')
class TestNCDepot(common.TransactionCase):

    def setUp(self):
        super(TestNCDepot, self).setUp()

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

        self.type_activite_ag = self.env['manureva.type_activite'].create({
            'name': 'Aviation générale',
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Pilot Privé',
            'is_company': False,
        })

        self.usager = self.env['manureva.usager'].create({
            'partner_id': self.partner.id,
            'type_activite_id': self.type_activite_ag.id,
        })

        self.constructeur_partner = self.env['res.partner'].create({
            'name': 'Cessna',
            'is_company': True,
        })

        self.constructeur = self.env['manureva.constructeur'].create({
            'partner_id': self.constructeur_partner.id,
        })

        self.type_aeronef = self.env['manureva.type_aeronef'].create({
            'name': 'C208',
            'typ_oaci': 'C208',
            'constructeur_id': self.constructeur.id,
            'tonnage': 3.6,
        })

        self.aeronef = self.env['manureva.aeronef'].create({
            'name': 'F-OABC',
            'usager_id': self.usager.id,
            'type_aeronef_id': self.type_aeronef.id,
        })

    def test_01_create_vol_local(self):
        """Test création vol local"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'L',
            'touch_and_go': 5,
            'remise_de_gaz': 2,
            'date_debut': date.today(),
            'heure_debut': '10:00',
            'heure_fin': '11:30',
        })

        self.assertEqual(nc_depot.vol_local_voyage, 'L')
        self.assertEqual(nc_depot.touch_and_go, 5)
        self.assertEqual(nc_depot.remise_de_gaz, 2)

    def test_02_create_vol_voyage(self):
        """Test création vol voyage"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'V',
            'mouvement': 'D',
            'circonstance': 'N',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date_bloc': date.today(),
            'heure_bloc': '14:00',
            'date_piste': date.today(),
            'heure_piste': '14:05',
            'nombre_passagers': 5,
            'type_voyage': '2',
            'balisage': 'N',
            'reg_vol': '3',
            'vis_horizontale': 10000,
        })

        self.assertEqual(nc_depot.vol_local_voyage, 'V')
        self.assertEqual(nc_depot.mouvement, 'D')
        self.assertEqual(nc_depot.nombre_passagers, 5)
        self.assertEqual(nc_depot.type_voyage, '2')

    def test_03_create_vol_mixte(self):
        """Test création vol local et voyage"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'M',
            'touch_and_go': 3,
            'remise_de_gaz': 1,
            'date_debut': date.today(),
            'heure_debut': '09:00',
            'heure_fin': '10:00',
            'mouvement': 'D',
            'circonstance': 'N',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date_bloc': date.today(),
            'heure_bloc': '10:30',
            'date_piste': date.today(),
            'heure_piste': '10:35',
            'nombre_passagers': 3,
            'type_voyage': '2',
        })

        self.assertEqual(nc_depot.vol_local_voyage, 'M')
        self.assertEqual(nc_depot.touch_and_go, 3)
        self.assertEqual(nc_depot.mouvement, 'D')

    def test_04_vol_travail_aerien(self):
        """Test vol de travail aérien"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'V',
            'mouvement': 'D',
            'circonstance': 'N',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date_bloc': date.today(),
            'heure_bloc': '08:00',
            'date_piste': date.today(),
            'heure_piste': '08:05',
            'nombre_passagers': 0,
            'type_voyage': '4',  # Vol de travail aérien
        })

        self.assertEqual(nc_depot.type_voyage, '4')
        self.assertEqual(nc_depot.nombre_passagers, 0)

    def test_05_related_lib_aerodrome(self):
        """Test champ lié libellé aérodrome"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'V',
            'mouvement': 'A',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date_bloc': date.today(),
            'heure_bloc': '15:00',
        })

        self.assertEqual(nc_depot.lib_aerod_prov_dest, 'MOOREA')

    def test_06_related_lib_type_aeronef(self):
        """Test champ lié libellé type aéronef"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'L',
            'date_debut': date.today(),
            'heure_debut': '10:00',
            'heure_fin': '11:00',
        })

        self.assertEqual(nc_depot.lib_type_aeronef, 'C208')

    def test_07_vol_deroute(self):
        """Test vol dérouté"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'V',
            'mouvement': 'A',
            'circonstance': 'D',  # Dérouté
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date_bloc': date.today(),
            'heure_bloc': '16:30',
        })

        self.assertEqual(nc_depot.circonstance, 'D')

    def test_08_vol_interrompu(self):
        """Test vol interrompu"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'V',
            'mouvement': 'D',
            'circonstance': 'I',  # Interrompu
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date_bloc': date.today(),
            'heure_bloc': '12:00',
        })

        self.assertEqual(nc_depot.circonstance, 'I')

    def test_09_regime_vol_ifr(self):
        """Test régime de vol IFR"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'V',
            'mouvement': 'D',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date_bloc': date.today(),
            'heure_bloc': '18:00',
            'reg_vol': '1',  # IFR
        })

        self.assertEqual(nc_depot.reg_vol, '1')

    def test_10_balisage_en_service(self):
        """Test balisage en service"""
        nc_depot = self.env['manureva.nc_depot'].create({
            'aerodrome_id': self.aerodrome_ntaa.id,
            'aeronef_id': self.aeronef.id,
            'type_aeronef_id': self.type_aeronef.id,
            'vol_local_voyage': 'V',
            'mouvement': 'A',
            'aerod_prov_dest': self.aerodrome_nttm.id,
            'date_bloc': date.today(),
            'heure_bloc': '19:30',
            'balisage': 'S',  # En service
        })

        self.assertEqual(nc_depot.balisage, 'S')
