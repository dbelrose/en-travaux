# supplier_bill_email_import — Module Odoo 17 — v3

## Présentation

Ce module comptabilise automatiquement les **factures fournisseurs** et les
**alertes bancaires** reçues par email.

| Type d'email | Résultat dans Odoo |
|---|---|
| Facture fournisseur (EDT, OPT, Syndic…) | `account.move` (facture fournisseur) |
| Alerte bancaire (Marara Paiement, OPT…) | `account.bank.statement.line` (relevé) |

**Nouveautés v3 :**
- Nouveau modèle **`bank.alert.email.rule`** pour les alertes bancaires
- Extraction multi-opérations (plusieurs débits/crédits par email)
- Création des lignes de relevé bancaire dans le journal configuré
- **Rapprochement automatique** contre les pièces ouvertes (montant exact)
- Déduplication : un doublon d'email n'est jamais retraité
- Le wizard unifié détecte automatiquement le type de règle

---

## Architecture du flux (v3)

```
Email entrant (fetchmail ou import .eml)
        │
        ▼
  Détection du type de règle
        │
  ┌─────┴──────────────────────────────┐
  │                                    │
  ▼                                    ▼
supplier.email.rule             bank.alert.email.rule
(facture fournisseur)           (alerte bancaire)
        │                               │
  _parse_email_body()         _parse_transactions()
  create_vendor_bill()         [regex multi-occurrence]
        │                               │
  account.move (brouillon)    account.bank.statement.line
  [+ validation + paiement]   [+ rapprochement auto optionnel]
```

---

## Installation

1. Copiez `supplier_bill_email_import/` dans votre dossier `addons`.
2. **(Recommandé)** `pip install pdfminer.six`
3. **Paramètres > Activer le mode développeur > Mettre à jour la liste**.
4. Installez **"Import Factures & Alertes Bancaires par Email"**.

---

## Configuration — Règle d'alerte bancaire

### Étape 1 — Créer la règle

`Comptabilité > Configuration > Règles import — Alertes bancaires`

| Champ | Description |
|-------|-------------|
| **Nom** | Ex : Alerte Marara Paiement XPF |
| **Pattern expéditeur** | `no-reply@mararapaiement\.pf` |
| **Pattern sujet** | `Alerte sur votre compte` (optionnel) |
| **Journal bancaire** | Votre journal de banque XPF |
| **Code devise** | `XPF` |

### Étape 2 — Vérification du n° de compte (optionnel)

Si vous avez plusieurs comptes chez la même banque, configurez :

| Champ | Exemple |
|-------|---------|
| **Regex n° de compte** | `compte\s+\w+\s+\(([\w\-]+)\s+XPF\)` |
| **N° de compte attendu** | `00001-2510504C068-36` |

### Étape 3 — Regex de transaction

La regex est appliquée en **finditer** sur le corps texte.
Elle doit capturer **4 groupes** : date, sens, montant, libellé.

**Exemple pour Marara Paiement :**

Email reçu :
```
Le 03/03/2026, débit de 2 110 XPF PRELEVEMENT,
Le 03/03/2026, débit de 2 472 XPF PRELEVEMENT,
Le 03/03/2026, débit de 3 354 XPF PRELEVEMENT,
Le 03/03/2026, débit de 24 000 XPF VIREMENT WEB.
```

Regex :
```
Le\s+(\d{2}/\d{2}/\d{4}),\s+(d[ée]bit|cr[ée]dit)\s+de\s+([\d\s\u00a0\u202f,\.]+?)\s*(?:XPF|FCFP)\s+([A-Z][A-Z\s]+?)(?=\s*[,<\n]|$)
```

Groupes extraits :
- Groupe 1 → `03/03/2026`
- Groupe 2 → `débit`
- Groupe 3 → `2 110`
- Groupe 4 → `PRELEVEMENT`

### Étape 4 — Rapprochement automatique (optionnel)

| Champ | Description |
|-------|-------------|
| **Rapprochement automatique** | Active la tentative de rapprochement |
| **Fournisseur pour le rapprochement** | Limite la recherche à un tiers |
| **Filtre libellé (regex)** | Ex : `PRELEVEMENT` — ne rapproche que les prélèvements |

**Logique de rapprochement :**
1. Pour chaque débit, Odoo cherche une facture fournisseur ouverte dont `amount_residual` = montant exact
2. Si une unique correspondance est trouvée → rapprochement automatique ✔
3. Si 0 ou plusieurs correspondances → ligne en attente de traitement manuel

> ⚠ Le rapprochement automatique ne fonctionne qu'avec des montants **exacts et uniques**.
> Un prélèvement de 3 354 XPF rapproche automatiquement la facture EDT de 3 354 XPF
> si elle est la seule ouverte à ce montant.

### Étape 5 — Transfert automatique Gmail/Outlook

Configurez une règle de transfert dans votre messagerie :
- **Expéditeur** : `no-reply@mararapaiement.pf`
- **Destination** : `alias-banque@votredomaine.odoo.com`

---

## Flux complet pour une alerte Marara Paiement

```
Email d'alerte Marara Paiement
    │  4 opérations débitrices
    ▼
bank.alert.email.rule._parse_transactions()
    │  → [{date, amount: -2110, label: 'PRELEVEMENT'},
    │     {date, amount: -2472, label: 'PRELEVEMENT'},
    │     {date, amount: -3354, label: 'PRELEVEMENT'},
    │     {date, amount: -24000, label: 'VIREMENT WEB'}]
    ▼
Pour chaque transaction :
    account.bank.statement.line.create()
        │  journal = journal bancaire XPF
        │  date = 03/03/2026
        │  amount = -3354 (débit = négatif)
        │  payment_ref = 'PRELEVEMENT'
        ▼
    [si auto_reconcile et filtre 'PRELEVEMENT']
        → recherche account.move.line ouvert
          avec amount_residual = 3354
        → si trouvé unique :
            reconcile() ← facture EDT 3354 XPF
        → sinon :
            en attente (dashboard bancaire Odoo)
```

---

## Déduplication

Chaque ligne de relevé créée porte en narration une **référence de dédup** :
```
Règle 'Alerte Marara Paiement XPF' | 1|20260303|-3354.00|PRELEVEMENT
```
Un email importé une seconde fois ne crée aucun doublon.

---

## Résultats dans le wizard

Après import d'un fichier `.eml` d'alerte bancaire, le wizard affiche :

| Colonne | Description |
|---------|-------------|
| **Type** | `Alerte bancaire` |
| **Opérations créées** | Nombre de lignes de relevé nouvellement créées |
| **Doublons banque** | Opérations déjà présentes (ignorées) |
| **Rapprochées** | Lignes rapprochées automatiquement |
| **Règle bancaire** | Règle utilisée |

---

## Regex prédéfinies

### Marara Paiement (Polynésie française)

| Donnée | Regex |
|--------|-------|
| N° compte | `compte\s+\w+\s+\(([\w\-]+)\s+XPF\)` |
| Transaction | `Le\s+(\d{2}/\d{2}/\d{4}),\s+(d[ée]bit\|cr[ée]dit)\s+de\s+([\d\s\u00a0\u202f,\.]+?)\s*(?:XPF\|FCFP)\s+([A-Z][A-Z\s]+?)(?=\s*[,<\n]\|$)` |

### EDT (factures fournisseurs — inchangé)

| Donnée | Regex |
|--------|-------|
| N° facture | `facture\s+(\S+)\s+du` |
| Date | `du\s+(\d{2}/\d{2}/\d{4})` |
| Montant | `montant de ([\d\s\u00a0\u202f,\.]+?)\s*(?:FCFP\|XPF)` |
| N° contrat | `contrat\s+([\w\-]+)` |

---

## Licence

LGPL-3
