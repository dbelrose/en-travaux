"""
Tests unitaires – cps.feuille.soins
Couvre :
  - Filtre "Mes feuilles" (praticien_id.user_ids ∋ uid)
  - Formatage virgule décimale
"""
from odoo.tests.common import TransactionCase


class TestFeuilleSoins(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.cat_patient   = cls.env.ref('os_auxiliaire_medical.partner_category_patient')
        cls.cat_praticien = cls.env.ref('os_auxiliaire_medical.partner_category_praticien')

        # Utilisateur kiné
        cls.user_kine = cls.env['res.users'].create({
            'name': 'Kiné Feuille',
            'login': 'kine_feuille@cps.pf',
            'groups_id': [(4, cls.env.ref('base.group_user').id)],
        })
        cls.user_autre = cls.env['res.users'].create({
            'name': 'Autre Praticien',
            'login': 'autre_prat@cps.pf',
            'groups_id': [(4, cls.env.ref('base.group_user').id)],
        })

        cls.praticien_kine = cls.env['res.partner'].create({
            'name': 'Praticien Kiné',
            'category_id': [(4, cls.cat_praticien.id)],
            'user_ids': [(4, cls.user_kine.id)],
        })
        cls.praticien_autre = cls.env['res.partner'].create({
            'name': 'Praticien Autre',
            'category_id': [(4, cls.cat_praticien.id)],
            'user_ids': [(4, cls.user_autre.id)],
        })
        cls.patient = cls.env['res.partner'].create({
            'name': 'Patient Test',
            'category_id': [(4, cls.cat_patient.id)],
        })

        cls.acte_type = cls.env['cps.acte.type'].create({
            'name': 'Acte test',
            'lettre_cle': 'AMK',
            'coefficient_defaut': 7.5,
            'tarif_unitaire': 490,
            'profession': 'kinesitherapeute',
        })

        cls.feuille_kine = cls.env['cps.feuille.soins'].create({
            'praticien_id': cls.praticien_kine.id,
            'patient_id':   cls.patient.id,
            'date_soins':   '2026-04-10',
        })
        cls.feuille_autre = cls.env['cps.feuille.soins'].create({
            'praticien_id': cls.praticien_autre.id,
            'patient_id':   cls.patient.id,
            'date_soins':   '2026-04-11',
        })

    # ── Filtre "Mes feuilles" ─────────────────────────────────────────────

    def test_mes_feuilles_retourne_feuilles_praticien_connecte(self):
        """
        Le domaine [('praticien_id.user_ids', 'in', [uid])] doit retourner
        uniquement les feuilles du praticien lié à l'utilisateur connecté.
        """
        feuilles = self.env['cps.feuille.soins'].with_user(self.user_kine).search(
            [('praticien_id.user_ids', 'in', [self.user_kine.id])]
        )
        self.assertIn(self.feuille_kine, feuilles,
                      "La feuille du kiné doit être retournée.")
        self.assertNotIn(self.feuille_autre, feuilles,
                         "La feuille d'un autre praticien ne doit pas être retournée.")

    def test_mes_feuilles_exclut_autres(self):
        """L'utilisateur 'autre' ne doit pas voir la feuille du kiné."""
        feuilles = self.env['cps.feuille.soins'].with_user(self.user_autre).search(
            [('praticien_id.user_ids', 'in', [self.user_autre.id])]
        )
        self.assertIn(self.feuille_autre, feuilles)
        self.assertNotIn(self.feuille_kine, feuilles)

    # ── Formatage virgule ─────────────────────────────────────────────────

    def test_format_montant_entier(self):
        """Un montant entier ne doit pas afficher de décimale."""
        result = self.feuille_kine._format_amount(3675)
        # Pas de point décimal, espace insécable comme séparateur de milliers
        self.assertNotIn('.', result)

    def test_format_montant_decimal(self):
        """Un montant décimal doit utiliser la virgule, pas le point."""
        result = self.feuille_kine._format_amount(3675.50)
        self.assertIn(',', result)
        self.assertNotIn('.', result)
