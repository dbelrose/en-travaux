# OS Auxiliaire Médical (Odoo 17)

Module Odoo 17 pour la gestion des feuilles de soins auxiliaires médicaux
et des bordereaux de facturation CPS (Caisse de Prévoyance Sociale) de Polynésie française.

---

## Installation

1. Copier le dossier `os_auxiliaire_medical/` dans votre répertoire `addons/` Odoo
2. Redémarrer le serveur Odoo
3. Activer le mode développeur (Paramètres → Mode développeur)
4. Mettre à jour la liste des modules (Paramètres → Apps → Mettre à jour la liste)
5. Rechercher "CPS" et cliquer **Installer**

### Dépendances Python supplémentaires (pour l'export Excel)
```bash
pip install openpyxl
```

---

## Structure du module

```
os_auxiliaire_medical/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── praticien.py        # Auxiliaire médical (code CPS, profession...)
│   ├── patient.py          # Patient / bénéficiaire (DN, date naissance...)
│   ├── feuille_soins.py    # Feuille FSA25 + lignes d'actes
│   └── bordereau.py        # Bordereau mensuel de facturation
├── wizards/
│   ├── wizard_bordereau.py # Assistant de génération de bordereau
│   └── wizard_bordereau_views.xml
├── views/
│   ├── praticien_views.xml
│   ├── patient_views.xml
│   ├── feuille_soins_views.xml
│   ├── bordereau_views.xml
│   └── menu_views.xml
├── report/
│   ├── report_bordereau.xml    # Template QWeb PDF bordereau
│   └── report_feuille_soins.xml # Template QWeb PDF feuille de soins
├── controllers/
│   └── main.py             # Export Excel via route HTTP
├── security/
│   └── ir.model.access.csv
└── data/
    └── data.xml            # Séquences automatiques
```

---

## Modèles de données

### `cps.praticien`
| Champ | Description |
|---|---|
| `name` | Nom complet |
| `code_auxiliaire` | Code CPS obligatoire (ex: O233) |
| `profession` | kiné / ortho / orthoptiste / pédicure... |
| `tel`, `bp`, `email` | Coordonnées |

### `cps.patient`
| Champ | Description |
|---|---|
| `nom`, `prenom` | Identité |
| `dn` | Numéro de matricule CPS |
| `date_naissance` | Date de naissance |
| `est_assure` | Si False → renseigner l'assuré séparé |

### `cps.feuille.soins` (FSA25)
| Champ | Description |
|---|---|
| `name` | N° facture (séquence auto FSA-AAAA-XXXXX) |
| `fsa_numero` | N° imprimé sur le formulaire papier |
| `state` | draft → confirmed → submitted → paid |
| `patient_id` | Bénéficiaire |
| `praticien_id` | Auxiliaire médical |
| `date_prescription` | Date de la prescription |
| `acte_ids` | Lignes d'actes (lettre clé, coefficient, montant) |
| `taux_remboursement` | % CPS (défaut 70%) |
| `montant_total` | Calculé depuis les actes |
| `montant_tiers_payant` | Part CPS |
| `montant_patient` | Part patient |
| `bordereau_id` | Bordereau associé |
| `photo_feuille` | Scan/photo du document papier |

### `cps.feuille.soins.acte`
| Champ | Description |
|---|---|
| `date_acte` | Date de la séance |
| `lettre_cle` | AMO, AMK, AMS, AMI... |
| `coefficient` | Coefficient tarifaire |
| `ifd`, `ik` | Frais de déplacement |
| `dimanche_ferie`, `nuit` | Majorations |
| `montant` | Montant calculé |

### `cps.bordereau`
| Champ | Description |
|---|---|
| `name` | N° bordereau (séquence auto BD-AAAAMM-XXXX) |
| `praticien_id` | Praticien |
| `mois` | Libellé mois (ex: Février 2026) |
| `state` | draft → validated → submitted → closed |
| `feuille_ids` | Feuilles rattachées |
| `total_cps`, `total_patient`, `total_general` | Totaux calculés |

---

## Workflow

```
Créer patient → Créer feuille de soins → Saisir actes
    → Confirmer feuille → Assistant "Générer bordereau"
    → Valider bordereau → Imprimer PDF / Exporter Excel
    → Transmettre CPS → Clôturer
```

### Raccourci : assistant de génération de bordereau
Menu **CPS → Générer un bordereau** :
- Sélectionner praticien + mois + année
- Toutes les feuilles confirmées sans bordereau sont auto-chargées
- Cliquer "Générer" → le bordereau est créé et les feuilles rattachées

---

## Exports disponibles

| Format | Déclencheur |
|---|---|
| **PDF bordereau** | Bouton "Imprimer PDF" sur le bordereau (QWeb) |
| **Excel bordereau** | Bouton "Exporter Excel" → `/cps/bordereau/{id}/xlsx` |
| **PDF feuille de soins** | Bouton "Imprimer" sur la feuille (QWeb) |

---

## Tarifs indicatifs (modifiables dans `feuille_soins.py`)

| Lettre clé | Valeur unitaire |
|---|---|
| AMO | 433 F CFP |
| AMK | 433 F CFP |
| AMS | 283 F CFP |
| AMI | 366 F CFP |

---

## Compatibilité

- **Odoo** : 17.0
- **Python** : 3.10+
- **Dépendances Odoo** : `base`, `mail`, `account`
