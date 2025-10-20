from odoo import fields, models, tools, api


class FactureGlobale(models.Model):
    _auto = False
    _name = 'manureva.facture_globale'
    _description = 'Facture globale'
    _order = 'annee, mois, code_usager, nom_aerodrome, type_aeronef_code'
    _rec_name = 'nom_aerodrome'

    annee = fields.Integer(
        group_operator="count_distinct",
        string="Année",
        readonly=True,
    )
    mois = fields.Integer(
        group_operator="count_distinct",
        string="Mois",
        readonly=True,
    )
    code_usager = fields.Char(
        string="Code usager",
        readonly=True,
    )
    date_debut = fields.Date(
        string="Début",
        readonly=True,
    )
    entete = fields.Char(
        string="Entête",
        readonly=True,
    )
    signataire = fields.Char(
        string="Signataire",
        readonly=True,
    )
    code_aerodrome = fields.Char(
        string="Code aérodrome",
        readonly=True,
    )
    nom_aerodrome = fields.Char(
        group_operator="count_distinct",
        string="Nom aérodrome",
        readonly=True,
    )
    type_aeronef_code = fields.Char(
        string="Type d'aeronef",
        readonly=True,
    )
    se_bp = fields.Char(
        string="BP service",
        readonly=True,
    )
    se_cp = fields.Char(
        string="CP service",
        readonly=True,
    )
    se_commune = fields.Char(
        string="Commune service",
        readonly=True,
    )
    ile = fields.Char(
        string="Ile",
        readonly=True,
    )
    pays = fields.Char(
        string="Pays",
        readonly=True,
    )
    telephone = fields.Char(
        string="Téléphone",
        readonly=True,
    )
    fax = fields.Char(
        string="Fax",
        readonly=True,
    )
    min = fields.Char(
        string="Code ministère",
        readonly=True,
    )
    ser = fields.Char(
        string="Code service",
        readonly=True,
    )
    etmi = fields.Char(
        string="Entete ministère",
        readonly=True,
    )
    etse = fields.Char(
        string="Entete service",
        readonly=True,
    )
    bureau = fields.Char(
        string="Bureau",
        readonly=True,
    )
    service = fields.Char(
        string="Service",
        readonly=True,
    )
    ministere = fields.Char(
        string="Ministère",
        readonly=True,
    )
    usager = fields.Char(
        string="Opérateur",
        readonly=True,
    )
    rue = fields.Char(
        string="Rue",
        readonly=True,
    )
    rue2 = fields.Char(
        string="Rue 2",
        readonly=True,
    )
    cp = fields.Char(
        string="CP",
        readonly=True,
    )
    commune = fields.Char(
        string="Commune",
        readonly=True,
    )
    usager_id = fields.Char(
        group_operator="count_distinct",
        string="Opérateur ID",
        readonly=True,
    )
    atterissage = fields.Integer(
        string="Atterissage",
        readonly=True,
    )
    passagers = fields.Integer(
        string="Passagers",
        readonly=True,
    )
    balisage = fields.Integer(
        string="Balisage",
        readonly=True,
    )
    montant_total = fields.Integer(
        string="Montant Total",
        readonly=True,
    )
    taux_reduit = fields.Float(
        string="Taux réduit",
        readonly=True,
    )
    taux_normal = fields.Float(
        string="Taux normal",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW 
            %s as (
            %s
            %s
            %s
            %s
            %s )""" % (self._table, self._select(), self._from(), self._where(), self._group_by(), self._order_by()))

    def _select(self):
        select_str = """
                SELECT     
                 tout.annee
                , tout.mois
                , make_date(tout.annee, tout.mois, 1) date_debut
                , tout.code_usager
                , tout.code_aerodrome
                , tout.type_aeronef_code
                , max (tout.nom_aerodrome) nom_aerodrome
                , max (tout.se_bp) se_bp
                , max (tout.se_cp) se_cp
                , max (tout.se_commune) se_commune
                , max (tout.ile) ile
                , max (tout.pays) pays
                , max (tout.telephone) telephone
                , max (tout.fax) fax
                , max (tout.min) min
                , max (tout.ser) ser
                , max (tout.etmi) etmi
                , max (tout.etse) etse
                , max (tout.bureau) bureau
                , max (tout.service) service
                , max (tout.ministere) ministere
                , max (tout.usager) usager
                , max (tout.rue) rue
                , max (tout.rue2) rue2
                , max (tout.cp) cp
                , max (tout.commune) commune
                , max (tout.usager_id) usager_id
                , max (tout.signataire) signataire
                , max (tout.comment) entete
                , sum(tout."Atterissage") atterissage
                , sum(tout."Passagers") passagers
                , sum(tout."Balisage") balisage
                , sum(COALESCE(tout."Atterissage"+tout."Passagers"+tout."Balisage",
                               tout."Atterissage"+tout."Balisage",
                               tout."Atterissage"+tout."Passagers",
                               tout."Passagers"+tout."Balisage",
                               tout."Atterissage",
                               tout."Passagers",
                               tout."Balisage"
                               )) montant_total
                , max(tvn.taux)/100 taux_normal
                , max(tvr.taux)/100 taux_reduit
                , row_number() over (order by 1, 2, 3, 4) id
        """
        return select_str

    def _from(self):
        from_str = """
                FROM (
			        select
                -- ministère
                    mi.comment ministere,
                    mi.initials min,
                    com.report_header etmi,
                
                -- service
                    upper(se.name) service,
                    upper(se.street) bureau,
                    'B.P. '||se.pobox se_bp,
                    se.city se_commune,
                    se.zip se_cp,
                    se.phone telephone,
                    se.fax fax,
                    se.initials ser,
                    
                    upper(cos.report_header) etse,
                    
                    cs.name ile,
                    
                    co.name pays,
                
                    upper(ug.cie_oaci) code_usager,
                    pn.street rue,
                    pn.street2 rue2,
                    pn.zip cp,
                    pn.city commune,
               
                  pe.annee annee
                , pe.mois mois
                , lf.atterrissage "Atterissage"
                , lf.passager "Passagers"
                , lf.balisage "Balisage"
                , ad.name code_aerodrome
                , ad.aerodrome nom_aerodrome
                , te.name type_aeronef_code
                , pn.name usager
                , pe.usager_id
                , di.name signataire
                , pn.comment 
                
                from 	
                    manureva_ligne_facture lf
                    left join manureva_facture fa on lf.facture_id = fa.id
                    left join manureva_usager ug on fa.usager_id = ug.id
                    left join res_partner pt on ug.partner_id = pt.id
                    left join manureva_periode pe on fa.periode_id = pe.id
                    left join manureva_aerodrome ad on fa.aerodrome_id = ad.id
                    left join manureva_type_aerodrome ta on ad.type_aerodrome_id = ta.id
                    left join manureva_type_aeronef te on lf.type_aeronef_id = te.id
                    left join res_partner se on se.id = 4239
                    left join res_country co on se.country_id = co.id
                    left join res_partner mi on se.parent_id = mi.id
                    left join res_city ct on ct.id = se.city_id
                    left join res_company cos on cos.partner_id = se.id
                    left join res_company com on com.partner_id = mi.id
                    left join res_country_state cs on se.state_id = cs.id
                    left join manureva_tva tr on tr.type_taxe_id = 1
                    left join manureva_tva tn on tn.type_taxe_id = 2
                    left join res_partner di on di.parent_id=se.id and di.function='Directeur'
                    left join res_partner pn on ug.partner_id = pn.id
				) as tout
                , manureva_type_taxe		ttn
                , manureva_type_taxe		ttr
                , manureva_tva				tvn
                , manureva_tva				tvr
        """
        return from_str

    def _where(self):
        where_str = """
                 -- TVA normale
                 WHERE ttn.name='Normal'
                 and tvn.type_taxe_id=ttn.id
                -- TVA réduite
                 and ttr.name='Réduit'
                 and tvr.type_taxe_id=ttr.id
        """
        return where_str

    def _group_by(self):
        group_by_str = """
                GROUP BY 1, 2, 3, 4, 5, 6
        """
        return group_by_str

    def _order_by(self):
        order_by_str = """
                ORDER BY 1, 2, 4, 6, 7
        """
        return order_by_str

