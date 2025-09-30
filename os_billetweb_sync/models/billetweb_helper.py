import logging
import requests

from odoo import models

_logger = logging.getLogger(__name__)


class BilletwebSyncHelper(models.AbstractModel):
    _name = 'billetweb.sync.helper'
    _description = 'BilletWeb API Utility Functions'

    def fetch_event_info_from_api(self, api_user, api_key, event_id):
        base_url = "https://www.billetweb.fr/api/events?user="

        api_url = f"{base_url}{api_user}&key={api_key}&version=1&past=1"
        _logger.info(f"URL : {api_url}")

        response = requests.get(api_url, timeout=15)
        if response.status_code != 200:
            _logger.warning(f"[BilletWeb] Erreur API /events : {response.status_code}")
            return None

        try:
            data = response.json()
            _logger.debug(f"[BilletWeb] Réponse JSON /events : {data}")
        except Exception as e:
            _logger.warning(f"[BilletWeb] JSON invalide /events : {e}")
            return None

        events = data if isinstance(data, list) else data.get('events', [])
        for event in events:
            if event['id'] == str(event_id):
                return event

        return None

    def find_or_create_event(self, attendee_info, api_user, api_key):
        """Trouve ou crée un event.event Odoo avec date_end via BilletWeb."""
        event_id = attendee_info.get('event')
        event_name = attendee_info.get('event_name')
        event_start = attendee_info.get('event_start')

        xml_id = f"os_billetweb_sync.event_{event_id}"
        EventModel = self.env['event.event']
        IrModelData = self.env['ir.model.data']

        try:
            event = self.env.ref(xml_id)
        except ValueError:
            event = None

        if not event:
            event_info = self.fetch_event_info_from_api(api_user, api_key, event_id)
            event_end = event_info.get('end') if event_info else event_start

            event = EventModel.create({
                'name': event_name or f"Événement BilletWeb {event_id}",
                'date_begin': event_start,
                'date_end': event_end,
            })
            _logger.info(f"[BilletWeb] Événement créé : {event.name}")

            try:
                IrModelData.create({
                    'name': f"event_{event_id}",
                    'model': 'event.event',
                    'module': 'os_billetweb_sync',
                    'res_id': event.id,
                    'noupdate': True,
                })
                _logger.info(f"[BilletWeb] ID externe enregistré : os_billetweb_sync.event_{event_id}")
            except Exception as e:
                _logger.warning(f"[BilletWeb] Échec xml_id : {e}")

        return event
