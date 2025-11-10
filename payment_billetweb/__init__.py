# -*- coding: utf-8 -*-

from . import models
from . import controllers

from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(env):
    """Hook d'initialisation après l'installation."""
    setup_provider(env, 'billetweb')


def uninstall_hook(env):
    """Hook de désinstallation."""
    reset_payment_provider(env, 'billetweb')