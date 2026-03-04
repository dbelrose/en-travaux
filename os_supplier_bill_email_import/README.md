# supplier_bill_email_import — Module Odoo 17 — v2

## Présentation

Ce module comptabilise automatiquement les factures fournisseurs reçues par
email, avec ventilation analytique par produit / logement.

**Nouveautés v2 :**
- Exploitation de la **pièce jointe PDF** de l'email (extraction de texte)
- Extraction des **lignes de détail** du PDF (une ligne de facture par ligne)
- **Validation automatique** de la facture après création
- **Enregistrement et rapprochement automatique** d'un paiement fournisseur

Il supporte deux modes d'import :

| Mode | Description |
|------|-------------|
| **Automatique** ✨ | Le module `fetchmail` relève le serveur IMAP/POP3, les emails sont routés vers `message_new()` et les factures sont créées sans intervention |
| **Manuel** | Import de fichiers `.eml` via un assistant (fallback ou rattrapage) |

---

## Architecture du flux automatique (v2)

```
┌──────────────────────────────────────────────────────────────┐
│  Serveur mail fournisseur (EDT, OPT, Syndic…)               │
│  → Email de facture + PDF joint                             │
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
│  ② Extraction PDF joint (si use_pdf_attachment)             │
│  ③ Sélection du texte source (corps / PDF / mixte)          │
│  ④ Extraction regex : n° facture, date, montant, contrat    │
│  ⑤ Extraction lignes de détail PDF (si pdf_extract_lines)   │
│  ⑥ product.attribute.value → product.template               │
│  ⑦ account.analytic.account (par nom du produit)            │
│  ⑧ Création account.move (facture brouillon / postée)       │
│  ⑨ Création account.payment + rapprochement (si configuré)  │
└──────────────────────────────────────────────────────────────┘
```

---

## Installation

1. Copiez `supplier_bill_email_import/` dans votre dossier `addons`.
2. **(Recommandé)** Installez le moteur PDF : `pip install pdfminer.six`
3. **Paramètres > Activer le mode développeur > Mettre à jour la liste**.
4. Installez **"Import Factures Fournisseurs par Email"**.

---

## Moteurs PDF supportés

| Moteur | Installation | Précision |
|--------|-------------|-----------|
| `pdfminer.six` ⭐ | `pip install pdfminer.six` | Maximale |
| `pypdf` | `pip install pypdf` | Bonne |
| `PyPDF2` | `pip install PyPDF2` | Correcte |

Le module détecte automatiquement le moteur disponible au démarrage (priorité dans l'ordre ci-dessus). Un avertissement est loggé si aucun n'est installé.

---

## Configuration en 7 étapes

### Étapes 1 à 3 — (inchangées)

Voir version précédente : attributs produit, comptes analytiques, règle de parsing EDT.

### Étape 4 — Pièce jointe PDF (onglet "Pièce jointe PDF")

| Champ | Description |
|-------|-------------|
| **Exploiter la pièce jointe PDF** | Active l'extraction du texte PDF |
| **Préférer le PDF au corps de l'email** | Utilise le PDF comme source principale (recommandé) |
| **Extraire les lignes de détail** | Crée une ligne de facture par ligne détectée dans le PDF |
| **Regex ligne de détail** | Pattern avec 2 groupes : `groupe1` = libellé, `groupe2` = montant |
| **Compte pour les lignes PDF** | Compte de charge des lignes PDF (défaut : compte principal) |
| **Taxes sur les lignes PDF** | Taxes à appliquer (laisser vide si montants TTC) |

**Exemple de regex lignes EDT :**
```
^(.+?)\s{2,}([\d\s\u202f,\.]+)\s*(?:FCFP|XPF)\s*$
```

### Étape 5 — Paiement automatique (onglet "Paiement automatique")

| Champ | Description |
|-------|-------------|
| **Valider automatiquement la facture** | Passe la facture de Brouillon à Validé |
| **Enregistrer le paiement automatiquement** | Crée et rapproche un paiement sortant |
| **Journal de paiement** | Journal bancaire ou caisse |
| **Date du paiement** | Date de la facture ou date du jour |
| **Mémo paiement** | Texte avec variables `{invoice_number}`, `{contract_number}`, `{partner}` |

> ⚠ **À utiliser avec précaution** — réservez le paiement automatique aux fournisseurs
> de confiance à montants fixes (abonnements, contrats cadre).

### Étapes 6 & 7 — (inchangées)

Serveur de messagerie entrant et transfert automatique Gmail/Outlook.

---

## Comportement des lignes PDF

### Avec `pdf_extract_lines` activé

Si la regex de ligne trouve des correspondances dans le PDF :
- Une ligne de facture est créée par correspondance
- Le compte utilisé est `pdf_line_account_id` (ou `account_id` en fallback)
- Les taxes `pdf_line_tax_ids` sont appliquées si configurées

Si la regex ne trouve **aucune** correspondance :
- Fallback automatique vers une ligne unique avec le montant total parsé

### Sans `pdf_extract_lines`

Comportement identique à la v1 : une seule ligne avec le montant total.

---

## Flux du paiement automatique

```
Facture créée (brouillon)
    │
    ▼ [si auto_post_bill]
Facture postée (état Validé)
    │
    ▼ [si auto_register_payment]
account.payment créé
    │  payment_type = 'outbound'
    │  partner_type = 'supplier'
    │  amount = move.amount_residual
    │
    ▼ payment.action_post()
Paiement validé
    │
    ▼ reconcile()
Facture rapprochée (état Payé)
```

---

## Suivi et monitoring

La vue liste des règles affiche en temps réel :
- Date du dernier import
- Résultat (✔ créé / ⚠ doublon / ❌ erreur + [validée] + [payée & rapprochée])
- Nombre de factures créées
- Indicateurs PDF et paiement automatique (colonnes optionnelles)

Le wizard EML affiche par fichier traité :
- Source de parsing (corps / PDF / mixte)
- Nombre de lignes PDF extraites
- Indicateur de paiement enregistré

---

## Déduplication

Le module vérifie l'existence d'une facture avec le même numéro (`ref`) avant
de créer un doublon. Un email déjà traité est ignoré silencieusement.

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

## Licence

LGPL-3
