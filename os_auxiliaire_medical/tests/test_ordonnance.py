"""
Tests unitaires – cps.ordonnance
Couvre :
  - Création d'une ordonnance sans patient (OCR use-case)
  - Unicité de l'acte_type_id par ordonnance
  - Patient obligatoire dès qu'on ajoute une ligne d'acte
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestOrdonnance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Catégories
        cls.cat_patient   = cls.env.ref('os_auxiliaire_medical.partner_category_patient')
        cls.cat_praticien = cls.env.ref('os_auxiliaire_medical.partner_category_praticien')

        # Partenaires
        cls.patient = cls.env['res.partner'].create({
            'name': 'Jean Martin',
            'category_id': [(4, cls.cat_patient.id)],
        })
        cls.praticien = cls.env['res.partner'].create({
            'name': 'Sophie Bernard',
            'category_id': [(4, cls.cat_praticien.id)],
        })

        # Types d'actes
        cls.acte_a = cls.env['cps.acte.type'].create({
            'name': 'Acte A',
            'lettre_cle': 'AMO',
            'coefficient_defaut': 10.0,
            'tarif_unitaire': 490,
            'profession': 'orthophoniste',
        })
        cls.acte_b = cls.env['cps.acte.type'].create({
            'name': 'Acte B',
            'lettre_cle': 'AMK',
            'coefficient_defaut': 7.5,
            'tarif_unitaire': 490,
            'profession': 'kinesitherapeute',
        })

    # ── Création sans patient ─────────────────────────────────────────────

    def test_creation_sans_patient_autorisee(self):
        """Une ordonnance peut être créée sans patient (import OCR)."""
        ordonnance = self.env['cps.ordonnance'].create({
            'praticien_id': self.praticien.id,
            'date_prescription': '2026-04-01',
            # patient_id absent intentionnellement
        })
        self.assertFalse(ordonnance.patient_id)
        self.assertTrue(ordonnance.id)

    # ── Patient obligatoire avec lignes ──────────────────────────────────

    def test_patient_obligatoire_avec_lignes(self):
        """Ajouter une ligne d'acte sans patient doit lever une ValidationError."""
        ordonnance = self.env['cps.ordonnance'].create({
            'praticien_id': self.praticien.id,
            'date_prescription': '2026-04-01',
        })
        with self.assertRaises(ValidationError):
            self.env['cps.ordonnance.ligne'].create({
                'ordonnance_id':       ordonnance.id,
                'acte_type_id':        self.acte_a.id,
                'nb_seances_prescrites': 10,
            })
            # Forcer l'évaluation de la contrainte
            ordonnance._check_patient_for_lines()

    # ── Unicité acte_type_id ──────────────────────────────────────────────

    def test_acte_unique_par_ordonnance(self):
        """Deux lignes avec le même acte_type_id doivent lever une ValidationError."""
        ordonnance = self.env['cps.ordonnance'].create({
            'patient_id':      self.patient.id,
            'praticien_id':    self.praticien.id,
            'date_prescription': '2026-04-01',
        })
        self.env['cps.ordonnance.ligne'].create({
            'ordonnance_id':       ordonnance.id,
            'acte_type_id':        self.acte_a.id,
            'nb_seances_prescrites': 10,
        })
        with self.assertRaises(ValidationError):
            self.env['cps.ordonnance.ligne'].create({
                'ordonnance_id':       ordonnance.id,
                'acte_type_id':        self.acte_a.id,  # doublon
                'nb_seances_prescrites': 5,
            })
            ordonnance._check_unique_acte_type_per_ligne()

    def test_deux_actes_differents_autorises(self):
        """Deux lignes avec des acte_type_id différents doivent être acceptées."""
        ordonnance = self.env['cps.ordonnance'].create({
            'patient_id':      self.patient.id,
            'praticien_id':    self.praticien.id,
            'date_prescription': '2026-04-01',
        })
        self.env['cps.ordonnance.ligne'].create({
            'ordonnance_id':       ordonnance.id,
            'acte_type_id':        self.acte_a.id,
            'nb_seances_prescrites': 10,
        })
        ligne_b = self.env['cps.ordonnance.ligne'].create({
            'ordonnance_id':       ordonnance.id,
            'acte_type_id':        self.acte_b.id,
            'nb_seances_prescrites': 5,
        })
        self.assertEqual(len(ordonnance.ligne_ids), 2)
        self.assertIn(ligne_b, ordonnance.ligne_ids)
