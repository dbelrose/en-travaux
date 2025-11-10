/** @odoo-module **/

import paymentForm from '@payment/js/payment_form';

paymentForm.include({

    /**
     * @override
     */
    async _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'billetweb') {
            return this._super(...arguments);
        }

        // Pour Billetweb, on ouvre le lien dans un nouvel onglet
        const redirectFormHtml = processingValues.redirect_form_html;
        const $form = $(redirectFormHtml);
        const actionUrl = $form.attr('action');

        if (actionUrl) {
            // Ouvrir dans un nouvel onglet
            window.open(actionUrl, '_blank');

            // Afficher un message à l'utilisateur
            this._displayDialog(
                'Paiement Billetweb',
                'Veuillez finaliser votre paiement dans l\'onglet Billetweb qui vient de s\'ouvrir. ' +
                'Une fois le paiement effectué, cette page se mettra à jour automatiquement.',
                'info'
            );

            // Démarrer le polling pour vérifier le statut
            this._startBilletwebStatusPolling();
        } else {
            return this._super(...arguments);
        }
    },

    /**
     * Démarre le polling pour vérifier le statut du paiement Billetweb
     *
     * @private
     */
    _startBilletwebStatusPolling() {
        const self = this;
        const maxAttempts = 60; // 5 minutes maximum (60 * 5 secondes)
        let attempts = 0;

        const checkStatus = () => {
            if (attempts >= maxAttempts) {
                self._enableButton();
                return;
            }

            this.rpc('/payment/status/poll', {
                csrf_token: odoo.csrf_token,
            }).then((data) => {
                if (data.success && data.display_values_list.length > 0) {
                    const txData = data.display_values_list[0];

                    if (txData.state === 'done') {
                        // Paiement confirmé, rediriger
                        window.location = txData.landing_route;
                        return;
                    } else if (txData.state === 'cancel' || txData.state === 'error') {
                        // Paiement échoué
                        self._enableButton();
                        self._displayErrorDialog(
                            'Paiement échoué',
                            'Le paiement n\'a pas pu être finalisé. Veuillez réessayer.'
                        );
                        return;
                    }
                }

                // Continuer le polling
                attempts++;
                setTimeout(checkStatus, 5000);
            }).catch(() => {
                // En cas d'erreur, continuer le polling
                attempts++;
                setTimeout(checkStatus, 5000);
            });
        };

        // Démarrer le premier check après 5 secondes
        setTimeout(checkStatus, 5000);
    },

    /**
     * Affiche une boîte de dialogue d'information
     *
     * @private
     * @param {String} title - Titre de la boîte de dialogue
     * @param {String} message - Message à afficher
     * @param {String} type - Type de dialogue (info, warning, error)
     */
    _displayDialog(title, message, type = 'info') {
        const iconClass = {
            'info': 'fa-info-circle text-info',
            'warning': 'fa-exclamation-triangle text-warning',
            'error': 'fa-times-circle text-danger'
        }[type] || 'fa-info-circle';

        const $dialog = $(`
            <div class="modal fade" tabindex="-1" role="dialog">
                <div class="modal-dialog" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fa ${iconClass}"></i> ${title}
                            </h5>
                            <button type="button" class="close" data-dismiss="modal">
                                <span>&times;</span>
                            </button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-primary" data-dismiss="modal">
                                OK
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `);

        $dialog.modal('show');
        $dialog.on('hidden.bs.modal', function() {
            $(this).remove();
        });
    }
});