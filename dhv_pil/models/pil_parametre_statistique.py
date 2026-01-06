from odoo.exceptions import ValidationError
from odoo import fields, models, api
from datetime import datetime
from datetime import date

class PilParamsStats(models.TransientModel):
    _name = 'pil.params.stats'
    _inherit = ['multi.step.wizard.mixin']
    _description = 'Description'

    debutdatedemande=fields.Date(default=date(datetime.today().year,1,1), required=True )
    findatedemande=fields.Date(default=str(datetime.now().date()),required=True)
    type_sortie=fields.Selection(selection=[('pdf','pdf'),('xls','xls'),('xlsx','xlsx')],default='pdf',required=True)
    anneedemande= fields.Integer(default=datetime.today().year, required=True )
    periodedemande=fields.Selection(selection=[('Trim1','Trim 1'),('Trim2','Trim 2'),('Trim3','Trim3'),('Sem1','Semestre 1'),('Sem2','Semestre 2')],default='' )


    @api.onchange('anneedemande','periodedemande')
    def onchange_annee(self):
            if (self.anneedemande>0):
                if (self.periodedemande!=''):
                    periode=self.periodedemande

                    if  periode=='Trim1':
                            now=date(self.anneedemande,1,1)
                            self.debutdatedemande=now
                            self.findatedemande=date(self.anneedemande,3,31)
                    elif  periode== 'Trim2':
                            now=date(self.anneedemande,4,1)
                            self.debutdatedemande=now
                            self.findatedemande=date(self.anneedemande,6,30)
                    elif  periode== 'Trim3':
                            now=date(self.anneedemande,7,1)
                            self.debutdatedemande=now
                            self.findatedemande=date(self.anneedemande,9,30)

                    elif  periode== 'Trim4':
                            now=date(self.anneedemande,10,1)
                            self.debutdatedemande=now
                            self.findatedemande=date(self.anneedemande,12,31)
                    elif  periode== 'Sem1':
                            now=date(self.anneedemande,1,1)
                            self.debutdatedemande=now
                            self.findatedemande=date(self.anneedemande,6,30)
                    elif  periode== 'Sem2':
                            now=date(self.anneedemande,7,1)
                            self.debutdatedemande=now
                            self.findatedemande=date(self.anneedemande,12,31)

                else:
                    now=datetime.date(self.anneedemande,1,1)
                    self.debutdatedemande=now
                    self.findatedemande=date(self.anneedemande,12,31)

            else:
                self.anneedemande=datetime.today().year
                self.debutdatedemande=date(self.anneedemande,1,1)
                self.findatedemande=date(self.anneedemande,12,31)



    def action_print(self,url):
        self.ensure_one()
        parametres=''
        if self.type_sortie :
            url += self.type_sortie

        if self.debutdatedemande :
            parametres= '?debutDatedemande='+  (self.debutdatedemande.strftime("%d-%m-%Y"))

        if self.findatedemande :
            parametres +='&finDatedemande=' +  (self.findatedemande.strftime("%d-%m-%Y"))

        if parametres !='' :
            url += parametres

        action = {
            'type': 'ir.actions.act_url',
            'name': ('Impression Tableau de bord'),
            'url': url,
            'target': 'new',
        }
        return action

    def action_print_tableaubord(self):
        self.ensure_one()
        url = 'https://odoo:Jasper4Odoo@www.jasper.gov.pf/jasperserver/rest_v2/reports/DHV/PIL/Tableau_de_bord_pil.'
        return self.action_print(url)

    def action_print_suivi(self):
        self.ensure_one()
        url = 'https://odoo:Jasper4Odoo@www.jasper.gov.pf/jasperserver/rest_v2/reports/DHV/PIL/Situation_Suivi_Pil.'
        return self.action_print(url)
