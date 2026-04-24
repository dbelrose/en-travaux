import json
import base64
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CpsWizardOcrOrdonnance(models.TransientModel):
    """
    Assistant d'import OCR d'une ordonnance.

    Le patient n'est PAS obligatoire à l'ouverture du wizard :
    l'OCR peut reconnaître le nom du patient depuis l'image et le créer
    ou le lier automatiquement. L'utilisateur peut aussi le renseigner
    manuellement après l'import.
    """
    _name = 'cps.wizard.ocr.ordonnance'
    _description = "Wizard import OCR ordonnance"

    ordonnance_id = fields.Many2one('cps.ordonnance', string='Ordonnance cible')

    # Patient optionnel : l'OCR peut le déduire
    patient_id = fields.Many2one(
        'res.partner', string='Patient',
        domain="[('category_id.name', '=', 'Patient CPS')]",
        # required=False intentionnel – voir docstring
        help="Laissez vide pour que l'OCR tente d'identifier le patient depuis l'image.",
    )

    image = fields.Binary(string="Image de l'ordonnance", required=True)
    image_filename = fields.Char()

    result_raw   = fields.Text(string='Réponse brute OCR', readonly=True)
    result_lines = fields.Text(string='Lignes reconnues', readonly=True)
    state = fields.Selection([
        ('draft', 'Prêt'), ('done', 'Importé'), ('error', 'Erreur'),
    ], default='draft')
    error_msg = fields.Char(readonly=True)

    def action_run_ocr(self):
        self.ensure_one()
        if not self.image:
            raise UserError(_("Veuillez joindre une image de l'ordonnance."))

        IrParam = self.env['ir.config_parameter'].sudo()
        api_key = IrParam.get_param('claude_api_key', '')
        if not api_key:
            raise UserError(_("Clé API Anthropic non configurée (Paramètres > Technique > Paramètres système > claude_api_key)."))

        try:
            import anthropic
        except ImportError:
            raise UserError(_("Le paquet Python 'anthropic' n'est pas installé sur le serveur."))

        image_b64 = self.image.decode() if isinstance(self.image, bytes) else self.image
        # Détecter le media type depuis le nom de fichier
        fname = (self.image_filename or '').lower()
        if fname.endswith('.png'):
            media_type = 'image/png'
        elif fname.endswith('.jpg') or fname.endswith('.jpeg'):
            media_type = 'image/jpeg'
        elif fname.endswith('.webp'):
            media_type = 'image/webp'
        else:
            media_type = 'image/jpeg'

        prompt = (
            "Tu es un assistant médical. Analyse cette ordonnance et extrais en JSON :\n"
            "{\n"
            "  \"patient_nom\": \"...\",\n"
            "  \"prescripteur_nom\": \"...\",\n"
            "  \"date\": \"JJ/MM/AAAA\",\n"
            "  \"actes\": [\n"
            "    {\"lettre_cle\": \"...\", \"coefficient\": ..., \"nb_seances\": ...}\n"
            "  ]\n"
            "}\n"
            "Réponds uniquement avec le JSON, sans texte autour."
        )

        client = anthropic.Anthropic(api_key=api_key)
        try:
            response = client.messages.create(
                model=IrParam.get_param('claude_model', 'claude-haiku-4-5-20251001'),
                max_tokens=1024,
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'image', 'source': {
                            'type': 'base64', 'media_type': media_type, 'data': image_b64,
                        }},
                        {'type': 'text', 'text': prompt},
                    ],
                }],
            )
            raw = response.content[0].text if response.content else ''
        except Exception as exc:
            self.state = 'error'
            self.error_msg = str(exc)
            return self._reopen()

        self.result_raw = raw

        # Parse JSON
        try:
            # Nettoyer les balises Markdown éventuelles
            clean = re.sub(r'```(?:json)?', '', raw).strip('` \n')
            data = json.loads(clean)
        except json.JSONDecodeError:
            self.state = 'error'
            self.error_msg = _("L'OCR n'a pas retourné un JSON valide : %s") % raw[:200]
            return self._reopen()

        lines_info = []

        # ── Patient ──────────────────────────────────────────────────────
        patient = self.patient_id
        if not patient and data.get('patient_nom'):
            patient = self.env['res.partner'].search(
                [('name', 'ilike', data['patient_nom']),
                 ('category_id.name', '=', 'Patient CPS')], limit=1,
            )
            if not patient:
                lines_info.append(_("⚠ Patient '%s' non trouvé – à associer manuellement.") % data['patient_nom'])
            else:
                lines_info.append(_("✔ Patient détecté : %s") % patient.name)

        # ── Mise à jour de l'ordonnance ──────────────────────────────────
        ordonnance = self.ordonnance_id
        if ordonnance and patient and not ordonnance.patient_id:
            ordonnance.patient_id = patient

        # ── Prescripteur ────────────────────────────────────────────────
        if data.get('prescripteur_nom') and ordonnance:
            pres = self.env['res.partner'].search(
                [('name', 'ilike', data['prescripteur_nom']),
                 ('category_id.name', '=', 'Prescripteur')], limit=1,
            )
            if pres and not ordonnance.prescripteur_id:
                ordonnance.prescripteur_id = pres

        # ── Actes ────────────────────────────────────────────────────────
        actes_importes = 0
        for acte_data in (data.get('actes') or []):
            lettre = (acte_data.get('lettre_cle') or '').upper().strip()
            if not lettre:
                continue
            acte_type = self.env['cps.acte.type'].search(
                [('lettre_cle', '=', lettre)], limit=1,
            )
            if not acte_type:
                lines_info.append(_("⚠ Lettre clé '%s' non trouvée dans le référentiel.") % lettre)
                continue
            if ordonnance:
                # Vérifier l'unicité (contrainte modèle)
                if acte_type in ordonnance.ligne_ids.mapped('acte_type_id'):
                    lines_info.append(_("⚠ Acte '%s' déjà présent dans l'ordonnance, ignoré.") % lettre)
                    continue
                coef = acte_data.get('coefficient') or acte_type.coefficient_defaut
                nb   = acte_data.get('nb_seances') or acte_type.nb_seances_defaut or 1
                self.env['cps.ordonnance.ligne'].create({
                    'ordonnance_id':       ordonnance.id,
                    'acte_type_id':        acte_type.id,
                    'nb_seances_prescrites': nb,
                })
                actes_importes += 1
                lines_info.append(_("✔ Acte %s – %s séance(s)") % (lettre, nb))

        self.result_lines = '\n'.join(lines_info)
        self.state = 'done'
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
