# Module Import Réservations Airbnb par Email

## 📋 Description

Ce module automatise complètement l'import des réservations Airbnb depuis les emails de notification envoyés par `automated@airbnb.com`.

## ✨ Fonctionnalités principales

### Connexion IMAP automatique
- Récupération des emails toutes les 15 minutes via cron job
- Support SSL/TLS sécurisé
- Configuration multi-société

### Parsing intelligent
- Extraction automatique de toutes les données depuis l'email HTML
- Support des formats français (dates, montants)
- Détection robuste des codes de confirmation

### Intégration CRM
- Création automatique de leads avec pipeline de suivi
- 5 stages : Nouveau → Confirmé → Arrivé → Terminé → Erreur
- Historique email complet

### Gestion multi-société
- Support complet pour plusieurs hébergeurs
- Paramétrage IMAP indépendant par société
- Isolation des données

### Détection de doublons
- Ignore automatiquement les emails déjà traités
- Évite les rappels Airbnb en double
- Journal des emails traités

### Création automatique
- Contact client avec données Airbnb
- Réservation complète avec toutes les informations
- Lead CRM avec historique email
- Liaison aux vues mensuelles et trimestrielles

## 🔄 Workflow automatique

```
1. Email reçu → Lead CRM créé (stage "Nouveau")
2. Parsing HTML → Extraction des données
3. Création contact + réservation → Lead passe en "Confirmé"
4. J-0 arrivée → Lead passe en "Arrivé"
5. J+0 départ → Lead passe en "Terminé"
```

## ⚙️ Configuration

### 1. Paramétrage IMAP par société

Accéder à : `Settings > Companies > [Votre société] > onglet "📧 Email Airbnb"`

Configurer :
- **Serveur IMAP** : adresse du serveur (ex: `mail.belroseplace.site`)
- **Port IMAP** : 993 pour SSL (recommandé), 143 pour non-sécurisé
- **Utiliser SSL** : Activé (recommandé)
- **Dossier IMAP** : INBOX (par défaut)
- **Utilisateur IMAP** : adresse email complète
- **Mot de passe IMAP** : mot de passe du compte

### 2. Taux de change

Le module utilise un taux de change fixe :
- 1000 XPF = 8.38 EUR
- Soit 1 EUR = 119.33 XPF

### 3. Mapping des logements

Le module recherche les logements via le champ `description_sale` de `product.template`.

Pour associer un logement :
1. Créer un produit/service dans Odoo
2. Remplir le champ "Description vente" avec le nom exact tel qu'il apparaît dans les emails Airbnb
3. Le module créera automatiquement le lien

## 📊 Journal de traitement

Accéder au journal : `Email Airbnb > Journal emails`

États possibles :
- 🔵 **En cours** : Email en cours de traitement
- ✅ **Traité** : Email traité avec succès
- ⚠️ **Doublon** : Email déjà traité précédemment
- ❌ **Erreur** : Échec du traitement

Pour chaque email, vous pouvez :
- Voir le contenu HTML brut
- Consulter la réservation créée
- Consulter le lead CRM créé
- Retraiter l'email en cas d'erreur

## 🔍 Modèles de données

### airbnb.email.log
Journal des emails reçus et traités

### airbnb.email.fetcher
Service de récupération des emails (TransientModel)

### airbnb.email.parser
Service de parsing HTML (TransientModel)

### airbnb.email.processor
Service de création des réservations (TransientModel)

### Extensions
- `crm.lead` : Ajout champs Airbnb (code confirmation, réservation, email source)
- `booking.import.line` : Ajout champ lead_id
- `res.company` : Ajout configuration IMAP

## 🔐 Sécurité

- Le mot de passe IMAP est stocké chiffré dans la base de données
- Connexion SSL/TLS recommandée
- Accès restreint aux utilisateurs authentifiés

## 🧪 Tests

### Test connexion IMAP
1. Aller dans `Settings > Companies > [Société] > Email Airbnb`
2. Cliquer sur "🔧 Tester la connexion"
3. Vérifier le message de succès/erreur

### Test récupération manuelle
1. Aller dans `Settings > Companies > [Société] > Email Airbnb`
2. Cliquer sur "📧 Récupérer les emails maintenant"
3. Vérifier les emails traités dans le journal

## 📝 Notes

### Limitations
- Les emails doivent provenir de `automated@airbnb.com`
- Format HTML requis (emails texte non supportés)
- Le nom de famille du voyageur n'est pas disponible dans les emails Airbnb

### Dépendances
- Module `os_hospitality_managment` (requis)
- Module `crm` (Odoo standard)
- Bibliothèques Python : `email`, `imaplib`, `ssl`

### Compatibilité
- Odoo 17.0
- Compatible avec `os_airbnb_pdf_import` (complémentaire)

## 🆘 Support

Pour toute question ou problème :
1. Consulter le journal des emails (`Email Airbnb > Journal emails`)
2. Vérifier les logs Odoo pour les erreurs détaillées
3. Tester la connexion IMAP
4. Vérifier que le traitement automatique est activé

## 📜 Licence

LGPL-3

## 👥 Auteur

OpalSea - https://www.opalsea.site
