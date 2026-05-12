import ast
from odoo import models, fields, api, _
from odoo.exceptions import UserError


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
        help="Pré-remplit le nombre de séances dans les lignes d'ordonnance.",
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
        help="Laisser vide pour que l'acte soit visible par toutes les sociétés. "
             "Un acte partagé modifié génère automatiquement une copie propre à votre société.",
    )

    # ── Indique si l'acte est la copie-société d'un acte partagé ─────────────
    is_company_override = fields.Boolean(
        string='Personnalisation société',
        default=False,
        help="Coché si cet acte est une personnalisation d'un acte partagé pour cette société.",
    )

    note = fields.Text(string='Note', help="Note de référence aux textes.")

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
            if rec.is_company_override:
                label = f"★ {label}"
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

    # ── Copie société sur modification d'un acte partagé ─────────────────────

    def write(self, vals):
        """
        Quand un acte PARTAGÉ (company_id=False) est modifié :
          1. Une copie société est créée (ou mise à jour) avec les nouvelles valeurs.
          2. L'acte partagé d'origine n'est PAS modifié.
        Les actes déjà propres à une société sont modifiés normalement.
        """
        if self.env.context.get('_cps_bypass_shared_write'):
            return super().write(vals)

        shared = self.filtered(lambda r: not r.company_id)
        company_specific = self - shared

        result = True
        if company_specific:
            result = super(CpsActeType, company_specific).write(vals)

        if shared:
            company = self.env.company
            for rec in shared:
                rec._apply_to_company_copy(vals, company)
            # On ne modifie PAS l'enregistrement partagé.
            # On retourne True pour ne pas provoquer d'erreur ORM côté client.
            # Note : le formulaire affichera toujours l'acte partagé original ;
            # la copie société apparaîtra dans la liste avec le préfixe ★.

        return result

    def _apply_to_company_copy(self, vals, company):
        """Crée ou met à jour la copie-société de cet acte partagé."""
        self.ensure_one()
        existing = self.with_context(_cps_bypass_shared_write=True).search([
            ('company_id', '=', company.id),
            ('lettre_cle', '=', self.lettre_cle),
            ('name', '=', self.name),
            ('is_company_override', '=', True),
        ], limit=1)

        if existing:
            super(CpsActeType, existing).write(vals)
        else:
            copy_vals = self._get_copy_vals()
            copy_vals.update(vals)
            copy_vals['company_id'] = company.id
            copy_vals['is_company_override'] = True
            self.with_context(_cps_bypass_shared_write=True).create([copy_vals])

    def _get_copy_vals(self):
        """Retourne un dict avec toutes les valeurs copiables de cet acte."""
        self.ensure_one()
        return {
            'name': self.name,
            'lettre_cle': self.lettre_cle,
            'coefficient_defaut': self.coefficient_defaut,
            'tarif_unitaire': self.tarif_unitaire,
            'profession': self.profession,
            'sequence': self.sequence,
            'duree_seance': self.duree_seance,
            'nb_seances_defaut': self.nb_seances_defaut,
            'nb_seances_max': self.nb_seances_max,
            'delai_min_jours': self.delai_min_jours,
            'type_supplement': self.type_supplement,
            'active': self.active,
        }

    def action_create_company_copy(self):
        """
        Bouton « Personnaliser pour ma société » : crée une copie-société
        modifiable et redirige vers cette copie.
        """
        self.ensure_one()
        if self.company_id:
            raise UserError(_("Cet acte appartient déjà à la société %s.") % self.company_id.name)
        company = self.env.company
        existing = self.search([
            ('company_id', '=', company.id),
            ('lettre_cle', '=', self.lettre_cle),
            ('name', '=', self.name),
            ('is_company_override', '=', True),
        ], limit=1)
        if existing:
            target = existing
        else:
            copy_vals = self._get_copy_vals()
            copy_vals['company_id'] = company.id
            copy_vals['is_company_override'] = True
            target = self.with_context(_cps_bypass_shared_write=True).create([copy_vals])

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': target.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Action d'ouverture avec filtre profession ─────────────────────────────

    def action_open_acte_type(self):
        """
        FIX : l'ancienne version utilisait ('user_id', '=', uid) qui cherche
        le « responsable commercial » du partenaire, pas l'utilisateur connecté.
        On utilise maintenant :
          1. env.user.partner_id  (partenaire propre de l'utilisateur)
          2. Recherche via user_ids (Many2many des utilisateurs liés au partenaire)
        """
        profession = False

        # 1. Partner de l'utilisateur courant
        partner = self.env.user.partner_id
        if partner and hasattr(partner, 'get_cps_profession_key'):
            profession = partner.get_cps_profession_key()

        # 2. Fallback : partenaire lié à l'utilisateur via user_ids
        if not profession:
            praticien = self.env['res.partner'].search([
                ('user_ids', 'in', [self.env.uid]),
                ('category_id.name', '=', 'Praticien CPS'),
            ], limit=1)
            if praticien:
                profession = praticien.get_cps_profession_key()

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
