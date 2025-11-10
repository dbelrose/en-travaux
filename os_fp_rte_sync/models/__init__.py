# -*- coding: utf-8 -*-
# Nettoyé - on garde seulement ce qui est nécessaire
from . import hooks
from . import res_partner
from . import settings
from . import rte_sync
from . import res_partner_id_number
from . import res_partner_image_generator
from . import res_partner_image_cache_wizard  # Utile mais pas critique pour la sync
from . import partner_image_wizard

# Supprimé :
# - generate_placeholder_image (pas utilisé)
# - images_config (remplacé par ResPartnerImageGenerator._get_fontawesome_mapping)
# - partner_image_auto_assignment (remplacé par ResPartnerImageGenerator)