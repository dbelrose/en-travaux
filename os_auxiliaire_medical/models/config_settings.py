from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Clé API Anthropic ─────────────────────────────────────────────────────
    cps_anthropic_api_key = fields.Char(
        string='Clé API Anthropic (OCR Claude)',
        config_parameter='cps.anthropic.api.key',
        help="Clé secrète Anthropic pour l'option d'analyse OCR par Claude Haiku 4.5. Format : sk-ant-...",
    )

    # ── Durée de validité ordonnance ──────────────────────────────────────────
    cps_ordonnance_validite_jours = fields.Integer(
        string="Durée de validité d'une ordonnance (jours)",
        config_parameter='cps.ordonnance.validite_jours',
        default=90,
        help='Nombre de jours ajoutés à la date de prescription pour calculer '
             'automatiquement la date de fin de validité. Défaut : 90 jours.',
    )

    # ── Tarifs par lettre clé ─────────────────────────────────────────────────
    cps_tarif_amo = fields.Float(
        string='Tarif AMO / AMK (F XPF)', config_parameter='cps.tarif.amo',
        default=490, digits=(10, 0),
    )
    cps_tarif_ami = fields.Float(
        string='Tarif AMI / AIS / DI (F XPF)', config_parameter='cps.tarif.ami',
        default=366, digits=(10, 0),
    )
    cps_tarif_ams = fields.Float(
        string='Tarif AMS / AMP (F XPF)', config_parameter='cps.tarif.ams',
        default=283, digits=(10, 0),
    )
    cps_tarif_amy = fields.Float(
        string='Tarif AMY (F XPF)', config_parameter='cps.tarif.amy',
        default=490, digits=(10, 0),
    )

    # ── Suppléments ───────────────────────────────────────────────────────────
    cps_supplement_ifd = fields.Float(
        string='Supplément IFD / unité (F XPF)', config_parameter='cps.supplement.ifd',
        default=250, digits=(10, 0),
    )
    cps_supplement_ifn = fields.Float(
        string='Supplément IFN fixe (F XPF)', config_parameter='cps.supplement.ifn',
        default=250, digits=(10, 0),
    )
    cps_taux_remboursement_defaut = fields.Float(
        string='Taux de remboursement par défaut (%)',
        config_parameter='cps.taux.remboursement', default=70.0,
    )

    def action_update_all_actes_tarifs(self):
        IrParam = self.env['ir.config_parameter'].sudo()
        ActeType = self.env['cps.acte.type']
        mapping = {
            'AMO': float(IrParam.get_param('cps.tarif.amo', 490)),
            'AMK': float(IrParam.get_param('cps.tarif.amo', 490)),
            'AMY': float(IrParam.get_param('cps.tarif.amy', 490)),
            'AMI': float(IrParam.get_param('cps.tarif.ami', 366)),
            'AIS': float(IrParam.get_param('cps.tarif.ami', 366)),
            'DI':  float(IrParam.get_param('cps.tarif.ami', 366)),
            'AMS': float(IrParam.get_param('cps.tarif.ams', 283)),
            'AMP': float(IrParam.get_param('cps.tarif.ams', 283)),
        }
        count = 0
        for lk, tarif in mapping.items():
            actes = ActeType.search([('lettre_cle', '=', lk)])
            if actes:
                actes.write({'tarif_unitaire': tarif})
                count += len(actes)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tarifs mis à jour'),
                'message': _('%d acte(s) mis à jour depuis la configuration.') % count,
                'type': 'success', 'sticky': False,
            },
        }
