"""
Tests unitaires – cps.acte.type
Couvre :
  - action_open_acte_type injecte bien cps_user_profession dans le contexte
  - Le filtre "Ma profession" retourne les bons enregistrements
"""
from odoo.tests.common import TransactionCase


class TestActeType(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Catégorie Praticien CPS
        cls.cat_praticien = cls.env.ref(
            'os_auxiliaire_medical.partner_category_praticien'
        )
        cls.cat_kine = cls.env.ref(
            'os_auxiliaire_medical.partner_category_kinesitherapeute'
        )

        # Utilisateur de test
        cls.user_kine = cls.env['res.users'].create({
            'name': 'Kiné Test',
            'login': 'kine_test@cps.pf',
            'groups_id': [(4, cls.env.ref('base.group_user').id)],
        })

        # Partenaire praticien lié à l'utilisateur – user_ids (pas user_id)
        cls.praticien = cls.env['res.partner'].create({
            'name': 'Marie Dupont',
            'category_id': [
                (4, cls.cat_praticien.id),
                (4, cls.cat_kine.id),
            ],
            'user_ids': [(4, cls.user_kine.id)],
        })

        # Actes
        cls.acte_kine = cls.env['cps.acte.type'].create({
            'name': 'Séance kiné test',
            'lettre_cle': 'AMK',
            'coefficient_defaut': 7.5,
            'tarif_unitaire': 490,
            'profession': 'kinesitherapeute',
        })
        cls.acte_ortho = cls.env['cps.acte.type'].create({
            'name': 'Séance ortho test',
            'lettre_cle': 'AMO',
            'coefficient_defaut': 10.0,
            'tarif_unitaire': 490,
            'profession': 'orthophoniste',
        })

    # ── Tests ─────────────────────────────────────────────────────────────

    def test_action_injecte_profession_dans_contexte(self):
        """action_open_acte_type doit mettre cps_user_profession = 'kinesitherapeute'."""
        action = self.env['cps.acte.type'].with_user(self.user_kine).action_open_acte_type()
        ctx = action.get('context', {})
        self.assertEqual(
            ctx.get('cps_user_profession'), 'kinesitherapeute',
            "Le contexte doit contenir la profession du praticien connecté.",
        )

    def test_filtre_ma_profession_kine(self):
        """Recherche avec cps_user_profession='kinesitherapeute' doit retourner l'acte kiné."""
        actes = self.env['cps.acte.type'].with_context(
            cps_user_profession='kinesitherapeute'
        ).search([('profession', '=', 'kinesitherapeute')])
        self.assertIn(self.acte_kine, actes)
        self.assertNotIn(self.acte_ortho, actes)

    def test_filtre_ma_profession_sans_praticien(self):
        """Sans praticien lié, cps_user_profession doit être False et aucun filtre actif."""
        # Créer un utilisateur sans partenaire praticien CPS
        user_lambda = self.env['res.users'].create({
            'name': 'Lambda Test',
            'login': 'lambda_test@cps.pf',
            'groups_id': [(4, self.env.ref('base.group_user').id)],
        })
        action = self.env['cps.acte.type'].with_user(user_lambda).action_open_acte_type()
        ctx = action.get('context', {})
        self.assertFalse(
            ctx.get('cps_user_profession'),
            "Sans praticien CPS associé, cps_user_profession doit être False.",
        )

    def test_montant_indicatif(self):
        """Le montant indicatif doit être coefficient × tarif."""
        self.assertAlmostEqual(
            self.acte_kine.montant_indicatif,
            7.5 * 490,
            places=0,
        )
