/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.BookingForm = publicWidget.Widget.extend({
    selector: '.booking_form',
    events: {
        'change #start_date, #end_date': '_onDateChange',
    },

    start: function () {
        this._super.apply(this, arguments);
        this._updatePriceDisplay();
    },

    _onDateChange: function () {
        this._updatePriceDisplay();
    },

    _updatePriceDisplay: async function () {
        const startDate = this.$('#start_date').val();
        const endDate = this.$('#end_date').val();
        const productId = this.$('input[name="product_id"]').val();

        if (!startDate || !endDate || !productId) {
            return;
        }

        try {
            const result = await this._rpc({
                route: '/booking/availability',
                params: {
                    product_id: parseInt(productId),
                    start_date: startDate,
                    end_date: endDate,
                },
            });

            if (result.error) {
                this._showError(result.error);
                return;
            }

            if (!result.available) {
                this._showError('Ce logement n\'est pas disponible pour ces dates.');
                this.$('button[type="submit"]').prop('disabled', true);
                return;
            }

            this.$('button[type="submit"]').prop('disabled', false);

            // Mise à jour de l'affichage des prix
            const $priceInfo = this.$('.price-info');
            if ($priceInfo.length) {
                let html = `
                    <p><strong>Nombre de nuits:</strong> ${result.nights}</p>
                    <p><strong>Sous-total:</strong> ${result.subtotal.toFixed(2)} €</p>
                `;

                if (result.discount_percent > 0) {
                    html += `
                        <p class="text-success">
                            <strong>Réduction ${result.discount_percent}%:</strong> 
                            -${result.discount_amount.toFixed(2)} €
                        </p>
                    `;
                }

                html += `<p class="h4"><strong>Total:</strong> ${result.total.toFixed(2)} €</p>`;
                $priceInfo.html(html);
            }

        } catch (error) {
            console.error('Error checking availability:', error);
        }
    },

    _showError: function (message) {
        const $alert = this.$('.availability-alert');
        if ($alert.length) {
            $alert.removeClass('d-none alert-success').addClass('alert-danger')
                  .text(message);
        }
    },
});

export default publicWidget.registry.BookingForm;
