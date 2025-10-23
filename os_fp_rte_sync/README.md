
# OS FP RTE Sync — V1.1

Évolutions V1.1 :
- Tags **APE**/**Effectif** (`res.partner.category`) sur ENT & ETAB.
- **Pliage** si un seul établissement (pas de contact enfant, l’ENT porte l’adresse).
- **Établissements = sociétés** (`is_company=True`, `company_type='company'`).
- **Forme juridique** via `partner_company_type_id` (module OCA `partner_company_type`).
- **Identifiants** via `res.partner.id_number` (OCA `partner_identification`) — TAITI (ENT) & RTE_ETAB (ETAB).
- **Effectif** via `employee_quantity_range_id` (OCA `partner_employee_quantity`).
- Exécution **BG** (one‑shot cron) et perfs (prefetch + commit par lot).

Dépendances OCA: `partner_company_type`, `partner_identification`, `partner_employee_quantity`.
Voir OCA/partner-contact.
