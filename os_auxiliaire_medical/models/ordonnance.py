from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import requests


class CpsOrdonnance(models.Model):
    _name = 'cps.ordonnance'
    _description = 'Ordonnance CPS'
    _order = 'date_prescription desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Référence', copy=False, readonly=True, default='/',
    )
    state = fields.Selection([
        ('brouillon', 'Brouillonne'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
    ], default='brouillon', tracking=True)

    praticien_id = fields.Many2one(
        'res.partner', string='Praticien',
        domain="[('category_id.name', '=', 'Praticien CPS')]",
        required=True, default=lambda self: self._default_praticien(),
    )
    patient_id = fields.Many2one(
        'res.partner', string='Patient',
        domain="[('category_id.name', '=', 'Patient CPS')]",
        required=False, index=True,
    )
    prescripteur_id = fields.Many2one(
        'res.partner', string='Prescripteur',
        domain="[('category_id.name', '=', 'Prescripteur')]",
    )
    company_id = fields.Many2one(
        'res.company', string='Société',
        required=True, default=lambda self: self.env.company,
    )
    date_prescription = fields.Date(string='Date de prescription', required=False)
    date_fin_validite = fields.Date(string='Fin de validité')
    ordonnance_image = fields.Binary(string="Photo de l'ordonnance", attachment=True)
    ordonnance_filename = fields.Char()

    ligne_ids = fields.One2many(
        'cps.ordonnance.ligne', 'ordonnance_id', string='Lignes',
    )

    notes = fields.Text()

    # ── Profession du praticien : champ plat pour les contextes de vue XML ────
    # Odoo 17 interdit les chemins pointés (parent.praticien_id.cps_profession)
    # dans les attributs context/domain des vues. On expose donc la clé de
    # profession directement sur l'ordonnance.
    praticien_profession = fields.Char(
        string='Profession praticien',
        compute='_compute_praticien_profession',
        store=False,
    )

    # Ajouter cette contrainte pour maintenir la cohérence métier :
    @api.constrains('patient_id', 'date_prescription', 'ligne_ids')
    def _check_required_for_validation(self):
        for rec in self:
            if rec.state != 'brouillon':
                if not rec.patient_id:
                    raise UserError(_("Le patient est obligatoire pour valider l'ordonnance."))
                if not rec.date_prescription:
                    raise UserError(_("La date de prescription est obligatoire pour valider l'ordonnance."))

    @api.depends('praticien_id', 'praticien_id.category_id',
                 'praticien_id.category_id.parent_id')
    def _compute_praticien_profession(self):
        for rec in self:
            if rec.praticien_id and hasattr(rec.praticien_id, 'get_cps_profession_key'):
                rec.praticien_profession = rec.praticien_id.get_cps_profession_key() or ''
            else:
                rec.praticien_profession = ''

    # ──────────────────────────────────────────────────────────────────────────

    def _default_praticien(self):
        return self.env.user.partner_id.filtered(
            lambda p: 'Praticien CPS' in p.category_id.mapped('name')
        ) or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'cps.ordonnance'
                ) or '/'
            if not vals.get('date_fin_validite') and vals.get('date_prescription'):
                from datetime import date, timedelta
                validite = int(
                    self.env['ir.config_parameter'].sudo()
                    .get_param('cps.ordonnance.validite_jours', 90)
                )
                d = fields.Date.from_string(vals['date_prescription'])
                vals['date_fin_validite'] = (d + timedelta(days=validite)).isoformat()
        return super().create(vals_list)

    @api.onchange('date_prescription')
    def _onchange_date_prescription(self):
        if self.date_prescription:
            from datetime import timedelta
            validite = int(
                self.env['ir.config_parameter'].sudo()
                .get_param('cps.ordonnance.validite_jours', 90)
            )
            self.date_fin_validite = (
                    self.date_prescription + timedelta(days=validite)
            )

    # ── OCR ────────────────────────────────────────────────────────────

    def action_open_ocr_wizard(self):
        """Ouvre le wizard d'import OCR en pré-remplissant l'ordonnance courante."""
        self.ensure_one()
        wizard = self.env['cps.wizard.ocr.ordonnance'].create({
            'ordonnance_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': "Import OCR d'une ordonnance",
            'res_model': 'cps.wizard.ocr.ordonnance',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ── OCR Claude ────────────────────────────────────────────────────────────

    def action_ocr_ordonnance(self):
        """Lance l'analyse OCR de l'image d'ordonnance via l'API Anthropic."""
        self.ensure_one()
        if not self.ordonnance_image:
            raise UserError(_("Veuillez d'abord charger une photo de l'ordonnance."))

        IrParam = self.env['ir.config_parameter'].sudo()
        api_key = IrParam.get_param('cps.anthropic.api.key', '')
        if not api_key:
            raise UserError(_(
                "Clé API Anthropic non configurée. "
                "Allez dans Paramètres CPS → Configuration."
            ))
        model = IrParam.get_param(
            'cps.claude.model', 'claude-haiku-4-5-20251001'
        )

        img_data = self.ordonnance_image
        img_bytes = base64.b64decode(img_data)
        # Détecter le type MIME simplement
        if img_bytes[:3] == b'\xff\xd8\xff':
            media_type = 'image/jpeg'
        elif img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            media_type = 'image/png'
        else:
            media_type = 'image/jpeg'

        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": img_data if isinstance(img_data, str)
                            else img_data.decode(),
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Tu es un assistant médical spécialisé en Polynésie française. "
                            "Extrait de cette ordonnance médicale : "
                            "1. Le nom et prénom du patient. "
                            "2. La date de prescription (format YYYY-MM-DD). "
                            "3. Les actes prescrits avec lettre clé, coefficient et quantité. "
                            "4. Le nom du médecin prescripteur. "
                            "Réponds en JSON structuré uniquement."
                        ),
                    },
                ],
            }],
        }

        try:
            resp = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            body = resp.json()

            # ── Comptabiliser les tokens ──────────────────────────────────
            usage = body.get('usage', {})
            self.env['cps.api.usage'].log_usage(
                model=model,
                operation='ocr_vision',
                input_tokens=usage.get('input_tokens', 0),
                output_tokens=usage.get('output_tokens', 0),
                ordonnance_id=self.id,
            )

            # ── Traiter la réponse ────────────────────────────────────────
            texte = ''.join(
                b.get('text', '') for b in body.get('content', [])
                if b.get('type') == 'text'
            )
            return self._parse_ocr_response(texte)

        except requests.RequestException as e:
            self.env['cps.api.usage'].log_usage(
                model=model,
                operation='ocr_vision',
                success=False,
                error_message=str(e),
                ordonnance_id=self.id,
            )
            raise UserError(_("Erreur API Anthropic : %s") % str(e))

    def _parse_ocr_response(self, texte):
        """Parse la réponse JSON de l'OCR et pré-remplit les champs."""
        import json, re
        match = re.search(r'\{.*\}', texte, re.DOTALL)
        if not match:
            raise UserError(_(
                "La réponse de l'IA ne contient pas de JSON valide.\n%s"
            ) % texte[:500])
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            raise UserError(_("JSON invalide : %s") % str(e))

        vals = {}
        # Patient
        if data.get('patient'):
            p = data['patient']
            nom = p.get('nom', '')
            prenom = p.get('prenom', '')
            if nom or prenom:
                patient = self.env['res.partner'].search(
                    [('name', 'ilike', f"{nom} {prenom}".strip())], limit=1
                )
                if patient:
                    vals['patient_id'] = patient.id

        # Date de prescription
        if data.get('date_prescription'):
            try:
                vals['date_prescription'] = fields.Date.from_string(
                    data['date_prescription']
                )
            except Exception:
                pass

        if vals:
            self.write(vals)

        # Lignes d'actes
        if data.get('actes'):
            for acte_data in data['actes']:
                self._create_ligne_from_ocr(acte_data)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('OCR réussi'),
                'message': _(
                    'L\'ordonnance a été analysée. Vérifiez les informations extraites.'
                ),
                'type': 'success', 'sticky': False,
            },
        }

    def _create_ligne_from_ocr(self, acte_data):
        """Crée une ligne d'ordonnance depuis les données OCR."""
        lettre_cle = acte_data.get('lettre_cle', '')
        coefficient = acte_data.get('coefficient', 0)
        quantite = acte_data.get('quantite', 1)

        acte_type = self.env['cps.acte.type'].search([
            ('lettre_cle', '=', lettre_cle),
            ('coefficient_defaut', '=', float(coefficient)),
        ], limit=1)

        if acte_type:
            # nb_seances_defaut depuis le type d'acte (comme pour la sélection manuelle)
            quantite = acte_type.nb_seances_defaut or quantite or 1

        self.env['cps.ordonnance.ligne'].create({
            'ordonnance_id': self.id,
            'acte_type_id': acte_type.id if acte_type else False,
            'lettre_cle': lettre_cle,
            'coefficient': float(coefficient or 0),
            'nb_seances': quantite,
        })


class CpsOrdonnanceLigne(models.Model):
    _name = 'cps.ordonnance.ligne'
    _description = "Ligne d'ordonnance CPS"
    _order = 'sequence, id'

    ordonnance_id = fields.Many2one(
        'cps.ordonnance', string='Ordonnance', required=True, ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)

    acte_type_id = fields.Many2one(
        'cps.acte.type',
        string="Type d'acte",
        domain=(
            "['|', ('company_id', '=', False),"
            " ('company_id', '=', parent.company_id)]"
        ),
    )

    # ── Champs dénormalisés (remplis depuis le type d'acte) ───────────────────
    lettre_cle = fields.Char(string='Lettre clé', size=10)
    coefficient = fields.Float(string='Coefficient', digits=(6, 2))
    tarif_unitaire = fields.Float(string='Tarif unitaire', digits=(10, 0))
    montant_unitaire = fields.Float(
        string='Montant / séance', compute='_compute_montants', store=True,
    )
    montant_total = fields.Float(
        string='Montant total', compute='_compute_montants', store=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # FIX / FEATURE : quantité par défaut depuis cps.acte.type.nb_seances_defaut
    # ──────────────────────────────────────────────────────────────────────────
    nb_seances = fields.Integer(
        string='Nb séances',
        default=1,
        help='Pré-rempli automatiquement depuis le type d\'acte (nb_seances_defaut).',
    )
    nb_seances_max = fields.Integer(
        string='Séances max', related='acte_type_id.nb_seances_max', readonly=True,
    )
    nb_seances_realises = fields.Integer(string='Séances réalisées', default=0)
    nb_seances_restantes = fields.Integer(
        string='Séances restantes',
        compute='_compute_restants', store=True,
    )

    notes = fields.Char(string='Remarques')

    # ── Onchange : remplissage automatique depuis le type d'acte ──────────────

    @api.onchange('acte_type_id')
    def _onchange_acte_type_id(self):
        """
        FEATURE : Lors de la sélection d'un type d'acte, recopier :
          • lettre_cle, coefficient, tarif_unitaire
          • nb_seances  ← nb_seances_defaut  (QUANTITÉ PAR DÉFAUT)
        """
        if self.acte_type_id:
            at = self.acte_type_id
            self.lettre_cle = at.lettre_cle
            self.coefficient = at.coefficient_defaut
            self.tarif_unitaire = at.tarif_unitaire
            # ← Point spécifiquement demandé :
            self.nb_seances = at.nb_seances_defaut or 1
        else:
            self.lettre_cle = False
            self.coefficient = 0.0
            self.tarif_unitaire = 0.0
            self.nb_seances = 1

    # ── Calculs ──────────────────────────────────────────────────────────────

    @api.depends('coefficient', 'tarif_unitaire', 'nb_seances')
    def _compute_montants(self):
        for rec in self:
            rec.montant_unitaire = round(rec.coefficient * rec.tarif_unitaire, 0)
            rec.montant_total = rec.montant_unitaire * rec.nb_seances

    @api.depends('nb_seances', 'nb_seances_realises')
    def _compute_restants(self):
        for rec in self:
            rec.nb_seances_restantes = max(
                0, (rec.nb_seances or 0) - (rec.nb_seances_realises or 0)
            )

    @api.constrains('nb_seances', 'nb_seances_max')
    def _check_nb_seances(self):
        for rec in self:
            if rec.nb_seances_max and rec.nb_seances > rec.nb_seances_max:
                raise UserError(_(
                    "Le nombre de séances (%d) dépasse le maximum autorisé "
                    "pour cet acte (%d séances)."
                ) % (rec.nb_seances, rec.nb_seances_max))
