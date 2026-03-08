# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

_PROVIDER_VIEW_ARCH = """<xpath expr="//page[@name='credentials']" position="after">
    <page name="helcim_credentials" string="Identifiants Helcim"
          invisible="code != 'helcim'">
        <group>
            <group string="API Helcim">
                <field name="helcim_api_token"
                       password="True"
                       placeholder="Votre jeton API Helcim..."
                       required="code == 'helcim'"/>
                <field name="helcim_terminal_id"
                       placeholder="Laissez vide pour le terminal par défaut"/>
                <field name="helcim_currency_iso"
                       placeholder="XPF"
                       required="code == 'helcim'"/>
            </group>
            <group string="Test de connexion">
                <div>
                    <button name="action_helcim_test_connection"
                            type="object"
                            string="Tester la connexion API"
                            class="btn btn-secondary"
                            icon="fa-plug"/>
                </div>
            </group>
        </group>
    </page>
</xpath>"""

_TRANSACTION_VIEW_ARCH = """<xpath expr="//notebook" position="inside">
    <page name="helcim_details" string="Détails Helcim"
          invisible="provider_code != 'helcim'">
        <group>
            <group string="Identifiants Helcim">
                <field name="helcim_transaction_id" readonly="1"/>
                <field name="helcim_approval_code" readonly="1"/>
                <field name="helcim_checkout_token" readonly="1"
                       groups="base.group_system"/>
            </group>
            <group string="Informations de carte">
                <field name="helcim_card_type" readonly="1"/>
                <field name="helcim_card_number" readonly="1"/>
            </group>
        </group>
    </page>
</xpath>"""


def post_init_hook(env):
    """
    Contexte réel d'exécution dans Odoo 17 :
    - post_init_hook s'exécute avec le registre du module EN COURS de chargement
    - Les modèles Python du module courant NE SONT PAS encore dans env.registry
    - Les colonnes SQL helcim_* EXISTENT déjà en base (créées avant ce hook)
    - Le code 'helcim' N'EST PAS encore dans la Selection de payment.provider.code

    Stratégie : tout créer en SQL brut, puis enregistrer les external IDs via ORM
    (ir.model.data est un modèle natif Odoo, toujours disponible).
    """
    provider_id = _create_provider_sql(env)
    _create_imd(env, 'payment_provider_helcim', 'payment.provider', provider_id, noupdate=True)
    _create_payment_method(env, provider_id)
    _create_view(env, 'payment_provider_helcim_form_view',
                 'payment.provider.helcim.form', 'payment.provider',
                 'payment.payment_provider_form', _PROVIDER_VIEW_ARCH)
    _create_view(env, 'payment_transaction_helcim_form_view',
                 'payment.transaction.helcim.form', 'payment.transaction',
                 'payment.payment_transaction_form', _TRANSACTION_VIEW_ARCH)


def _create_provider_sql(env):
    """
    Insère le provider Helcim directement en SQL.
    Contourne complètement l'ORM et son registre Selection incomplet.
    Retourne l'id du provider créé ou existant.
    """
    cr = env.cr

    # Vérifier si un provider helcim existe déjà
    cr.execute("SELECT id FROM payment_provider WHERE code = 'helcim' LIMIT 1")
    row = cr.fetchone()
    if row:
        _logger.info("Helcim: Provider déjà existant (id=%d).", row[0])
        return row[0]

    pre_msg = ('<p>Paiement sécurisé par carte de crédit ou débit via Helcim. '
               'Vos données bancaires sont protégées par chiffrement SSL et conformes PCI-DSS.</p>')
    pending_msg = ('<p>Votre paiement est en cours de traitement. '
                   'Vous recevrez une confirmation par e-mail.</p>')
    done_msg = '<p>Votre paiement a été accepté. Merci pour votre confiance !</p>'
    cancel_msg = "<p>Votre paiement a été annulé. N'hésitez pas à réessayer ou à nous contacter.</p>"

    cr.execute("""
        INSERT INTO payment_provider
            (name, code, state, is_published, allow_tokenization, allow_express_checkout,
             pre_msg, pending_msg, done_msg, cancel_msg,
             helcim_currency_iso,
             create_uid, write_uid, create_date, write_date)
        VALUES
            ('Helcim', 'helcim', 'disabled', false, false, false,
             %s, %s, %s, %s,
             'XPF',
             1, 1, NOW(), NOW())
        RETURNING id
    """, (pre_msg, pending_msg, done_msg, cancel_msg))

    provider_id = cr.fetchone()[0]
    _logger.info("Helcim: Provider créé en SQL (id=%d).", provider_id)
    return provider_id


def _create_payment_method(env, provider_id):
    """Lie le provider Helcim à la méthode de paiement 'card'."""
    module = 'os_helcim_payment_provider'
    cr = env.cr

    # Vérifier si déjà configuré
    imd = env['ir.model.data'].search([
        ('module', '=', module), ('name', '=', 'payment_method_helcim_card'),
    ], limit=1)
    if imd:
        return

    # Chercher une méthode 'card' existante
    cr.execute("SELECT id FROM payment_method WHERE code = 'card' LIMIT 1")
    row = cr.fetchone()
    if row:
        method_id = row[0]
        # Lier via la table de relation many2many
        cr.execute("""
            INSERT INTO payment_method_payment_provider_rel (payment_method_id, payment_provider_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (method_id, provider_id))
        _logger.info("Helcim: Provider lié à la méthode 'card' existante (id=%d).", method_id)
        _create_imd(env, 'payment_method_helcim_card', 'payment.method', method_id, noupdate=True)
    else:
        # Créer la méthode 'card' en SQL
        cr.execute("""
            INSERT INTO payment_method (name, code, sequence, active, create_uid, write_uid, create_date, write_date)
            VALUES ('Carte bancaire', 'card', 10, true, 1, 1, NOW(), NOW())
            RETURNING id
        """)
        method_id = cr.fetchone()[0]
        cr.execute("""
            INSERT INTO payment_method_payment_provider_rel (payment_method_id, payment_provider_id)
            VALUES (%s, %s)
        """, (method_id, provider_id))
        _logger.info("Helcim: Méthode 'card' créée en SQL (id=%d).", method_id)
        _create_imd(env, 'payment_method_helcim_card', 'payment.method', method_id, noupdate=True)


def _create_imd(env, name, model, res_id, noupdate=False):
    """Crée un ir.model.data (external ID) via ORM — toujours disponible."""
    module = 'os_helcim_payment_provider'
    existing = env['ir.model.data'].search([
        ('module', '=', module), ('name', '=', name),
    ], limit=1)
    if existing:
        return
    env['ir.model.data'].create({
        'name': name,
        'module': module,
        'model': model,
        'res_id': res_id,
        'noupdate': noupdate,
    })


def _create_view(env, xmlid, name, model, parent_xmlid, arch):
    """Crée une vue héritée via ORM ir.ui.view — toujours disponible."""
    module = 'os_helcim_payment_provider'
    imd = env['ir.model.data'].search([
        ('module', '=', module), ('name', '=', xmlid),
    ], limit=1)
    if imd:
        _logger.info("Helcim: Vue '%s' déjà existante.", xmlid)
        return

    parent_view = env.ref(parent_xmlid)
    view = env['ir.ui.view'].create({
        'name': name,
        'model': model,
        'inherit_id': parent_view.id,
        'mode': 'primary',
        'arch_base': arch,
    })
    _create_imd(env, xmlid, 'ir.ui.view', view.id, noupdate=False)
    _logger.info("Helcim: Vue '%s' créée (id=%d).", xmlid, view.id)


def uninstall_hook(env):
    """Désactive le fournisseur Helcim et supprime les vues dynamiques."""
    env.cr.execute("UPDATE payment_provider SET state = 'disabled' WHERE code = 'helcim'")
    module = 'os_helcim_payment_provider'
    for xmlid in ('payment_provider_helcim_form_view', 'payment_transaction_helcim_form_view'):
        imd = env['ir.model.data'].search([
            ('module', '=', module), ('name', '=', xmlid),
        ], limit=1)
        if imd:
            view = env['ir.ui.view'].browse(imd.res_id)
            if view.exists():
                view.unlink()
