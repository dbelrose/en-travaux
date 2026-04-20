"""
Wizard OCR pour l'import d'ordonnances – v5.
Option : anonymisation du prénom patient + soumission à Claude Haiku 4.5.
"""
import base64, io, re, datetime, json, logging
import urllib.request, urllib.error

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MOIS_FR = {
    'janvier': 1, 'fevrier': 2, 'février': 2, 'mars': 3, 'avril': 4,
    'mai': 5, 'juin': 6, 'juillet': 7, 'aout': 8, 'août': 8,
    'septembre': 9, 'octobre': 10, 'novembre': 11, 'decembre': 12, 'décembre': 12,
}
RE_DATE = re.compile(r'\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})\b')
RE_DATE_L = re.compile(
    r'\b(\d{1,2})\s+(' + '|'.join(MOIS_FR.keys()) + r')\s+(\d{4})\b', re.IGNORECASE)
RE_ACTE = re.compile(
    r'\b(AM[OKYIS]|AMP|AIS|DI)\s*(\d+(?:[.,]\d+)?)'
    r'(?:\s*[xX×]\s*(\d+))?(?:\s*séances?)?', re.IGNORECASE)
RE_DR = re.compile(
    r'(?:Dr\.?|Docteur|M\.?\s+|Mme\.?\s+)\s*'
    r'([A-ZÉÈÀÙÂÊÎÔÛÄ][A-ZÉÈÀÙÂÊÎÔÛÄa-záéèàùâêîôûä\-]+(?:\s+[A-ZÉÈÀÙa-záéèàù\-]+)*)',
    re.UNICODE)
RE_PATIENT = re.compile(
    r'(?:Patient\s*:?\s*|pour\s+(?:M\.?|Mme\.?)\s+|(?:M\.?|Mme\.?)\s+)'
    r'([A-ZÉÈÀÙÂÊÎÔÛÄ][A-ZÉÈÀÙÂÊÎÔÛÄa-záéèàùâêîôûä\-]+(?:\s+[A-ZÉÈÀÙa-záéèàùâêîôûä\-]+)*)',
    re.UNICODE)
RE_CODE_PRESC = re.compile(
    r'(?:code\s*(?:prescripteur)?\s*:?\s*|n°?\s*rpps\s*:?\s*|n°?\s*am\s*:?\s*)'
    r'([A-Z0-9]{4,15})', re.IGNORECASE)


def _parse_date(jj, mm, aaaa):
    try:
        y = int(aaaa); y = y + 2000 if y < 100 else y
        return datetime.date(y, int(mm), int(jj))
    except Exception:
        return None


def _extract_text_pdf(data):
    try:
        from pdfminer.high_level import extract_text
        return extract_text(io.BytesIO(data))
    except ImportError:
        return ''
    except Exception as e:
        _logger.warning('pdfminer: %s', e); return ''


def _extract_text_image(data):
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        for lang in ('fra', 'fra+eng', 'eng'):
            try:
                t = pytesseract.image_to_string(img, lang=lang)
                if t.strip():
                    return t
            except Exception:
                continue
        return ''
    except ImportError:
        return ''
    except Exception as e:
        _logger.warning('pytesseract: %s', e); return ''


def _pdf_to_images(data):
    try:
        from pdf2image import convert_from_bytes
        return convert_from_bytes(data, dpi=200)
    except Exception:
        return []


def parse_ordonnance_text(text):
    result = {
        'prescripteur_nom': '', 'prescripteur_code': '',
        'date_prescription': None, 'patient_nom': '', 'patient_prenom': '',
        'actes': [], 'texte_brut': text,
    }
    if not text:
        return result
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Dates
    dates = []
    for m in RE_DATE.finditer(text):
        d = _parse_date(m.group(1), m.group(2), m.group(3))
        if d and datetime.date(2000,1,1) <= d <= datetime.date(2099,12,31):
            dates.append(d)
    for m in RE_DATE_L.finditer(text.lower()):
        mo = MOIS_FR.get(m.group(2).lower())
        if mo:
            d = _parse_date(m.group(1), mo, m.group(3))
            if d: dates.append(d)
    if dates:
        result['date_prescription'] = max(dates)
    # Prescripteur
    dr = RE_DR.search(text)
    if dr:
        result['prescripteur_nom'] = dr.group(1).strip()
    code = RE_CODE_PRESC.search(text)
    if code:
        result['prescripteur_code'] = code.group(1).strip()
    # Patient
    mid_s = max(0, len(lines) // 4); mid_e = min(len(lines), len(lines)*3//4)
    pm = RE_PATIENT.search('\n'.join(lines[mid_s:mid_e]))
    if pm:
        parts = pm.group(1).strip().split()
        if parts:
            result['patient_nom'] = parts[0].upper()
            result['patient_prenom'] = ' '.join(parts[1:]).capitalize()
    else:
        for line in lines[mid_s:mid_e]:
            if re.match(r'^[A-ZÉÈÀÙÂÊÎÔÛÄ\s\-]{3,40}$', line) and len(line.split()) <= 4:
                parts = line.strip().split()
                if len(parts) >= 2:
                    result['patient_nom'] = parts[0]
                    result['patient_prenom'] = ' '.join(parts[1:]).capitalize()
                    break
    # Actes
    for m in RE_ACTE.finditer(text):
        result['actes'].append({
            'lettre_cle': m.group(1).upper(),
            'coefficient': float(m.group(2).replace(',', '.')),
            'nb_seances': int(m.group(3)) if m.group(3) else 1,
        })
    return result


CLAUDE_SYSTEM_PROMPT = """Tu es un assistant médical analysant des ordonnances de Polynésie française.
Extrais les informations et réponds UNIQUEMENT avec un objet JSON valide, sans markdown ni explication.
Format strict :
{
  "prescripteur_nom": "...",
  "prescripteur_code": "...",
  "date_prescription": "YYYY-MM-DD ou null",
  "patient_nom": "...",
  "actes": [
    {"lettre_cle": "AMO", "coefficient": 10.0, "nb_seances": 30}
  ]
}
Le prénom du patient a été remplacé par [PRÉNOM] pour des raisons de confidentialité.
Ne retourne rien d'autre que le JSON."""


class WizardOcrOrdonnance(models.TransientModel):
    _name = 'cps.wizard.ocr.ordonnance'
    _description = "Import OCR d'une ordonnance (photo ou PDF)"

    ordonnance_id = fields.Many2one('cps.ordonnance', required=True, ondelete='cascade')
    fichier = fields.Binary(string='Fichier (image ou PDF)', required=True)
    fichier_nom = fields.Char(string='Nom du fichier')
    texte_extrait = fields.Text(string='Texte extrait (éditable)')

    # Champs parsés
    prescripteur_nom = fields.Char(string='Nom du prescripteur')
    prescripteur_code = fields.Char(string='Code prescripteur')
    date_prescription = fields.Date(string='Date de prescription')
    patient_nom = fields.Char(string='Nom du patient')
    patient_prenom = fields.Char(string='Prénom du patient')
    actes_detectes = fields.Text(string='Actes détectés', readonly=True)

    # ── Option Claude ──────────────────────────────────────────────────────────
    use_claude_ai = fields.Boolean(
        string='Analyser avec Claude Haiku 4.5',
        default=False,
        help='Envoie le texte (prénom patient anonymisé) à Claude Haiku 4.5 '
             'pour une extraction plus fiable. Nécessite une clé API Anthropic.',
    )
    claude_api_key = fields.Char(
        string='Clé API Anthropic',
        help='Laissez vide pour utiliser la clé configurée dans Paramètres CPS.',
    )
    claude_status = fields.Char(string='Statut Claude', readonly=True)

    etat = fields.Selection([
        ('attente', 'En attente'),
        ('extrait', 'Texte extrait'),
        ('applique', 'Appliqué'),
    ], default='attente', readonly=True)

    # ── Étape 1 : Extraction ──────────────────────────────────────────────────

    def action_extraire(self):
        self.ensure_one()
        if not self.fichier:
            raise UserError(_('Veuillez charger un fichier.'))
        data = base64.b64decode(self.fichier)
        nom = (self.fichier_nom or '').lower()
        texte = ''
        if nom.endswith('.pdf'):
            texte = _extract_text_pdf(data)
            if not texte.strip():
                images = _pdf_to_images(data)
                parts = []
                for img in images:
                    buf = io.BytesIO(); img.save(buf, format='PNG')
                    parts.append(_extract_text_image(buf.getvalue()))
                texte = '\n'.join(parts)
        else:
            texte = _extract_text_image(data)

        if not texte.strip():
            raise UserError(_(
                'Impossible d\'extraire le texte.\n'
                '• PDF texte : pip install pdfminer.six\n'
                '• Image/PDF scanné : pip install pytesseract Pillow + tesseract-ocr-fra'
            ))

        parsed = parse_ordonnance_text(texte)
        actes_txt = self._format_actes(parsed['actes'])

        vals = {
            'texte_extrait': texte,
            'prescripteur_nom': parsed['prescripteur_nom'],
            'prescripteur_code': parsed['prescripteur_code'],
            'date_prescription': parsed['date_prescription'],
            'patient_nom': parsed['patient_nom'],
            'patient_prenom': parsed['patient_prenom'],
            'actes_detectes': actes_txt or _('Aucun acte détecté.'),
            'etat': 'extrait',
        }

        # Appel Claude si demandé
        if self.use_claude_ai:
            vals.update(self._run_claude(texte, parsed.get('patient_prenom', '')))

        self.write(vals)
        return self._reopen()

    def action_reanalyser(self):
        self.ensure_one()
        parsed = parse_ordonnance_text(self.texte_extrait or '')
        actes_txt = self._format_actes(parsed['actes'])
        vals = {
            'prescripteur_nom': parsed['prescripteur_nom'] or self.prescripteur_nom,
            'prescripteur_code': parsed['prescripteur_code'] or self.prescripteur_code,
            'date_prescription': parsed['date_prescription'] or self.date_prescription,
            'patient_nom': parsed['patient_nom'] or self.patient_nom,
            'patient_prenom': parsed['patient_prenom'] or self.patient_prenom,
            'actes_detectes': actes_txt or _('Aucun acte détecté.'),
        }
        if self.use_claude_ai:
            vals.update(self._run_claude(
                self.texte_extrait or '',
                parsed.get('patient_prenom', '') or self.patient_prenom or ''
            ))
        self.write(vals)
        return self._reopen()

    # ── Claude Haiku 4.5 ──────────────────────────────────────────────────────

    def _get_api_key(self):
        if self.claude_api_key:
            return self.claude_api_key
        return self.env['ir.config_parameter'].sudo().get_param(
            'cps.anthropic.api.key', ''
        )

    def _anonymize_prenom(self, texte, prenom):
        """Remplace le prénom du patient par [PRÉNOM] dans le texte."""
        if not prenom or len(prenom) < 2:
            return texte
        return re.sub(re.escape(prenom), '[PRÉNOM]', texte, flags=re.IGNORECASE)

    def _run_claude(self, texte, prenom):
        """
        Anonymise le prénom du patient puis envoie à Claude Haiku 4.5.
        Retourne un dict de vals à merger dans le write().
        """
        api_key = self._get_api_key()
        if not api_key:
            return {'claude_status': _('⚠ Clé API Anthropic non configurée.')}

        texte_anon = self._anonymize_prenom(texte, prenom)

        payload = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 1000,
            'system': CLAUDE_SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': texte_anon}],
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01',
                'x-api-key': api_key,
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            err = e.read().decode('utf-8', errors='replace')
            _logger.error('Claude API HTTP %s: %s', e.code, err)
            return {'claude_status': _('❌ Erreur API Claude : HTTP %s') % e.code}
        except Exception as e:
            _logger.error('Claude API error: %s', e)
            return {'claude_status': _('❌ Erreur réseau : %s') % str(e)}

        # Extraire le texte de la réponse
        try:
            raw = ''
            for block in body.get('content', []):
                if block.get('type') == 'text':
                    raw += block.get('text', '')
            # Nettoyer éventuels blocs markdown
            raw = re.sub(r'```(?:json)?', '', raw).strip()
            data = json.loads(raw)
        except (json.JSONDecodeError, KeyError) as e:
            _logger.warning('Claude JSON parse error: %s – raw: %s', e, raw[:500])
            return {'claude_status': _('⚠ Réponse Claude non parseable.')}

        # Mettre à jour les champs avec les données Claude
        vals = {'claude_status': _('✅ Analyse Claude réussie.')}
        if data.get('prescripteur_nom'):
            vals['prescripteur_nom'] = data['prescripteur_nom']
        if data.get('prescripteur_code'):
            vals['prescripteur_code'] = data['prescripteur_code']
        if data.get('date_prescription'):
            try:
                vals['date_prescription'] = datetime.date.fromisoformat(data['date_prescription'])
            except Exception:
                pass
        if data.get('patient_nom'):
            vals['patient_nom'] = data['patient_nom']
        # Reconstruire le résumé des actes depuis Claude
        actes = data.get('actes', [])
        if actes:
            vals['actes_detectes'] = self._format_actes(actes)
        return vals

    # ── Application ───────────────────────────────────────────────────────────

    def action_appliquer(self):
        self.ensure_one()
        ord_ = self.ordonnance_id
        vals = {}
        if self.prescripteur_nom:
            vals['prescripteur_nom'] = self.prescripteur_nom
        if self.prescripteur_code:
            vals['prescripteur_code'] = self.prescripteur_code
        if self.date_prescription:
            vals['date_prescription'] = self.date_prescription
        if self.patient_nom:
            patient = self.env['res.partner'].search(
                [('lastname', 'ilike', self.patient_nom),
                 ('category_id.name', '=', 'Patient CPS')], limit=1)
            if patient:
                vals['patient_id'] = patient.id
        ord_.write(vals)

        # Créer les lignes depuis le texte parsé
        parsed = parse_ordonnance_text(self.texte_extrait or '')
        for a in parsed['actes']:
            at = self.env['cps.acte.type'].search([
                ('lettre_cle', '=', a['lettre_cle']),
                ('coefficient_defaut', '=', a['coefficient']),
            ], limit=1)
            if not at:
                at = self.env['cps.acte.type'].search(
                    [('lettre_cle', '=', a['lettre_cle'])], order='sequence', limit=1)
            if at and not ord_.ligne_ids.filtered(lambda l: l.acte_type_id == at):
                self.env['cps.ordonnance.ligne'].create({
                    'ordonnance_id': ord_.id,
                    'acte_type_id': at.id,
                    'nb_seances_prescrites': a['nb_seances'],
                })
        self.etat = 'applique'
        return {'type': 'ir.actions.act_window', 'res_model': 'cps.ordonnance',
                'res_id': ord_.id, 'view_mode': 'form', 'target': 'current'}

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _format_actes(actes):
        return ''.join(
            f"  • {a['lettre_cle']} {a['coefficient']} × {a['nb_seances']} séance(s)\n"
            for a in actes
        )

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}
