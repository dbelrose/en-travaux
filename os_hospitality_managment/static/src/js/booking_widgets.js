/* JavaScript pour les widgets booking */
/* Fichier: static/src/js/booking_widgets.js */

odoo.define('os_hospitality_managment.booking_widgets', function (require) {
'use strict';

var core = require('web.core');
var Widget = require('web.Widget');
var field_registry = require('web.field_registry');
var AbstractField = require('web.AbstractField');

var _t = core._t;

/**
 * Widget personnalisé pour afficher l'état de facturation avec des icônes
 */
var InvoiceStateWidget = AbstractField.extend({
    className: 'o_field_invoice_state',
    
    init: function () {
        this._super.apply(this, arguments);
        this.states = {
            'none': { label: _t('Aucune'), icon: 'fa-circle-o', class: 'text-muted' },
            'booking_only': { label: _t('Booking seul'), icon: 'fa-circle-o-notch', class: 'text-warning' },
            'concierge_only': { label: _t('Concierge seul'), icon: 'fa-circle-o-notch', class: 'text-warning' },
            'customer_only': { label: _t('Clients seuls'), icon: 'fa-circle-o-notch', class: 'text-info' },
            'booking_concierge': { label: _t('B. + C.'), icon: 'fa-adjust', class: 'text-primary' },
            'booking_customer': { label: _t('B. + Clients'), icon: 'fa-adjust', class: 'text-primary' },
            'concierge_customer': { label: _t('C. + Clients'), icon: 'fa-adjust', class: 'text-primary' },
            'all': { label: _t('Complètes'), icon: 'fa-check-circle', class: 'text-success' }
        };
    },

    _render: function () {
        var state = this.value || 'none';
        var stateInfo = this.states[state] || this.states['none'];
        
        this.$el.empty();
        this.$el.append($('<i>').addClass('fa ' + stateInfo.icon + ' ' + stateInfo.class));
        this.$el.append($('<span>').text(' ' + stateInfo.label).addClass(stateInfo.class));
        
        // Ajouter tooltip avec détails
        this.$el.attr('title', this._getTooltipText(state));
    },
    
    _getTooltipText: function (state) {
        var tooltips = {
            'none': _t('Aucune facture générée'),
            'booking_only': _t('Seule la facture Booking.com a été générée'),
            'concierge_only': _t('Seule la facture concierge a été générée'),
            'customer_only': _t('Seules les factures clients ont été générées'),
            'booking_concierge': _t('Factures Booking.com et concierge générées'),
            'booking_customer': _t('Factures Booking.com et clients générées'),
            'concierge_customer': _t('Factures concierge et clients générées'),
            'all': _t('Toutes les factures ont été générées')
        };
        return tooltips[state] || '';
    }
});

field_registry.add('invoice_state_widget', InvoiceStateWidget);

/**
 * Widget pour afficher les montants monétaires avec animation
 */
var AnimatedMonetaryWidget = AbstractField.extend({
    className: 'o_field_animated_monetary',
    
    _render: function () {
        var value = this.value || 0;
        var currency = this.record && this.record.data && this.record.data.company_currency_id;
        var formatted = this._formatCurrency(value, currency);
        
        this.$el.empty();
        
        if (value > 0) {
            this.$el.addClass('positive');
        } else if (value < 0) {
            this.$el.addClass('negative');
        }
        
        // Animation de comptage si la valeur a changé
        this._animateValue(0, value, formatted);
    },
    
    _formatCurrency: function (value, currency) {
        if (currency && currency.data && currency.data.symbol) {
            var symbol = currency.data.symbol;
            var position = currency.data.position;
            
            if (position === 'before') {
                return symbol + ' ' + this._formatNumber(value);
            } else {
                return this._formatNumber(value) + ' ' + symbol;
            }
        }
        return this._formatNumber(value) + ' XPF';
    },
    
    _formatNumber: function (value) {
        return new Intl.NumberFormat('fr-FR', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(Math.abs(value));
    },
    
    _animateValue: function (start, end, finalFormat) {
        var self = this;
        var duration = 1000; // 1 seconde
        var steps = 30;
        var increment = (end - start) / steps;
        var current = start;
        var step = 0;
        
        var timer = setInterval(function () {
            current += increment;
            step++;
            
            if (step >= steps) {
                clearInterval(timer);
                self.$el.text(finalFormat);
            } else {
                self.$el.text(self._formatNumber(current));
            }
        }, duration / steps);
    }
});

field_registry.add('animated_monetary', AnimatedMonetaryWidget);

/**
 * Fonctions utilitaires pour les notifications personnalisées
 */
var NotificationService = require('web.NotificationService');

var HospitalityNotifications = {
    showSuccess: function (message, title) {
        title = title || _t('Succès');
        this.call('notification', 'notify', {
            title: title,
            message: message,
            type: 'success',
        });
    },

    showInfo: function (message, title) {
        title = title || _t('Information');
        this.call('notification', 'notify', {
            title: title,
            message: message,
            type: 'info',
        });
    },

    showWarning: function (message, title) {
        title = title || _t('Attention');
        this.call('notification', 'notify', {
            title: title,
            message: message,
            type: 'warning',
        });
    },

    showError: function (message, title) {
        title = title || _t('Erreur');
        this.call('notification', 'notify', {
            title: title,
            message: message,
            type: 'danger',
        });
    }
};

/**
 * Mixin pour les vues avec fonctionnalités hospitalité
 */
var HospitalityViewMixin = {
    /**
     * Ajoute des boutons d'action rapide à une vue liste
     */
    _addQuickActionButtons: function () {
        var self = this;
        
        if (this.modelName === 'booking.month') {
            this.$('.o_list_view').before(
                $('<div class="o_hospitality_quick_actions mb-3">')
                    .append(
                        $('<button class="btn btn-primary btn-sm mr-2">')
                            .text(_t('Générer toutes les factures clients'))
                            .click(function () {
                                self._generateAllCustomerInvoices();
                            })
                    )
                    .append(
                        $('<button class="btn btn-secondary btn-sm">')
                            .text(_t('Assistant configuration'))
                            .click(function () {
                                self._openConfigWizard();
                            })
                    )
            );
        }
    },
    
    _generateAllCustomerInvoices: function () {
        var self = this;
        
        // Afficher un loader
        var $loader = $('<div class="text-center">')
            .append($('<div class="hospitality_loading">'))
            .append($('<p>').text(_t('Génération en cours...')));
        
        this.$el.append($loader);
        
        // Appel RPC pour générer les factures
        this._rpc({
            model: 'booking.month',
            method: 'action_generate_customer_invoices_batch',
            args: [this.getSelectedIds()]
        }).then(function (result) {
            $loader.remove();
            HospitalityNotifications.showSuccess(result.message);
            this.trigger_up('reload');
        }).catch(function () {
            $loader.remove();
            HospitalityNotifications.showError(_t('Erreur lors de la génération des factures'));
        });
    },

    _openConfigWizard: function () {
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'hospitality.config.wizard',
            views: [[false, 'form']],
            target: 'new',
        });
    },
};

return {
    InvoiceStateWidget: InvoiceStateWidget,
    AnimatedMonetaryWidget: AnimatedMonetaryWidget,
    HospitalityNotifications: HospitalityNotifications,
    HospitalityViewMixin: HospitalityViewMixin,
};

});
