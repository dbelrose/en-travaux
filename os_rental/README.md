# Module Odoo 17 - Réservation de Logements avec Billetweb

## Description
Module complet de réservation de logements avec intégration de paiement via l'API Billetweb.

## Fonctionnalités

### Backend (Odoo)
- Gestion des logements en tant que produits (catégorie os_hospitality_managment.product_category_tdsmdt)
- Calendrier d'occupation avec gestion des disponibilités
- Tarification par nuit avec réductions automatiques :
  - 10% à partir de 7 nuits (paramétrable)
  - 20% à partir de 30 nuits (paramétrable)
- Contraintes configurables :
  - Minimum 2 nuits (paramétrable)
  - Maximum 3 mois (paramétrable)
- Intégration complète avec l'API Billetweb
- Traitement asynchrone avec queue_job
- Notifications par email avec lien de paiement

### Frontend (Website)
- Catalogue de logements disponibles
- Formulaire de réservation avec vérification en temps réel
- Calcul dynamique des prix avec réductions
- Espace client pour consulter les réservations
- Webhook pour mise à jour automatique des paiements

## Installation

1. Copier le module dans votre répertoire addons Odoo
2. Activer le mode développeur
3. Mettre à jour la liste des applications
4. Installer le module "Réservation Logement avec Billetweb"

## Configuration

### 1. Configuration Billetweb
Aller dans **Réservations > Configuration**
- Renseigner votre clé API Billetweb
- Vérifier les IDs d'événement et de ticket
- Ajuster les paramètres de réduction

### 2. Configuration des Logements
Aller dans **Inventaire > Produits**
- Créer ou modifier un produit
- Assigner à la catégorie des logements
- Renseigner le tarif par nuit et la capacité
- L'onglet "Hébergement" apparaîtra automatiquement

### 3. Configuration du Webhook
Configurer dans Billetweb le webhook pointant vers :
```
https://votre-domaine.com/booking/webhook/billetweb
```

## Utilisation

### Côté Client (Website)
1. Accéder à `/booking` pour voir les logements
2. Cliquer sur "Réserver"
3. Remplir le formulaire avec les dates
4. Recevoir l'email avec le lien de paiement Billetweb
5. Effectuer le paiement
6. La réservation passe automatiquement en "Payé"

### Côté Admin (Backend)
1. Consulter les réservations dans **Réservations > Réservations**
2. Vue calendrier pour visualiser l'occupation
3. Traitement manuel possible si nécessaire

## API et Intégration

### Vérification de disponibilité (AJAX)
```javascript
await this._rpc({
    route: '/booking/availability',
    params: {
        product_id: 123,
        start_date: '2025-01-01',
        end_date: '2025-01-08',
    },
});
```

### Webhook Billetweb
Le module écoute les notifications POST de Billetweb et met à jour automatiquement le statut des réservations.

## Dépendances
- base
- product
- website
- queue_job

## Notes Techniques
- Utilise queue_job pour les appels API asynchrones
- Gestion des erreurs et logs pour l'API Billetweb
- Validation des contraintes de réservation
- Prévention des doubles réservations

## Support
Pour toute question ou problème, consulter la documentation Odoo ou Billetweb.

## Licence
LGPL-3