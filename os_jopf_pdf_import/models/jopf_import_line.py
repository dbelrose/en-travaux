from odoo import models, fields

class JopfImportLine(models.Model):
    _name = 'jopf.import.line'
    _description = 'Ligne import JOPF'
    _order = 'import_id desc, id'

    import_id = fields.Many2one('jopf.import', required=True, ondelete='cascade', index=True)
    association_id = fields.Many2one('res.partner', domain=[('is_company', '=', True)], index=True)
    association_name = fields.Char()
    person_id = fields.Many2one('res.partner', domain=[('is_company', '=', False)], index=True)
    person_name = fields.Char()
    role = fields.Char()
    date_bureau = fields.Char()
    state = fields.Selection([
        ('success', 'OK'), ('created', 'Créé'), ('updated', 'MàJ'),
        ('unchanged', 'Inchangé'), ('error', 'Erreur')
    ], default='success')
    error_message = fields.Text()
