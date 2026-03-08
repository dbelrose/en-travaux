/** @odoo-module **/

/**
 * os_helcim_payment_provider/static/src/js/payment_form.js
 *
 * Extension du formulaire de paiement Odoo pour l'intégration HelcimPay.js.
 * Gère l'affichage du modal HelcimPay.js et la validation côté client.
 */

import { _t } from "@web/core/l10n/translation";
import { loadJS } from "@web/core/assets";
import paymentForm from "@payment/js/payment_form";

paymentForm.include({

    /**
     * Surcharge de la méthode de soumission du formulaire de paiement.
     * Pour Helcim, on laisse le template gérer l'initialisation du modal.
     */
    async _submitForm(ev) {
        const providersCode = this.$('input[name="o_payment_radio"]:checked').data('provider-code');

        if (providersCode !== 'helcim') {
            return this._super(...arguments);
        }

        // Pour Helcim, la soumission est gérée par HelcimPay.js
        // Le formulaire est déjà initialisé avec le checkoutToken dans le template
        ev.preventDefault();
        ev.stopPropagation();
    },

});
