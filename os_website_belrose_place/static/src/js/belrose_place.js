/** ================================================================
 *  BELROSE PLACE TAHITI — JavaScript v5
 *  Fixes définitifs :
 *  - Reveal : root:null (viewport), pas de root:#wrapwrap
 *  - Galerie : offsetWidth du wrap au moment du clic
 *  - Scroll ancre : sur document, scroller = #wrapwrap
 * ================================================================ */

odoo.define('os_website_belrose_place.main', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');

    /* ── Scroller Odoo (#wrapwrap) ─────────────────────────────── */
    function getScroller() {
        return document.getElementById('wrapwrap') || window;
    }
    function getScrollTop(sc) {
        return sc === window ? window.pageYOffset : sc.scrollTop;
    }
    function smoothScrollTo(sc, targetY, ms) {
        ms = ms || 700;
        const start = getScrollTop(sc);
        const dist  = targetY - start;
        let t0 = null;
        const ease = t => 1 - Math.pow(1 - t, 3);
        const step = ts => {
            if (!t0) t0 = ts;
            const p = Math.min((ts - t0) / ms, 1);
            const y = start + dist * ease(p);
            sc === window ? window.scrollTo(0, y) : (sc.scrollTop = y);
            if (p < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    }
    function scrollToEl(el) {
        if (!el) return;
        const sc     = getScroller();
        const scRect = sc === window ? { top: 0 } : sc.getBoundingClientRect();
        const cur    = getScrollTop(sc);
        const targetY = cur + (el.getBoundingClientRect().top - scRect.top) - 80;
        smoothScrollTo(sc, targetY, 800);
    }

    /* ── 1. SCROLL ANCRES (document entier) ────────────────────── */
    document.addEventListener('click', function (e) {
        const a = e.target.closest('a[href^="#"]');
        if (!a) return;
        const hash = a.getAttribute('href');
        if (!hash || hash === '#') return;
        const target = document.querySelector(hash);
        if (!target) return;
        e.preventDefault();
        scrollToEl(target);
    });

    /* ── 2. NAVBAR ──────────────────────────────────────────────── */
    publicWidget.registry.BelroseNavbar = publicWidget.Widget.extend({
        selector: '.belrose-navbar',
        start() {
            this._sc   = getScroller();
            this._nav  = this.el;
            this._menu = document.getElementById('belroseNavLinks');
            this._btn  = document.getElementById('belroseBurger');

            this._fn = () =>
                this._nav.classList.toggle('is-scrolled', getScrollTop(this._sc) > 60);
            this._sc.addEventListener('scroll', this._fn, { passive: true });
            this._fn();

            this._btn  && this._btn.addEventListener('click', () => this._toggle());
            this._menu && this._menu.querySelectorAll('.nav-link').forEach(l =>
                l.addEventListener('click', () => this._close())
            );
            return this._super(...arguments);
        },
        destroy() { this._sc.removeEventListener('scroll', this._fn); this._super(...arguments); },
        _toggle() {
            const open = this._menu && this._menu.classList.toggle('is-open');
            const ss = this._btn && this._btn.querySelectorAll('span');
            if (ss && ss.length >= 3) {
                ss[0].style.transform = open ? 'translateY(6.5px) rotate(45deg)' : '';
                ss[1].style.opacity   = open ? '0' : '1';
                ss[2].style.transform = open ? 'translateY(-6.5px) rotate(-45deg)' : '';
            }
        },
        _close() {
            this._menu && this._menu.classList.remove('is-open');
            const ss = this._btn && this._btn.querySelectorAll('span');
            ss && ss.forEach(s => { s.style.transform = ''; s.style.opacity = ''; });
        },
    });

    /* ── 3. PARALLAXE HERO ──────────────────────────────────────── */
    publicWidget.registry.BelroseParallax = publicWidget.Widget.extend({
        selector: '.belrose-hero',
        start() {
            this._bg  = this.el.querySelector('.belrose-hero-bg');
            this._sc  = getScroller();
            this._req = false;
            if (!this._bg) return this._super(...arguments);
            this._fn = () => {
                if (this._req) return;
                this._req = true;
                requestAnimationFrame(() => {
                    const sy = getScrollTop(this._sc);
                    const h  = this.el.offsetHeight;
                    if (sy < h * 1.5)
                        this._bg.style.transform = `scale(1.1) translateY(${(sy / h) * 12}%)`;
                    this._req = false;
                });
            };
            this._sc.addEventListener('scroll', this._fn, { passive: true });
            return this._super(...arguments);
        },
        destroy() { this._sc.removeEventListener('scroll', this._fn); this._super(...arguments); },
    });

    /* ── 4. GALERIE ─────────────────────────────────────────────── */
    publicWidget.registry.BelroseGallery = publicWidget.Widget.extend({
        selector: '#bpGallery',
        start() {
            this._track  = this.el.querySelector('#bpGalleryTrack');
            this._wrap   = this.el.querySelector('.bp-gallery-track-wrap');
            this._slides = this._track
                ? [...this._track.querySelectorAll('.bp-gallery-slide')]
                : [];
            this._dots   = [...this.el.querySelectorAll('.bp-gallery-dot')];
            this._cur    = 0;
            this._n      = this._slides.length;
            this._timer  = null;

            if (!this._track || this._n < 2) return this._super(...arguments);

            const prev = this.el.querySelector('#bpGalleryPrev');
            const next = this.el.querySelector('#bpGalleryNext');
            prev && prev.addEventListener('click', () => { this._go(-1); this._reset(); });
            next && next.addEventListener('click', () => { this._go(1);  this._reset(); });

            this._dots.forEach((d, i) =>
                d.addEventListener('click', () => { this._goto(i); this._reset(); })
            );

            // Swipe
            let sx = 0;
            this.el.addEventListener('touchstart', e => { sx = e.touches[0].clientX; }, { passive: true });
            this.el.addEventListener('touchend',   e => {
                const d = sx - e.changedTouches[0].clientX;
                if (Math.abs(d) > 40) { this._go(d > 0 ? 1 : -1); this._reset(); }
            }, { passive: true });

            this.el.addEventListener('mouseenter', () => this._pause());
            this.el.addEventListener('mouseleave', () => this._play());

            this._goto(0);
            this._play();
            return this._super(...arguments);
        },
        destroy() { this._pause(); this._super(...arguments); },

        _go(d)   { this._goto(this._cur + d); },
        _goto(i) { this._cur = (i + this._n) % this._n; this._update(); },

        _update() {
            if (!this._track || !this._wrap) return;
            // Largeur réelle du wrapper à l'instant T (évite les problèmes de layout)
            const wrapW = this._wrap.offsetWidth;
            const offset = this._cur * wrapW;
            this._track.style.transform = `translateX(-${offset}px)`;
            this._dots.forEach((d, i) => d.classList.toggle('active', i === this._cur));
        },

        _play()  { this._pause(); this._timer = setInterval(() => this._go(1), 4500); },
        _pause() { clearInterval(this._timer); this._timer = null; },
        _reset() { this._pause(); this._play(); },
    });

    /* ── 5. SCROLL REVEAL ───────────────────────────────────────── */
    // root:null = viewport du navigateur, fonctionne indépendamment du scroller Odoo
    publicWidget.registry.BelroseReveal = publicWidget.Widget.extend({
        selector: 'body',
        start() {
            this._obs = new IntersectionObserver(
                entries => entries.forEach(e => {
                    if (e.isIntersecting) {
                        e.target.classList.add('is-visible');
                        this._obs.unobserve(e.target);
                    }
                }),
                { root: null, threshold: 0.08, rootMargin: '0px 0px -30px 0px' }
            );
            document.querySelectorAll('.bp-reveal, .bp-reveal-left, .bp-reveal-right')
                .forEach(el => this._obs.observe(el));
            return this._super(...arguments);
        },
        destroy() { this._obs && this._obs.disconnect(); this._super(...arguments); },
    });

    return {};
});
