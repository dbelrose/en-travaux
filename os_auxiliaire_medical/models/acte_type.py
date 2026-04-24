import ast
from odoo import models, fields, api


class CpsActeType(models.Model):
    _name = 'cps.acte.type'
    _description = "Type d'acte CPS (catalogue)"
    _order = 'sequence, profession, lettre_cle, coefficient_defaut'

    # ── Ordre de priorité (distribution automatique) ──────────────────────────
    sequence = fields.Integer(
        string='Séquence', default=10,
        help='Ordre de priorité lors de la distribution automatique des séances '
             '(le plus petit en premier).',
    )

    name = fields.Char(string='Libellé', required=True)
    lettre_cle = fields.Char(string='Lettre clé', required=True, size=10,
                              help='Ex: AMO, AMK, AMS, AMI…')
    coefficient_defaut = fields.Float(string='Coefficient par défaut', digits=(6, 2))
    tarif_unitaire = fields.Float(string='Tarif unitaire (F XPF)', digits=(10, 0),
                                   help='Valeur de la lettre clé en F XPF')

    # ── Contraintes de planification ──────────────────────────────────────────
    duree_seance = fields.Integer(
        string='Durée de la séance (min)', default=30,
        help='Durée standard en minutes.',
    )
    nb_seances_defaut = fields.Integer(
        string='Nb de séances par défaut', default=1,
        help='Pré-remplit le nombre de séances dans les lignes d\'ordonnance.',
    )
    nb_seances_max = fields.Integer(
        string='Séances max / prescription', default=0,
        help='0 = pas de limite.',
    )
    delai_min_jours = fields.Integer(
        string='Délai min entre 2 séances (j)', default=0,
        help='Nombre de jours minimum entre deux séances de cet acte. 0 = sans contrainte.',
    )

    # ── Type supplément ───────────────────────────────────────────────────────
    type_supplement = fields.Selection([
        ('none', 'Acte standard'),
        ('ifn', 'Supplément IFN (montant depuis la configuration)'),
        ('ifd', 'Supplément IFD/unité (montant depuis la configuration)'),
    ], string='Type de supplément', default='none')

    profession = fields.Selection([
        ('kinesitherapeute', 'Masseur-kinésithérapeute'),
        ('orthophoniste', 'Orthophoniste'),
        ('orthoptiste', 'Orthoptiste'),
        ('pedicure', 'Pédicure-Podologue'),
        ('infirmier', 'Infirmier(e)'),
        ('autre', 'Autre'),
    ], string='Profession',
       help='Laisser vide pour un acte commun à toutes les professions.')

    active = fields.Boolean(default=True)

    montant_indicatif = fields.Float(
        string='Montant indicatif (F XPF)',
        compute='_compute_montant_indicatif',
        digits=(10, 0),
    )

    company_id = fields.Many2one(
        'res.company', string='Société', index=True,
        help='Laisser vide pour que l\'acte soit visible par toutes les sociétés.',
    )

    @api.depends('coefficient_defaut', 'tarif_unitaire', 'type_supplement')
    def _compute_montant_indicatif(self):
        for rec in self:
            if rec.type_supplement == 'ifn':
                montant = float(
                    self.env['ir.config_parameter'].sudo()
                    .get_param('cps.supplement.ifn', 250)
                )
            elif rec.type_supplement == 'ifd':
                montant = float(
                    self.env['ir.config_parameter'].sudo()
                    .get_param('cps.supplement.ifd', 250)
                )
            else:
                montant = round(rec.coefficient_defaut * rec.tarif_unitaire, 0)
            rec.montant_indicatif = montant

    def name_get(self):
        result = []
        for rec in self:
            coef = '{:g}'.format(rec.coefficient_defaut) if rec.coefficient_defaut else '—'
            label = f"{coef} – {rec.lettre_cle} – {rec.name}"
            result.append((rec.id, label))
        return result

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = list(domain or [])
        if name:
            text_domain = ['|', ('name', operator, name), ('lettre_cle', operator, name)]
            try:
                coef = float(name.replace(',', '.'))
                text_domain = ['|'] + text_domain + [('coefficient_defaut', '=', coef)]
            except (ValueError, TypeError):
                pass
            domain = text_domain + domain
        return self._search(domain, limit=limit, order=order)

    def action_open_acte_type(self):
        praticien = self.env['res.partner'].search(
            [('user_id', '=', self.env.uid), ('category_id.name', '=', 'Praticien CPS')], limit=1
        )
        profession = praticien.get_cps_profession_key() if praticien else False
        action = self.env['ir.actions.act_window']._for_xml_id(
            'os_auxiliaire_medical.action_acte_type'
        )
        ctx_raw = action.get('context') or {}
        if isinstance(ctx_raw, str):
            try:
                ctx = ast.literal_eval(ctx_raw)
            except (ValueError, SyntaxError):
                ctx = {}
        else:
            ctx = dict(ctx_raw)
        ctx['cps_user_profession'] = profession
        ctx['search_default_ma_profession'] = 1 if profession else 0
        action['context'] = ctx
        return action
