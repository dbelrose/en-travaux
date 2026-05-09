from odoo import models, fields, api, _


class CpsTarifHistorique(models.Model):
    _name = 'cps.tarif.historique'
    _description = 'Historique des tarifs CPS (valeurs de lettres clés et suppléments)'
    _order = 'date_application desc, lettre_cle'
    _rec_name = 'name'

    name = fields.Char(
        string='Libellé',
        compute='_compute_name', store=True, readonly=False,
    )
    date_application = fields.Date(
        string="Date d'application", required=True,
        default=fields.Date.today,
    )
    lettre_cle = fields.Char(
        string='Lettre clé', required=True, size=10,
        help='AMO, AMK, AMS, AMI, AMY, AMP, AIS, DI…',
    )
    tarif_unitaire = fields.Float(
        string='Tarif unitaire (F XPF)', required=True, digits=(10, 0),
    )

    # ── Suppléments associés à cette révision tarifaire ─────────────────────
    supplement_ifd = fields.Float(
        string='Supplément IFD / unité (F XPF)', digits=(10, 0), default=0,
        help='Laisser 0 pour ne pas modifier la valeur en vigueur.',
    )
    supplement_ifn = fields.Float(
        string='Supplément IFN fixe (F XPF)', digits=(10, 0), default=0,
        help='Laisser 0 pour ne pas modifier la valeur en vigueur.',
    )

    reference = fields.Char(
        string='Référence réglementaire',
        help="Numéro d'arrêté (ex : Arrêté n° 1239 CM du 31/07/2024).",
    )
    notes = fields.Text(string='Notes')
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company', string='Société',
        required=True, default=lambda self: self.env.company, index=True,
    )

    # ── Compute ──────────────────────────────────────────────────────────────

    @api.depends('lettre_cle', 'tarif_unitaire', 'date_application')
    def _compute_name(self):
        for rec in self:
            if rec.lettre_cle and rec.tarif_unitaire and rec.date_application:
                tarif_str = '{:,}'.format(int(rec.tarif_unitaire)).replace(',', '\u202f')
                rec.name = (
                    f"{rec.lettre_cle} – {tarif_str} F XPF "
                    f"(dès le {rec.date_application.strftime('%d/%m/%Y')})"
                )
            elif not rec.name:
                rec.name = ''

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_appliquer_tarif(self):
        """
        • Met à jour le tarif_unitaire de tous les actes portant la même lettre clé.
        • Met à jour le paramètre de configuration correspondant.
        • Met à jour les suppléments IFD/IFN si renseignés.
        """
        self.ensure_one()
        IrParam = self.env['ir.config_parameter'].sudo()
        ActeType = self.env['cps.acte.type']

        lk = self.lettre_cle.upper()

        # --- Actes ---
        actes = ActeType.search([('lettre_cle', '=', lk)])
        actes.write({'tarif_unitaire': self.tarif_unitaire})

        # --- Paramètre de configuration ---
        config_map = {
            'AMO': 'cps.tarif.amo', 'AMK': 'cps.tarif.amo',
            'AMY': 'cps.tarif.amy',
            'AMI': 'cps.tarif.ami', 'AIS': 'cps.tarif.ami', 'DI': 'cps.tarif.ami',
            'AMS': 'cps.tarif.ams', 'AMP': 'cps.tarif.ams',
        }
        if lk in config_map:
            IrParam.set_param(config_map[lk], str(self.tarif_unitaire))

        # --- Suppléments optionnels ---
        if self.supplement_ifd:
            IrParam.set_param('cps.supplement.ifd', str(self.supplement_ifd))
        if self.supplement_ifn:
            IrParam.set_param('cps.supplement.ifn', str(self.supplement_ifn))

        count = len(actes)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tarif appliqué'),
                'message': _(
                    '%d acte(s) %s mis à jour → %d F XPF.'
                ) % (count, lk, int(self.tarif_unitaire)),
                'type': 'success',
                'sticky': False,
            },
        }
