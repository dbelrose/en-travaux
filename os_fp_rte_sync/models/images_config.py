# -*- coding: utf-8 -*-
"""
Configuration des images automatiques pour res.partner

Ce fichier peut être externalisé pour faciliter la maintenance
et permettre des modifications sans toucher au code principal.
"""

# Mapping des activités vers les images
# Structure: 'pattern_ape': {'keywords': [...], 'default': (...)}
ACTIVITY_IMAGE_MAPPING = {

    # =============================================================================
    # SPORTS - Code APE 9312z - Activités de clubs de sports
    # =============================================================================
    'activités de clubs de sports': {
        'keywords': [
            # Sports de raquette
            (r'\b(tennis(?!.*table))\b',
             'os_fp_rte_sync/static/img/sports/tennis.png',
             'Tennis'),

            (r'\b(tennis[- ]de[- ]table|ping[- ]?pong|tt)\b',
             'os_fp_rte_sync/static/img/sports/table_tennis.png',
             'Tennis de table'),

            (r'\b(badminton)\b',
             'os_fp_rte_sync/static/img/sports/badminton.png',
             'Badminton'),

            (r'\b(squash)\b',
             'os_fp_rte_sync/static/img/sports/squash.png',
             'Squash'),

            # Sports de combat
            (r'\b(judo|ju[- ]?jitsu)\b',
             'os_fp_rte_sync/static/img/sports/judo.png',
             'Judo'),

            (r'\b(karate|karaté)\b',
             'os_fp_rte_sync/static/img/sports/karate.png',
             'Karaté'),

            (r'\b(boxe|boxing)\b',
             'os_fp_rte_sync/static/img/sports/boxing.png',
             'Boxe'),

            (r'\b(taekwondo|tae[- ]?kwon[- ]?do)\b',
             'os_fp_rte_sync/static/img/sports/taekwondo.png',
             'Taekwondo'),

            (r'\b(lutte|wrestling)\b',
             'os_fp_rte_sync/static/img/sports/wrestling.png',
             'Lutte'),

            (r'\b(mma|arts martiaux mixtes)\b',
             'os_fp_rte_sync/static/img/sports/mma.png',
             'MMA'),

            # Sports de tir
            (r'\b(tir à l\'arc|archerie|arc)\b',
             'os_fp_rte_sync/static/img/sports/archery.png',
             'Tir à l\'arc'),

            (r'\b(tir sportif|carabine|pistolet)\b',
             'os_fp_rte_sync/static/img/sports/shooting.png',
             'Tir sportif'),

            # Sports aquatiques (importants en Polynésie)
            (r'\b(natation|swimming|nage)\b',
             'os_fp_rte_sync/static/img/sports/swimming.png',
             'Natation'),

            (r'\b(plongée|diving|scuba)\b',
             'os_fp_rte_sync/static/img/sports/diving.png',
             'Plongée'),

            (r'\b(surf(?:ing)?)\b',
             'os_fp_rte_sync/static/img/sports/surfing.png',
             'Surf'),

            (r'\b(bodyboard)\b',
             'os_fp_rte_sync/static/img/sports/bodyboard.png',
             'Bodyboard'),

            (r'\b(stand[- ]?up[- ]?paddle|sup|paddle)\b',
             'os_fp_rte_sync/static/img/sports/sup.png',
             'Stand Up Paddle'),

            (r'\b(voile|sailing|catamaran)\b',
             'os_fp_rte_sync/static/img/sports/sailing.png',
             'Voile'),

            (r'\b(va\'?a|pirogue|outrigger)\b',
             'os_fp_rte_sync/static/img/sports/vaa.png',
             'Va\'a / Pirogue'),

            (r'\b(kayak|canoë)\b',
             'os_fp_rte_sync/static/img/sports/kayak.png',
             'Kayak'),

            (r'\b(kite[- ]?surf)\b',
             'os_fp_rte_sync/static/img/sports/kitesurf.png',
             'Kitesurf'),

            (r'\b(wind[- ]?surf|planche à voile)\b',
             'os_fp_rte_sync/static/img/sports/windsurf.png',
             'Windsurf'),

            (r'\b(water[- ]?polo)\b',
             'os_fp_rte_sync/static/img/sports/waterpolo.png',
             'Water-polo'),

            # Sports collectifs
            (r'\b(football|foot(?!.*américain)|soccer)\b',
             'os_fp_rte_sync/static/img/sports/football.png',
             'Football'),

            (r'\b(rugby)\b',
             'os_fp_rte_sync/static/img/sports/rugby.png',
             'Rugby'),

            (r'\b(basket(?:ball)?)\b',
             'os_fp_rte_sync/static/img/sports/basketball.png',
             'Basketball'),

            (r'\b(volley(?:ball)?)\b',
             'os_fp_rte_sync/static/img/sports/volleyball.png',
             'Volleyball'),

            (r'\b(handball|hand[- ]?ball)\b',
             'os_fp_rte_sync/static/img/sports/handball.png',
             'Handball'),

            (r'\b(baseball)\b',
             'os_fp_rte_sync/static/img/sports/baseball.png',
             'Baseball'),

            # Sports de précision
            (r'\b(pétanque|boules)\b',
             'os_fp_rte_sync/static/img/sports/petanque.png',
             'Pétanque'),

            (r'\b(golf)\b',
             'os_fp_rte_sync/static/img/sports/golf.png',
             'Golf'),

            (r'\b(fléchettes|darts)\b',
             'os_fp_rte_sync/static/img/sports/darts.png',
             'Fléchettes'),

            # Autres sports
            (r'\b(athlétisme|athletics)\b',
             'os_fp_rte_sync/static/img/sports/athletics.png',
             'Athlétisme'),

            (r'\b(cyclisme|vélo|cycling|vtt)\b',
             'os_fp_rte_sync/static/img/sports/cycling.png',
             'Cyclisme'),

            (r'\b(équitation|horse|cheval)\b',
             'os_fp_rte_sync/static/img/sports/equestrian.png',
             'Équitation'),

            (r'\b(danse|dance|ori tahiti)\b',
             'os_fp_rte_sync/static/img/sports/dance.png',
             'Danse'),

            (r'\b(fitness|musculation|gym|crossfit)\b',
             'os_fp_rte_sync/static/img/sports/fitness.png',
             'Fitness'),

            (r'\b(yoga)\b',
             'os_fp_rte_sync/static/img/sports/yoga.png',
             'Yoga'),

            (r'\b(escalade|climbing)\b',
             'os_fp_rte_sync/static/img/sports/climbing.png',
             'Escalade'),

            (r'\b(triathlon)\b',
             'os_fp_rte_sync/static/img/sports/triathlon.png',
             'Triathlon'),
        ],
        'default': ('os_fp_rte_sync/static/img/sports/default_sport.png', 'Sport')
    },

    # =============================================================================
    # ARTS ET CULTURE - Codes APE 9003a/9003b
    # =============================================================================
    'création artistique': {
        'keywords': [
            (r'\b(peintur[e|ing]|arts? plastiques?)\b',
             'os_fp_rte_sync/static/img/art/painting.png',
             'Peinture'),

            (r'\b(sculptur[e|ing])\b',
             'os_fp_rte_sync/static/img/art/sculpture.png',
             'Sculpture'),

            (r'\b(photographie|photo)\b',
             'os_fp_rte_sync/static/img/art/photography.png',
             'Photographie'),

            (r'\b(théâtre|theater)\b',
             'os_fp_rte_sync/static/img/art/theater.png',
             'Théâtre'),

            (r'\b(musique|music|orchestre)\b',
             'os_fp_rte_sync/static/img/art/music.png',
             'Musique'),

            (r'\b(cinéma|film)\b',
             'os_fp_rte_sync/static/img/art/cinema.png',
             'Cinéma'),

            (r'\b(artisanat|artisan)\b',
             'os_fp_rte_sync/static/img/art/crafts.png',
             'Artisanat'),
        ],
        'default': ('os_fp_rte_sync/static/img/art/default_art.png', 'Art')
    },

    # =============================================================================
    # RESTAURATION - Codes APE 5610a/5610b/5610c
    # =============================================================================
    'restauration': {
        'keywords': [
            (r'\b(pizz[ae]ria)\b',
             'os_fp_rte_sync/static/img/food/pizza.png',
             'Pizzeria'),

            (r'\b(burger|hamburger)\b',
             'os_fp_rte_sync/static/img/food/burger.png',
             'Burger'),

            (r'\b(sushi|japonais)\b',
             'os_fp_rte_sync/static/img/food/sushi.png',
             'Sushi'),

            (r'\b(crêpe|galette)\b',
             'os_fp_rte_sync/static/img/food/crepe.png',
             'Crêperie'),

            (r'\b(chinois|asiatique|thai|vietnamien)\b',
             'os_fp_rte_sync/static/img/food/asian.png',
             'Asiatique'),

            (r'\b(tahitien|ma\'?a|fafaru)\b',
             'os_fp_rte_sync/static/img/food/tahitian.png',
             'Tahitien'),

            (r'\b(poisson cru|i\'?a ota)\b',
             'os_fp_rte_sync/static/img/food/poisson_cru.png',
             'Poisson cru'),

            (r'\b(roulotte)\b',
             'os_fp_rte_sync/static/img/food/food_truck.png',
             'Roulotte'),

            (r'\b(snack)\b',
             'os_fp_rte_sync/static/img/food/snack.png',
             'Snack'),

            (r'\b(brasserie)\b',
             'os_fp_rte_sync/static/img/food/brasserie.png',
             'Brasserie'),
        ],
        'default': ('os_fp_rte_sync/static/img/food/restaurant.png', 'Restaurant')
    },

    # =============================================================================
    # HÉBERGEMENT - Code APE 5510z
    # =============================================================================
    'hôtels et hébergement': {
        'keywords': [
            (r'\b(hôtel|hotel)\b',
             'os_fp_rte_sync/static/img/accommodation/hotel.png',
             'Hôtel'),

            (r'\b(pension)\b',
             'os_fp_rte_sync/static/img/accommodation/pension.png',
             'Pension'),

            (r'\b(bungalow|fare)\b',
             'os_fp_rte_sync/static/img/accommodation/bungalow.png',
             'Bungalow'),

            (r'\b(resort)\b',
             'os_fp_rte_sync/static/img/accommodation/resort.png',
             'Resort'),
        ],
        'default': ('os_fp_rte_sync/static/img/accommodation/default.png', 'Hébergement')
    },

    # =============================================================================
    # COMMERCE - Codes APE 47xx
    # =============================================================================
    'commerce de détail': {
        'keywords': [
            (r'\b(pharmacie|pharmacy)\b',
             'os_fp_rte_sync/static/img/commerce/pharmacy.png',
             'Pharmacie'),

            (r'\b(boulangerie|pain)\b',
             'os_fp_rte_sync/static/img/commerce/bakery.png',
             'Boulangerie'),

            (r'\b(fleuriste|fleurs)\b',
             'os_fp_rte_sync/static/img/commerce/florist.png',
             'Fleuriste'),

            (r'\b(librairie|livres)\b',
             'os_fp_rte_sync/static/img/commerce/bookstore.png',
             'Librairie'),

            (r'\b(supermarché|carrefour|champion)\b',
             'os_fp_rte_sync/static/img/commerce/supermarket.png',
             'Supermarché'),

            (r'\b(bijouterie|perles)\b',
             'os_fp_rte_sync/static/img/commerce/jewelry.png',
             'Bijouterie'),
        ],
        'default': ('os_fp_rte_sync/static/img/commerce/shop.png', 'Commerce')
    },
}

# Paramètres du système
IMAGE_CONFIG = {
    # Taille de traitement des images
    'image_size': (1920, 1920),

    # Activer les logs détaillés
    'verbose_logging': True,

    # Ne jamais écraser une image existante
    'preserve_existing': True,

    # Préfixe pour les chemins d'images
    'image_path_prefix': 'os_fp_rte_sync/static/img/',
}
