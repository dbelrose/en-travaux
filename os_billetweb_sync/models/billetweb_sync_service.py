from odoo import models, fields, api
import requests
import logging
import json
import hashlib
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

api_url_payout = 'https://www.billetweb.fr/api/payout'  # Détail d'un virement
api_url_attendees = 'https://www.billetweb.fr/api/attendees'  # Billets vendus tous événements confondus


class BilletWebApiCall(models.Model):
    """Journal des appels API pour éviter les doublons et respecter le fair use"""
    _name = 'billetweb.api.call'
    _description = 'Journal des appels API BilletWeb'
    _order = 'call_date desc'

    call_hash = fields.Char('Hash de l\'appel', required=True, index=True,
                            help='Hash unique basé sur l\'URL et les paramètres')
    api_endpoint = fields.Char('Point d\'accès API', required=True)
    api_user = fields.Char('Utilisateur API', required=True)
    api_date = fields.Char('Date API', help='Date utilisée dans l\'appel API')
    ext_id = fields.Char('ID Externe', help='ID externe pour les appels spécifiques')
    call_date = fields.Datetime('Date d\'appel', default=fields.Datetime.now, required=True)
    success = fields.Boolean('Succès', default=False)
    status_code = fields.Integer('Code de statut HTTP')
    response_size = fields.Integer('Taille de la réponse (bytes)')
    error_message = fields.Text('Message d\'erreur')
    cache_until = fields.Datetime('Cache valide jusqu\'à',
                                  help='Date jusqu\'à laquelle le cache est considéré comme valide')

    @api.model
    def generate_call_hash(self, endpoint, api_user, api_key, **params):
        """Génère un hash unique pour identifier un appel API"""
        # On n'inclut pas la clé API dans le hash pour des raisons de sécurité
        # mais on utilise les autres paramètres pour créer une signature unique
        hash_data = f"{endpoint}|{api_user}|{json.dumps(sorted(params.items()))}"
        return hashlib.sha256(hash_data.encode()).hexdigest()

    @api.model
    def is_call_cached(self, call_hash, cache_duration_hours=24):
        """Vérifie si un appel est déjà en cache et encore valide"""
        cache_limit = fields.Datetime.now() - timedelta(hours=cache_duration_hours)
        cached_call = self.search([
            ('call_hash', '=', call_hash),
            ('success', '=', True),
            ('call_date', '>=', cache_limit)
        ], limit=1)
        return cached_call if cached_call else False


class BilletWebApiPayouts(models.Model):
    """Cache des données payouts de l'API BilletWeb"""
    _name = 'billetweb.api.payouts'
    _description = 'Cache API BilletWeb - Payouts'
    _rec_name = 'payout_id'

    api_call_id = fields.Many2one('billetweb.api.call', 'Appel API', required=True, ondelete='cascade')
    payout_id = fields.Char('ID Payout', required=True, index=True)
    date = fields.Date('Date')
    amount = fields.Float('Montant')
    account = fields.Char('Compte')
    iban = fields.Char('IBAN')
    swift = fields.Char('SWIFT')
    api_user = fields.Char('Utilisateur API', required=True)
    raw_data = fields.Text('Données brutes JSON')

    _sql_constraints = [
        ('unique_payout_per_call', 'UNIQUE(api_call_id, payout_id)',
         'Un payout ne peut apparaître qu\'une fois par appel API')
    ]


class BilletWebApiPayoutDetails(models.Model):
    """Cache des détails de payout de l'API BilletWeb"""
    _name = 'billetweb.api.payout.details'
    _description = 'Cache API BilletWeb - Détails Payout'
    _rec_name = 'ext_id'

    api_call_id = fields.Many2one('billetweb.api.call', 'Appel API', required=True, ondelete='cascade')
    payout_api_id = fields.Many2one('billetweb.api.payouts', 'Payout API', required=True, ondelete='cascade')
    detail_id = fields.Char('ID Détail', required=True)
    ext_id = fields.Char('ID Externe', required=True, index=True)
    date = fields.Datetime('Date')
    order_id = fields.Char('ID Commande')
    event = fields.Char('Événement')
    price = fields.Float('Prix')
    tax_rate = fields.Float('Taux de taxe')
    tax_amount = fields.Float('Montant de taxe')
    fees = fields.Float('Frais')
    raw_data = fields.Text('Données brutes JSON')


class BilletWebApiAttendees(models.Model):
    """Cache des données attendees de l'API BilletWeb"""
    _name = 'billetweb.api.attendees'
    _description = 'Cache API BilletWeb - Participants'
    _rec_name = 'ext_id'

    api_call_id = fields.Many2one('billetweb.api.call', 'Appel API', required=True, ondelete='cascade')
    ext_id = fields.Char('ID Externe', required=True, index=True)
    api_user = fields.Char('Utilisateur API', required=True)
    raw_data = fields.Text('Données brutes JSON', required=True)

    _sql_constraints = [
        ('unique_attendee_per_call', 'UNIQUE(api_call_id, ext_id)',
         'Un participant ne peut apparaître qu\'une fois par appel API')
    ]


class BilletWebSyncService(models.AbstractModel):
    _name = 'billetweb.sync.service'
    _description = 'Service de synchronisation BilletWeb avec gestion du cache'

    def get_api_matrix(self):
        """Récupère la matrice (date, user, key) pour l'appel API."""
        today = fields.Date.today()
        matrix = []

        billet_web_partners = self.env['res.partner.id_number'].search([
            ('partner_issued_id.name', '=', 'BilletWeb.fr'),
            ('category_id.code', '=', 'APIUSR'),
            ('valid_from', '<=', today),
            ('valid_until', '>=', today),
            ('status', '!=', 'close')
        ])

        for partner in billet_web_partners:
            api_user = partner.name
            api_key_record = self.env['res.partner.id_number'].search([
                ('partner_id', '=', partner.partner_id.id),
                ('partner_issued_id.name', '=', 'BilletWeb.fr'),
                ('category_id.code', '=', 'APIKEY'),
                ('valid_from', '<=', today),
                ('valid_until', '>=', today),
                ('status', '!=', 'close')
            ], limit=1)

            api_key = api_key_record.name if api_key_record else None
            if not api_key:
                continue

            current_year = today.year
            current_month = today.month
            date_1 = f"{current_year}-{current_month:02d}-01"
            date_2 = f"{current_year}-{current_month:02d}-16"

            matrix.append((date_1, api_user, api_key))
            matrix.append((date_2, api_user, api_key))

        return matrix

    def _make_api_call(self, url, endpoint, api_user, api_key, **params):
        """Effectue un appel API avec gestion du cache et du journal"""
        # Générer le hash pour identifier cet appel
        call_hash = self.env['billetweb.api.call'].generate_call_hash(
            endpoint, api_user, api_key, **params
        )

        # Vérifier si l'appel est déjà en cache
        cached_call = self.env['billetweb.api.call'].is_call_cached(call_hash)
        if cached_call:
            _logger.info(f"[BilletWeb] Utilisation du cache pour {endpoint} (hash: {call_hash[:8]}...)")
            return cached_call, None  # Retourne l'appel en cache, pas de nouvelles données

        # Effectuer l'appel API
        _logger.info(f"[BilletWeb] Nouvel appel API : {url}")

        api_call = self.env['billetweb.api.call'].create({
            'call_hash': call_hash,
            'api_endpoint': endpoint,
            'api_user': api_user,
            'api_date': params.get('api_date'),
            'ext_id': params.get('ext_id'),
        })

        try:
            response = requests.get(url, timeout=15)
            api_call.write({
                'status_code': response.status_code,
                'response_size': len(response.content) if response.content else 0,
            })

            if response.status_code == 200:
                data = response.json()
                api_call.write({
                    'success': True,
                    'cache_until': fields.Datetime.now() + timedelta(hours=24)
                })
                return api_call, data
            else:
                error_msg = f"Erreur HTTP {response.status_code}: {response.text}"
                api_call.write({'error_message': error_msg})
                _logger.error(f"[BilletWeb] {error_msg}")
                return api_call, None

        except requests.exceptions.RequestException as e:
            error_msg = f"Erreur réseau: {str(e)}"
            api_call.write({'error_message': error_msg})
            _logger.error(f"[BilletWeb] {error_msg}")
            return api_call, None
        except Exception as e:
            error_msg = f"Erreur de parsing JSON: {str(e)}"
            api_call.write({'error_message': error_msg})
            _logger.error(f"[BilletWeb] {error_msg}")
            return api_call, None

    def call_api(self, api_user, api_key, api_date):
        """Appelle l'API /api/payouts et /api/payout/:id/data avec gestion du cache."""
        base_url = "https://www.billetweb.fr/api/"
        payouts_url = f"{base_url}payouts/"
        payout_url = f"{base_url}payout/"

        maitre_url = f"{payouts_url}{api_date}/?user={api_user}&key={api_key}&version=1"

        # Appel API pour récupérer la liste des payouts
        api_call, payouts_data = self._make_api_call(
            maitre_url, 'payouts', api_user, api_key, api_date=api_date
        )

        if not payouts_data:
            if api_call.success:  # Données en cache
                # Récupérer les données depuis le cache
                cached_payouts = self.env['billetweb.api.payouts'].search([
                    ('api_call_id.call_hash', '=', api_call.call_hash),
                    ('api_call_id.success', '=', True)
                ])
                return self._process_cached_payouts(cached_payouts, api_user, api_key)
            else:
                return []

        # Stocker les nouvelles données payouts en cache
        created_payouts = []
        for payout in payouts_data:
            if not isinstance(payout, dict):
                _logger.warning(f"[BilletWeb] Format inattendu pour payouts : {payout}")
                continue

            # Stocker en cache
            cached_payout = self.env['billetweb.api.payouts'].create({
                'api_call_id': api_call.id,
                'payout_id': payout["id"],
                'date': payout["date"],
                'amount': payout["amount"],
                'account': payout["account"],
                'iban': payout["iban"],
                'swift': payout["swift"],
                'api_user': api_user,
                'raw_data': json.dumps(payout)
            })

            # Vérifier si le payout existe déjà dans le modèle business
            if self.env['billetweb.payout'].search([('payout_id', '=', payout['id'])]):
                _logger.info(f"[BilletWeb] Payout déjà traité: {payout['id']}")
                continue

            # Créer le payout dans le modèle business
            payout_rec = self.env['billetweb.payout'].create({
                'payout_id': payout["id"],
                'date': payout["date"],
                'amount': payout["amount"],
                'account': payout["account"],
                'iban': payout["iban"],
                'swift': payout["swift"],
                'company_id': self.find_company(api_user).id,
            })
            created_payouts.append(payout_rec)

            # Charger les détails pour ce payout
            self._load_payout_details(payout["id"], api_user, api_key, payout_rec, cached_payout)

        return created_payouts

    def _load_payout_details(self, payout_id, api_user, api_key, payout_rec, cached_payout):
        """Charge les détails d'un payout avec gestion du cache"""
        base_url = "https://www.billetweb.fr/api/"
        payout_url = f"{base_url}payout/"
        detail_url = f"{payout_url}{payout_id}/?user={api_user}&key={api_key}&version=1"

        # Appel API pour les détails du payout
        api_call, details_data = self._make_api_call(
            detail_url, 'payout_details', api_user, api_key, payout_id=payout_id
        )

        if not details_data:
            if api_call.success:  # Données en cache
                cached_details = self.env['billetweb.api.payout.details'].search([
                    ('api_call_id.call_hash', '=', api_call.call_hash),
                    ('api_call_id.success', '=', True)
                ])
                self._process_cached_payout_details(cached_details, payout_rec)
            return

        # Stocker et traiter les nouveaux détails
        for detail in details_data:
            if isinstance(detail, str):
                detail = json.loads(detail)

            # Stocker en cache
            cached_detail = self.env['billetweb.api.payout.details'].create({
                'api_call_id': api_call.id,
                'payout_api_id': cached_payout.id,
                'detail_id': detail["id"],
                'ext_id': detail["ext_id"],
                'date': detail["date"],
                'order_id': detail["order_id"],
                'event': detail["event"],
                'price': detail["price"],
                'tax_rate': detail["tax_rate"],
                'tax_amount': detail["tax_amount"],
                'fees': detail["fees"],
                'raw_data': json.dumps(detail)
            })

            # Créer le détail dans le modèle business
            self.env['billetweb.payout.detail'].create({
                'payout_id': payout_rec.id,
                'ext_id': detail["ext_id"],
                'order_id': detail["order_id"],
                'date': detail["date"],
                'event': detail["event"],
                'price': detail["price"],
                'tax_rate': detail["tax_rate"],
                'tax_amount': detail["tax_amount"],
                'fees': detail["fees"],
            })

    def _process_cached_payouts(self, cached_payouts, api_user, api_key):
        """Traite les payouts depuis le cache"""
        created_payouts = []
        for cached_payout in cached_payouts:
            # Vérifier si le payout existe déjà dans le modèle business
            if self.env['billetweb.payout'].search([('payout_id', '=', cached_payout.payout_id)]):
                continue

            # Créer depuis le cache
            payout_rec = self.env['billetweb.payout'].create({
                'payout_id': cached_payout.payout_id,
                'date': cached_payout.date,
                'amount': cached_payout.amount,
                'account': cached_payout.account,
                'iban': cached_payout.iban,
                'swift': cached_payout.swift,
                'company_id': self.find_company(api_user).id,
            })
            created_payouts.append(payout_rec)

            # Traiter les détails en cache
            cached_details = self.env['billetweb.api.payout.details'].search([
                ('payout_api_id', '=', cached_payout.id)
            ])
            self._process_cached_payout_details(cached_details, payout_rec)

        return created_payouts

    def _process_cached_payout_details(self, cached_details, payout_rec):
        """Traite les détails de payout depuis le cache"""
        for cached_detail in cached_details:
            self.env['billetweb.payout.detail'].create({
                'payout_id': payout_rec.id,
                'ext_id': cached_detail.ext_id,
                'order_id': cached_detail.order_id,
                'date': cached_detail.date,
                'event': cached_detail.event,
                'price': cached_detail.price,
                'tax_rate': cached_detail.tax_rate,
                'tax_amount': cached_detail.tax_amount,
                'fees': cached_detail.fees,
            })

    def call_attendee_api(self, api_user, api_key, ext_id):
        """Appelle l'API BilletWeb pour récupérer un participant avec gestion du cache."""
        base_url = "https://www.billetweb.fr/api/attendees?user="
        api_url = f"{base_url}{api_user}&key={api_key}&version=1&ticket={ext_id}"

        # Appel API avec gestion du cache
        api_call, attendee_data = self._make_api_call(
            api_url, 'attendees', api_user, api_key, ext_id=ext_id
        )

        if not attendee_data:
            if api_call.success:  # Données en cache
                cached_attendee = self.env['billetweb.api.attendees'].search([
                    ('api_call_id.call_hash', '=', api_call.call_hash),
                    ('api_call_id.success', '=', True)
                ], limit=1)
                if cached_attendee:
                    _logger.info(f"[BilletWeb] Attendee trouvé en cache pour ext_id={ext_id}")
                    return json.loads(cached_attendee.raw_data)
            return None

        if not attendee_data or not isinstance(attendee_data, list):
            _logger.warning(f"[BilletWeb] Pas d'attendee trouvé pour ext_id={ext_id}")
            return None

        # Stocker en cache
        first_attendee = attendee_data[0]
        self.env['billetweb.api.attendees'].create({
            'api_call_id': api_call.id,
            'ext_id': ext_id,
            'api_user': api_user,
            'raw_data': json.dumps(first_attendee)
        })

        _logger.info(f"[BilletWeb] Attendee trouvé et mis en cache pour ext_id={ext_id}")
        return first_attendee

    def find_company(self, api_user):
        """Retourne la société liée à un identifiant BilletWeb (api_user)"""
        id_number = self.env['res.partner.id_number'].search([
            ('name', '=', api_user),
            ('partner_issued_id.name', '=', 'BilletWeb.fr'),
            ('category_id.code', '=', 'APIUSR'),
            ('status', '!=', 'close')
        ], limit=1)

        if not id_number:
            raise ValueError(f"[BilletWeb] Aucun identifiant APIUSR actif pour {api_user}")

        partner = id_number.partner_id
        company = self.env['res.company'].search([('partner_id', '=', partner.id)], limit=1)

        if not company:
            raise ValueError(f"[BilletWeb] Aucune société liée au partenaire {partner.name} (id={partner.id})")

        return company

    def get_event_by_external_id(self, event_id):
        """Renvoie un événement Odoo depuis son identifiant externe BilletWeb."""
        xml_id = f"os_billetweb_sync.event_{event_id}"
        try:
            return self.env.ref(xml_id)
        except ValueError:
            return None

    @api.model
    def cleanup_old_cache(self, days_to_keep=30):
        """Nettoie les anciens appels API et leur cache associé"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days_to_keep)
        old_calls = self.env['billetweb.api.call'].search([
            ('call_date', '<', cutoff_date)
        ])
        count = len(old_calls)
        old_calls.unlink()  # Cascade delete supprimera aussi les données de cache
        _logger.info(f"[BilletWeb] Nettoyage terminé : {count} anciens appels API supprimés")
        return count
