# -*- coding: utf-8 -*-
# Nettoyé - on garde seulement ce qui est nécessaire

from . import res_partner
from . import settings
from . import rte_sync
from . import res_partner_image_generator
from . import res_partner_image_cache_wizard  # Utile mais pas critique pour la sync

# Supprimé :
# - generate_placeholder_image (pas utilisé)
# - images_config (remplacé par ResPartnerImageGenerator._get_fontawesome_mapping)
# - partner_image_wizard (redondant)
# - partner_image_auto_assignment (remplacé par ResPartnerImageGenerator)