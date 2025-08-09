# Booking.com Import Manager

Module Odoo pour gérer les réservations Booking.com avec génération automatique de factures.

## Fonctionnalités principales

### 🚀 Deux modes d'utilisation

1. **Import de fichier Excel**
   - Import automatique des fichiers Booking.com
   - Prévisualisation avant import
   - Validation et nettoyage des données

2. **Saisie manuelle**
   - Interface simplifiée pour saisie directe
   - Création rapide de réservations
   - Modification en temps réel

### 💰 Calculs automatiques

- **Taxes de séjour** : 60 XPF par nuitée adulte
- **Exemptions enfants** : Gratuit pour les ≤12 ans
- **Commissions** : Calcul automatique des commissions Booking
- **Totaux par trimestre** : Regroupement automatique

### 📄 Génération de factures

Le module génère automatiquement trois types de factures :

1. **Factures mairie** : Taxes de séjour par trimestre
2. **Factures concierge** : Commissions (20% du tarif net)
3. **Factures Booking.com** : Commissions plateformes

## Installation

### Prérequis

```bash
pip install pandas openpyxl num2words
```

### Installation du module

1. Copier le module dans le répertoire `addons` d'Odoo
2. Redémarrer le serveur Odoo
3. Aller dans Apps > Modules locaux
4. Chercher "Booking.com Import Manager"
5. Cliquer sur "Installer"

## Utilisation

### 📥 Import de fichier Excel

1. **Menu** : Booking.com > Import > Import fichier Excel
2. **Sélectionner** le fichier Excel exporté depuis Booking.com
3. **Prévisualiser** les données (vérification automatique)
4. **Confirmer** l'import
5. Les factures sont générées automatiquement

#### Format de fichier attendu

Le fichier Excel doit contenir les colonnes suivantes :
- `Nom du client` ou `Réservé par`
- `Type d'hébergement`
- `Arrivée`
- `Durée (nuits)`
- `Personnes`
- `Âges des enfants`
- `Statut` (doit contenir "ok")
- `Statut du paiement`
- `Tarif`
- `Montant de la commission`
- `Numéro de téléphone`
- `Booker country`

### ✏️ Saisie manuelle

1. **Menu** : Booking.com > Import > Saisie manuelle
2. **Sélectionner** l'année, le mois et la propriété
3. **Créer** l'enregistrement
4. **Ajouter** les réservations une par une
5. **Générer** les factures manuellement si nécessaire

### 📊 Gestion des données

#### Menu principal : Booking.com > Réservations > Gestion des réservations

- **Vue liste** : Aperçu de tous les imports
- **Vue formulaire** : Détail avec calculs automatiques
- **Filtres** : Par année, propriété, période
- **Recherche** : Par nom, propriété, période

#### Actions disponibles

- **Ajouter réservation** : Wizard rapide d'ajout
- **Modifier réservation** : Edition en place ou via wizard
- **Générer factures** : Boutons individuels par type
- **Dupliquer** : Copie d'une réservation existante

## Structure des données

### Modèle `booking.import`

Enregistrement principal regroupant les réservations par période et propriété.

**Champs clés :**
- `name` : Nom automatique (YYYY-MM Propriété)
- `year`, `month` : Période
- `property_type_id` : Type d'hébergement
- `line_ids` : Lignes de réservation
- `total_commission` : Commission totale
- `nuitees_trimestre` : Total nuitées taxables

### Modèle `booking.import.line`

Ligne individuelle de réservation.

**Champs clés :**
- `partner_id`, `booker_id` : Client et réservateur
- `arrival_date`, `duration_nights` : Dates de séjour
- `pax_nb`, `children` : Nombre de personnes
- `rate`, `commission_amount` : Informations financières
- `nights_adults` : Nuitées taxables (calculé)
- `tax_amount` : Montant taxe (calculé)

## Calculs des taxes

### Taxe de séjour

```
Nuitées taxables = Durée × (Personnes - Enfants ≤12 ans)
Montant taxe = Nuitées taxables × 60 XPF
```

### Commission concierge

```
Base = Tarif - Commission Booking - Taxe séjour
Commission concierge = Base × 20%
```

## Factures générées

### 1. Factures mairie (Taxes de séjour)

- **Fréquence** : Par trimestre et par propriété
- **Client** : Mairie de Punaauia
- **Ligne** : Une par mois du trimestre
- **Calcul** : Nuitées taxables × 60 XPF
- **Compte** : 63513000

### 2. Factures concierge (Commissions)

- **Fréquence** : Par mois et par propriété
- **Client** : Propriétaire de l'hébergement
- **Calcul** : (Tarif - Commission - Taxe) × 20%
- **Compte** : 62220000

### 3. Factures Booking.com (Commissions)

- **Fréquence** : Par mois et par propriété
- **Client** : Booking.com
- **Calcul** : Montant commission Booking
- **Compte** : 62220000
- **Échéance** : Premier du mois suivant + 30 jours

## Dépannage

### Erreurs courantes

1. **"Fichier non reconnu"**
   - Vérifier le format Excel (.xlsx)
   - Vérifier la présence des colonnes requises
   - Vérifier l'encodage des caractères

2. **"Aucun enregistrement valide"**
   - Vérifier que la colonne "Statut" contient "ok"
   - Vérifier les dates d'arrivée (format valide)
   - Vérifier les montants numériques

3. **"Erreur de calcul des taxes"**
   - Vérifier l'âge des enfants (format "1, 5, 12")
   - Vérifier le nombre de personnes > 0
   - Vérifier la durée > 0

### Support et développement

Pour toute question ou suggestion d'amélioration, contactez l'équipe de développement.

## Changelog

### Version 1.0.0
- Import de fichiers Excel Booking.com
- Saisie manuelle de réservations
- Calcul automatique des taxes de séjour
- Génération automatique des factures
- Interface utilisateur complète
- Support multi-sociétés