# -*- coding: utf-8 -*-
"""
Fichier contenant les classes et méthodes utilitaires communes aux tests
"""
from odoo.tests import common
from datetime import date


class ManurevaTestCase(common.TransactionCase):
    """Classe de base pour les tests Manureva avec des méthodes utilitaires"""

    def create_aerodrome(self, code='NTAA', nom='TAHITI', type_aerodrome=None, balisage=False):
        """Créer un aérodrome de test"""
        if not type_aerodrome:
            type_aerodrome = self.env['manureva.type_aerodrome'].create({
                'name': 'Tous',
                'a_facturer': True,
            })

        country_pf = self.env.ref('base.pf')

        return self.env['manureva.aerodrome'].create({
            'name': code,
            'apt_oaci': code,
            'apt_nom': nom,
            'aerodrome': nom,
            'type_aerodrome_id': type_aerodrome.id,
            'country_id': country_pf.id,
            'balisage': balisage,
        })

    def create_usager(self, oaci='VTA', nom='Air Tahiti', type_activite=None):
        """Créer un usager de test"""
        if not type_activite:
            type_activite = self.env['manureva.type_activite'].create({
                'name': 'Transport aérien public',
            })

        partner = self.env['res.partner'].create({
            'name': nom,
            'is_company': True,
        })

        return self.env['manureva.usager'].create({
            'cie_oaci': oaci,
            'partner_id': partner.id,
            'type_activite_id': type_activite.id,
        })

    def create_type_aeronef(self, code='AT45', tonnage=18.6, pax=48):
        """Créer un type d'aéronef de test"""
        constructeur_partner = self.env['res.partner'].create({
            'name': f'Constructeur {code}',
            'is_company': True,
        })

        constructeur = self.env['manureva.constructeur'].create({
            'partner_id': constructeur_partner.id,
        })

        return self.env['manureva.type_aeronef'].create({
            'name': code,
            'typ_oaci': code,
            'constructeur_id': constructeur.id,
            'tonnage': tonnage,
            'pax': pax,
        })

    def create_aeronef(self, immat='FORVB', usager=None, type_aeronef=None):
        """Créer un aéronef de test"""
        if not usager:
            usager = self.create_usager()

        if not type_aeronef:
            type_aeronef = self.create_type_aeronef()

        return self.env['manureva.aeronef'].create({
            'name': immat,
            'usager_id': usager.id,
            'type_aeronef_id': type_aeronef.id,
        })

    def create_seac(self, aerodrome=None, usager=None, aeronef=None,
                    mouvement='A', date_vol=None, heure='10:00',
                    pax_plus=0, pax_moins=0):
        """Créer un mouvement SEAC de test"""
        if not aerodrome:
            aerodrome = self.create_aerodrome()

        if not usager:
            usager = self.create_usager()

        if not aeronef:
            aeronef = self.create_aeronef(usager=usager)

        if not date_vol:
            date_vol = date.today()

        return self.env['manureva.seac'].create({
            'aerodrome_id': aerodrome.id,
            'usager_id': usager.id,
            'aeronef_id': aeronef.id,
            'mouvement': mouvement,
            'date': date_vol,
            'heure_texte': heure,
            'pax_plus': pax_plus,
            'pax_moins': pax_moins,
            'circonstance': 'N',
            'balisage': 'N',
        })

    def create_param_att(self, type_aerodrome=None, mmd_inf=0, mmd_sup=2,
                         base=165, coefficient=0, correction=0):
        """Créer un paramètre atterrissage de test"""
        if not type_aerodrome:
            type_aerodrome = self.env['manureva.type_aerodrome'].create({
                'name': 'Tous',
                'a_facturer': True,
            })

        return self.env['manureva.param_att'].create({
            'type_aerodrome_id': type_aerodrome.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'mmd_inf': mmd_inf,
            'mmd_sup': mmd_sup,
            'base': base,
            'coefficient': coefficient,
            'correction': correction,
            'avec_correction': coefficient > 0,
            'domestique': True,
        })

    def create_param_pax(self, type_aerodrome=None, montant=149):
        """Créer un paramètre passager de test"""
        if not type_aerodrome:
            type_aerodrome = self.env['manureva.type_aerodrome'].create({
                'name': 'Tous',
                'a_facturer': True,
            })

        return self.env['manureva.param_pax'].create({
            'type_aerodrome_id': type_aerodrome.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'montant': montant,
        })

    def create_balisage(self, type_aerodrome=None, montant=689, avant=6, apres=18):
        """Créer un paramètre balisage de test"""
        if not type_aerodrome:
            type_aerodrome = self.env['manureva.type_aerodrome'].create({
                'name': 'Tous',
                'a_facturer': True,
            })

        return self.env['manureva.balisage'].create({
            'type_aerodrome_id': type_aerodrome.id,
            'debut': '2000-01-01',
            'fin': '2099-12-31',
            'avant': avant,
            'apres': apres,
            'montant': montant,
        })

    def create_full_config(self):
        """Créer une configuration complète pour les tests"""
        # Type d'aérodrome
        type_aerodrome = self.env['manureva.type_aerodrome'].create({
            'name': 'Tous',
            'a_facturer': True,
        })

        # Aérodrome
        aerodrome = self.create_aerodrome(type_aerodrome=type_aerodrome)

        # Usager
        usager = self.create_usager()

        # Type d'aéronef
        type_aeronef = self.create_type_aeronef()

        # Aéronef
        aeronef = self.create_aeronef(usager=usager, type_aeronef=type_aeronef)

        # Paramètres
        self.create_param_att(type_aerodrome=type_aerodrome, mmd_inf=6, mmd_sup=25,
                              base=497, coefficient=180, correction=6)
        self.create_param_pax(type_aerodrome=type_aerodrome)
        self.create_balisage(type_aerodrome=type_aerodrome)

        return {
            'aerodrome': aerodrome,
            'usager': usager,
            'type_aeronef': type_aeronef,
            'aeronef': aeronef,
            'type_aerodrome': type_aerodrome,
        }

    def assertMontantProche(self, montant1, montant2, delta=1):
        """Vérifier que deux montants sont proches (arrondi)"""
        self.assertAlmostEqual(montant1, montant2, delta=delta,
                               msg=f"Les montants {montant1} et {montant2} diffèrent de plus de {delta}")

    def get_or_create_periode(self, annee, mois, usager):
        """Récupérer ou créer une période"""
        periode = self.env['manureva.periode'].search([
            ('annee', '=', annee),
            ('mois', '=', mois),
            ('usager_id', '=', usager.id),
        ])

        if not periode:
            periode = self.env['manureva.periode'].create({
                'annee': annee,
                'mois': mois,
                'usager_id': usager.id,
                'a_facturer': True,
                'facture': False,
            })

        return periode


class ManurevaPerformanceTestCase(ManurevaTestCase):
    """Classe de base pour les tests de performance"""

    def mesurer_temps(self, func, *args, **kwargs):
        """Mesurer le temps d'exécution d'une fonction"""
        import time
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        return result, end - start
