# os_helcim_payment_provider

Module Odoo 17 d'intégration du fournisseur de paiement **Helcim** via **HelcimPay.js**.

Développé pour le marché polynésien avec support natif du **Franc CFP (XPF)**.

---

## Fonctionnalités

- ✅ Paiement en ligne via modal HelcimPay.js (iframe sécurisé)
- ✅ Conformité PCI-DSS : les données de carte ne transitent jamais par vos serveurs
- ✅ Support devise XPF (Franc CFP) et toutes devises ISO 4217
- ✅ Mode test et mode production
- ✅ Remboursements partiels et totaux (reverse + refund)
- ✅ Validation HMAC SHA-256 des réponses de transaction
- ✅ Webhook Helcim pour notifications asynchrones
- ✅ Interface d'administration en français
- ✅ Test de connexion API depuis l'interface Odoo

---

## Prérequis

- Odoo 17.0 (Community ou Enterprise)
- Un compte marchand Helcim actif : https://www.helcim.com
- Un jeton API Helcim (généré depuis Compte Helcim > Paramètres > API)

---

## Installation

1. Copier le dossier `os_helcim_payment_provider` dans votre répertoire d'addons Odoo
2. Mettre à jour la liste des modules : `Paramètres > Activer le mode développeur > Mettre à jour la liste des apps`
3. Rechercher et installer **"Payment Provider: Helcim"**

---

## Configuration

### 1. Obtenir votre jeton API Helcim

1. Connectez-vous à votre compte Helcim : https://app.helcim.com
2. Allez dans **Paramètres** > **API & Développeurs** > **Accès API**
3. Créez une nouvelle configuration d'accès avec les permissions :
   - `helcim-pay` : Initialize HelcimPay.js
   - `card-transactions` : Read, Refund, Reverse
4. Copiez le jeton API généré

### 2. Configurer le fournisseur dans Odoo

1. Allez dans **Comptabilité** > **Configuration** > **Fournisseurs de paiement**
   (ou **Site Web** > **Configuration** > **Fournisseurs de paiement**)
2. Cliquez sur **Helcim**
3. Dans l'onglet **Identifiants** :
   - **Jeton API Helcim** : collez votre jeton API
   - **ID Terminal** : optionnel, laissez vide pour le terminal par défaut
   - **Code devise ISO** : `XPF` pour la Polynésie française (défaut)
4. Cliquez sur **Tester la connexion API** pour valider
5. Passez l'état à **Activé**

### 3. Test en mode sandbox

Helcim fournit un environnement de test. Pour tester :
1. Créez un compte développeur Helcim : https://devdocs.helcim.com
2. Utilisez le jeton API de votre compte de test
3. Passez l'état du fournisseur à **Mode test** dans Odoo
4. Utilisez les cartes de test Helcim (ex: 4111111111111111)

---

## Architecture technique

### Flux de paiement

```
Client (navigateur)
    │
    ├─► Odoo: Initialisation paiement
    │       │
    │       └─► [BACKEND] payment_provider._helcim_initialize_checkout_session()
    │               │
    │               └─► POST https://api.helcim.com/v2/helcim-pay/initialize
    │                       │
    │                       └─► Retourne {checkoutToken, secretToken}
    │
    ├─► Template QWeb: Affichage formulaire avec checkoutToken
    │       │
    │       └─► Script HelcimPay.js: appendHelcimIframe(checkoutToken)
    │
    ├─► Modal HelcimPay.js (iframe sécurisé Helcim)
    │       │
    │       └─► Client saisit ses données de carte
    │
    ├─► HelcimPay.js: postMessage(SUCCESS, transactionData)
    │
    └─► [BACKEND] POST /payment/helcim/validate
            │
            ├─► Validation HMAC SHA-256
            └─► payment_transaction._process_notification_data()
                    │
                    └─► Mise à jour statut Odoo (done/cancelled/pending)
```

### Structure des fichiers

```
os_helcim_payment_provider/
├── __manifest__.py              # Déclaration du module
├── __init__.py                  # Hooks post-install / uninstall
├── controllers/
│   ├── __init__.py
│   └── main.py                  # Routes HTTP: /payment/helcim/*
├── models/
│   ├── __init__.py
│   ├── payment_provider.py      # Héritage payment.provider + API Helcim
│   └── payment_transaction.py  # Héritage payment.transaction + traitement
├── views/
│   ├── payment_helcim_templates.xml  # Template QWeb du modal
│   └── payment_provider_views.xml    # Vues backend (form, list)
├── data/
│   ├── payment_provider_data.xml    # Enregistrement fournisseur Helcim
│   └── payment_method_data.xml      # Méthode de paiement par carte
├── static/src/
│   ├── js/payment_form.js       # Extension JS formulaire Odoo
│   └── img/helcim_logo.png      # Logo Helcim
└── i18n/
    └── fr.po                    # Traductions françaises
```

---

## Sécurité

- **PCI-DSS** : Les données de carte ne transitent JAMAIS par vos serveurs Odoo grâce au modal HelcimPay.js
- **HMAC SHA-256** : Chaque réponse de transaction est validée par signature cryptographique
- **HTTPS** : Toutes les communications avec l'API Helcim sont chiffrées (TLS 1.2+)
- **Tokens** : Le `secretToken` est stocké en base et utilisé uniquement pour la validation, jamais exposé côté client

---

## Support

Pour toute question relative à l'intégration :
- Documentation API Helcim : https://devdocs.helcim.com
- Support Helcim : https://www.helcim.com/support
- Issues du module : Ouvrez un ticket auprès de votre intégrateur Odoo

---

## Licence

LGPL-3 — Voir le fichier LICENSE pour les détails.

© 2024 Opensense - https://www.opensense.pf
