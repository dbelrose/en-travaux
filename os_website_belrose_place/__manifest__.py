# -*- coding: utf-8 -*-
{
    'name': 'Belrose Place - Site Web',
    'version': '17.0.3.0.0',
    'summary': 'Site web Belrose Place Tahiti — avec moteur de recherche et réservation voyageur',
    'description': """
        Module site web public de Belrose Place Tahiti. v3 inclut :
        - Page d'accueil, chèque cadeau, mentions légales
        - Moteur de recherche (dates + voyageurs) → résultats filtrés par dispo + capacité
        - Formulaire de réservation avec pré-calcul des prix et réductions
        - Page de confirmation, page d'erreur, mes réservations
        - Calendrier de disponibilité (FullCalendar 6)
        - Estimateur de prix AJAX (non bloquant)
    """,
    'author': 'OpalSea',
    'website': 'https://opalsea.site',
    'category': 'Website',
    'license': 'LGPL-3',
    'depends': [
        'website',
        'os_rental',
    ],
    'data': [
        'data/website_menu_data.xml',
        'views/website_templates.xml',
        'views/website_homepage.xml',
        'views/website_cheque_cadeau.xml',
        'views/website_mentions_legales.xml',
        'views/website_layout.xml',
        'views/website_booking.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'os_website_belrose_place/static/src/css/belrose_place.css',
            'os_website_belrose_place/static/src/css/belrose_booking.css',
            'os_website_belrose_place/static/src/js/belrose_place.js',
            'os_website_belrose_place/static/src/js/belrose_booking.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
