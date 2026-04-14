import ast
from odoo import models, fields, api


class CpsActeType(models.Model):
    _name = 'cps.acte.type'
    _description = 'Type d\'acte CPS (catalogue)'
    _order = 'profession, lettre_cle, coefficient_defaut'

    name = fields.Char(string='Libellé', required=True)
    lettre_cle = fields.Char(string='Lettre clé', required=True, size=10,
                              help='Ex: AMO, AMK, AMS, AMI...')
    coefficient_defaut = fields.Float(string='Coefficient par défaut', digits=(6, 2))
    tarif_unitaire = fields.Float(string='Tarif unitaire (F CFP)', digits=(10, 0),
                                   help='Valeur de la lettre clé en F CFP')

    # Profession concernée — False / vide = applicable à toutes les professions
    profession = fields.Selection([
        ('kinesitherapeute', 'Masseur-kinésithérapeute'),
        ('orthophoniste', 'Orthophoniste'),
        ('orthoptiste', 'Orthoptiste'),
        ('pedicure', 'Pédicure-Podologue'),
        ('infirmier', 'Infirmier(e)'),
        ('autre', 'Autre'),
    ], string='Profession', help='Laisser vide pour un acte commun à toutes les professions.')

    active = fields.Boolean(default=True)

    # Montant indicatif calculé (coefficient × tarif)
    montant_indicatif = fields.Float(
        string='Montant indicatif (F CFP)',
        compute='_compute_montant_indicatif',
        digits=(10, 0),
    )

    # ── Multi-company ───────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        index=True,
        help='Laisser vide pour que l\'acte soit visible par toutes les sociétés.\n'
             'Renseigner uniquement pour restreindre à une société particulière.',
    )

    # ── Compute ─────────────────────────────────────────────────────────────

    @api.depends('coefficient_defaut', 'tarif_unitaire')
    def _compute_montant_indicatif(self):
        for rec in self:
            rec.montant_indicatif = round(rec.coefficient_defaut * rec.tarif_unitaire, 0)

    def name_get(self):
        result = []
        for rec in self:
            label = f"{rec.lettre_cle} {rec.coefficient_defaut:g} – {rec.name}"
            result.append((rec.id, label))
        return result

    # ── Ouverture depuis le menu — injection de default_profession ──────────

    def action_open_acte_type(self):
        """
        Point d'entrée du menu "Types d'actes".
        Enrichit le contexte avec la profession du praticien connecté
        afin que le filtre "Ma profession" soit actif par défaut.

        Note : ir.actions.act_window stocke le champ `context` en base comme
        une chaîne de caractères (fields.Char). _for_xml_id / read() le
        retourne donc sous forme de str. On utilise ast.literal_eval pour
        le convertir en dict avant de le modifier, en gérant le cas où il
        serait déjà un dict (évolution future d'Odoo).
        """
        praticien = self.env['cps.praticien'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )
        profession = praticien.profession if praticien else False

        action = self.env['ir.actions.act_window']._for_xml_id(
            'os_auxiliaire_medical.action_acte_type'
        )

        # --- Parsing robuste du contexte -----------------------------------
        # Le champ context d'ir.actions.act_window est un Char : read()
        # retourne une str. dict(str) lèverait un TypeError ; on évalue
        # d'abord la chaîne avec ast.literal_eval.
        ctx_raw = action.get('context') or {}
        if isinstance(ctx_raw, str):
            try:
                ctx = ast.literal_eval(ctx_raw)
            except (ValueError, SyntaxError):
                ctx = {}
        else:
            ctx = dict(ctx_raw)
        # -------------------------------------------------------------------

        ctx['default_profession'] = profession
        # Active le filtre "Ma profession" uniquement si une profession est
        # trouvée ; sinon on désactive le filtre pour ne pas masquer tous
        # les actes à un utilisateur sans praticien associé.
        ctx['search_default_ma_profession'] = 1 if profession else 0
        action['context'] = ctx
        return action
