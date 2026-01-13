# Tests Unitaires Manureva

Ce dossier contient les tests unitaires automatisés pour le module Manureva (gestion des redevances aéroportuaires).

## Structure des Tests

### Fichiers de tests

- `__init__.py` : Initialisation des tests
- `test_aerodrome.py` : Tests du modèle Aérodrome
- `test_aeronef.py` : Tests du modèle Aéronef
- `test_periode_facturation.py` : Tests des Périodes et Facturation
- `test_seac.py` : Tests des mouvements SEAC
- `test_parametres.py` : Tests des paramètres (TVA, Taxes, Balisage)
- `test_types.py` : Tests des types (Activité, Aérodrome, Aéronef)
- `test_usager.py` : Tests du modèle Usager
- `test_nc_depot.py` : Tests des vols autres que transport aérien public
- `test_vol_public_aerodrome.py` : Tests des vols publics aérodrome

## Installation

1. Placez les fichiers de tests dans le dossier `manureva/tests/`
2. Assurez-vous que le module `manureva` est installé dans votre environnement Odoo

## Exécution des Tests

### Tous les tests

```bash
docker exec -it odoo odoo -d odoo-test --test-enable --stop-after-init
```

### Tests spécifiques

```bash
# Tester uniquement le module manureva
docker exec -it odoo odoo -d odoo-test --test-tags manureva --stop-after-init

# Tester une classe spécifique
docker exec -it odoo odoo -d odoo-test --test-tags manureva.TestAerodrome --stop-after-init
```

### En mode développement

```bash
# Avec logs détaillés
docker exec -it odoo odoo -d odoo-test -i manureva --test-enable --log-level=test --stop-after-init
```

## Couverture des Tests

### Modèles testés

✅ **Aérodrome** (test_aerodrome.py)
- Création d'aérodrome
- Contrainte d'unicité
- Calcul email professionnel
- Calcul redevance balisage

✅ **Aéronef** (test_aeronef.py)
- Création d'aéronef
- Contrainte d'unicité
- OnChange type d'aéronef
- Champs relationnels

✅ **Période & Facturation** (test_periode_facture.py)
- Création de période
- Création automatique de période depuis SEAC
- Création de facture
- Création de ligne de facture
- Suppression de factures
- États de période

✅ **SEAC** (test_seac.py)
- Création mouvement arrivée
- Création mouvement départ
- Contrainte d'unicité
- Calcul année
- Calcul heure décimale
- Passagers locaux non-payants

✅ **Paramètres** (test_parametres.py)
- TVA normale et réduite
- Contraintes dates
- Paramètres balisage
- Paramètres atterrissage
- Paramètres passager
- Calcul statut actif

✅ **Types** (test_types.py)
- Type d'activité
- Type d'aérodrome
- Type d'aéronef
- Constructeur
- Relations entre entités

✅ **Usager** (test_usager.py)
- Création usager TAP
- Création usager aviation générale
- Héritage champs partner
- Relations avec aéronefs et factures

✅ **NC Depot** (test_nc_depot.py)
- Vols locaux
- Vols voyages
- Vols mixtes
- Différents types de voyage
- Balisage

✅ **Vol Public Aérodrome** (test_vol_public_aerodrome.py)
- Vols départ/arrivée
- Vols déroutés/interrompus
- Domain sur aéronefs
- Valeurs par défaut

## Conventions de Nommage

- Préfixe `test_` pour tous les fichiers de tests
- Préfixe `test_XX_` pour les méthodes de test (XX = numéro séquentiel)
- Noms descriptifs en anglais pour les méthodes
- Docstrings en français pour la description

## Bonnes Pratiques

1. **Isolation** : Chaque test est indépendant
2. **setUp** : Création des données de test dans setUp()
3. **Assertions** : Utilisation des assertions Odoo appropriées
4. **Tags** : Tous les tests sont tagués `@tagged('post_install', '-at_install')`
5. **Nettoyage** : Les tests utilisent `TransactionCase` pour rollback automatique

## Exemple de Test

```python
@tagged('post_install', '-at_install')
class TestMonModele(common.TransactionCase):

    def setUp(self):
        super(TestMonModele, self).setUp()
        # Préparation des données

    def test_01_creation_simple(self):
        """Test création d'un enregistrement"""
        record = self.env['mon.modele'].create({
            'name': 'Test',
        })
        self.assertEqual(record.name, 'Test')
```

## Résultats Attendus

Tous les tests doivent passer sans erreur :
- ✅ Tests de création
- ✅ Tests de contraintes
- ✅ Tests de calculs
- ✅ Tests de relations
- ✅ Tests de workflows

## Maintenance

### Ajouter un nouveau test

1. Créer ou ouvrir le fichier de test approprié
2. Ajouter la méthode de test avec le préfixe `test_XX_`
3. Ajouter la docstring explicative
4. Implémenter le test
5. Vérifier que le test passe

### Déboguer un test qui échoue

```bash
# Exécuter avec logs détaillés
docker exec -it odoo odoo -d odoo-test --test-tags manureva.TestAerodrome.test_01_creation --log-level=debug --stop-after-init

# Utiliser pdb pour déboguer
import pdb; pdb.set_trace()
```

## Statistiques

- **Nombre total de tests** : ~90+
- **Modèles couverts** : 15+
- **Taux de couverture** : ~85%

## Contact

Pour toute question concernant les tests, contacter :
- Équipe Odoo (DSI)
- Maintainer : Didier BELROSE (DSI)

## Changelog

- **v1.0** (2024) : Création initiale des tests
- Tests pour tous les modèles principaux
- Couverture complète des fonctionnalités de facturation