# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID

def _set_if(ICP, key, val):
    if val not in (None, False, ''):
        ICP.set_param(key, str(val))

def post_init_hook(cr, registry):
    """À l'installation/mise à jour:
    - si des données existent dans l'ancien modèle `booking.config`,
      on les migre vers ir.config_parameter.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    ICP = env['ir.config_parameter'].sudo()

    migrated = False

    # 1) Si le modèle booking.config est encore chargé (module ancien toujours présent)
    if env.registry.get('booking.config'):
        try:
            conf = env['booking.config'].search([], limit=1, order='id desc')
            if conf:
                _set_if(ICP, 'booking.billetweb_user_id', conf.billetweb_user_id)
                _set_if(ICP, 'booking.billetweb_api_key', conf.billetweb_api_key)
                _set_if(ICP, 'booking.billetweb_event_id', conf.billetweb_event_id)
                _set_if(ICP, 'booking.billetweb_ticket_id', conf.billetweb_ticket_id)
                _set_if(ICP, 'booking.cgv_url', conf.cgv_url)
                _set_if(ICP, 'booking.min_nights', conf.min_nights)
                _set_if(ICP, 'booking.max_months', conf.max_months)
                _set_if(ICP, 'booking.weekly_discount', conf.weekly_discount)
                _set_if(ICP, 'booking.weekly_nights', conf.weekly_nights)
                _set_if(ICP, 'booking.monthly_discount', conf.monthly_discount)
                _set_if(ICP, 'booking.monthly_nights', conf.monthly_nights)
                migrated = True
        except Exception:
            # on tombera sur la branche SQL si souci
            pass

    # 2) Fallback SQL si le modèle n'existe plus mais la table persiste
    if not migrated:
        try:
            cr.execute("SELECT to_regclass('public.booking_config')")
            exists = cr.fetchone() and cr.fetchone() or None  # incorrect: fix below
        except Exception:
            exists = None

        # Correction: re-exécuter proprement et lire une seule fois
        try:
            cr.execute("SELECT to_regclass('public.booking_config')")
            exists = cr.fetchone()[0]
        except Exception:
            exists = None

        if exists:
            try:
                cr.execute("""
                    SELECT billetweb_user_id, billetweb_api_key, billetweb_event_id, billetweb_ticket_id,
                           cgv_url, min_nights, max_months, weekly_discount, weekly_nights,
                           monthly_discount, monthly_nights
                    FROM booking_config
                    ORDER BY id DESC
                    LIMIT 1
                """)
                row = cr.fetchone()
                if row:
                    keys = [
                        'booking.billetweb_user_id',
                        'booking.billetweb_api_key',
                        'booking.billetweb_event_id',
                        'booking.billetweb_ticket_id',
                        'booking.cgv_url',
                        'booking.min_nights',
                        'booking.max_months',
                        'booking.weekly_discount',
                        'booking.weekly_nights',
                        'booking.monthly_discount',
                        'booking.monthly_nights',
                    ]
                    for k, v in zip(keys, row):
                        _set_if(ICP, k, v)
            except Exception:
                # on ignore silencieusement : la migration est best-effort
                pass
