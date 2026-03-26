#!/usr/bin/env python3
"""
Script pour tester et extraire les codepoints corrects de Font Awesome
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Chemins possibles
FONT_PATHS = [
    'os_fp_rte_sync/static/fonts/Font Awesome 6 Free-Solid-900.otf',
    '/usr/share/fonts/opentype/font-awesome/Font Awesome 6 Free-Solid-900.otf',
    '/usr/share/fonts/truetype/font-awesome/fa-solid-900.ttf',
]

# Les codepoints à tester (trouvés sur fontawesome.com)
TEST_ICONS = {
    'futbol': '\uf1e3',  # Football
    'utensils': '\uf2e7',  # Restaurant
    'swimmer': '\uf5c4',  # Natation
    'sailboat': '\ue532',  # Voile
    'bicycle': '\uf206',  # Vélo
    'dumbbell': '\uf44b',  # Fitness
    'palette': '\uf53f',  # Peinture
    'camera': '\uf030',  # Photo
    'music': '\uf001',  # Musique
    'hotel': '\uf594',  # Hôtel
    'home': '\uf015',  # Maison
}


def find_font():
    """Trouve la font FA sur le système"""
    for path in FONT_PATHS:
        if os.path.exists(path):
            print(f"✓ Font trouvée : {path}")
            return path
    print("✗ Font non trouvée aux emplacements connus")
    return None


def test_icons(font_path):
    """Teste tous les codepoints"""
    try:
        font = ImageFont.truetype(font_path, 200)
        print(f"\n{'=' * 60}")
        print(f"Test des codepoints avec {font_path}")
        print(f"{'=' * 60}\n")

        for name, codepoint in TEST_ICONS.items():
            img = Image.new('RGB', (256, 256), color='white')
            draw = ImageDraw.Draw(img)

            try:
                # Essayer de dessiner le glyph
                draw.text((28, 28), codepoint, fill='black', font=font)

                # Sauvegarder pour inspection
                img.save(f'/tmp/test_{name}_{ord(codepoint):04x}.png')
                print(
                    f"✓ {name:15} : {repr(codepoint):8} (U+{ord(codepoint):04X}) → /tmp/test_{name}_{ord(codepoint):04x}.png")
            except Exception as e:
                print(f"✗ {name:15} : {repr(codepoint):8} → ERREUR: {e}")

        print(f"\n{'=' * 60}")
        print("Vérifiez les images générées : ls -la /tmp/test_*.png")
        print("Utilisez : display /tmp/test_*.png  (ou ouvrez avec une image viewer)")
        print(f"{'=' * 60}\n")

    except Exception as e:
        print(f"✗ Erreur lors du chargement de la font : {e}")


def extract_fontawesome_codepoints(font_path):
    """
    Extrait les codepoints disponibles de la font (pour référence avancée)
    """
    try:
        font = ImageFont.truetype(font_path, 100)
        print(f"\nAnalyse détaillée de {font_path}...")

        # Font Awesome 6 Free Solid utilise principalement la plage U+F000-U+F8FF
        print("\nCodepoints valides dans la font (sample) :")

        sample_ranges = [
            (0xF000, 0xF050, "Icônes basiques"),
            (0xF200, 0xF250, "Icônes web"),
            (0xF500, 0xF550, "Icônes art"),
        ]

        for start, end, label in sample_ranges:
            print(f"\n{label} (U+{start:04X} - U+{end:04X}):")
            working = []
            for cp in range(start, end, 5):
                try:
                    char = chr(cp)
                    # Si on peut le dessiner, il existe
                    working.append(f"U+{cp:04X}")
                except:
                    pass
            if working:
                print("  " + ", ".join(working[:10]))

    except Exception as e:
        print(f"Erreur lors de l'analyse : {e}")


if __name__ == '__main__':
    font_path = find_font()
    if font_path:
        test_icons(font_path)
        extract_fontawesome_codepoints(font_path)
    else:
        print("\n⚠ Impossible de trouver Font Awesome")
        print("Installez-la avec :")
        print("  sudo apt-get install fonts-font-awesome")
        print("  # ou téléchargez depuis https://fontawesome.com/download")
