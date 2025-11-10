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

# Import de queue_job (obligatoire pour cette version)
try:
    from odoo.addons.queue_job.delay import group
    from odoo.addons.queue_job.job import job

    QUEUE_JOB_AVAILABLE = True
except ImportError:
    QUEUE_JOB_AVAILABLE = False
    _logger.error("queue_job module not found - sync will run synchronously")


    # Décorateur dummy
    def job(*args, **kwargs):
        def decorator(func):
            return func

        if args and callable(args[0]):
            return args[0]
        return decorator


def _http_get(url, timeout=120):
    try:
        import requests
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Exception:
        from urllib.request import urlopen
        return urlopen(url, timeout=timeout).read()


class RteSyncRun(models.Model):
    _name = "rte.sync.run"
    _description = "Historique synchronisation RTE (ISPF)"

    start = fields.Datetime(default=lambda self: fields.Datetime.now())
    end = fields.Datetime()
    status = fields.Selection(
        [("done", "Terminé"), ("skipped", "Aucune nouvelle version"), ("failed", "Échec"), ("pending", "En attente")],
        default="pending",
        required=True,
    )
    message = fields.Text()
    created_count = fields.Integer()
    updated_count = fields.Integer()
    skipped_count = fields.Integer()
    checksum = fields.Char()
    job_uuid = fields.Char("Job UUID", index=True)

    def name_get(self):
        return [(r.id, f"RTE Sync {r.start} [{r.status}]") for r in self]


class RteSyncMixin(models.AbstractModel):
    _name = "rte.sync.mixin"
    _description = "Fonctions utilitaires RTE"

    def _set_employee_range_by_class(self, partner, class_code):
        """
        Affecte res.partner.employee_quantity_range depuis le code numérique de Classe_Effectifs.
        Construit le XML-ID : os_fp_rte_sync.res_partner_employee_quantity_range_XX
        Retourne True si affecté, False sinon.
        """
        if class_code is None or class_code == "":
            return False
        try:
            # classe fournie comme "08" / "7" / 7 --> convertissons en int
            code = int(str(class_code).strip())
        except Exception:
            return False

        # Si tes IDs XML sont 00..09 :
        xml_id = f"os_fp_rte_sync.res_partner_employee_quantity_range_{code:02d}"

        # Si au contraire tes IDs sont 01..10, décommente la ligne suivante et commente la précédente :
        # xml_id = f"os_fp_rte_sync.res_partner_employee_quantity_range_{code:02d}"

        rec = self.env.ref(xml_id, raise_if_not_found=False)
        if rec and "employee_quantity_range_id" in partner._fields:
            partner.write({"employee_quantity_range_id": rec.id})
            return True
        return False

    def _get_dataset_meta(self):
        raw = _http_get(f"https://www.data.gouv.fr/api/1/datasets/{DGOUV_DATASET_SLUG}/")
        return json.loads(raw.decode("utf-8"))

    def _get_rte_resource_meta(self, rid=None):
        rid = rid or self.env["ir.config_parameter"].sudo().get_param(
            "fp_rte_sync.resource_rid", default=RTE_RESOURCE_RID_DEFAULT
        )
        meta = self._get_dataset_meta()
        for res in meta.get("resources", []):
            if res.get("id") == rid:
                return res
        raise ValueError(f"Ressource {rid} introuvable sur {DGOUV_DATASET_SLUG}.")

    def _import_only_active(self):
        val = self.env["ir.config_parameter"].sudo().get_param("fp_rte_sync.import_only_active", default="True")
        return str(val).lower() in ("1", "true", "yes", "y")

    def _batch_commit(self):
        val = self.env["ir.config_parameter"].sudo().get_param("fp_rte_sync.batch_commit", default="1000")
        try:
            return max(100, int(val))
        except Exception:
            return 1000

    def _norm_naf(self, s):
        return re.sub(r"[^A-Z0-9*]", "", (s or "").upper())

    def _naf_to_xml_id(self, naf_code):
        normalized = self._norm_naf(naf_code).lower()
        return f"res_partner_category_ape_{normalized}"

    def _get_naf_name_from_ref(self, naf_code):
        xml_id = self._naf_to_xml_id(naf_code)
        try:
            tag = self.env.ref(f"os_fp_rte_sync.{xml_id}", raise_if_not_found=False)
            if tag:
                return tag.name
        except Exception:
            pass
        return self._norm_naf(naf_code)

    def _naf_allowed(self, naf_code):
        code = self._norm_naf(naf_code)
        white = (self.env["ir.config_parameter"].sudo().get_param("fp_rte_sync.naf_whitelist", "")).strip()
        if not white:
            return True
        for pat in [self._norm_naf(w) for w in white.split(",") if w.strip()]:
            if re.match("^" + pat.replace("*", ".*") + "$", code):
                return True
        return False

    def _country_pf(self):
        return self.env["res.country"].search([("code", "=", "PF")], limit=1)

    def _get_or_create_tag(self, parent_name, child_name):
        Cat = self.env["res.partner.category"].sudo()
        parent = Cat.search([("name", "=", parent_name), ("parent_id", "=", False)], limit=1)
        if not parent:
            parent = Cat.create({"name": parent_name})
        tag = Cat.search([("name", "=", child_name), ("parent_id", "=", parent.id)], limit=1)
        if not tag:
            tag = Cat.create({"name": child_name, "parent_id": parent.id})
        return tag

    def _apply_tags(self, partner, naf_code, effectif_label):
        tags = self.env["res.partner.category"].sudo()
        if naf_code:
            naf_name = self._get_naf_name_from_ref(naf_code)
            tags |= self._get_or_create_tag("APE", naf_name)
        # if effectif_label:
        #     tags |= self._get_or_create_tag("Effectif", effectif_label.strip())
        if tags:
            partner.write({"category_id": [(4, t.id) for t in tags]})

    def _company_type_to_xml_id(self, code_fjur):
        if not code_fjur:
            return None
        normalized = re.sub(r"[^a-z0-9_]", "", code_fjur.strip().lower().replace(" ", "_"))
        return f"partner_company_type_{normalized}"

    def _map_company_type(self, code_fjur):
        ctype_model = self.env["res.partner.company.type"].sudo()
        code = (code_fjur or "").strip()
        if not code:
            return False
        xml_id = self._company_type_to_xml_id(code)
        if xml_id:
            try:
                ctype = self.env.ref(f"os_fp_rte_sync.{xml_id}", raise_if_not_found=False)
                if ctype:
                    return ctype.id
            except Exception:
                pass
        has_code = "code" in ctype_model._fields
        domain = [("code", "=", code)] if has_code else [("name", "=", code)]
        ctype = ctype_model.search(domain, limit=1)
        if not ctype:
            vals = {"name": code}
            if has_code:
                vals["code"] = code
            ctype = ctype_model.create(vals)
        return ctype.id

    def _ensure_id_category(self, name, code=None):
        Cat = self.env["res.partner.id_category"].sudo()
        dom = [("name", "=", name)]
        if code and "code" in Cat._fields:
            dom = [("code", "=", code)]
        cat = Cat.search(dom, limit=1)
        if not cat:
            vals = {"name": name}
            if code and "code" in Cat._fields:
                vals["code"] = code
            cat = Cat.create(vals)
        return cat

    def _get_or_create_ispf_partner(self):
        """Récupère ou crée le partenaire ISPF (émetteur des numéros)"""
        ispf = self.env.ref('os_fp_rte_sync.res_partner_pf_2584_1', raise_if_not_found=False)
        if not ispf:
            # Créer l'ISPF s'il n'existe pas
            ispf_vals = {
                'name': 'ISPF - Institut de la Statistique de Polynésie française',
                'is_company': True,
                'company_type': 'company',
                'street': 'Immeuble Papineau',
                'street2': 'Avenue Pouvanaa a Oopa',
                'zip': '98713',
                'city': 'Papeete',
                'country_id': self._country_pf().id,
                'phone': '+689 40 47 34 34',
                'website': 'https://www.ispf.pf',
            }
            ispf = self.env['res.partner'].sudo().create(ispf_vals)
            # Créer l'ID externe
            self.env['ir.model.data'].sudo().create({
                'name': 'res_partner_pf_2584_1',
                'module': 'os_fp_rte_sync',
                'model': 'res.partner',
                'res_id': ispf.id,
            })
            _logger.info("Partenaire ISPF créé avec l'ID externe res_partner_pf_2584_1")
        return ispf

    def _ensure_id_number(self, partner, category_name, value, code=None, date_creation=None):
        """
        Crée ou met à jour un res.partner.id_number avec support des dates.
        Règle d'unicité : (category_id, name) unique -> ré-attache si existant sur un autre partner.
        """
        if not value:
            return

        cat = self._ensure_id_category(category_name, code=code or category_name.lower())
        IdNum = self.env["res.partner.id_number"].sudo()

        # --- RECHERCHE GLOBALE par (category_id, name), PAS par partner ---
        existing = IdNum.search([
            ("category_id", "=", cat.id),
            ("name", "=", value),
        ], limit=1)

        vals_common = {"status": "open"}
        # Emetteur ISPF si applicable
        if code in ('tahiti', 'rte_etab'):
            ispf = self._get_or_create_ispf_partner()
            vals_common["partner_issued_id"] = ispf.id

        # Dates
        if date_creation:
            vals_common.update({
                "date_issued": date_creation,
                "valid_from": date_creation,
            })

        if not existing:
            # Créer directement sur le partner cible
            create_vals = {"partner_id": partner.id, "category_id": cat.id, "name": value, **vals_common}
            IdNum.create(create_vals)
            _logger.debug("ID number créé: %s = %s sur partner %s", category_name, value, partner.id)
            return

        # Ici: déjà existant sur la base -> s'assurer qu'il est rattaché au bon partner
        to_write = {}
        if existing.partner_id.id != partner.id:
            to_write["partner_id"] = partner.id  # -> ré-attache (déplace) l'ID

        # Compléter les méta si manquants
        if "partner_issued_id" in IdNum._fields and not existing.partner_issued_id and "partner_issued_id" in vals_common:
            to_write["partner_issued_id"] = vals_common["partner_issued_id"]

        if date_creation:
            if "date_issued" in IdNum._fields and not existing.date_issued:
                to_write["date_issued"] = date_creation
            if "valid_from" in IdNum._fields and not existing.valid_from:
                to_write["valid_from"] = date_creation

        if to_write:
            existing.write(to_write)
            _logger.debug("ID number mis à jour/déplacé: %s = %s -> partner %s", category_name, value, partner.id)

    def _set_employee_range(self, partner, effectif_label):
        if not effectif_label:
            return
        Range = self.env["res.partner.employee_quantity_range"].sudo()
        r = Range.search([("name", "=", effectif_label.strip())], limit=1)
        if not r:
            r = Range.create({"name": effectif_label.strip()})
        if "employee_quantity_range_id" in partner._fields:
            partner.write({"employee_quantity_range_id": r.id})

    def _detect_columns(self, header_lower):
        def pick(*cands):
            for c in cands:
                for h in header_lower:
                    if c in h:
                        return h
            return None

        return {
            "tahiti": pick("numtah", "tahiti"),
            "numeta": pick("numeta"),
            "tahiti_etab": pick("numtah eta", "numtaheta", "num_tah_eta", "numtah_etab", "tahiti_etab"),
            "name_ent": pick("nom_ent"),
            "sigle_ent": pick("sigle_ent", "sigle"),
            "name_etab": pick("nom_etab"),
            "zip_ent": pick("code_postal_ent", "cp", "code postal"),
            "city_etab": pick("com_etab_libelle", "commune_etab", "ville_etab"),
            "street_num": pick("num_adr", "numero", "numéro"),
            "street_name": pick("rue", "adresse", "adresse 1", "adr1"),
            "street2_a": pick("immeuble"),
            "street2_b": pick("adrgeo"),
            "street2_c": pick("pk"),
            "street2_d": pick("quartier"),
            "naf_etab": pick("naf2008_etab", "naf_etab", "naf etab"),
            "naf_ent": pick("naf2008_ent", "naf_ent", "naf ent"),
            "forme": pick("code_fjur", "forme juridique"),
            "effectif": pick("classe_effectifs", "classe d'effectifs", "classe effectif", "effectif"),
            "effectif_class": pick("classe_effectifs", "classe_effectifs_code", "classe_effectifs_num",
                                   "classe_effectifs_id"),
            "rad_ent": pick("rad_ent", "radiation_ent"),
            "rad_etab": pick("rad_etab", "radiation_etab"),
            "insc_ent": pick("insc_ent"),
        }

    def _extract_zip(self, v):
        m = re.search(r"\b(\d{5})\b", (v or ""))
        return m.group(1) if m else ""

    def _parse_date(self, v):
        if not v:
            return None
        v = (v or "").strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(v[:10], fmt).date()
            except Exception:
                continue
        return None

    def _build_diff(self, rec, vals):
        if not rec:
            return vals
        changes = {}
        fields_map = rec._fields
        for k, v in vals.items():
            f = fields_map.get(k)
            if not f:
                continue
            cur = getattr(rec, k)
            if f.type == "many2one":
                cur_id = getattr(cur, "id", False) or False
                new_id = getattr(v, "id", v)
                if cur_id != (new_id or False):
                    changes[k] = v
            else:
                if cur != v:
                    changes[k] = v
        return changes

    def _get_partner_by_tahiti(self, tahiti):
        """Récupère un partenaire par son numéro TAHITI via res.partner.id_number"""
        if not tahiti:
            return self.env['res.partner'].browse()

        id_number = self.env['res.partner.id_number'].sudo().search([
            ('name', '=', tahiti),
            ('category_id.code', '=', 'tahiti')
        ], limit=1)

        return id_number.partner_id if id_number else self.env['res.partner'].browse()

    def _get_partner_by_etablissement(self, etab_key):
        """Récupère un partenaire par son numéro d'établissement via res.partner.id_number"""
        if not etab_key:
            return self.env['res.partner'].browse()

        id_number = self.env['res.partner.id_number'].sudo().search([
            ('name', '=', etab_key),
            ('category_id.code', '=', 'rte_etab')
        ], limit=1)

        return id_number.partner_id if id_number else self.env['res.partner'].browse()


class RteSyncWizard(RteSyncMixin, models.TransientModel):
    _name = "rte.sync.wizard"
    _description = "Assistant de synchronisation RTE"

    def action_sync_now(self):
        """Lance la synchronisation en arrière-plan via queue_job."""
        force = bool(self.env.context.get("force"))

        if not QUEUE_JOB_AVAILABLE:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "queue_job non disponible",
                    "message": "Installez le module queue_job pour utiliser la sync en arrière-plan",
                    "type": "warning",
                },
            }

        # Créer un job queue_job
        job_uuid = self.env["rte.sync.runner"].with_delay(channel='root:rte').run_sync(force=force)

        # Créer une entrée dans l'historique
        self.env["rte.sync.run"].create({
            "status": "pending",
            "message": "Sync en attente dans la queue...",
            "job_uuid": job_uuid,
        })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "RTE Sync lancée en arrière-plan",
                "message": f"Job UUID: {job_uuid}. Consultez l'historique pour suivre la progression.",
                "type": "success",
                "sticky": False,
            },
        }


class RteSyncRunner(RteSyncMixin, models.AbstractModel):
    _name = "rte.sync.runner"
    _description = "Exécution de la synchronisation RTE"

    # ------------------ Helpers de normalisation (nouveaux) ------------------

    def _canon_id(self, v):
        """
        Normalise un identifiant numérique (TAHITI/NUMETA) :
        - supprime espaces
        - convertit "123456.0" -> "123456"
        - conserve uniquement les chiffres
        """
        s = ("" if v is None else str(v)).strip()
        if not s:
            return ""
        if re.fullmatch(r"\d+\.0", s):
            return s[:-2]
        s = re.sub(r"\s", "", s)
        if re.fullmatch(r"\d+\.\d+", s):
            try:
                f = float(s)
                if f.is_integer():
                    return str(int(f))
            except Exception:
                pass
        return re.sub(r"\D", "", s)

    def _canon_etab_key(self, tahiti, numeta, tahiti_etab):
        """
        Clé canonique d'établissement :
        - si `tahiti_etab` fourni, tente d'extraire "TAHITI-NUMETA"
        - sinon compose "TAHITI-NUMETA" à partir des valeurs normalisées
        """
        t = self._canon_id(tahiti)
        n = self._canon_id(numeta)
        e = (tahiti_etab or "").strip()
        if e:
            parts = re.findall(r"\d+", e)
            if len(parts) >= 2:
                return f"{parts[0]}-{parts[1]}"
        return f"{t}-{n}" if (t and n) else ""

    # -------------------------------------------------------------------------

    @job(default_channel='root:rte')
    @api.model
    def run_sync(self, force=False):
        """
        Synchronisation RTE via l'API tabulaire data.gouv.fr.

        Correctifs principaux :
        - Pagination robuste via links.next (+ respect page_size <= 50)
        - Normalisation des identifiants (TAHITI/NUMETA/clé établissement)
        - Dé-duplication cross-pages et comptage distinct des établissements
        - Pliage correct des entreprises mono-établissement
        """
        run = self.env["rte.sync.run"].sudo().create({
            "status": "pending",
            "message": "Synchronisation en cours via API tabulaire...",
        })
        try:
            # RID de la ressource
            rid = self.env["ir.config_parameter"].sudo().get_param(
                "fp_rte_sync.resource_rid", default=RTE_RESOURCE_RID_DEFAULT
            )

            # Vérifier si une nouvelle version existe
            res_meta = self._get_rte_resource_meta(rid)
            checksum = (res_meta.get("checksum") or {}).get("value")
            last_checksum = self.env["ir.config_parameter"].sudo().get_param("fp_rte_sync.last_checksum")
            if not force and checksum and last_checksum and checksum == last_checksum:
                run.write({
                    "status": "skipped",
                    "checksum": checksum,
                    "message": "Aucune nouvelle version (checksum inchangé).",
                })
                _logger.info("RTE: checksum identique, skip.")
                return run

            # -------- API Tabulaire : profil / colonnes
            base_api_url = f"https://tabular-api.data.gouv.fr/api/resources/{rid}"
            _logger.info("RTE: Récupération du profil de la ressource...")
            profile_url = f"{base_api_url}/profile/"
            profile_raw = _http_get(profile_url, timeout=60)
            profile_data = json.loads(profile_raw.decode("utf-8"))
            headers = profile_data.get("profile", {}).get("header", [])
            if not headers:
                raise ValueError("Aucun header trouvé dans le profil de la ressource.")
            headers_lc = [h.strip().lower() for h in headers]
            header_map = self._detect_columns(headers_lc)
            _logger.info(f"RTE header_map: {header_map}")

            Partner = self.env["res.partner"].sudo()
            country_pf = self._country_pf()
            created = updated = skipped = 0
            now = fields.Datetime.now()
            import_only_active = self._import_only_active()
            batch_size = self._batch_commit()

            def rv(row_dict, key):
                """Retourne la valeur d'une colonne (mappée) en str (ou None)"""
                col = header_map.get(key)
                if not col:
                    return None
                for k in row_dict.keys():
                    if k.strip().lower() == col:
                        val = row_dict[k]
                        if val is None:
                            return None
                        return str(val) if not isinstance(val, str) else val
                return None

            # -------- Pagination (respect links.next, page_size <= 50) --------
            page = 1
            default_page_size = "50"
            page_size_cfg = self.env["ir.config_parameter"].sudo().get_param(
                "fp_rte_sync.api_page_size", default=default_page_size
            )
            try:
                page_size = max(10, min(50, int(page_size_cfg)))
            except Exception:
                page_size = 50

            naf_whitelist = self.env["ir.config_parameter"].sudo().get_param(
                "fp_rte_sync.naf_whitelist", default=""
            ).strip()
            naf_filter = ""
            if naf_whitelist:
                naf_codes = [self._norm_naf(code.strip()) for code in naf_whitelist.split(",") if code.strip()]
                if naf_codes:
                    naf_filter = ",".join(naf_codes)

            total_rows = 0
            _logger.info(
                f"RTE: Début sync paginée (page_size={page_size}, naf_filter={naf_filter or 'aucun'})..."
            )

            all_rows = []
            next_url = None
            while True:
                if next_url:
                    data_url = next_url
                else:
                    data_url = f"{base_api_url}/data/?page={page}&page_size={page_size}"
                    if naf_filter:
                        data_url += f"&NAF2008_ETAB__in={naf_filter}"
                _logger.info(f"RTE: Récupération page {page}...")
                try:
                    data_raw = _http_get(data_url, timeout=120)
                    data_response = json.loads(data_raw.decode("utf-8"))
                except Exception as e:
                    _logger.error(f"RTE: Erreur lors de la récupération de la page {page}: {e}")
                    break

                rows_data = data_response.get("data", [])
                meta = data_response.get("meta", {})
                total = meta.get("total", 0)
                if page == 1:
                    total_rows = total
                    _logger.info(f"RTE: Total de lignes à traiter (annonce API): {total_rows}")
                if not rows_data:
                    _logger.info("RTE: Aucune donnée sur cette page, fin de pagination.")
                    break

                _logger.info(f"RTE: Page {page} - {len(rows_data)} lignes récupérées")
                all_rows.extend(rows_data)

                links = data_response.get("links", {})
                next_url = links.get("next")
                if not next_url:
                    _logger.info("RTE: Dernière page atteinte.")
                    break
                page += 1

            _logger.info(f"RTE: {len(all_rows)} lignes totales récupérées via l'API tabulaire")

            # -------- 1ère passe : filtrage + collecte clés (dé-dup) ----------
            rows = []
            tahitis_set, etab_keys_set = set(), set()
            uniq_etabs_by_tahiti = {}   # tahiti -> set(etab_key)
            seen_pairs = set()          # (tahiti_norm, etab_key_norm | __NO_ETAB__)

            _logger.info("RTE: 1ère passe - filtrage et collecte...")
            for row_dict in all_rows:
                tahiti_raw = (rv(row_dict, "tahiti") or "").strip()
                numeta_raw = (rv(row_dict, "numeta") or "").strip()
                tahiti_etab_raw = (rv(row_dict, "tahiti_etab") or "").strip()

                tahiti = self._canon_id(tahiti_raw)
                if not tahiti:
                    continue
                numeta = self._canon_id(numeta_raw)
                tahiti_etab = tahiti_etab_raw

                is_establishment = bool(tahiti_etab or numeta)
                etab_key = self._canon_etab_key(tahiti, numeta, tahiti_etab)

                naf = (rv(row_dict, "naf_etab") or rv(row_dict, "naf_ent") or "").strip()
                rad_ent = (rv(row_dict, "rad_ent") or "").strip()
                rad_etab = (rv(row_dict, "rad_etab") or "").strip()
                is_active_row = not bool(rad_etab if is_establishment else rad_ent)

                if not self._naf_allowed(naf):
                    skipped += 1
                    continue
                pair_key = (tahiti, etab_key or "__NO_ETAB__")
                if pair_key in seen_pairs:
                    # doublon cross-pages => ignorer
                    continue
                seen_pairs.add(pair_key)

                rows.append((row_dict, tahiti, is_establishment, etab_key, naf, is_active_row))
                tahitis_set.add(tahiti)
                if etab_key:
                    etab_keys_set.add(etab_key)
                    uniq_etabs_by_tahiti.setdefault(tahiti, set()).add(etab_key)

            _logger.info("RTE: Filtrage terminé - %s lignes valides, %s ignorées", len(rows), skipped)

            # -------- Prefetch existants via res.partner.id_number ------------
            by_tahiti = {}
            by_etab = {}
            if tahitis_set:
                id_numbers_tahiti = self.env['res.partner.id_number'].sudo().search([
                    ('name', 'in', list(tahitis_set)),
                    ('category_id.code', '=', 'tahiti')
                ])
                by_tahiti = {idn.name: idn.partner_id for idn in id_numbers_tahiti if idn.partner_id}
            if etab_keys_set:
                id_numbers_etab = self.env['res.partner.id_number'].sudo().search([
                    ('name', 'in', list(etab_keys_set)),
                    ('category_id.code', '=', 'rte_etab')
                ])
                by_etab = {idn.name: idn.partner_id for idn in id_numbers_etab if idn.partner_id}
            _logger.info("RTE: Prefetch - %s parents, %s établissements trouvés", len(by_tahiti), len(by_etab))

            # -------- 2e passe : upsert --------------------------------------
            count = 0
            for row_dict, tahiti, is_est, etab_key, naf, is_active_row in rows:
                name_ent = (rv(row_dict, "name_ent") or "").strip()
                sigle_ent = (rv(row_dict, "sigle_ent") or "").strip()
                base_name = f"{name_ent} ({sigle_ent})" if (name_ent and sigle_ent) else (name_ent or f"Entreprise {tahiti}")

                street = " ".join(
                    x for x in [(rv(row_dict, "street_num") or "").strip(), (rv(row_dict, "street_name") or "").strip()] if x
                )
                street2 = " - ".join(
                    x for x in [
                        (rv(row_dict, "street2_a") or "").strip(),
                        (rv(row_dict, "street2_b") or "").strip(),
                        (rv(row_dict, "street2_c") or "").strip(),
                        (rv(row_dict, "street2_d") or "").strip(),
                    ] if x
                )
                zip_ent = self._extract_zip(rv(row_dict, "zip_ent"))
                city_etab = (rv(row_dict, "city_etab") or "").strip()

                base_vals = {
                    "street": street,
                    "street2": street2,
                    "zip": zip_ent,
                    "city": city_etab,
                    "x_naf": naf,
                    "x_rte_updated_at": now,
                }
                if country_pf:
                    base_vals["country_id"] = country_pf.id

                date_creation = self._parse_date((rv(row_dict, "insc_ent") or "").strip())
                ctype_id = self._map_company_type((rv(row_dict, "forme") or "").strip())

                parent = by_tahiti.get(tahiti)
                if not parent:
                    parent_vals = {
                        "name": base_name,
                        "is_company": True,
                        "company_type": "company",
                        "active": True,
                        **base_vals,
                    }
                    if ctype_id:
                        parent_vals["partner_company_type_id"] = ctype_id
                    parent = Partner.create(parent_vals)
                    by_tahiti[tahiti] = parent
                    created += 1
                    _logger.debug(f"RTE: Création parent {tahiti}")
                    if not parent.image_1920:
                        try:
                            Partner._auto_assign_image_from_generator(parent)
                        except Exception as e:
                            _logger.warning("Image assignment failed: %s", e)
                else:
                    _logger.debug(f"RTE: Parent {tahiti} existe déjà (ID: {parent.id})")
                    if ctype_id and (
                        not parent.partner_company_type_id or parent.partner_company_type_id.id != ctype_id
                    ):
                        parent.write({"partner_company_type_id": ctype_id})

                # Comptage distinct des établissements
                etab_count = len(uniq_etabs_by_tahiti.get(tahiti, set()))
                fold_single = bool(etab_key and etab_count == 1)

                if is_est and etab_key and not fold_single:
                    # Plusieurs établissements : enfant distinct
                    child_vals = {
                        "name": f"{base_name}",
                        "parent_id": parent.id,
                        "is_company": True,
                        "company_type": "company",
                        "active": True,
                        **base_vals,
                    }
                    if ctype_id:
                        child_vals["partner_company_type_id"] = ctype_id

                    existing_child = by_etab.get(etab_key)
                    if existing_child:
                        to_write = self._build_diff(existing_child, child_vals)
                        if to_write:
                            existing_child.write(to_write)
                            updated += 1
                        child = existing_child
                    else:
                        child = Partner.create(child_vals)
                        created += 1
                        by_etab[etab_key] = child
                        if not child.image_1920:
                            try:
                                Partner._auto_assign_image_from_generator(child)
                            except Exception as e:
                                _logger.warning("Image assignment failed: %s", e)

                    # ID numbers (avec dates)
                    self._ensure_id_number(parent, "TAHITI", tahiti, code="tahiti", date_creation=date_creation)
                    self._ensure_id_number(
                        by_etab.get(etab_key) or child,
                        "RTE_ETAB",
                        etab_key,
                        code="rte_etab",
                        date_creation=date_creation
                    )

                    self._apply_tags(parent, naf, (rv(row_dict, "effectif") or "").strip())
                    self._apply_tags(by_etab.get(etab_key) or child, naf, (rv(row_dict, "effectif") or "").strip())
                    # self._set_employee_range(parent, (rv(row_dict, "effectif") or "").strip())
                    # 1) tentative par CODE (Classe_Effectifs)
                    class_raw = rv(row_dict, "effectif_class")
                    ok = False
                    if class_raw is not None:
                        ok = self._set_employee_range_by_class(parent, class_raw)

                    # 2) fallback par LIBELLÉ (si jamais la colonne est textuelle dans un autre export)
                    if not ok:
                        self._set_employee_range(parent, (rv(row_dict, "effectif") or "").strip())

                else:
                    # Un seul établissement (ou pas d'établissement) : tout sur le parent (pliage)
                    self._ensure_id_number(parent, "TAHITI", tahiti, code="tahiti", date_creation=date_creation)
                    if etab_key:
                        self._ensure_id_number(parent, "RTE_ETAB", etab_key, code="rte_etab",
                                               date_creation=date_creation)
                        # IMPORTANT : éviter la création d'un enfant plus tard
                        by_etab[etab_key] = parent

                    self._apply_tags(parent, naf, (rv(row_dict, "effectif") or "").strip())
                    # self._set_employee_range(parent, (rv(row_dict, "effectif") or "").strip())

                    # 1) tentative par CODE (Classe_Effectifs)
                    class_raw = rv(row_dict, "effectif_class")
                    ok = False
                    if class_raw is not None:
                        ok = self._set_employee_range_by_class(parent, class_raw)

                    # 2) fallback par LIBELLÉ (si jamais la colonne est textuelle dans un autre export)
                    if not ok:
                        self._set_employee_range(parent, (rv(row_dict, "effectif") or "").strip())

                    if not parent.image_1920:
                        try:
                            Partner._auto_assign_image_from_generator(parent)
                        except Exception as e:
                            _logger.warning("Image assignment failed: %s", e)

                # Désactivation si demandé et ligne inactive
                if import_only_active and not is_active_row:
                    if parent and parent.active:
                        parent.write({"active": False, "x_rte_updated_at": now})
                        updated += 1

                count += 1
                if count % batch_size == 0:
                    self.env.cr.commit()
                    _logger.info("RTE sync: %s lignes traitées (commit lot)", count)

            # Fin de sync / persistance checksum
            if checksum:
                self.env["ir.config_parameter"].sudo().set_param("fp_rte_sync.last_checksum", checksum)

            msg = f"OK – créés:{created}, maj:{updated}, ignorés:{skipped}"
            run.write({
                "status": "done",
                "checksum": checksum,
                "created_count": created,
                "updated_count": updated,
                "skipped_count": skipped,
                "end": fields.Datetime.now(),
                "message": msg,
            })
            _logger.info("RTE sync done: %s", msg)
            return run

        except Exception as e:
            run.write({
                "status": "failed",
                "message": tools.ustr(e),
                "end": fields.Datetime.now()
            })
            _logger.exception("RTE sync failed")
            raise
