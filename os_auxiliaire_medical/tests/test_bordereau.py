"""
Tests unitaires – cps.bordereau
Couvre :
  - get_export_data : majuscules noms/prénoms
  - get_export_data : date au format JJ/MM/AA fuseau Tahiti
  - get_export_data : montants avec virgule décimale
  - get_export_data : libellés "NOM PRENOM", "Part CPS", "Part patient"
  - get_export_data : pas de colonne "Total"
  - Pas de couleur de fond (contrôlé par le template QWeb, pas testé en unitaire ici)
"""
import datetime
import pytz

from odoo.tests.common import TransactionCase
from unittest.mock import patch


class TestBordereau(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.cat_patient   = cls.env.ref('os_auxiliaire_medical.partner_category_patient')
        cls.cat_praticien = cls.env.ref('os_auxiliaire_medical.partner_category_praticien')

        cls.praticien = cls.env['res.partner'].create({
            'name': 'jean-paul martin',     # minuscules pour vérifier la mise en majuscules
            'category_id': [(4, cls.cat_praticien.id)],
        })
        cls.patient_a = cls.env['res.partner'].create({
            'name': 'alice dupont',         # minuscules
            'category_id': [(4, cls.cat_patient.id)],
        })

        cls.bordereau = cls.env['cps.bordereau'].create({
            'praticien_id':  cls.praticien.id,
            'date_bordereau': datetime.date(2026, 4, 1),
        })

        cls.feuille = cls.env['cps.feuille.soins'].create({
            'praticien_id': cls.praticien.id,
            'patient_id':   cls.patient_a.id,
            'date_soins':   '2026-04-10',
            'bordereau_id': cls.bordereau.id,
        })

    # ── Majuscules ────────────────────────────────────────────────────────

    def test_nom_praticien_en_majuscules(self):
        data = self.bordereau.get_export_data()
        self.assertEqual(data['praticien_nom'], 'JEAN-PAUL MARTIN')

    def test_nom_patient_en_majuscules(self):
        data = self.bordereau.get_export_data()
        noms = [row['nom_prenom'] for row in data['rows']]
        self.assertIn('ALICE DUPONT', noms)

    # ── Date Tahiti JJ/MM/AA ──────────────────────────────────────────────

    def test_date_impression_format_tahiti(self):
        """La date d'impression doit être au format JJ/MM/AA, fuseau Pacific/Tahiti."""
        tz = pytz.timezone('Pacific/Tahiti')
        today_tahiti = datetime.datetime.now(tz).strftime('%d/%m/%y')
        self.assertEqual(
            self.bordereau._tahiti_today_short(),
            today_tahiti,
        )

    def test_date_impression_dans_export(self):
        data = self.bordereau.get_export_data()
        # Vérifie le format JJ/MM/AA (6 chiffres + 2 slashs)
        d = data['date_impression']
        self.assertRegex(d, r'^\d{2}/\d{2}/\d{2}$')

    # ── Virgule décimale ─────────────────────────────────────────────────

    def test_montant_virgule_pas_point(self):
        montant = self.bordereau._format_amount_comma(3675.50)
        self.assertIn(',', montant)
        self.assertNotIn('.', montant)

    def test_montant_entier_sans_decimale(self):
        montant = self.bordereau._format_amount_comma(3675)
        self.assertNotIn('.', montant)
        # pas de ",00" inutile pour un entier
        self.assertNotIn(',00', montant)

    # ── Libellés ─────────────────────────────────────────────────────────

    def test_label_nom_prenom(self):
        data = self.bordereau.get_export_data()
        self.assertEqual(data['label_nom_prenom'], 'NOM PRENOM')

    def test_label_part_cps(self):
        data = self.bordereau.get_export_data()
        self.assertEqual(data['label_part_cps'], 'Part CPS')

    def test_label_part_patient(self):
        data = self.bordereau.get_export_data()
        self.assertEqual(data['label_part_patient'], 'Part patient')

    # ── Pas de colonne "Total" dans les lignes ────────────────────────────

    def test_pas_de_colonne_total_dans_lignes(self):
        """Les lignes du dict ne doivent PAS contenir la clé 'total'."""
        data = self.bordereau.get_export_data()
        for row in data['rows']:
            self.assertNotIn('total', row,
                             "La colonne 'total' ne doit pas être présente dans les lignes PDF.")
            # Les valeurs brutes sont disponibles mais sous noms distincts
            self.assertIn('montant_total_raw', row)
