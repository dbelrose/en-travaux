# os_website_belrose_place — v2.0.0

Module Odoo 17 — Site web public **Belrose Place Tahiti** avec IHM de réservation voyageur intégrée.

---

## Nouveautés v2 (par rapport à v1)

### IHM de réservation voyageur complète
Cinq nouvelles pages accessibles depuis le menu **Réserver** :

| URL | Template | Description |
|-----|----------|-------------|
| `/reservation` | `bp_accommodation_list` | Grille des logements disponibles |
| `/reservation/nouveau?product_id=X` | `bp_booking_form` | Formulaire de réservation avec estimateur de prix AJAX |
| `/reservation/soumettre` (POST) | `bp_booking_confirmation` / `bp_booking_error` | Traitement + page de confirmation |
| `/reservation/mes-reservations` | `bp_my_bookings` | Historique des réservations (connecté) |
| `/reservation/disponibilites/<id>` | `bp_booking_calendar` | Calendrier de disponibilité FullCalendar |

### Vérification de disponibilité en temps réel
- Endpoint JSON `/reservation/disponibilite` (AJAX)
- Calcul du prix, réductions hebdo/mensuelle, affichage immédiat
- Blocage du bouton « Confirmer » tant que les dates ne sont pas valides

### Calendrier interactif
- Chargement dynamique de **FullCalendar 6** (CDN jsDelivr)
- Jours libres teintés en vert, périodes réservées colorées selon l'état (confirmé / paiement en attente / payé)

### Design cohérent
- Nouveau fichier `belrose_booking.css` — reprend toutes les variables CSS de `belrose_place.css` (palette obsidian / teal / gold, polices Cormorant + DM Sans)
- Navbar enrichie : lien **Réserver** mis en valeur (bouton teal)
- Footer : lien **Réserver** ajouté dans la navigation

---

## Dépendances

```python
'depends': ['website', 'os_rental']
```

Le module `os_rental` doit être installé au préalable. Il fournit :
- Le modèle `booking.reservation`
- Le modèle `product.template` enrichi (`is_accommodation`, `nightly_rate`, `max_occupancy`)
- Les paramètres de configuration (`ir.config_parameter` sous le préfixe `booking.*`)
- L'intégration Billetweb (création de commande, envoi du lien de paiement)

---

## Structure du module

```
os_website_belrose_place/
├── __manifest__.py
├── __init__.py
├── controllers/
│   ├── __init__.py
│   └── main.py              ← BelrosePlaceWebsite (pages statiques + réservation)
├── data/
│   └── website_menu_data.xml ← Menus + nouveau lien "Réserver"
├── views/
│   ├── website_templates.xml
│   ├── website_layout.xml    ← Header / Footer (lien Réserver ajouté)
│   ├── website_homepage.xml
│   ├── website_cheque_cadeau.xml
│   ├── website_mentions_legales.xml
│   └── website_booking.xml  ← NOUVEAU — 6 templates IHM réservation
└── static/src/
    ├── css/
    │   ├── belrose_place.css
    │   └── belrose_booking.css ← NOUVEAU — styles IHM réservation
    └── js/
        ├── belrose_place.js
        └── belrose_booking.js  ← NOUVEAU — AJAX disponibilité + FullCalendar
```

---

## Flow de réservation voyageur

```
/reservation
    └─→ /reservation/nouveau?product_id=X
            │  (AJAX en temps réel → /reservation/disponibilite)
            └─→ POST /reservation/soumettre
                    ├─→ /reservation/confirmation  (succès)
                    └─→ /reservation/erreur        (échec)

/reservation/disponibilites/<id>   (calendrier, accessible depuis toutes les pages)
/reservation/mes-reservations      (connecté)
```

---

## Configuration requise

Les paramètres Billetweb et les règles de séjour sont gérés dans `os_rental` :
**Paramètres → Réservations / Billetweb**

- Clé API Billetweb
- ID événement et tarif Billetweb
- Durée minimale de séjour (défaut : 2 nuits)
- Réduction hebdomadaire (défaut : 10 % dès 7 nuits)
- Réduction mensuelle (défaut : 20 % dès 30 nuits)

---

*Développé par [OpalSea](https://opalsea.site) — Licence LGPL-3*
