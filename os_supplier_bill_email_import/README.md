# supplier_bill_email_import — Module Odoo 17

## Présentation

Ce module comptabilise automatiquement les factures fournisseurs reçues par
email, avec ventilation analytique par produit / logement.

Il supporte deux modes d'import :

| Mode | Description |
|------|-------------|
| **Automatique** ✨ | Le module `fetchmail` relève le serveur IMAP/POP3, les emails sont routés vers `message_new()` et les factures sont créées sans intervention |
| **Manuel** | Import de fichiers `.eml` via un assistant (fallback ou rattrapage) |

---

## Architecture du flux automatique

```
┌──────────────────────────────────────────────────────────────┐
│  Serveur mail fournisseur (EDT, OPT, Syndic…)               │
│  → Email de facture envoyé à votre Gmail/Outlook            │
└──────────────────────┬───────────────────────────────────────┘
                       │  Règle de transfert automatique
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Alias Odoo   edt-factures@votredomaine.odoo.com            │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  fetchmail.server  (relève toutes les X minutes)            │
│  → message_route() → mail.alias → message_new()            │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  supplier.email.rule.message_new()                          │
│  ① Vérification expéditeur (sender_email_pattern)           │
│  ② Extraction regex : n° facture, date, montant, contrat    │
│  ③ product.attribute.value → product.template               │
│  ④ account.analytic.account (par nom du produit)            │
│  ⑤ Création account.move (facture brouillon)                │
└──────────────────────────────────────────────────────────────┘
```

---

## Installation

1. Copiez `supplier_bill_email_import/` dans votre dossier `addons`.
2. **Paramètres > Activer le mode développeur > Mettre à jour la liste**.
3. Installez **"Import Factures Fournisseurs par Email"**.

---

## Configuration en 5 étapes

### Étape 1 — Attributs produit (logements)

Pour chaque logement (product.template), ajoutez l'attribut :
- **Nom** : `N° de contrat EDT`
- **Valeur** : le numéro exact du contrat (`01-2022-000194`, etc.)

### Étape 2 — Comptes analytiques

Dans `Comptabilité > Configuration > Comptes analytiques`, créez un compte
par logement avec le **même nom** que le produit correspondant.

### Étape 3 — Règle de parsing EDT

`Comptabilité > Configuration > Règles import email fournisseurs`
→ Ouvrez la règle *"EDT – Électricité"* et complétez :

| Champ | Valeur |
|-------|--------|
| Fournisseur | Fiche partenaire EDT |
| Compte de charge | `606100 – Électricité` |
| Journal achats | Journal Achats |
| Plan analytique | Votre plan analytique |

L'**alias email** est créé automatiquement à la sauvegarde.

### Étape 4 — Serveur de messagerie entrant

`Comptabilité > Configuration > Serveurs de messagerie entrants`
→ Créez un serveur IMAP pointant vers une boîte dédiée
  (ex : `factures-auto@votredomaine.com`) :

| Paramètre | Valeur |
|-----------|--------|
| Serveur | `imap.gmail.com` |
| Port | `993` |
| SSL | Oui |
| Login / Mot de passe | Identifiants de la boîte dédiée |
| Intervalle | `5` minutes |
| Action | *Créer un nouvel enregistrement* sur le modèle `supplier.email.rule` |

### Étape 5 — Transfert automatique dans votre messagerie principale

Dans Gmail / Outlook, créez un filtre :
- **De** : `efacture@hoani.edt.engie.pf`
- **Action** : Transférer automatiquement vers l'alias Odoo
  (`edt-factures@votredomaine.odoo.com` ou la boîte IMAP dédiée)

**C'est tout.** À la prochaine facture EDT, Odoo créera automatiquement
la facture fournisseur avec ventilation analytique.

---

## Suivi et monitoring

La vue liste des règles affiche en temps réel :
- Date du dernier import
- Résultat (✔ créé / ⚠ doublon / ❌ erreur)
- Nombre de factures créées

Le chatter de chaque règle conserve l'historique des emails reçus.

---

## Ajouter un nouveau fournisseur

1. Créer une nouvelle règle (OPT Téléphonie, Syndic…)
2. Adapter les regex au format de leurs emails
3. Créer l'attribut produit correspondant
4. Configurer le transfert email vers le nouvel alias

**Aucune modification de code.**

---

## Regex EDT (préconfigurées)

Format email :
```
Votre facture F202602042089 du 10/02/2026 d'un montant de 3 354 FCFP
pour le contrat 01-2022-000194 est disponible…
```

| Donnée | Regex |
|--------|-------|
| N° facture | `facture\s+(\S+)\s+du` |
| Date | `du\s+(\d{2}/\d{2}/\d{4})` |
| Montant | `montant de ([\d\s\u00a0\u202f,\.]+?)\s*(?:FCFP\|XPF)` |
| N° contrat | `contrat\s+([\w\-]+)` |

---

## Déduplication

Le module vérifie l'existence d'une facture avec le même numéro (`ref`)
avant de créer un doublon. Un email déjà traité sera ignoré silencieusement.

---

## Licence

LGPL-3
