# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import base64
import re
import logging

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

_logger = logging.getLogger(__name__)

ROLE_MAPPING = {
    'président': 'Président(e)',
    'présidente': 'Président(e)',
    'vice-président': 'Vice-président(e)',
    'vice-présidente': 'Vice-président(e)',
    'secrétaire': 'Secrétaire',
    'secrétaire adjoint': 'Secrétaire adjoint(e)',
    'secrétaire adjointe': 'Secrétaire adjoint(e)',
    'trésorier': 'Trésorier(ère)',
    'trésorière': 'Trésorier(ère)',
    'trésorier adjoint': 'Trésorier(ère) adjoint(e)',
    'trésorière adjointe': 'Trésorier(ère) adjoint(e)',
    'assesseur': 'Assesseur',
    'président d\'honneur': 'Président(e) d\'honneur',
    'présidente d\'honneur': 'Président(e) d\'honneur',
}


class JopfImport(models.Model):
    _name = 'jopf.import'
    _description = 'Import JOPF'
    _order = 'date_import desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default='Nouveau',
        tracking=True
    )
    date_import = fields.Datetime(
        string='Date import',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True
    )
    date_jopf = fields.Date(string='Date JOPF')
    file_data = fields.Binary(
        string='Fichier PDF',
        required=True,
        attachment=True
    )
    file_name = fields.Char(string='Nom fichier')
    text_content = fields.Text(string='Contenu extrait', readonly=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('processing', 'En cours'),
        ('imported', 'Importé'),
        ('error', 'Erreur')
    ], string='État', default='draft', readonly=True, tracking=True)

    line_ids = fields.One2many(
        'jopf.import.line',
        'import_id',
        string='Lignes',
        readonly=True
    )
    partner_ids = fields.Many2many(
        'res.partner',
        'jopf_import_partner_rel',
        'import_id',
        'partner_id',
        string='Partenaires',
        readonly=True
    )
    log = fields.Html(string='Log', readonly=True)

    association_count = fields.Integer(
        string='Nb associations',
        compute='_compute_stats',
        store=True
    )
    person_count = fields.Integer(
        string='Nb personnes',
        compute='_compute_stats',
        store=True
    )
    error_count = fields.Integer(
        string='Nb erreurs',
        compute='_compute_stats',
        store=True
    )

    ocr_language = fields.Selection([
        ('fra', 'Français'),
        ('eng', 'Anglais'),
        ('fra+eng', 'Français + Anglais')
    ], default='fra', string='Langue OCR')
    ocr_dpi = fields.Integer(string='DPI', default=300)
    ocr_psm = fields.Selection([
        ('3', '3 - Automatique (défaut)'),
        ('4', '4 - Une colonne de texte'),
        ('6', '6 - Bloc uniforme de texte'),
        ('11', '11 - Texte épars'),
    ], default='4', string='Mode segmentation OCR',
        help='PSM 4 est recommandé pour les documents multi-colonnes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'La référence doit être unique!')
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nouveau') == 'Nouveau':
            vals['name'] = self.env['ir.sequence'].next_by_code('jopf.import') or 'Nouveau'
        return super().create(vals)

    @api.depends('line_ids.state')
    def _compute_stats(self):
        for rec in self:
            rec.association_count = len(rec.line_ids.mapped('association_id'))
            rec.person_count = len(rec.line_ids.mapped('person_id'))
            rec.error_count = len(rec.line_ids.filtered(lambda l: l.state == 'error'))

    def action_import(self):
        """Lance l'importation du fichier PDF"""
        self.ensure_one()

        if not OCR_AVAILABLE:
            raise UserError(
                'Librairies OCR manquantes.\n\n'
                'Installez: pip install pdf2image pytesseract Pillow'
            )

        self.state = 'processing'
        self.env.cr.commit()

        try:
            # Extraction du texte
            text = self._extract_text_from_pdf()
            self.text_content = text

            # Parsing des associations
            associations = self._parse_jopf_text(text)

            if not associations:
                raise UserError('Aucune association trouvée dans le document')

            # Création des logs
            log = [
                f'<h3>Import du {fields.Datetime.now()}</h3>',
                f'<p><strong>{len(associations)} associations détectées</strong></p>'
            ]

            partners = self.env['res.partner']

            # Traitement de chaque association
            for i, assoc in enumerate(associations, 1):
                try:
                    log.append(f'<p><strong>[{i}/{len(associations)}] {assoc["name"]}</strong></p>')
                    log.append(f'<ul><li>Date: {assoc["date"]}</li>')
                    log.append(f'<li>Membres: {len(assoc["membres"])}</li></ul>')

                    p, _ = self._process_association(assoc)
                    partners |= p

                    log.append('<ul>')
                    for m in assoc['membres']:
                        log.append(f'<li>✓ {m["prenom"]} {m["nom"]} - {m["role"]}</li>')
                    log.append('</ul>')

                except Exception as e:
                    log.append(f'<p style="color:red">✗ Erreur: {str(e)}</p>')
                    _logger.error(f"Erreur traitement {assoc['name']}: {e}", exc_info=True)

            self.write({
                'state': 'imported',
                'partner_ids': [(6, 0, partners.ids)],
                'log': ''.join(log)
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Succès',
                    'message': (
                        f'{self.association_count} associations, '
                        f'{self.person_count} personnes importées'
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Erreur import: {e}", exc_info=True)
            self.write({
                'state': 'error',
                'log': f'<div style="color:red"><strong>Erreur:</strong> {str(e)}</div>'
            })
            raise UserError(f"Erreur lors de l'import: {str(e)}")

    def _extract_text_from_pdf(self):
        """Extrait le texte du PDF avec OCR optimisé pour multi-colonnes"""
        if not self.file_data:
            raise UserError('Aucun fichier attaché')

        try:
            pdf_bytes = base64.b64decode(self.file_data)
            images = convert_from_bytes(pdf_bytes, dpi=self.ocr_dpi)

            texts = []
            for i, img in enumerate(images, 1):
                _logger.info(f'OCR page {i}/{len(images)}')
                img = self._preprocess_image(img)

                # Configuration OCR optimisée pour multi-colonnes
                config = f'--psm {self.ocr_psm} -c preserve_interword_spaces=1'

                text = pytesseract.image_to_string(
                    img,
                    lang=self.ocr_language,
                    config=config
                )
                texts.append(text)

            return '\n\n'.join(texts)

        except Exception as e:
            error_msg = str(e)
            if 'poppler' in error_msg.lower() or 'pdfinfo' in error_msg.lower():
                raise UserError(
                    'Poppler n\'est pas installé.\n\n'
                    'Installation Docker (dans le conteneur):\n'
                    'docker exec -u root <conteneur> bash -c '
                    '"apt-get update && apt-get install -y poppler-utils '
                    'tesseract-ocr tesseract-ocr-fra"\n'
                    'docker restart <conteneur>\n\n'
                    'Ou ajoutez dans Dockerfile:\n'
                    'RUN apt-get update && apt-get install -y '
                    'poppler-utils tesseract-ocr tesseract-ocr-fra'
                )
            elif 'tesseract' in error_msg.lower():
                raise UserError(
                    'Tesseract OCR n\'est pas installé.\n\n'
                    'Installation Docker:\n'
                    'docker exec -u root <conteneur> bash -c '
                    '"apt-get update && apt-get install -y '
                    'tesseract-ocr tesseract-ocr-fra"\n'
                    'docker restart <conteneur>'
                )
            else:
                raise UserError(f'Erreur OCR: {error_msg}')

    def _preprocess_image(self, img):
        """Prétraite l'image pour améliorer l'OCR"""
        # Conversion en niveaux de gris
        img = img.convert('L')

        # Amélioration du contraste
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Amélioration de la netteté
        img = img.filter(ImageFilter.SHARPEN)

        # Augmentation de la luminosité si nécessaire
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.2)

        return img

    def _parse_jopf_text(self, text):
        """Parse le texte pour extraire les associations - VERSION STRICTE AVEC TRACES"""

        _logger.info('=' * 80)
        _logger.info('DÉBUT DU PARSING')
        _logger.info('=' * 80)

        # Nettoyage léger du texte (préservation de la casse)
        text = re.sub(r'\s+', ' ', text)
        _logger.info(f'Texte nettoyé: {len(text)} caractères')

        # RÈGLE 1: Le nom de l'association est TOUJOURS en MAJUSCULES (non accentuées sauf Œ)
        # Pattern simplifié : majuscules non accentuées + Œ uniquement
        assoc_pattern = (
            r"([A-ZŒ][A-ZŒ\s\-'\d]+)\s+"
            r"RENOUVELLEMENT DU BUREAU\s*:?\s*"
        )

        # Test du pattern
        test_matches = list(re.finditer(assoc_pattern, text))
        _logger.info(f'Nombre de patterns "RENOUVELLEMENT DU BUREAU" trouvés: {len(test_matches)}')
        for idx, m in enumerate(test_matches, 1):
            _logger.info(f'  Match {idx}: "{m.group(1).strip()}"')

        # Découpage du texte
        parts = re.split(assoc_pattern, text)
        _logger.info(f'Texte découpé en {len(parts)} parties')

        associations = []

        # Parcours des sections
        for i in range(1, len(parts), 2):
            if i + 1 >= len(parts):
                break

            # Nom de l'association (déjà en majuscules)
            assoc_name = parts[i].strip()
            _logger.info(f'\n--- Traitement section {(i + 1) // 2} ---')
            _logger.info(f'Nom brut: "{assoc_name}"')

            # Nettoyage: retirer le prénom/nom qui pourrait être collé à la fin
            # Le nom d'association se termine avant un mot avec majuscule initiale + minuscules
            # Chercher le pattern "NOM Prénom" à la fin
            clean_match = re.search(
                r'^(.*?)\s+([A-ZŒ\-\']+)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*)\s*

    def _extract_membres_strict(self, content):
        """
        Extraction STRICTE des membres selon le format: Qualité : NOM Prénom
        RÈGLE: NOM toujours en MAJUSCULES (non accentuées sauf Œ), Prénom avec majuscule initiale
        """

        _logger.info('    --- Extraction des membres ---')

        # Patterns stricts avec : obligatoire
        # Simplification: [A-ZŒ] pour les majuscules (non accentuées sauf Œ)
        patterns = [
            # Président d'honneur (avant président simple)
            (
            r"Président(?:e)?\s+d'honneur\s*:\s*([A-ZŒ][\w\-']+(?:\s+[A-ZŒ][\w\-']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-']*)*)",
            "président d'honneur"),

            # Président simple
            (
            r"Président(?:e)?\s*:\s*([A-ZŒ][\w\-']+(?:\s+[A-ZŒ][\w\-']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-']*)*)",
            'président'),

            # Vice-président
            (
            r"Vice[- ]président(?:e)?\s*:\s*([A-ZŒ][\w\-']+(?:\s+[A-ZŒ][\w\-']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-']*)*)",
            'vice-président'),

            # Secrétaire adjoint (avant secrétaire simple)
            (
            r"Secrétaire\s+adjoint(?:e)?\s*:\s*([A-ZŒ][\w\-']+(?:\s+[A-ZŒ][\w\-']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-']*)*)",
            'secrétaire adjoint'),

            # Secrétaire simple
            (
            r"Secrétaire\s*:\s*([A-ZŒ][\w\-']+(?:\s+[A-ZŒ][\w\-']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-']*)*)",
            'secrétaire'),

            # Trésorier adjoint (avant trésorier simple)
            (
            r"Trésorier(?:ère)?\s+adjoint(?:e)?\s*:\s*([A-ZŒ][\w\-']+(?:\s+[A-ZŒ][\w\-']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-']*)*)",
            'trésorier adjoint'),

            # Trésorier simple
            (
            r"Trésorier(?:ère)?\s*:\s*([A-ZŒ][\w\-']+(?:\s+[A-ZŒ][\w\-']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-']*)*)",
            'trésorier'),

            # Assesseur
            (
            r"Assesseur\s*:\s*([A-ZŒ][\w\-']+(?:\s+[A-ZŒ][\w\-']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-']*)*)",
            'assesseur'),
        ]

        membres = []
        used_positions = set()

        for pattern, role_key in patterns:
            matches = list(re.finditer(pattern, content, re.MULTILINE))
            if matches:
                _logger.info(f'    Pattern "{role_key}": {len(matches)} match(es)')

            for match in matches:
                position = match.start()

                # Éviter les doublons
                if position in used_positions:
                    _logger.debug(f'      Position {position} déjà utilisée, ignoré')
                    continue

                used_positions.add(position)

                # RÈGLE 3: Conservation stricte de la casse
                nom = match.group(1).strip()  # NOM en MAJUSCULES
                prenom = match.group(2).strip()  # Prénom avec capitale

                _logger.info(f'    Match trouvé: {role_key} - "{nom}" "{prenom}"')

                # Validation : le nom doit être en majuscules (non accentuées sauf Œ)
                test_upper = nom.replace(' ', '').replace('-', '').replace("'", '').replace('Œ', '')
                if not test_upper.isupper():
                    _logger.warning(f'      ⚠ Nom ignoré (pas en majuscules): {nom} {prenom}')
                    continue

                # Détermination du rôle exact
                full_role_text = match.group(0).lower()
                role = self._determine_role(role_key, full_role_text)

                membres.append({
                    'nom': nom,  # Conservation casse originale (MAJUSCULES)
                    'prenom': prenom,  # Conservation casse originale
                    'role': role
                })

                _logger.info(f'      ✓ Ajouté: {prenom} {nom} - {role}')

        return membres

    def _determine_role(self, role_key, full_text):
        """Détermine le rôle exact avec genre et variations"""

        is_adjoint = 'adjoint' in full_text
        is_honneur = 'honneur' in full_text

        search_key = role_key
        if is_adjoint:
            search_key += ' adjoint'

        role = ROLE_MAPPING.get(search_key, role_key.title())

        if is_honneur and 'honneur' not in role.lower():
            role += ' d\'honneur'

        return role

    def _process_association(self, data):
        """Crée ou met à jour une association et ses membres"""
        Partner = self.env['res.partner']
        Line = self.env['jopf.import.line']

        cat = self.env.ref(
            'os_jopf_pdf_import.partner_category_jopf_association',
            raise_if_not_found=False
        )

        # Recherche de l'association (nom exact, casse préservée)
        assoc = Partner.search([
            ('name', '=', data['name']),
            ('is_company', '=', True)
        ], limit=1)

        if not assoc:
            assoc = Partner.create({
                'name': data['name'],  # Conservation casse originale
                'is_company': True,
                'category_id': [(6, 0, [cat.id])] if cat else False,
                'comment': f"JOPF - Bureau {data['date']}",
                'country_id': self.env.ref('base.pf').id,
            })
            _logger.info(f'Association créée: {data["name"]}')
        else:
            _logger.info(f'Association trouvée: {data["name"]}')

        # Ligne d'import pour l'association
        Line.create({
            'import_id': self.id,
            'association_id': assoc.id,
            'association_name': data['name'],
            'date_bureau': data['date'],
            'state': 'success',
        })

        partners = assoc

        # Traitement des membres
        for m in data['membres']:
            person = self._process_person(m, assoc)
            partners |= person

        return partners, None

    def _process_person(self, data, assoc):
        """Crée ou met à jour une personne avec lastname et firstname"""
        Partner = self.env['res.partner']
        Line = self.env['jopf.import.line']

        # RÈGLE 4: Renseigner lastname et firstname
        nom = data['nom']  # Conservation casse (MAJUSCULES)
        prenom = data['prenom']  # Conservation casse
        name = f"{prenom} {nom}"

        # Recherche de la personne
        person = Partner.search([
            ('lastname', '=', nom),
            ('firstname', '=', prenom),
            ('is_company', '=', False)
        ], limit=1)

        # Valeurs à créer/mettre à jour
        vals = {
            'name': name,
            'lastname': nom,  # RÈGLE: Renseigner lastname
            'firstname': prenom,  # RÈGLE: Renseigner firstname
            'is_company': False,
            'parent_id': assoc.id,
            'function': data['role'],
            'country_id': self.env.ref('base.pf').id,
        }

        if not person:
            person = Partner.create(vals)
            state = 'created'
            _logger.info(f'Personne créée: {name} - {data["role"]}')
        else:
            person.write({
                'parent_id': assoc.id,
                'function': data['role'],
                'name': name,  # Mise à jour au cas où
            })
            state = 'updated'
            _logger.info(f'Personne mise à jour: {name} - {data["role"]}')

        # Ligne d'import pour la personne
        Line.create({
            'import_id': self.id,
            'association_id': assoc.id,
            'person_id': person.id,
            'person_name': name,
            'role': data['role'],
            'state': state,
        })

        return person

    def action_view_partners(self):
        """Ouvre la vue des partenaires créés"""
        self.ensure_one()
        return {
            'name': 'Partenaires importés',
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.partner_ids.ids)],
            'context': {'create': False},
        }

    def action_reset_to_draft(self):
        """Remet l'import en brouillon"""
        self.write({'state': 'draft'})

,
assoc_name
)

if clean_match:
# Le nom d'association est avant le "NOM Prénom"
    assoc_name_clean = clean_match.group(1).strip()
membre_nom = clean_match.group(2).strip()
membre_prenom = clean_match.group(3).strip()
_logger.info(f'  Nettoyage: association="{assoc_name_clean}"')
_logger.info(f'  Membre collé retiré: {membre_prenom} {membre_nom}')
assoc_name = assoc_name_clean

# Validation : le nom doit être entièrement en majuscules (non accentuées sauf Œ)
test_upper = assoc_name.replace(' ', '').replace('-', '').replace("'", '').replace('Œ', '')
if not test_upper.isupper():
    _logger.warning(f'  ⚠ Nom ignoré (pas entièrement en majuscules): "{assoc_name}"')
continue

_logger.info(f'  ✓ Nom validé: "{assoc_name}"')

content = parts[i + 1]
_logger.info(f'  Contenu: {len(content)} caractères')

# Extraction de la date
date_match = re.search(r'\((\d{1,2}\s+\w+\s+\d{4})\)', content)
date_str = date_match.group(1) if date_match else ''
if date_str:
    _logger.info(f'  Date trouvée: {date_str}')

# Trouver la fin du contenu de cette association
next_assoc_match = re.search(
    r"[A-ZŒ][A-ZŒ\s\-'\d]+\s+RENOUVELLEMENT DU BUREAU",
    content
)

if next_assoc_match:
    content = content[:next_assoc_match.start()]
    _logger.info(f'  Contenu limité à {len(content)} caractères (avant prochaine assoc)')

# RÈGLE 2: Extraction stricte des membres avec format "Qualité : NOM Prénom"
membres = self._extract_membres_strict(content)
_logger.info(f'  Membres trouvés: {len(membres)}')

if membres:
    associations.append({
        'name': assoc_name,  # Conservation de la casse originale
        'date': date_str,
        'membres': membres
    })
    _logger.info(f'  ✓ Association ajoutée: {assoc_name} ({len(membres)} membres)')
else:
    _logger.warning(f'  ⚠ Association sans membres: {assoc_name}')

_logger.info('=' * 80)
_logger.info(f'FIN DU PARSING - {len(associations)} associations trouvées')
_logger.info('=' * 80)

return associations


def _extract_membres_strict(self, content):
    """
    Extraction STRICTE des membres selon le format: Qualité : NOM Prénom
    RÈGLE: NOM toujours en MAJUSCULES, Prénom avec majuscule initiale
    """

    # Patterns stricts avec : obligatoire
    patterns = [
        # Président d'honneur (avant président simple)
        (
        r'Président(?:e)?\s+d\'honneur\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*)*)',
        'président d\'honneur'),

        # Président simple
        (
        r'Président(?:e)?\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*)*)',
        'président'),

        # Vice-président
        (
        r'Vice[- ]président(?:e)?\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*)*)',
        'vice-président'),

        # Secrétaire adjoint (avant secrétaire simple)
        (
        r'Secrétaire\s+adjoint(?:e)?\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*)*)',
        'secrétaire adjoint'),

        # Secrétaire simple
        (
        r'Secrétaire\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*)*)',
        'secrétaire'),

        # Trésorier adjoint (avant trésorier simple)
        (
        r'Trésorier(?:ère)?\s+adjoint(?:e)?\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*)*)',
        'trésorier adjoint'),

        # Trésorier simple
        (
        r'Trésorier(?:ère)?\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*)*)',
        'trésorier'),

        # Assesseur
        (
        r'Assesseur\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+(?:\s+[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][\w\-\']+)?)\s+([A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*(?:\s+[A-Z][a-zàâäéèêëïîôùûüç][\w\-\']*)*)',
        'assesseur'),
    ]

    membres = []
    used_positions = set()

    for pattern, role_key in patterns:
        for match in re.finditer(pattern, content, re.MULTILINE):
            position = match.start()

            # Éviter les doublons
            if position in used_positions:
                continue

            used_positions.add(position)

            # RÈGLE 3: Conservation stricte de la casse
            nom = match.group(1).strip()  # NOM en MAJUSCULES
            prenom = match.group(2).strip()  # Prénom avec capitale

            # Validation : le nom doit être en majuscules
            if not nom.replace(' ', '').replace('-', '').replace('\'', '').isupper():
                _logger.warning(f'Nom ignoré (pas en majuscules): {nom} {prenom}')
                continue

            # Détermination du rôle exact
            full_role_text = match.group(0).lower()
            role = self._determine_role(role_key, full_role_text)

            membres.append({
                'nom': nom,  # Conservation casse originale (MAJUSCULES)
                'prenom': prenom,  # Conservation casse originale
                'role': role
            })

            _logger.debug(f'Membre trouvé: {prenom} {nom} - {role}')

    return membres


def _determine_role(self, role_key, full_text):
    """Détermine le rôle exact avec genre et variations"""

    is_adjoint = 'adjoint' in full_text
    is_honneur = 'honneur' in full_text

    search_key = role_key
    if is_adjoint:
        search_key += ' adjoint'

    role = ROLE_MAPPING.get(search_key, role_key.title())

    if is_honneur and 'honneur' not in role.lower():
        role += ' d\'honneur'

    return role


def _process_association(self, data):
    """Crée ou met à jour une association et ses membres"""
    Partner = self.env['res.partner']
    Line = self.env['jopf.import.line']

    cat = self.env.ref(
        'os_jopf_pdf_import.partner_category_jopf_association',
        raise_if_not_found=False
    )

    # Recherche de l'association (nom exact, casse préservée)
    assoc = Partner.search([
        ('name', '=', data['name']),
        ('is_company', '=', True)
    ], limit=1)

    if not assoc:
        assoc = Partner.create({
            'name': data['name'],  # Conservation casse originale
            'is_company': True,
            'category_id': [(6, 0, [cat.id])] if cat else False,
            'comment': f"JOPF - Bureau {data['date']}",
            'country_id': self.env.ref('base.pf').id,
        })
        _logger.info(f'Association créée: {data["name"]}')
    else:
        _logger.info(f'Association trouvée: {data["name"]}')

    # Ligne d'import pour l'association
    Line.create({
        'import_id': self.id,
        'association_id': assoc.id,
        'association_name': data['name'],
        'date_bureau': data['date'],
        'state': 'success',
    })

    partners = assoc

    # Traitement des membres
    for m in data['membres']:
        person = self._process_person(m, assoc)
        partners |= person

    return partners, None


def _process_person(self, data, assoc):
    """Crée ou met à jour une personne avec lastname et firstname"""
    Partner = self.env['res.partner']
    Line = self.env['jopf.import.line']

    # RÈGLE 4: Renseigner lastname et firstname
    nom = data['nom']  # Conservation casse (MAJUSCULES)
    prenom = data['prenom']  # Conservation casse
    name = f"{prenom} {nom}"

    # Recherche de la personne
    person = Partner.search([
        ('lastname', '=', nom),
        ('firstname', '=', prenom),
        ('is_company', '=', False)
    ], limit=1)

    # Valeurs à créer/mettre à jour
    vals = {
        'name': name,
        'lastname': nom,  # RÈGLE: Renseigner lastname
        'firstname': prenom,  # RÈGLE: Renseigner firstname
        'is_company': False,
        'parent_id': assoc.id,
        'function': data['role'],
        'country_id': self.env.ref('base.pf').id,
    }

    if not person:
        person = Partner.create(vals)
        state = 'created'
        _logger.info(f'Personne créée: {name} - {data["role"]}')
    else:
        person.write({
            'parent_id': assoc.id,
            'function': data['role'],
            'name': name,  # Mise à jour au cas où
        })
        state = 'updated'
        _logger.info(f'Personne mise à jour: {name} - {data["role"]}')

    # Ligne d'import pour la personne
    Line.create({
        'import_id': self.id,
        'association_id': assoc.id,
        'person_id': person.id,
        'person_name': name,
        'role': data['role'],
        'state': state,
    })

    return person


def action_view_partners(self):
    """Ouvre la vue des partenaires créés"""
    self.ensure_one()
    return {
        'name': 'Partenaires importés',
        'type': 'ir.actions.act_window',
        'res_model': 'res.partner',
        'view_mode': 'tree,form',
        'domain': [('id', 'in', self.partner_ids.ids)],
        'context': {'create': False},
    }


def action_reset_to_draft(self):
    """Remet l'import en brouillon"""
    self.write({'state': 'draft'})
