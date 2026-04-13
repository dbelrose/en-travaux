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
    # Les actes de nomenclature NPAP sont des données réglementaires
    # partagées entre toutes les sociétés (company_id = False).
    # company_id peut être renseigné pour des actes spécifiques à une société.
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
        Point d'entrée alternatif depuis un bouton ou un menu personnalisé.
        Enrichit le contexte avec la profession du praticien connecté
        afin que le filtre "Ma profession" soit actif et pertinent.

        Usage dans le menu XML :
            <menuitem action="action_open_acte_type_menu" .../>

        avec :
            <record id="action_open_acte_type_menu" model="ir.actions.act_window">
                ...
                <field name="binding_model_id" .../>
            </record>

        Ou directement en remplaçant action_acte_type par un server action
        qui appelle self.env['cps.acte.type'].action_open_acte_type().
        """
        praticien = self.env['cps.praticien'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )
        profession = praticien.profession if praticien else False

        action = self.env['ir.actions.act_window']._for_xml_id(
            'os_auxiliaire_medical.action_acte_type'
        )
        # Injecte default_profession dans le contexte existant de l'action
        ctx = dict(action.get('context') or {})
        ctx['default_profession'] = profession
        ctx['search_default_ma_profession'] = 1 if profession else 0
        action['context'] = ctx
        return action
