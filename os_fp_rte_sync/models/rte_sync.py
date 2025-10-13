# -*- coding: utf-8 -*-
import csv
import io
import json
import logging
import re
from datetime import datetime
from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

DGOUV_DATASET_SLUG = "repertoire-des-entreprises"
RTE_RESOURCE_RID_DEFAULT = "34184a7f-a4bf-4cf3-ac36-531388f3a6cb"


def _http_get(url, timeout=120):
    try:
        import requests  # type: ignore
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Exception:
        from urllib.request import urlopen  # type: ignore
        return urlopen(url, timeout=timeout).read()


class RteSyncRun(models.Model):
    _name = "rte.sync.run"
    _description = "Historique synchronisation RTE (ISPF)"

    start = fields.Datetime(default=lambda self: fields.Datetime.now())
    end = fields.Datetime()
    status = fields.Selection([
        ("done", "Terminé"), ("skipped", "Aucune nouvelle version"), ("failed", "Échec")
    ], default="done", required=True)
    message = fields.Text()
    created_count = fields.Integer()
    updated_count = fields.Integer()
    skipped_count = fields.Integer()
    checksum = fields.Char()

    def name_get(self):
        return [(r.id, f"RTE Sync {r.start} [{r.status}]") for r in self]


class RteSyncMixin(models.AbstractModel):
    _name = "rte.sync.mixin"
    _description = "Fonctions utilitaires RTE"

    def _get_dataset_meta(self):
        raw = _http_get(f"https://www.data.gouv.fr/api/1/datasets/{DGOUV_DATASET_SLUG}/")
        return json.loads(raw.decode("utf-8"))

    def _get_rte_resource_meta(self, rid=None):
        rid = rid or self.env['ir.config_parameter'].sudo().get_param('fp_rte_sync.resource_rid',
                                                                      default=RTE_RESOURCE_RID_DEFAULT)
        meta = self._get_dataset_meta()
        for res in meta.get('resources', []):
            if res.get('id') == rid:
                return res
        raise ValueError(f"Ressource {rid} introuvable sur {DGOUV_DATASET_SLUG}.")

    def _import_only_active(self):
        val = self.env['ir.config_parameter'].sudo().get_param('fp_rte_sync.import_only_active', default='True')
        return str(val).lower() in ('1', 'true', 'yes', 'y')

    def _batch_commit(self):
        val = self.env['ir.config_parameter'].sudo().get_param('fp_rte_sync.batch_commit', default='1000')
        try:
            return max(100, int(val))
        except Exception:
            return 1000

    # NAF
    def _norm_naf(self, s):
        return re.sub(r'[^A-Z0-9*]', '', (s or '').upper())

    def _naf_to_xml_id(self, naf_code):
        """Convertit un code NAF en XML ID valide"""
        normalized = self._norm_naf(naf_code).lower()
        return f"res_partner_category_ape_{normalized}"

    def _get_naf_name_from_ref(self, naf_code):
        """Récupère le nom du code APE depuis les données de référence"""
        xml_id = self._naf_to_xml_id(naf_code)
        try:
            tag = self.env.ref(f'os_fp_rte_sync.{xml_id}', raise_if_not_found=False)
            if tag:
                return tag.name
        except Exception:
            pass
        # Fallback: retourner juste le code
        return self._norm_naf(naf_code)

    def _naf_allowed(self, naf_code):
        code = self._norm_naf(naf_code)
        white = (self.env['ir.config_parameter'].sudo().get_param('fp_rte_sync.naf_whitelist', '')).strip()
        if not white:
            return True
        for pat in [self._norm_naf(w) for w in white.split(',') if w.strip()]:
            if re.match('^' + pat.replace('*', '.*') + '$', code):
                return True
        return False

    def _country_pf(self):
        return self.env['res.country'].search([('code', '=', 'PF')], limit=1)

    # Tags (res.partner.category)
    def _get_or_create_tag(self, parent_name, child_name):
        """
        Crée ou récupère un tag avec uniquement le nom (pas le code).
        Pour les codes APE, utilise les noms complets depuis les données de référence.
        """
        Cat = self.env['res.partner.category'].sudo()
        parent = Cat.search([('name', '=', parent_name), ('parent_id', '=', False)], limit=1)
        if not parent:
            parent = Cat.create({'name': parent_name})

        tag = Cat.search([('name', '=', child_name), ('parent_id', '=', parent.id)], limit=1)
        if not tag:
            tag = Cat.create({'name': child_name, 'parent_id': parent.id})
        return tag

    def _apply_tags(self, partner, naf_code, effectif_label):
        """
        Applique les tags au partenaire.
        Pour les codes APE, utilise le nom complet depuis les données de référence.
        """
        tags = self.env['res.partner.category'].sudo()

        if naf_code:
            # Récupérer le nom complet depuis les données de référence
            naf_name = self._get_naf_name_from_ref(naf_code)
            tags |= self._get_or_create_tag('APE', naf_name)

        if effectif_label:
            tags |= self._get_or_create_tag('Effectif', effectif_label.strip())

        if tags:
            partner.write({'category_id': [(4, t.id) for t in tags]})

    # Company type (OCA)
    def _company_type_to_xml_id(self, code_fjur):
        """Convertit un code forme juridique en XML ID valide"""
        if not code_fjur:
            return None
        # Remplacer les espaces par underscore, supprimer caractères spéciaux
        normalized = re.sub(r'[^a-z0-9_]', '', code_fjur.strip().lower().replace(' ', '_'))
        return f"partner_company_type_{normalized}"

    def _map_company_type(self, code_fjur):
        """
        Cherche d'abord dans les données de référence via XML ID,
        sinon crée dynamiquement.
        """
        ctype_model = self.env['res.partner.company.type'].sudo()
        code = (code_fjur or '').strip()
        if not code:
            return False

        # Essayer de récupérer depuis les données de référence
        xml_id = self._company_type_to_xml_id(code)
        if xml_id:
            try:
                ctype = self.env.ref(f'os_fp_rte_sync.{xml_id}', raise_if_not_found=False)
                if ctype:
                    return ctype.id
            except Exception:
                pass

        # Fallback: recherche/création dynamique
        has_code = 'code' in ctype_model._fields
        domain = [('code', '=', code)] if has_code else [('name', '=', code)]
        ctype = ctype_model.search(domain, limit=1)
        if not ctype:
            vals = {'name': code}
            if has_code:
                vals['code'] = code
            ctype = ctype_model.create(vals)
        return ctype.id

    # ID Numbers (OCA)
    def _ensure_id_category(self, name, code=None):
        Cat = self.env['res.partner.id_category'].sudo()
        dom = [('name', '=', name)]
        if code and 'code' in Cat._fields:
            dom = ['|', ('code', '=', code), ('name', '=', name)]
        cat = Cat.search(dom, limit=1)
        if not cat:
            vals = {'name': name}
            if code and 'code' in Cat._fields:
                vals['code'] = code
            cat = Cat.create(vals)
        return cat

    def _ensure_id_number(self, partner, category_name, value, code=None):
        if not value:
            return
        cat = self._ensure_id_category(category_name, code=code or category_name.lower())
        IdNum = self.env['res.partner.id_number'].sudo()
        existing = IdNum.search([('partner_id', '=', partner.id), ('name', '=', value), ('category_id', '=', cat.id)],
                                limit=1)
        if not existing:
            IdNum.create({'partner_id': partner.id, 'category_id': cat.id, 'name': value})

    # Effectif (OCA)
    def _effectif_to_xml_id(self, effectif_id):
        """Convertit un ID d'effectif en XML ID valide"""
        if not effectif_id:
            return None
        return f"partner_employee_quantity_{effectif_id}"

    def _set_employee_range(self, partner, effectif_label):
        """
        Cherche d'abord dans les données de référence,
        sinon crée dynamiquement.
        """
        if not effectif_label:
            return

        Range = self.env['res.partner.employee_quantity_range'].sudo()

        # Essayer de récupérer depuis les données de référence
        # On cherche par correspondance de label
        r = Range.search([('name', '=', effectif_label.strip())], limit=1)

        if not r:
            r = Range.create({'name': effectif_label.strip()})

        if 'employee_quantity_range_id' in partner._fields:
            partner.write({'employee_quantity_range_id': r.id})

    # Mapping entêtes
    def _detect_columns(self, header_lower):
        def pick(*cands):
            for c in cands:
                for h in header_lower:
                    if c in h:
                        return h
            return None

        return {
            'tahiti': pick('numtah', 'tahiti'),
            'numeta': pick('numeta'),
            'tahiti_etab': pick('numtah eta', 'numtaheta', 'num_tah_eta', 'numtah_etab', 'tahiti_etab'),
            'name_ent': pick('nom_ent'),
            'sigle_ent': pick('sigle_ent', 'sigle'),
            'name_etab': pick('nom_etab'),
            'zip_ent': pick('code_postal_ent', 'cp', 'code postal'),
            'city_etab': pick('com_etab_libelle', 'commune_etab', 'ville_etab'),
            'street_num': pick('num_adr', 'numero', 'numéro'),
            'street_name': pick('rue', 'adresse', 'adresse 1', 'adr1'),
            'street2_a': pick('immeuble'),
            'street2_b': pick('adrgeo'),
            'street2_c': pick('pk'),
            'street2_d': pick('quartier'),
            'naf_etab': pick('naf2008_etab', 'naf_etab', 'naf etab'),
            'naf_ent': pick('naf2008_ent', 'naf_ent', 'naf ent'),
            'forme': pick('code_fjur', 'forme juridique'),
            'effectif': pick('classe_effectifs', "classe d'effectifs",'classe effectif','effectif'),
                                                                                                 'rad_ent': pick(
                'rad_ent', 'radiation_ent'),
            'rad_etab': pick('rad_etab', 'radiation_etab'),
            'insc_ent': pick('insc_ent'),
        }

    def _extract_zip(self, v):
        m = re.search(r"\b(\d{5})\b", (v or ''))
        return m.group(1) if m else ''

    def _parse_date(self, v):
        if not v:
            return None
        v = (v or '').strip()
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
            try:
                return datetime.strptime(v[:10], fmt).date()
            except Exception:
                continue
        return None

    def _build_diff(self, rec, vals):
        if not rec:
            return vals
        changes = {}
        fields = rec._fields
        for k, v in vals.items():
            f = fields.get(k)
            if not f:
                continue
            cur = getattr(rec, k)
            if f.type == 'many2one':
                cur_id = getattr(cur, 'id', False) or False
                new_id = getattr(v, 'id', v)
                if cur_id != (new_id or False):
                    changes[k] = v
            else:
                if cur != v:
                    changes[k] = v
        return changes


class RteSyncWizard(RteSyncMixin, models.TransientModel):
    _name = 'rte.sync.wizard'
    _description = 'Assistant de synchronisation RTE'

    def action_sync_now(self):
        force = bool(self.env.context.get('force'))
        self.env['rte.sync.runner'].schedule_sync_once(force=force)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'RTE Sync planifiée',
                'message': "La synchronisation démarre en tâche de fond. Consultez l'historique pour suivre.",
                'type': 'success',
                'sticky': False,
            },
        }


class RteSyncRunner(RteSyncMixin, models.AbstractModel):
    _name = 'rte.sync.runner'
    _description = 'Exécution de la synchronisation RTE'

    @api.model
    def schedule_sync_once(self, force=False):
        code = f"env['rte.sync.runner'].run_sync(force={bool(force)})"
        cron = self.env['ir.cron'].sudo().create({
            'name': 'RTE Sync (one-shot)',
            'model_id': self.env['ir.model']._get_id('rte.sync.runner'),
            'state': 'code',
            'code': code,
            'numbercall': 1,
            'interval_number': 1,
            'interval_type': 'minutes',
            'nextcall': fields.Datetime.now(),
            'active': True,
            'user_id': self.env.ref('base.user_root').id,
            'priority': 1,
        })
        _logger.info("RTE one-shot cron created id=%s", cron.id)
        return cron.id

    @api.model
    def run_sync(self, force=False):
        run = self.env['rte.sync.run'].sudo().create({})
        try:
            res_meta = self._get_rte_resource_meta()
            checksum = (res_meta.get('checksum') or {}).get('value')
            latest_url = res_meta.get('latest') or res_meta.get('url')
            last_checksum = self.env['ir.config_parameter'].sudo().get_param('fp_rte_sync.last_checksum')
            if not force and checksum and last_checksum and checksum == last_checksum:
                run.write({'status': 'skipped', 'checksum': checksum,
                           'message': 'Aucune nouvelle version (checksum inchangé).'})
                _logger.info('RTE: checksum identique, skip.')
                return run

            content = _http_get(latest_url, timeout=600)
            text = None
            for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
                try:
                    text = content.decode(enc);
                    break
                except Exception:
                    continue
            if text is None:
                raise ValueError('Impossible de décoder le CSV (encodage).')

            buf = io.StringIO(text)
            reader = csv.DictReader(buf)
            if not reader.fieldnames:
                raise ValueError('CSV sans entêtes.')
            headers_lc = [h.strip().lower() for h in reader.fieldnames]
            header_map = self._detect_columns(headers_lc)
            _logger.info('RTE header_map: %s', header_map)

            Partner = self.env['res.partner'].sudo()
            country_pf = self._country_pf()
            created = updated = skipped = 0
            now = fields.Datetime.now()
            import_only_active = self._import_only_active()
            batch_size = self._batch_commit()

            def rv(row_l, key):
                col = header_map.get(key)
                return row_l.get(col) if col else None

            # 1ère passe : filtrage + collecte clés
            rows = []
            tahitis_set, etab_keys_set = set(), set()
            for row in reader:
                row_l = {(k or '').strip().lower(): v for k, v in row.items()}
                tahiti = (rv(row_l, 'tahiti') or '').strip()
                if not tahiti:
                    continue
                numeta = (rv(row_l, 'numeta') or '').strip()
                tahiti_etab = (rv(row_l, 'tahiti_etab') or '').strip()
                is_establishment = bool(tahiti_etab or numeta)
                etab_key = tahiti_etab or (f"{tahiti}-{numeta}" if numeta else '')
                naf = (rv(row_l, 'naf_etab') or rv(row_l, 'naf_ent') or '').strip()
                rad_ent = (rv(row_l, 'rad_ent') or '').strip()
                rad_etab = (rv(row_l, 'rad_etab') or '').strip()
                is_active_row = not bool(rad_etab if is_establishment else rad_ent)
                if self._naf_allowed(naf):
                    rows.append((row_l, tahiti, is_establishment, etab_key, naf, is_active_row))
                    tahitis_set.add(tahiti)
                    if etab_key:
                        etab_keys_set.add(etab_key)
                else:
                    skipped += 1

            # Prefetch existants
            parents = Partner.search([('x_tahiti', 'in', list(tahitis_set))]) if tahitis_set else Partner.browse()
            by_tahiti = {p.x_tahiti: p for p in parents if p.is_company}
            children = Partner.search(
                [('x_etablissement', 'in', list(etab_keys_set))]) if etab_keys_set else Partner.browse()
            by_etab = {c.x_etablissement: c for c in children}

            # 2e passe : upsert
            count = 0
            for row_l, tahiti, is_est, etab_key, naf, is_active_row in rows:
                name_ent = (rv(row_l, 'name_ent') or '').strip()
                sigle_ent = (rv(row_l, 'sigle_ent') or '').strip()
                base_name = f"{name_ent} ({sigle_ent})" if (name_ent and sigle_ent) else (
                            name_ent or f"Entreprise {tahiti}")
                street = " ".join(
                    x for x in [(rv(row_l, 'street_num') or '').strip(), (rv(row_l, 'street_name') or '').strip()] if x)
                street2 = " - ".join(x for x in [
                    (rv(row_l, 'street2_a') or '').strip(),
                    (rv(row_l, 'street2_b') or '').strip(),
                    (rv(row_l, 'street2_c') or '').strip(),
                    (rv(row_l, 'street2_d') or '').strip(),
                ] if x)
                zip_ent = self._extract_zip(rv(row_l, 'zip_ent'))
                city_etab = (rv(row_l, 'city_etab') or '').strip()

                base_vals = {
                    'street': street,
                    'street2': street2,
                    'zip': zip_ent,
                    'city': city_etab,
                    'x_naf': naf,
                    'x_forme_juridique': (rv(row_l, 'forme') or '').strip(),
                    'x_effectif_classe': (rv(row_l, 'effectif') or '').strip(),
                    'x_rte_updated_at': now,
                }
                if country_pf:
                    base_vals['country_id'] = country_pf.id
                dtc = self._parse_date((rv(row_l, 'insc_ent') or '').strip())
                if dtc:
                    base_vals['x_date_creation'] = dtc

                ctype_id = self._map_company_type((rv(row_l, 'forme') or '').strip())

                parent = by_tahiti.get(tahiti)
                if not parent:
                    parent_vals = {
                        'name': base_name,
                        'x_tahiti': tahiti,
                        'is_company': True,
                        'company_type': 'company',
                        'active': True,
                        **base_vals,
                    }
                    if ctype_id:
                        parent_vals['partner_company_type_id'] = ctype_id
                    parent = Partner.create(parent_vals)
                    by_tahiti[tahiti] = parent
                    created += 1
                else:
                    if ctype_id:
                        parent.write({'partner_company_type_id': ctype_id})

                # Pliage si 1 seul ETAB
                etab_count = sum(1 for _row_l, _t, _is, _ek, *_ in rows if _t == tahiti and _ek)
                fold_single = bool(etab_key and etab_count == 1)

                if is_est and etab_key and not fold_single:
                    child_vals = {
                        'name': f"Établissement {(rv(row_l, 'numeta') or '').strip() or etab_key} — {base_name}",
                        'x_etablissement': etab_key,
                        'parent_id': parent.id,
                        'is_company': True,
                        'company_type': 'company',
                        'active': True,
                        **base_vals,
                    }
                    if ctype_id:
                        child_vals['partner_company_type_id'] = ctype_id

                    existing_child = by_etab.get(etab_key)
                    if existing_child:
                        to_write = self._build_diff(existing_child, child_vals)
                        if to_write:
                            existing_child.write(to_write);
                            updated += 1
                        else:
                            skipped += 1
                    else:
                        child = Partner.create(child_vals);
                        created += 1
                        by_etab[etab_key] = child

                    # ID numbers & tags
                    self._ensure_id_number(parent, 'TAHITI', tahiti, code='tahiti')
                    self._ensure_id_number(by_etab.get(etab_key) or child, 'RTE_ETAB', etab_key, code='rte_etab')
                    self._apply_tags(parent, naf, (rv(row_l, 'effectif') or '').strip())
                    self._apply_tags(by_etab.get(etab_key) or child, naf, (rv(row_l, 'effectif') or '').strip())
                    self._set_employee_range(parent, (rv(row_l, 'effectif') or '').strip())

                    # Auto-assign images if enabled
                    if self.env['ir.config_parameter'].sudo().get_param('fp_rte_sync.auto_assign_images',
                                                                        default='True').lower() in (
                    '1', 'true', 'yes', 'y'):
                        Partner._auto_assign_image(parent)
                        if by_etab.get(etab_key):
                            Partner._auto_assign_image(by_etab.get(etab_key))

                else:
                    vals = {
                        'name': base_name,
                        'x_tahiti': tahiti,
                        'is_company': True,
                        'company_type': 'company',
                        'active': True,
                        **base_vals,
                    }
                    if ctype_id:
                        vals['partner_company_type_id'] = ctype_id
                    to_write = self._build_diff(parent, vals)
                    if to_write:
                        parent.write(to_write);
                        updated += 1
                    else:
                        skipped += 1

                    self._ensure_id_number(parent, 'TAHITI', tahiti, code='tahiti')
                    if etab_key:
                        self._ensure_id_number(parent, 'RTE_ETAB', etab_key, code='rte_etab')
                    self._apply_tags(parent, naf, (rv(row_l, 'effectif') or '').strip())
                    self._set_employee_range(parent, (rv(row_l, 'effectif') or '').strip())

                    # Auto-assign images if enabled
                    if self.env['ir.config_parameter'].sudo().get_param('fp_rte_sync.auto_assign_images',
                                                                        default='True').lower() in (
                    '1', 'true', 'yes', 'y'):
                        Partner._auto_assign_image(parent)

                # Archivage si inactif
                if import_only_active and not is_active_row:
                    if parent and parent.active:
                        parent.write({'active': False, 'x_rte_updated_at': now});
                        updated += 1

                count += 1
                if count % batch_size == 0:
                    self._cr.commit()
                    _logger.info('RTE sync: %s lignes traitées, commit.', count)

            if checksum:
                self.env['ir.config_parameter'].sudo().set_param('fp_rte_sync.last_checksum', checksum)

            msg = f"OK – créés:{created}, maj:{updated}, ignorés:{skipped}"
            run.write({'status': 'done', 'checksum': checksum, 'created_count': created, 'updated_count': updated,
                       'skipped_count': skipped, 'end': fields.Datetime.now(), 'message': msg})
            _logger.info('RTE sync done: %s', msg)
            return run

        except Exception as e:
            run.write({'status': 'failed', 'message': tools.ustr(e), 'end': fields.Datetime.now()})
            _logger.exception('RTE sync failed')
            return run
