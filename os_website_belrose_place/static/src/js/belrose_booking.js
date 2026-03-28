/**
 * Belrose Place — JS Réservation v2
 *
 * Rôles :
 *  1. Synchronisation date arrivée → date départ min (formulaire étape 2)
 *  2. Estimateur de prix AJAX (optionnel / non bloquant)
 *  3. Calendrier FullCalendar sur la page disponibilités
 */

(function () {
    'use strict';

    /* ── Formatage XPF ───────────────────────────────────────────── */
    function fmtXPF(n) {
        return new Intl.NumberFormat('fr-PF', {
            style: 'currency', currency: 'XPF', maximumFractionDigits: 0,
        }).format(n);
    }

    /* ── JSON-RPC helper ──────────────────────────────────────────── */
    function jsonRpc(url, params) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: params }),
        })
            .then(function (r) { return r.json(); })
            .then(function (d) { return (d && d.result) ? d.result : null; })
            .catch(function () { return null; });
    }

    /* ================================================================
       FORMULAIRE ÉTAPE 2 : estimateur AJAX (non bloquant)
       Le bouton submit est TOUJOURS actif grâce à la validation HTML5.
       Le JS améliore l'UX mais ne conditionne JAMAIS l'envoi du form.
    ================================================================ */
    function initBookingForm() {
        var configEl = document.getElementById('bpBookingConfig');
        if (!configEl) return;

        var config;
        try { config = JSON.parse(configEl.textContent); }
        catch (e) { return; }

        var startInput    = document.getElementById('bp_start_date');
        var endInput      = document.getElementById('bp_end_date');
        var priceBox      = document.getElementById('bpPriceEstimate');
        var alertBox      = document.getElementById('bpAvailAlert');

        if (!startInput || !endInput) return;

        var debounce = null;

        /* Mise à jour de la date min du champ "départ" */
        function syncEndMin() {
            if (!startInput.value) return;
            var minEnd = new Date(startInput.value);
            minEnd.setDate(minEnd.getDate() + (config.min_nights || 2));
            var iso = minEnd.toISOString().split('T')[0];
            endInput.min = iso;
            if (endInput.value && endInput.value < iso) {
                endInput.value = iso;
            }
        }

        /* Appel AJAX pour estimer le prix et vérifier la dispo */
        function fetchEstimate() {
            clearTimeout(debounce);
            var start = startInput.value;
            var end   = endInput.value;
            if (!start || !end || start >= end) {
                hidePriceBox();
                return;
            }
            debounce = setTimeout(function () {
                jsonRpc(config.availability_url, {
                    product_id: config.product_id,
                    start_date: start,
                    end_date:   end,
                }).then(function (res) {
                    if (!res || res.error) { hidePriceBox(); return; }

                    if (!res.available) {
                        showAlert('⚠ Ce logement n\'est pas disponible pour ces dates.', 'is-unavailable');
                        hidePriceBox();
                        return;
                    }
                    hideAlert();
                    showPriceBox(res);
                });
            }, 600);
        }

        function showPriceBox(res) {
            if (!priceBox) return;
            document.getElementById('bpNights').textContent   = res.nights;
            document.getElementById('bpSubtotal').textContent = fmtXPF(res.subtotal);
            document.getElementById('bpTotal').textContent    = fmtXPF(res.total);

            var discountRow   = document.getElementById('bpDiscountRow');
            var discountLabel = document.getElementById('bpDiscountLabel');
            var discountAmt   = document.getElementById('bpDiscountAmount');
            if (res.discount_percent > 0) {
                discountLabel.textContent = res.discount_label || ('Réduction ' + res.discount_percent + '%');
                discountAmt.textContent   = '− ' + fmtXPF(res.discount_amount);
                discountRow.classList.remove('bp-hidden');
            } else {
                discountRow.classList.add('bp-hidden');
            }
            priceBox.classList.remove('bp-hidden');
        }

        function hidePriceBox() {
            if (priceBox) priceBox.classList.add('bp-hidden');
        }

        function showAlert(msg, cls) {
            if (!alertBox) return;
            alertBox.textContent = msg;
            alertBox.className   = 'bp-avail-alert ' + cls;
            alertBox.classList.remove('bp-hidden');
        }

        function hideAlert() {
            if (!alertBox) return;
            alertBox.className = 'bp-avail-alert bp-hidden';
        }

        startInput.addEventListener('change', function () { syncEndMin(); fetchEstimate(); });
        endInput.addEventListener('change', fetchEstimate);

        /* Init si les dates sont déjà pré-remplies (venant de la recherche) */
        if (startInput.value && endInput.value) {
            syncEndMin();
            fetchEstimate();
        }
    }

    /* ================================================================
       CALENDRIER FULLCALENDAR
    ================================================================ */
    function initCalendar() {
        var mountEl = document.getElementById('bpFullCalendar');
        var dataEl  = document.getElementById('bpCalendarData');
        var metaEl  = document.getElementById('bpCalendarMeta');
        if (!mountEl || !dataEl || !metaEl) return;

        var rawEvents, meta;
        try {
            rawEvents = JSON.parse(dataEl.textContent);
            meta      = JSON.parse(metaEl.textContent);
        } catch (e) { return; }

        var stateClass = {
            confirmed:    'fc-event-confirmed',
            payment_sent: 'fc-event-payment_sent',
            paid:         'fc-event-paid',
        };

        var events = rawEvents.map(function (b) {
            return {
                title:      b.state === 'paid' ? 'Réservé' : 'En cours',
                start:      b.start,
                end:        b.end,
                classNames: [stateClass[b.state] || 'fc-event-confirmed'],
                display:    'background',
            };
        });

        function loadScript(src, cb) {
            var s = document.createElement('script');
            s.src = src; s.onload = cb;
            document.head.appendChild(s);
        }
        function loadStyle(href) {
            var l = document.createElement('link');
            l.rel = 'stylesheet'; l.href = href;
            document.head.appendChild(l);
        }

        loadStyle('https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.css');
        loadScript('https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.js', function () {
            /* global FullCalendar */
            var cal = new FullCalendar.Calendar(mountEl, {
                initialView:  'dayGridMonth',
                locale:       'fr',
                firstDay:     1,
                initialDate:  meta.today,
                height:       'auto',
                headerToolbar: {
                    left:   'prev,next today',
                    center: 'title',
                    right:  'dayGridMonth',
                },
                events: events,
                eventInteractive: false,
                dayCellClassNames: function (arg) {
                    var d = arg.date.toISOString().split('T')[0];
                    var occupied = events.some(function (e) {
                        return d >= e.start && d < e.end;
                    });
                    return occupied ? [] : ['bp-day-free'];
                },
            });
            cal.render();
        });
    }

    /* ── Boot ──────────────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', function () {
        initBookingForm();
        initCalendar();
    });

}());

/* ================================================================
   DÉTECTION BLOCAGE IFRAME BILLETWEB
   Si l'iframe ne charge pas (X-Frame-Options), on affiche le fallback
================================================================ */
(function () {
    'use strict';

    function initPaymentIframe() {
        var iframe   = document.getElementById('bpBilletwebIframe');
        var fallback = document.getElementById('bpIframeFallback');
        if (!iframe || !fallback) return;

        var loaded  = false;
        var timeout = null;

        // Si l'iframe se charge correctement
        iframe.addEventListener('load', function () {
            loaded = true;
            clearTimeout(timeout);
            // Tenter d'accéder au contentDocument — si bloqué, exception
            try {
                // Certains navigateurs lèvent une exception si l'iframe est bloquée
                var doc = iframe.contentDocument || iframe.contentWindow.document;
                if (!doc || !doc.body || doc.body.innerHTML === '') {
                    throw new Error('empty');
                }
            } catch (e) {
                showFallback(iframe, fallback);
            }
        });

        // Timeout : si après 8s l'iframe n'a pas chargé → fallback
        timeout = setTimeout(function () {
            if (!loaded) {
                showFallback(iframe, fallback);
            }
        }, 8000);
    }

    function showFallback(iframe, fallback) {
        iframe.style.display = 'none';
        fallback.classList.remove('bp-hidden');
    }

    document.addEventListener('DOMContentLoaded', function () {
        initPaymentIframe();
    });
}());
