# -*- coding: utf-8 -*-

import odoo
from odoo import api, SUPERUSER_ID
from functools import partial


def uninstall_hook(cr, registry):
    def rem_company_id(dbname):
        db_registry = odoo.modules.registry.Registry.new(dbname)
        with api.Environment.manage(), db_registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['res.config.settings'].search([
                ('company_id', '=', 'base.main_company'),
            ]).unlink()

        cr.postcommit.add(partial(rem_company_id, cr.dbname))


def post_init_hook(cr, registry):
    return True


def pre_init_hook(cr):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.users'].search([
        ('login', '=', 'admin@informatique.gov.pf')
    ]).unlink()
    env['res.partner'].search([
        ('name', '=', 'Administrateur du SI')
    ]).unlink()
    env.cr.commit()
