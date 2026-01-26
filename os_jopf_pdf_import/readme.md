# JOPF PDF Import - Module Odoo 17

Module d'importation automatique des associations et membres depuis les PDF du Journal Officiel de Polynésie Française.

## 📋 Prérequis

### Dépendances système

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-fra
```

#### Docker
Ajoutez dans votre `Dockerfile` :
```dockerfile
FROM odoo:17.0

USER root
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*
USER odoo
```

Ou installez directement dans le conteneur :
```bash
docker exec -u root <nom_conteneur> bash -c "apt-get update && apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-fra"
docker restart <nom_conteneur>
```

### Dépendances Python
```bash
pip install pdf2image pytesseract Pillow
```

## 📁 Structure du module

```
os_jopf_pdf_import/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── jopf_import.py
│   ├── jopf_import_line.py
│   └── res_partner.py
├── views/
│   ├── jopf_import_views.xml
│   ├── res_partner_views.xml
│   └── jopf_menu.xml
├── security/
│   ├── jopf_security.xml
│   └── ir.model.access.csv
└── data/
    ├── ir_sequence.xml
    └── partner_categories.xml
```

## 🚀 Installation

1. Copiez le dossier `os_jopf_pdf_import` dans votre répertoire `addons`
2. Installez les dépendances système et Python (voir ci-dessus)
3. Redémarrez Odoo
4. Mettez à jour la liste des applications
5. Installez le module "JOPF PDF Import"

## 💡 Utilisation

1. Allez dans le menu **JOPF > Imports**
2. Cliquez sur **Créer**
3. Uploadez votre PDF scanné du JOPF
4. Cliquez sur **Importer**
5. Consultez les résultats dans les onglets :
   - **Contenu extrait** : texte OCR
   - **Partenaires** : associations et personnes créées
   - **Détails** : lignes d'import détaillées
   - **Log** : historique détaillé de l'import

## ✨ Fonctionnalités

- ✅ **OCR automatique** avec Tesseract
- ✅ **Parsing intelligent** des structures JOPF
- ✅ **Détection des rôles** (Président, Secrétaire, Trésorier, etc.)
- ✅ **Gestion des doublons** automatique
- ✅ **Logs HTML colorés** et détaillés
- ✅ **Traçabilité complète** avec chatter
- ✅ **Statistiques temps réel** (nb associations, personnes, erreurs)
- ✅ **Séquençage automatique** des imports (JOPF00001, JOPF00002...)
- ✅ **Catégorisation** automatique des partenaires
- ✅ **Configuration OCR** (langue, résolution DPI)

## 🔧 Configuration

### Paramètres OCR

Dans le formulaire d'import, vous pouvez configurer :
- **Langue OCR** : Français (par défaut), Anglais, ou les deux
- **DPI** : Résolution de 300 DPI par défaut (augmentez pour améliorer la qualité)

### Groupes de sécurité

- **JOPF Manager** : Accès complet (lecture, écriture, création, suppression)
- **JOPF User** : Lecture et création uniquement

## 🐛 Dépannage

### Erreur "poppler not installed"
```bash
# Installation dans Docker
docker exec -u root <conteneur> bash -c "apt-get update && apt-get install -y poppler-utils"
docker restart <conteneur>
```

### Erreur "tesseract not found"
```bash
# Installation dans Docker
docker exec -u root <conteneur> bash -c "apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-fra"
docker restart <conteneur>
```

### OCR de mauvaise qualité
- Augmentez le DPI (passez à 400 ou 600)
- Vérifiez la qualité du PDF source
- Assurez-vous que le pack de langue français est installé

## 📊 Données créées

Le module crée automatiquement :
- **Associations** (res.partner avec `is_company=True`)
- **Personnes** (res.partner avec `is_company=False`)
- **Relations** entre personnes et associations (champ `parent_id`)
- **Fonctions** (champ `function` contenant le rôle)
- **Catégories** : "Association JOPF" et "Membre JOPF"

## 🔄 Mise à jour

Si une association ou personne existe déjà :
- L'association est mise à jour avec la nouvelle date de bureau
- La personne est rattachée à la nouvelle association
- La fonction est mise à jour avec le nouveau rôle

## 📝 Licence

LGPL-3

## 👥 Support

Pour toute question ou problème, contactez votre équipe de support Odoo.
