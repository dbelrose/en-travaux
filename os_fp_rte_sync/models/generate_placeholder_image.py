#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de génération d'images placeholder pour le système d'attribution automatique.

Ce script génère des images PNG colorées avec du texte pour chaque activité définie
dans le mapping. Utile pour le développement et les tests avant d'avoir les vraies images.

Usage:
    python generate_placeholder_images.py

Prérequis:
    pip install pillow
"""

import os
from PIL import Image, ImageDraw, ImageFont

# Configuration
OUTPUT_DIR = "os_fp_rte_sync/static/img"
IMAGE_SIZE = (1920, 1920)
FONT_SIZE = 120

# Couleurs par catégorie
CATEGORY_COLORS = {
    'sports': '#3498db',  # Bleu
    'art': '#9b59b6',  # Violet
    'food': '#e67e22',  # Orange
    'accommodation': '#1abc9c',  # Turquoise
    'commerce': '#e74c3c',  # Rouge
}

# Liste des images à générer (catégorie, nom_fichier, texte)
IMAGES_TO_GENERATE = [
    # Sports
    ('sports', 'tennis.png', '🎾\nTENNIS'),
    ('sports', 'table_tennis.png', '🏓\nTENNIS\nDE TABLE'),
    ('sports', 'badminton.png', '🏸\nBADMINTON'),
    ('sports', 'squash.png', '🎾\nSQUASH'),
    ('sports', 'judo.png', '🥋\nJUDO'),
    ('sports', 'karate.png', '🥋\nKARATE'),
    ('sports', 'boxing.png', '🥊\nBOXE'),
    ('sports', 'taekwondo.png', '🥋\nTAEKWONDO'),
    ('sports', 'wrestling.png', '🤼\nLUTTE'),
    ('sports', 'mma.png', '🥊\nMMA'),
    ('sports', 'archery.png', '🏹\nTIR À L\'ARC'),
    ('sports', 'shooting.png', '🎯\nTIR SPORTIF'),
    ('sports', 'swimming.png', '🏊\nNATATION'),
    ('sports', 'diving.png', '🤿\nPLONGÉE'),
    ('sports', 'surfing.png', '🏄\nSURF'),
    ('sports', 'bodyboard.png', '🏄\nBODYBOARD'),
    ('sports', 'sup.png', '🏄\nSUP'),
    ('sports', 'sailing.png', '⛵\nVOILE'),
    ('sports', 'vaa.png', '🛶\nVA\'A'),
    ('sports', 'kayak.png', '🛶\nKAYAK'),
    ('sports', 'kitesurf.png', '🪁\nKITESURF'),
    ('sports', 'windsurf.png', '🏄\nWINDSURF'),
    ('sports', 'waterpolo.png', '🤽\nWATER-POLO'),
    ('sports', 'football.png', '⚽\nFOOTBALL'),
    ('sports', 'rugby.png', '🏉\nRUGBY'),
    ('sports', 'basketball.png', '🏀\nBASKETBALL'),
    ('sports', 'volleyball.png', '🏐\nVOLLEYBALL'),
    ('sports', 'handball.png', '🤾\nHANDBALL'),
    ('sports', 'baseball.png', '⚾\nBASEBALL'),
    ('sports', 'petanque.png', '⚫\nPÉTANQUE'),
    ('sports', 'golf.png', '⛳\nGOLF'),
    ('sports', 'darts.png', '🎯\nFLÉCHETTES'),
    ('sports', 'athletics.png', '🏃\nATHLÉTISME'),
    ('sports', 'cycling.png', '🚴\nCYCLISME'),
    ('sports', 'equestrian.png', '🏇\nÉQUITATION'),
    ('sports', 'dance.png', '💃\nDANSE'),
    ('sports', 'fitness.png', '💪\nFITNESS'),
    ('sports', 'yoga.png', '🧘\nYOGA'),
    ('sports', 'climbing.png', '🧗\nESCALADE'),
    ('sports', 'triathlon.png', '🏊🚴🏃\nTRIATHLON'),
    ('sports', 'default_sport.png', '⚽🏀🎾\nSPORT'),

    # Arts
    ('art', 'painting.png', '🎨\nPEINTURE'),
    ('art', 'sculpture.png', '🗿\nSCULPTURE'),
    ('art', 'photography.png', '📷\nPHOTO'),
    ('art', 'theater.png', '🎭\nTHÉÂTRE'),
    ('art', 'music.png', '🎵\nMUSIQUE'),
    ('art', 'cinema.png', '🎬\nCINÉMA'),
    ('art', 'crafts.png', '🪡\nARTISANAT'),
    ('art', 'default_art.png', '🎨🎭🎵\nART'),

    # Restauration
    ('food', 'pizza.png', '🍕\nPIZZA'),
    ('food', 'burger.png', '🍔\nBURGER'),
    ('food', 'sushi.png', '🍣\nSUSHI'),
    ('food', 'crepe.png', '🥞\nCRÊPE'),
    ('food', 'asian.png', '🥢\nASIATIQUE'),
    ('food', 'tahitian.png', '🌺\nTAHITIEN'),
    ('food', 'poisson_cru.png', '🐟\nPOISSON CRU'),
    ('food', 'food_truck.png', '🚚\nROULOTTE'),
    ('food', 'snack.png', '🥪\nSNACK'),
    ('food', 'brasserie.png', '🍺\nBRASSERIE'),
    ('food', 'restaurant.png', '🍽️\nRESTAURANT'),

    # Hébergement
    ('accommodation', 'hotel.png', '🏨\nHÔTEL'),
    ('accommodation', 'pension.png', '🏡\nPENSION'),
    ('accommodation', 'bungalow.png', '🛖\nBUNGALOW'),
    ('accommodation', 'resort.png', '🏝️\nRESORT'),
    ('accommodation', 'default.png', '🏨🏡\nHÉBERGEMENT'),

    # Commerce
    ('commerce', 'pharmacy.png', '💊\nPHARMACIE'),
    ('commerce', 'bakery.png', '🥖\nBOULANGERIE'),
    ('commerce', 'florist.png', '💐\nFLEURISTE'),
    ('commerce', 'bookstore.png', '📚\nLIBRAIRIE'),
    ('commerce', 'supermarket.png', '🛒\nSUPERMARCHÉ'),
    ('commerce', 'jewelry.png', '💎\nBIJOUTERIE'),
    ('commerce', 'shop.png', '🏪\nCOMMERCE'),
]


def hex_to_rgb(hex_color):
    """Convertit une couleur hex en RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def create_placeholder_image(category, filename, text, output_dir):
    """
    Crée une image placeholder avec du texte.

    Args:
        category: Catégorie (sports, art, food, etc.)
        filename: Nom du fichier de sortie
        text: Texte à afficher sur l'image
        output_dir: Répertoire de sortie
    """
    # Créer le répertoire si nécessaire
    category_dir = os.path.join(output_dir, category)
    os.makedirs(category_dir, exist_ok=True)

    # Créer l'image
    img = Image.new('RGB', IMAGE_SIZE, color='white')
    draw = ImageDraw.Draw(img)

    # Couleur de fond dégradé
    bg_color = hex_to_rgb(CATEGORY_COLORS.get(category, '#95a5a6'))
    for y in range(IMAGE_SIZE[1]):
        # Dégradé du haut vers le bas
        factor = y / IMAGE_SIZE[1]
        r = int(bg_color[0] + (255 - bg_color[0]) * factor * 0.3)
        g = int(bg_color[1] + (255 - bg_color[1]) * factor * 0.3)
        b = int(bg_color[2] + (255 - bg_color[2]) * factor * 0.3)
        draw.line([(0, y), (IMAGE_SIZE[0], y)], fill=(r, g, b))

    # Ajouter le texte
    try:
        # Essayer d'utiliser une police système
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_SIZE)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", FONT_SIZE)
        except Exception:
            # Fallback sur la police par défaut
            font = ImageFont.load_default()

    # Centrer le texte
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (IMAGE_SIZE[0] - text_width) // 2
    y = (IMAGE_SIZE[1] - text_height) // 2

    # Ombre du texte
    shadow_offset = 5
    draw.text((x + shadow_offset, y + shadow_offset), text, fill='rgba(0,0,0,0.3)', font=font, align='center')

    # Texte principal
    draw.text((x, y), text, fill='white', font=font, align='center')

    # Bordure arrondie
    border_width = 20
    draw.rectangle(
        [(border_width, border_width), (IMAGE_SIZE[0] - border_width, IMAGE_SIZE[1] - border_width)],
        outline='white',
        width=border_width
    )

    # Sauvegarder
    output_path = os.path.join(category_dir, filename)
    img.save(output_path, 'PNG')
    print(f"✓ Créé: {output_path}")


def main():
    """Génère toutes les images placeholder."""
    print(f"Génération des images placeholder dans {OUTPUT_DIR}...")
    print(f"Taille: {IMAGE_SIZE[0]}x{IMAGE_SIZE[1]}px\n")

    # Créer le répertoire de base
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Générer toutes les images
    for category, filename, text in IMAGES_TO_GENERATE:
        create_placeholder_image(category, filename, text, OUTPUT_DIR)

    print(f"\n✅ {len(IMAGES_TO_GENERATE)} images générées avec succès!")
    print(f"\nStructure créée:")
    for category in set(cat for cat, _, _ in IMAGES_TO_GENERATE):
        count = len([1 for c, _, _ in IMAGES_TO_GENERATE if c == category])
        print(f"  - {OUTPUT_DIR}/{category}/ ({count} images)")


if __name__ == '__main__':
    main()
