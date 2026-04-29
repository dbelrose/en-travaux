# os_contact_encrypted — Chiffrement RSA des contacts Odoo 17

## Présentation

Module générique de chiffrement asymétrique (RSA-2048) des champs sensibles
des contacts (`res.partner`). Conçu pour des professionnels de santé (orthophonistes,
médecins, etc.) qui ont besoin que les données d'identification de leurs patients
ne soient lisibles que par eux-mêmes.

---

## Architecture de sécurité

```
┌─────────────────────────────────────────────────────────┐
│  Utilisateur (orthophoniste)                            │
│  ┌───────────────┐    ┌──────────────────────────────┐  │
│  │ Clé publique  │    │ Clé privée                   │  │
│  │ (stockée BDD) │    │ chiffrée avec MDP Odoo       │  │
│  │ en clair      │    │ (PKCS8 / AES-256-CBC)        │  │
│  └───────┬───────┘    └──────────────┬───────────────┘  │
│          │ chiffre                   │ déchiffre         │
│          ▼                           ▼ (avec MDP)        │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Champs chiffrés en BDD (base64 RSA-OAEP/SHA-256)  │  │
│  │ phone_os_enc, mobile_os_enc, email_os_enc…        │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Récupération d'urgence (admin uniquement)              │
│  ┌───────────────────────────────────────────────────┐  │
│  │ emergency_key_enc = clé_privée_user               │  │
│  │ re-chiffrée avec clé publique ADMIN (RSA-4096)    │  │
│  └───────────────────────────────────────────────────┘  │
│  Clé privée admin conservée hors-ligne (fichier PEM)    │
│  Chaque accès d'urgence journalisé dans le chatter      │
└─────────────────────────────────────────────────────────┘
```

---

## Installation

### 1. Dépendance Python
```bash
pip install cryptography
```

### 2. Copie du module
```bash
cp -r os_contact_encrypted /path/to/odoo/addons/
```

### 3. Mise à jour de la liste des modules
```
Paramètres → Activer le mode développeur → Mettre à jour la liste des applications
```

### 4. Installation
Rechercher `OS Contact Encrypted` et cliquer sur **Installer**.

---

## Configuration

### Étape 1 — Configurer les champs à chiffrer (Admin)

`Menu Chiffrement contacts → Champs à chiffrer`

Ajouter les champs souhaités parmi :
- Téléphone (`phone`)
- Mobile (`mobile`)
- Email (`email`)
- Nom complet (`name`)
- Adresse (`street`)
- N° fiscal / Sécurité sociale (`vat`)
- Site web (`website`)
- Notes internes (`comment`)

### Étape 2 — Configurer la récupération d'urgence (Admin)

`Menu Chiffrement contacts → Récupération d'urgence → Mode : Configuration initiale`

1. Choisir un mot de passe fort pour la clé privée admin
2. Cliquer **Générer la clé de récupération**
3. **Télécharger le fichier PEM** et le conserver hors-ligne (coffre-fort, gestionnaire de secrets)

⚠️ Sans ce fichier, aucune récupération d'urgence ne sera possible.

### Étape 3 — Initialisation par chaque utilisateur

À la première connexion, chaque utilisateur voit une notification :
> 🔐 Chiffrement patient non configuré. [Initialiser maintenant]

Ou via `Préférences utilisateur → bouton "Initialiser maintenant"`.

Le wizard demande le mot de passe Odoo de l'utilisateur pour :
1. Générer sa paire RSA-2048
2. Chiffrer sa clé privée avec ce mot de passe
3. Créer automatiquement sa clé d'urgence (si l'admin a configuré la clé de récupération)

---

## Utilisation quotidienne

### Saisie d'un contact (données chiffrées)
Les champs activés pour le chiffrement sont saisis normalement dans le formulaire contact.
À l'enregistrement, les valeurs sont automatiquement chiffrées avec la clé publique
de l'utilisateur connecté.

### Consultation des données chiffrées
Sur la fiche contact, un bandeau apparaît :
> 🔒 Ce contact contient des données chiffrées. Saisissez votre mot de passe pour les déchiffrer.

L'utilisateur saisit son mot de passe Odoo → les champs s'affichent en clair.

### Vue pour les autres utilisateurs
Les champs chiffrés affichent `████████` pour tout utilisateur autre que le propriétaire.

---

## Changement de mot de passe

⚠️ **Ne pas utiliser le changement de mot de passe natif d'Odoo** si des données sont chiffrées.

Utiliser : `Préférences utilisateur → Changer le mot de passe`

Ce wizard re-chiffre automatiquement la clé privée RSA avec le nouveau mot de passe
avant de changer le mot de passe Odoo.

---

## Récupération d'urgence

`Menu Chiffrement contacts → Récupération d'urgence → Mode : Accès d'urgence`

1. Sélectionner l'utilisateur concerné
2. Coller le contenu du fichier `emergency_admin_private.pem`
3. Saisir le mot de passe de cette clé
4. Définir un nouveau mot de passe pour l'utilisateur récupéré
5. Cliquer **Récupérer l'accès**

L'accès est automatiquement journalisé dans le profil de l'utilisateur (date, admin, heure).

---

## Sécurité — points clés

| Aspect | Détail |
|---|---|
| Algorithme | RSA-2048 (utilisateurs) / RSA-4096 (admin urgence) |
| Chiffrement des données | OAEP + SHA-256 |
| Protection clé privée | PKCS8 + AES-256-CBC (BestAvailable) |
| Clé d'urgence | Double couche : MDP user + clé publique admin |
| Stockage mot de passe | Jamais persisté (`store=False`) |
| Audit | Chaque accès d'urgence journalisé |
| Admin Odoo | Voit `phone_os_enc` (base64 illisible) — jamais le clair |

---

## Limites connues

- La taille maximale chiffrable par RSA-2048/OAEP est ~190 octets.
  Pour des champs longs (notes, adresses longues), envisager un chiffrement hybride AES+RSA.
- Le déchiffrement nécessite une saisie du mot de passe par session de formulaire
  (pas de session persistante pour des raisons de sécurité).
- Le champ `name` d'un contact chiffré peut perturber les recherches Odoo natives.

---

## Auteur

OS — Odoo 17.0
