from odoo import models, fields, api


class CpsApiUsage(models.Model):
    """
    Enregistre chaque appel à l'API Anthropic Claude avec le nombre de
    tokens consommés, par utilisateur et par société.
    """
    _name = 'cps.api.usage'
    _description = 'Consommation API Claude (tokens)'
    _order = 'date desc'
    _rec_name = 'date'

    user_id = fields.Many2one(
        'res.users', string='Utilisateur', required=True, index=True,
        default=lambda self: self.env.user, ondelete='restrict',
    )
    company_id = fields.Many2one(
        'res.company', string='Société', required=True, index=True,
        default=lambda self: self.env.company, ondelete='restrict',
    )
    date = fields.Datetime(
        string='Date / Heure', required=True, default=fields.Datetime.now, index=True,
    )
    model = fields.Char(string='Modèle Claude', required=True)
    operation = fields.Selection([
        ('ocr_texte',  'OCR – Texte'),
        ('ocr_vision', 'OCR – Vision'),
    ], string='Opération', required=True)

    # Référence optionnelle à l'ordonnance traitée
    ordonnance_id = fields.Many2one(
        'cps.ordonnance', string='Ordonnance', ondelete='set null',
    )

    input_tokens  = fields.Integer(string='Tokens entrée',  default=0)
    output_tokens = fields.Integer(string='Tokens sortie',  default=0)
    total_tokens  = fields.Integer(
        string='Total tokens', compute='_compute_total', store=True,
    )

    # Statut de l'appel
    success = fields.Boolean(string='Succès', default=True)
    error_message = fields.Char(string="Message d'erreur")

    @api.depends('input_tokens', 'output_tokens')
    def _compute_total(self):
        for rec in self:
            rec.total_tokens = (rec.input_tokens or 0) + (rec.output_tokens or 0)

    @api.model
    def log_usage(self, model, operation, input_tokens=0, output_tokens=0,
                  ordonnance_id=None, success=True, error_message=None):
        """
        Méthode utilitaire appelée depuis les wizards OCR pour enregistrer
        la consommation.

        Usage :
            self.env['cps.api.usage'].log_usage(
                model='claude-haiku-4-5-20251001',
                operation='ocr_texte',
                input_tokens=body.get('usage', {}).get('input_tokens', 0),
                output_tokens=body.get('usage', {}).get('output_tokens', 0),
                ordonnance_id=self.ordonnance_id.id,
            )
        """
        vals = {
            'model': model,
            'operation': operation,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'success': success,
        }
        if ordonnance_id:
            vals['ordonnance_id'] = ordonnance_id
        if error_message:
            vals['error_message'] = error_message
        return self.sudo().create([vals])
