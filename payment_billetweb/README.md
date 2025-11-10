# Module de Paiement Billetweb pour Odoo 17

## Description

Ce module intègre Billetweb comme processeur de paiement dans Odoo 17. Il permet de créer des commandes de paiement via l'API Billetweb et de gérer les transactions de manière transparente.

## Fonctionnalités

- ✅ Création de commandes de paiement via l'API Billetweb
- ✅ Redirection vers la page de paiement sécurisée Billetweb
- ✅ Gestion automatique des statuts de transaction (payé, en attente, annulé)
- ✅ Support des remboursements complets
- ✅ Synchronisation des événements Billetweb
- ✅ Vérification automatique du statut des paiements
- ✅ Interface utilisateur intuitive

## Installation

1. Copiez le dossier `payment_billetweb` dans votre répertoire `addons` d'Odoo
2. Redémarrez le serveur Odoo
3. Activez le mode développeur
4. Allez dans Apps et mettez à jour la liste des applications
5. Recherchez "Billetweb Payment Provider" et installez le module

## Configuration

### 1. Obtenir vos identifiants API Billetweb

1. Connectez-vous à votre [tableau de bord Billetweb](https://www.billetweb.fr/bo/)
2. Accédez aux paramètres API
3. Récupérez votre **User ID** et votre **API Key**

### 2. Configurer le provider dans Odoo

1. Allez dans **Comptabilité > Configuration > Providers de paiement**
2. Créez ou sélectionnez le provider **Billetweb**
3. Renseignez les informations suivantes :
   - **User ID** : Votre identifiant utilisateur Billetweb
   - **API Key** : Votre clé API Billetweb
   - **Event ID par défaut** : L'ID de l'événement Billetweb à utiliser pour les paiements
4. Activez le provider
5. Publiez-le si nécessaire

### 3. Synchroniser vos événements

- Cliquez sur le bouton **"Synchroniser les événements"** pour récupérer la liste de vos événements Billetweb
- Sélectionnez l'événement à utiliser par défaut pour les paiements

## Utilisation

### Pour vos clients

1. Le client sélectionne **Billetweb** comme moyen de paiement
2. Il est redirigé vers la page de paiement sécurisée Billetweb
3. Après le paiement, il est automatiquement redirigé vers Odoo
4. Le statut du paiement est mis à jour automatiquement

### Gestion des transactions

- Les transactions sont accessibles dans **Comptabilité > Providers de paiement > Transactions**
- Vous pouvez voir :
  - L'ID de commande Billetweb
  - L'ID de l'événement associé
  - L'URL de la boutique Billetweb
  - Le statut du paiement

### Remboursements

1. Ouvrez la transaction à rembourser
2. Cliquez sur **"Rembourser"**
3. Indiquez le montant (remboursement complet uniquement)
4. Le remboursement est traité automatiquement via l'API Billetweb

## Architecture technique

### Modèles

#### `payment.provider` (étendu)
- `billetweb_user_id` : ID utilisateur Billetweb
- `billetweb_api_key` : Clé API Billetweb
- `billetweb_default_event_id` : Événement par défaut

#### `payment.transaction` (étendu)
- `billetweb_order_id` : ID de la commande Billetweb
- `billetweb_event_id` : ID de l'événement associé
- `billetweb_shop_url` : URL de paiement

### Contrôleurs

- `/payment/billetweb/return` : Route de retour après paiement
- `/payment/billetweb/webhook` : Webhook pour notifications (optionnel)
- `/payment/billetweb/validate/<tx_ref>` : Validation manuelle d'une transaction

### API Billetweb supportées

- `GET /api/events` : Liste des événements
- `GET /api/event/{id}/tickets` : Tarifs d'un événement
- `POST /api/event/{id}/attendees` : Création de commande
- `GET /api/event/{id}/attendees` : Récupération des participants
- `POST /api/attendees/refund` : Remboursement
- `POST /api/attendees/validate` : Validation de paiement

## Limitations connues

1. **Pas de webhook natif** : Billetweb ne fournit pas de système de webhook automatique. Le module utilise un polling pour vérifier le statut des paiements.

2. **Remboursements complets uniquement** : L'API Billetweb ne supporte que les remboursements complets.

3. **Pas de tokenisation** : Billetweb ne supporte pas la sauvegarde des moyens de paiement.

4. **Dépendance aux événements** : Chaque transaction doit être associée à un événement Billetweb.

## Dépannage

### Le paiement ne se valide pas automatiquement

- Vérifiez que l'Event ID est correctement configuré
- Vérifiez que vos identifiants API sont valides
- Consultez les logs Odoo pour plus de détails

### Erreur "Aucun tarif trouvé"

- Assurez-vous que l'événement Billetweb a au moins un tarif actif
- Vérifiez que l'Event ID est correct

### Le remboursement échoue

- Vérifiez que la commande existe dans Billetweb
- Assurez-vous que la commande n'a pas déjà été remboursée
- Consultez les logs pour plus de détails

## Support

Pour toute question ou problème :
- Consultez la [documentation API Billetweb](https://www.billetweb.fr/bo/api.php)
- Ouvrez une issue sur le dépôt du module
- Contactez votre administrateur Odoo

## Licence

LGPL-3

## Auteur

Développé pour l'intégration de Billetweb avec Odoo 17

## Versions

- **1.0.0** (Initial) : Première version avec support de base de Billetweb