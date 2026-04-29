/** @odoo-module **/
/**
 * os_contact_encrypted — decrypt_widget.js  v2
 *
 * Vérifie si l'utilisateur a initialisé ses clés RSA.
 * Affiche une notification DISCRÈTE (non bloquante, non sticky) une seule fois
 * par session, avec un délai de 8 secondes pour ne pas perturber le chargement.
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, xml } from "@odoo/owl";

// Clé sessionStorage : on n'affiche la notif qu'une seule fois par session navigateur
const SESSION_KEY = "os_crypto_notif_shown";

class CryptoKeyCheck extends Component {
    static template = xml`<t/>`;

    setup() {
        this.notification = useService("notification");
        this.action = useService("action");

        onMounted(async () => {
            // Délai plus long (8 s) : l'interface est stable, l'utilisateur est actif
            setTimeout(() => this._checkKeys(), 8000);
        });
    }

    async _checkKeys() {
        // Ne montrer qu'une fois par session navigateur
        if (sessionStorage.getItem(SESSION_KEY)) return;

        try {
            const response = await fetch("/os_contact_encrypted/check_keys", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jsonrpc: "2.0", method: "call", id: 1, params: {} }),
            });
            if (!response.ok) return;
            const data = await response.json();
            if (data?.result?.has_keys === false) {
                sessionStorage.setItem(SESSION_KEY, "1");
                this._showInitNotification();
            }
        } catch (e) {
            console.debug("[os_contact_encrypted] check_keys:", e);
        }
    }

    _showInitNotification() {
        this.notification.add(
            "Configurez vos clés pour protéger vos contacts.",
            {
                title: "🔐 Chiffrement",
                // Non sticky : disparaît automatiquement après ~6 secondes
                type: "info",
                sticky: false,
                buttons: [
                    {
                        name: "Initialiser",
                        onClick: () => {
                            this.action.doAction(
                                "os_contact_encrypted.action_init_keypair_wizard"
                            );
                        },
                        primary: true,
                    },
                ],
            }
        );
    }
}

registry.category("main_components").add("OsCryptoKeyCheck", {
    Component: CryptoKeyCheck,
});
