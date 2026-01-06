# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from odoo.exceptions import ValidationError
from datetime import date


@tagged('post_install', '-at_install')
class TestPeriodeWizard(common.TransactionCase):

    def setUp(self):
        super(TestPeriodeWizard, self).setUp()

        # Création des données de test
        self.country_pf = self.env.ref('base.pf')

        self.type_aerodrome = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        self.aerodrome = self.env['manureva.aerodrome'].create({
            'name': 'NTAA',
            'apt_oaci': 'NTAA',
            'apt_nom': 'TAHITI',
            'aerodrome': 'TAHITI',
            'type_aerodrome_id': self.type_aerodrome.id,
            'country_id': self.country_pf.id,
            'balisage': True,
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Air Tahiti',
            'is_company': True,
        })

        self.type_activite = self.env['manureva.type_activite'].create({
            'name': 'Transport aérien public',
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

        # Paramètres de calcul
        self.param_att = self.env['manureva.param_att'].create({
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

        self.param_pax = self.env['manureva.param_pax'].create({
            'type_aerodrome_id': self.type_aerodrome.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'montant': 149.0,
        })

        self.balisage = self.env['manureva.balisage'].create({
            'type_aerodrome_id': self.type_aerodrome.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'avant': 6.0,
            'apres': 18.0,
            'montant': 689.0,
        })

        # Création de périodes à facturer
        self.periode1 = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': self.usager.id,
            'a_facturer': True,
            'facture': False,
        })

        self.periode2 = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 7,
            'usager_id': self.usager.id,
            'a_facturer': True,
            'facture': False,
        })

        # Création de mouvements SEAC
        date_mvt = date(2023, 6, 15)
        self.seac1 = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'mouvement': 'A',
            'date': date_mvt,
            'heure_texte': '10:30',
            'pax_plus': 45,
            'pax_moins': 0,
        })

        self.seac2 = self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'mouvement': 'D',
            'date': date_mvt,
            'heure_texte': '14:45',
            'pax_plus': 48,
            'pax_moins': 2,
        })

    def test_01_wizard_default_periodes(self):
        """Test sélection par défaut des périodes à facturer"""
        wizard = self.env['manureva.periode_wizard'].with_context(
            active_ids=[self.periode1.id, self.periode2.id]
        ).create({})

        self.assertEqual(len(wizard.periode_ids), 2)
        self.assertIn(self.periode1, wizard.periode_ids)
        self.assertIn(self.periode2, wizard.periode_ids)

    def test_02_wizard_facturer_periode(self):
        """Test facturation via wizard"""
        wizard = self.env['manureva.periode_wizard'].create({
            'periode_ids': [(6, 0, [self.periode1.id])],
        })

        wizard.facturer_periode()

        # Vérifier que la période a été facturée
        self.periode1.refresh()
        self.assertFalse(self.periode1.a_facturer)
        self.assertTrue(self.periode1.facture)

        # Vérifier qu'une facture a été créée
        factures = self.env['manureva.facture'].search([
            ('periode_id', '=', self.periode1.id)
        ])
        self.assertGreater(len(factures), 0)

    def test_03_wizard_facturer_multiple_periodes(self):
        """Test facturation de plusieurs périodes"""
        wizard = self.env['manureva.periode_wizard'].create({
            'periode_ids': [(6, 0, [self.periode1.id, self.periode2.id])],
        })

        # Créer des mouvements pour la période 2
        date_mvt2 = date(2023, 7, 10)
        self.env['manureva.seac'].create({
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'aeronef_id': self.aeronef.id,
            'mouvement': 'A',
            'date': date_mvt2,
            'heure_texte': '11:00',
            'pax_plus': 40,
            'pax_moins': 0,
        })

        wizard.facturer_periode()

        # Vérifier que les deux périodes ont été facturées
        self.periode1.refresh()
        self.periode2.refresh()

        self.assertTrue(self.periode1.facture)
        self.assertTrue(self.periode2.facture)


@tagged('post_install', '-at_install')
class TestPeriodeSupprimerFactureWizard(common.TransactionCase):

    def setUp(self):
        super(TestPeriodeSupprimerFactureWizard, self).setUp()

        # Création des données de test
        self.country_pf = self.env.ref('base.pf')

        self.type_aerodrome = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        self.aerodrome = self.env['manureva.aerodrome'].create({
            'name': 'NTAA',
            'apt_oaci': 'NTAA',
            'apt_nom': 'TAHITI',
            'aerodrome': 'TAHITI',
            'type_aerodrome_id': self.type_aerodrome.id,
            'country_id': self.country_pf.id,
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Air Tahiti',
            'is_company': True,
        })

        self.type_activite = self.env['manureva.type_activite'].create({
            'name': 'Transport aérien public',
        })

        self.usager = self.env['manureva.usager'].create({
            'cie_oaci': 'VTA',
            'partner_id': self.partner.id,
            'type_activite_id': self.type_activite.id,
        })

        # Périodes facturées
        self.periode_facturee = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 6,
            'usager_id': self.usager.id,
            'a_facturer': False,
            'facture': True,
            'state': '2facture',
        })

        self.facture = self.env['manureva.facture'].create({
            'facture': 2306001,
            'name': '06/23_VTA_NTAA',
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'periode_id': self.periode_facturee.id,
        })

        # Période non facturée
        self.periode_non_facturee = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 7,
            'usager_id': self.usager.id,
            'a_facturer': True,
            'facture': False,
            'state': '1a_facturer',
        })

    def test_01_wizard_default_periodes_facturees(self):
        """Test sélection par défaut des périodes facturées"""
        wizard = self.env['manureva.periode_supprimer_facture_wizard'].with_context(
            active_ids=[self.periode_facturee.id, self.periode_non_facturee.id]
        ).create({})

        # Seule la période facturée devrait être sélectionnée
        self.assertEqual(len(wizard.periode_ids), 1)
        self.assertIn(self.periode_facturee, wizard.periode_ids)
        self.assertNotIn(self.periode_non_facturee, wizard.periode_ids)

    def test_02_wizard_supprimer_factures(self):
        """Test suppression de factures via wizard"""
        wizard = self.env['manureva.periode_supprimer_facture_wizard'].create({
            'periode_ids': [(6, 0, [self.periode_facturee.id])],
        })

        facture_id = self.facture.id

        wizard.supprimer_facture_periode()

        # Vérifier que la période est repassée à "à facturer"
        self.periode_facturee.refresh()
        self.assertTrue(self.periode_facturee.a_facturer)
        self.assertFalse(self.periode_facturee.facture)
        self.assertEqual(self.periode_facturee.state, '1a_facturer')

        # Vérifier que la facture a été supprimée
        facture_existe = self.env['manureva.facture'].search([
            ('id', '=', facture_id)
        ])
        self.assertEqual(len(facture_existe), 0)

    def test_03_wizard_constraint_periode_non_facturee(self):
        """Test contrainte : ne peut supprimer que des périodes facturées"""
        with self.assertRaises(ValidationError):
            wizard = self.env['manureva.periode_supprimer_facture_wizard'].create({
                'periode_ids': [(6, 0, [self.periode_non_facturee.id])],
            })

    def test_04_wizard_supprimer_multiple_periodes(self):
        """Test suppression de factures de plusieurs périodes"""
        # Créer une deuxième période facturée
        periode_facturee2 = self.env['manureva.periode'].create({
            'annee': 2023,
            'mois': 8,
            'usager_id': self.usager.id,
            'a_facturer': False,
            'facture': True,
            'state': '2facture',
        })

        facture2 = self.env['manureva.facture'].create({
            'facture': 2308001,
            'name': '08/23_VTA_NTAA',
            'aerodrome_id': self.aerodrome.id,
            'usager_id': self.usager.id,
            'periode_id': periode_facturee2.id,
        })

        wizard = self.env['manureva.periode_supprimer_facture_wizard'].create({
            'periode_ids': [(6, 0, [self.periode_facturee.id, periode_facturee2.id])],
        })

        wizard.supprimer_facture_periode()

        # Vérifier que les deux périodes sont repassées à "à facturer"
        self.periode_facturee.refresh()
        periode_facturee2.refresh()

        self.assertTrue(self.periode_facturee.a_facturer)
        self.assertTrue(periode_facturee2.a_facturer)
        self.assertEqual(self.periode_facturee.state, '1a_facturer')
        self.assertEqual(periode_facturee2.state, '1a_facturer')


@tagged('post_install', '-at_install')
class TestVolPublicAerodromeWizard(common.TransactionCase):

    def setUp(self):
        super(TestVolPublicAerodromeWizard, self).setUp()

        # Création des données de test
        self.country_pf = self.env.ref('base.pf')

        self.type_aerodrome = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        self.aerodrome = self.env['manureva.aerodrome'].create({
            'name': 'NTAA',
            'apt_oaci': 'NTAA',
            'apt_nom': 'TAHITI',
            'aerodrome': 'TAHITI',
            'type_aerodrome_id': self.type_aerodrome.id,
            'country_id': self.country_pf.id,
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Air Tahiti',
            'is_company': True,
        })

        self.type_activite = self.env['manureva.type_activite'].create({
            'name': 'Transport aérien public',
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

    def test_01_wizard_initial_state(self):
        """Test état initial du wizard"""
        wizard = self.env['manureva.vol_public_aerodrome_wizard'].create({})

        self.assertEqual(wizard.state, 'start')

    def test_02_wizard_selection_aerodrome(self):
        """Test sélection aérodrome"""
        wizard = self.env['manureva.vol_public_aerodrome_wizard'].create({
            'fc02': self.aerodrome.id,
        })

        self.assertEqual(wizard.fc02, self.aerodrome)

        wizard.state_exit_start()
        self.assertEqual(wizard.state, 'operateur')

    def test_03_wizard_selection_operateur(self):
        """Test sélection opérateur"""
        wizard = self.env['manureva.vol_public_aerodrome_wizard'].create({
            'fc02': self.aerodrome.id,
            'fc03': self.usager.id,
            'state': 'operateur',
        })

        self.assertEqual(wizard.fc03, self.usager)

        wizard.state_exit_operateur()
        self.assertEqual(wizard.state, 'mouvement')

    def test_04_wizard_saisie_mouvement(self):
        """Test saisie mouvement"""
        wizard = self.env['manureva.vol_public_aerodrome_wizard'].create({
            'fc02': self.aerodrome.id,
            'fc03': self.usager.id,
            'fc27': self.aeronef.id,
            'fc15': 'D',
            'fc32': date.today(),
            'fc33': '10:30',
            'fc43': 'N',
            'state': 'mouvement',
        })

        wizard.state_exit_mouvement()
        self.assertEqual(wizard.state, 'validation')

    def test_05_wizard_validation_creation_seac(self):
        """Test validation et création SEAC"""
        date_vol = date.today()

        wizard = self.env['manureva.vol_public_aerodrome_wizard'].create({
            'fc02': self.aerodrome.id,
            'fc03': self.usager.id,
            'fc27': self.aeronef.id,
            'fc15': 'D',
            'fc32': date_vol,
            'fc33': '10:30',
            'fc43': 'N',
            'state': 'validation',
        })

        wizard.state_exit_validation()

        # Vérifier que le SEAC a été créé
        seac = self.env['manureva.seac'].search([
            ('aerodrome_id', '=', self.aerodrome.id),
            ('usager_id', '=', self.usager.id),
            ('aeronef_id', '=', self.aeronef.id),
            ('date', '=', date_vol),
            ('heure_texte', '=', '10:30'),
        ])

        self.assertEqual(len(seac), 1)
        self.assertEqual(seac.mouvement, 'D')
        self.assertEqual(seac.balisage, 'N')

        # Vérifier l'état final
        self.assertEqual(wizard.state, 'final')

    def test_06_wizard_navigation_retour(self):
        """Test navigation retour dans le wizard"""
        wizard = self.env['manureva.vol_public_aerodrome_wizard'].create({
            'fc02': self.aerodrome.id,
            'fc03': self.usager.id,
            'state': 'operateur',
        })

        wizard.state_previous_operateur()
        self.assertEqual(wizard.state, 'start')

        wizard2 = self.env['manureva.vol_public_aerodrome_wizard'].create({
            'fc02': self.aerodrome.id,
            'fc03': self.usager.id,
            'state': 'validation',
        })

        wizard2.state_previous_validation()
        self.assertEqual(wizard2.state, 'mouvement')
