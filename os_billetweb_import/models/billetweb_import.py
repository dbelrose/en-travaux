from odoo import models, fields, api, _
from io import StringIO
from odoo.exceptions import UserError
from datetime import datetime
from odoo.fields import Date

import datetime
import base64
import csv


# class BilletWebImport(models.TransientModel):
    # _name = 'os.billetweb.import'
    # _description = 'Importation des virements BilletWeb'
    #
    # file_data = fields.Binary(string="Fichier CSV")
    # file_name = fields.Char(string="Nom du fichier")
    # display_result = fields.Selection([
    #     ('payment', 'Paiements'),
    #     ('invoice', 'Factures')
    # ], default=lambda self: self.env.context.get('default_display_result', 'invoice'))
    #
    # def action_import_csv(self):
    #     created_payments = []
    #     created_invoices = []
    #
    #     if not self.file_data:
    #         raise ValueError("Aucun fichier fourni")
    #
    #     decoded_file = base64.b64decode(self.file_data)
    #     csvfile = io.StringIO(decoded_file.decode("utf-8-sig"))
    #     reader = csv.DictReader(csvfile, delimiter=';', quotechar='"')
    #
    #     for row in reader:
    #         utilisateur = row['Utilisateur'].strip()
    #         montant = float(row['Montant'].replace(',', '.'))
    #         date = datetime.strptime(row['Date'], '%Y-%m-%d').date()
    #         iban = row['IBAN'].replace(' ', '')
    #         annee = int(row['Année'])
    #
    #         if not utilisateur or not iban:
    #             continue
    #
    #         # 1. Créer ou trouver la société BilletWeb.fr
    #         billetweb = self.env['res.partner'].search([('name', '=', 'BilletWeb.fr')], limit=1)
    #         if not billetweb:
    #             billetweb = self.env['res.partner'].create({
    #                 'name': 'BilletWeb.fr',
    #                 'is_company': True,
    #                 'email': 'contact@billetweb.fr',
    #                 'website': 'https://www.billetweb.fr',
    #                 'country_id': self.env.ref('base.fr').id,
    #             })
    #
    #         # 2. Créer ou trouver la banque à partir de l'IBAN
    #         bank_code = iban[4:9] if len(iban) > 9 else 'UNKNOWN'
    #         bank = self.env['res.bank'].search([('bic', '=', bank_code)], limit=1)
    #         if not bank:
    #             bank = self.env['res.bank'].create({
    #                 'name': f'Banque {bank_code}',
    #                 'bic': bank_code,
    #             })
    #
    #         # 3. Créer ou trouver l'utilisateur
    #         utilisateur_partner = self.env['res.partner'].search([('name', '=', utilisateur)], limit=1)
    #         if not utilisateur_partner:
    #             utilisateur_partner = self.env['res.partner'].create({
    #                 'name': utilisateur,
    #                 'is_company': True,
    #             })
    #
    #         # 3.1 Créer la société liée si besoin
    #         company = self.env['res.company'].search([('partner_id', '=', utilisateur_partner.id)], limit=1)
    #         if not company:
    #             company = self.env['res.company'].create({
    #                 'name': utilisateur_partner.name,
    #                 'partner_id': utilisateur_partner.id,
    #                 'currency_id': self.env.ref('base.XPF').id,  # ou 'base.EUR' selon le cas
    #             })
    #
    #         # 3.2 Créer l'accès de l'utilisateur s'il a un mail et qu'il n'existe pas
    #         if utilisateur_partner.email:
    #             # Vérifie s'il a déjà un compte utilisateur
    #             existing_user = self.env['res.users'].search([
    #                 ('partner_id', '=', utilisateur_partner.id)
    #             ], limit=1)
    #
    #             if not existing_user:
    #                 user = self.env['res.users'].create({
    #                     'name': utilisateur_partner.name,
    #                     'login': utilisateur_partner.email,
    #                     'email': utilisateur_partner.email,
    #                     'partner_id': utilisateur_partner.id,
    #                     'company_ids': [(6, 0, [company.id])],
    #                     'company_id': company.id,
    #                     'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
    #                 })
    #
    #             # 3.2.1 Envoi de l'email avec le lien vers les factures fournisseur
    #             # base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #             # url = f"{base_url}/web#model=account.move&view_type=list&menu_id=&action=&domain=%5B('partner_id','=',{utilisateur_partner.id}),('move_type','=','in_invoice')%5D"
    #
    #             template = self.env.ref('os_billetweb_import.mail_template_billetweb_factures')
    #             base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #             facture_url = f"{base_url}/web#model=account.move&view_type=list&domain=%5B('partner_id','=',{utilisateur_partner.id}),('move_type','=','in_invoice')%5D"
    #
    #             template.with_context(access_url=facture_url).send_mail(
    #                 0,  # ou un ID factice si tu veux juste le mail
    #                 # facture.id if facture else 0,  # ou un ID factice si tu veux juste le mail
    #                 force_send=True
    #             )
    #
    #         # 4. Créer ou trouver le compte bancaire (IBAN)
    #         bank_account = self.env['res.partner.bank'].search([
    #             ('acc_number', '=', iban),
    #             ('partner_id', '=', utilisateur_partner.id)
    #         ], limit=1)
    #         if not bank_account:
    #             bank_account = self.env['res.partner.bank'].create({
    #                 'acc_number': iban,
    #                 'partner_id': utilisateur_partner.id,
    #                 'bank_id': bank.id,
    #             })
    #
    #         # 5. Créer le paiement s'il n'existe pas encore
    #         payment = self.env['account.payment'].search([
    #             ('partner_id', '=', utilisateur_partner.id),
    #             ('amount', '=', abs(montant)),
    #             ('date', '=', date),
    #         ], limit=1)
    #         if not payment:
    #             payment = self.env['account.payment'].create({
    #                 'payment_type': 'inbound' if montant > 0 else 'outbound',
    #                 'partner_type': 'customer',
    #                 'partner_id': utilisateur_partner.id,
    #                 'amount': abs(montant),
    #                 'currency_id': self.env.ref('base.EUR').id,
    #                 'journal_id': self.env['account.journal'].search([('type', '=', 'bank')], limit=1).id,
    #                 'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
    #                 'date': date,
    #             })
    #             created_payments.append(payment.id)
    #
    #     # 6. Créer les factures de commission mensuelles à 10%
    #     self._create_commission_invoices(created_invoices)
    #
    #     if self.display_result == 'payment' and created_payments:
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'name': 'Paiements importés',
    #             'res_model': 'account.payment',
    #             'view_mode': 'tree,form',
    #             'domain': [('id', 'in', created_payments)],
    #             'target': 'main',
    #         }
    #
    #     if self.display_result == 'invoice' and created_invoices:
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'name': 'Factures générées',
    #             'res_model': 'account.move',
    #             'view_mode': 'tree,form',
    #             'domain': [('id', 'in', created_invoices)],
    #             'target': 'main',
    #         }
    #
    #     # fallback : affichage des paiements par défaut
    #     if created_payments:
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'name': 'Paiements importés',
    #             'res_model': 'account.payment',
    #             'view_mode': 'tree,form',
    #             'domain': [('id', 'in', created_payments)],
    #             'target': 'main',
    #         }
    #
    #     # sinon affichage des factures
    #     if created_invoices:
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'name': 'Factures générées',
    #             'res_model': 'account.move',
    #             'view_mode': 'tree,form',
    #             'domain': [('id', 'in', created_invoices)],
    #             'target': 'main',
    #         }
    #
    #     return {'type': 'ir.actions.act_window_close'}
    #
    # def _create_commission_invoices(self, created_invoices):
    #     user_company = self.env.user.company_id
    #     journal = self.env['account.journal'].search([
    #         ('type', '=', 'sale'),
    #         ('company_id', '=', user_company.id)
    #     ], limit=1)
    #
    #     xpf_currency = self.env['res.currency'].search([('name', '=', 'XPF')], limit=1)
    #     lignes = self.env['account.payment'].search([('journal_id.type', '=', 'bank')])
    #
    #     # Regrouper les paiements par (partenaire, année, mois)
    #     paiements_groupés = {}
    #     for p in lignes:
    #         if not p.partner_id or not p.date:
    #             continue
    #         key = (p.partner_id.id, p.date.year, p.date.month)
    #         paiements_groupés.setdefault(key, []).append(p)
    #
    #     for (partner_id, year, month), paiements in paiements_groupés.items():
    #         ref = f"Commission BilletWeb {month:02d}/{year}"
    #         existing = self.env['account.move'].search([
    #             ('partner_id', '=', partner_id),
    #             ('ref', '=', ref),
    #             ('move_type', '=', 'out_invoice')
    #         ], limit=1)
    #         if existing:
    #             continue
    #
    #         # Trouver un compte de revenu
    #         account = self.env['account.account'].search([
    #             ('code', '=', '62220000'), ('company_id', '=', user_company.id)
    #         ], limit=1)
    #         if not account:
    #             account = self.env['account.account'].search([
    #                 ('user_type_id.type', '=', 'income'),
    #                 ('company_id', '=', user_company.id)
    #             ], limit=1)
    #         if not account:
    #             raise ValueError("Aucun compte de revenu trouvé pour générer la facture.")
    #
    #         invoice_lines = []
    #         for p in paiements:
    #             commission = round(p.amount * 1000 / 8.38, 0)
    #             invoice_lines.append((0, 0, {
    #                 'name': f"Commission sur virement du {p.date.strftime('%d/%m/%Y')} ({p.amount} EUR)",
    #                 'quantity': 0.1,
    #                 'price_unit': commission,
    #                 'account_id': account.id,
    #             }))
    #
    #         # Date de facture = 1er jour du mois suivant
    #         next_month = month + 1
    #         next_year = year
    #         if next_month > 12:
    #             next_month = 1
    #             next_year += 1
    #         invoice_date = datetime(next_year, next_month, 1).date()
    #
    #         invoice = self.env['account.move'].create({
    #             'partner_id': partner_id,
    #             'move_type': 'out_invoice',
    #             'currency_id': xpf_currency.id,
    #             'invoice_date': invoice_date,
    #             'ref': ref,
    #             'journal_id': journal.id,
    #             'invoice_line_ids': invoice_lines,
    #         })
    #         created_invoices.append(invoice.id)

class BilletwebImport(models.TransientModel):
    _name = 'billetweb.import'
    _description = 'Assistant d\'importation de participants'

    import_date = fields.Datetime(string='Date d\'importation', default=fields.Datetime.now)
    name = fields.Char(string='Nom', compute='_compute_name', store=True)
    file_data = fields.Binary(string="Fichier CSV", required=True)
    file_name = fields.Char(string="Nom du fichier")

    @api.depends('import_date')
    def _compute_name(self):
        for record in self:
            record.name = f"Importation du {record.import_date}"

    def billetweb_import_action(self):
        if not self.file_data:
            raise UserError(_("Veuillez sélectionner un fichier à importer."))

        data = base64.b64decode(self.file_data)
        csv_content = data.decode('utf-8-sig')  # UTF-8 avec BOM
        csv_reader = csv.reader(StringIO(csv_content), delimiter=';')

        currency_id = self.env.ref("base.EUR")

        Partner = self.env['res.partner']
        Payment = self.env['account.payment']
        root_partner_category = self.env['res.partner.category'].search([('parent_id', '=', False)], limit=1)
        root_product_category = self.env['product.category'].search([('parent_id', '=', False)], limit=1)

        stats = {
            'cat_created': 0,
            'events_created': 0,
            'registrations_created': 0,
            'tickets_created': 0,
            'contacts_created': 0,
            'product_cat_created': 0,
            'products_created': 0,
            'buyers_created': 0,
            'payments_created': 0,
            'refunds_created': 0,
        }

        headers = next(csv_reader, None)
        if not headers or len(headers) < 10:
            raise UserError(_("Le fichier CSV semble mal formaté ou vide."))

        for row in csv_reader:
            if not row or len(row) < 10:
                continue

            # On ignore la première colonne (colonne vide sans entête)
            row = row[1:]

            billet = row[0]  # Colonne "Billet"
            event_name = row[0][11:]
            event_ticket = row[0][:9]
            create_date = row[3]  # Jour de création
            email = row[10]  # Colonne "Email"
            prenom = row[9]  # Colonne "Prénom"
            nom = row[8]  # Colonne "Nom"
            buyer_email = row[13]  # Colonne "Email acheteur"
            first_name = row[12]  # Colonne "Prénom acheteur"
            last_name = row[11]  # Colonne "Nom acheteur"
            # order = row[14]  # Colonne "Commande"
            paid = row[23]  # Colonne "Payé"
            phone = f"+{row[33]}" if len(row) > 33 and row[33] else ''  # Numéro de téléphone...
            birthdate_date = Date.to_date(datetime.strptime(row[36], "%d/%m/%Y")) if len(row) > 36 and row[36] else None
            gender = "female" if len(row) > 35 and row[35] == "Femme" else "male" if len(row) > 35 and row[35] == "Homme" else None  # Genre
            prix = round((float(row[18].replace(',', '.')) - 0.29) / 1.01, 2) if row[18] else 0.0  # EUR
            list_price = round((float(row[18].replace(',', '.')) - 0.29) * 1000 / (1.01 * 8.38), 0)  # XPF
            list_price = list_price if list_price > 0.0 else 0
            rembourse = round((float(row[19].replace(',', '.')) - 0.29) / 1.01, 2) if row[19] else 0.0  # EUR
            tarif = row[5].split("|")[0].strip()  # Colonne "Tarif"
            categorie = row[6].replace('...', '').strip()  # Colonne "Catégorie"
            date = row[25][:10]  # Colonne "Date de paiement"
            payment_status = row[17]  # Paiement
            scanned = row[27]  # Scanné

            if not email:
                continue

            if categorie:
                category = self.env['res.partner.category'].search([('name', '=', categorie)], limit=1)
                if not category:
                    category = self.env['res.partner.category'].create({
                        'name': categorie,
                        'parent_id': root_partner_category.id,
                    })
                    stats['cat_created'] += 1

                product_category = self.env['product.category'].search([('name', '=', categorie)], limit=1)
                if not product_category:
                    product_category = self.env['product.category'].create({
                        'name': categorie,
                        'parent_id': root_product_category.id,
                    })
                    stats['product_cat_created'] += 1
            else:
                category = root_partner_category
                product_category = root_product_category

            if prenom or nom:
                partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
                if not partner:
                    partner = self.env['res.partner'].create({
                        'birthdate_date': birthdate_date,
                        'firstname': prenom,
                        'gender': gender,
                        'lastname': nom,
                        'phone': phone,
                        'email': email,
                        'category_id': [(6, 0, [category.id])]
                    })
                    stats['contacts_created'] += 1

            if first_name or last_name:
                buyer = self.env['res.partner'].search([('email', '=', buyer_email)], limit=1)
                if not buyer:
                    buyer = self.env['res.partner'].create({
                        'firstname': first_name,
                        'lastname': last_name,
                        'email': buyer_email,
                        'category_id': [(6, 0, [category.id])]
                    })
                    stats['buyers_created'] += 1

            if tarif:
                product_id = self.env['product.product'].search([('name', '=', tarif)], limit=1)
                if not product_id:
                    product_id = self.env['product.product'].create({
                        'name': tarif,
                        'type': 'service',
                        'list_price': list_price,
                        'categ_id': product_category.id,
                    })
                    stats['products_created'] += 1

            ref = f"{billet} - {tarif}"
            if prix > 0 and paid == 'Oui':
                payment = self.env['account.payment'].search([('ref', '=', ref),
                                                              ('payment_type', '=', 'inbound')], limit=1)
                if not payment:
                    self.env['account.payment'].create({
                        'date': date,
                        'partner_id': buyer.id,
                        'amount': prix,
                        'currency_id': currency_id.id,
                        'partner_type': 'customer',
                        'payment_type': 'inbound',
                        'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                        'journal_id': self.env['account.journal'].search([('type', '=', 'cash')], limit=1).id,
                        'ref': ref,
                    })
                    stats['payments_created'] += 1

            if rembourse > 0:
                refund = self.env['account.payment'].search([('ref', '=', ref),
                                                             ('payment_type', '=', 'outbound')], limit=1)
                if not refund:
                    self.env['account.payment'].create({
                        'date': date,
                        'partner_id': buyer.id,
                        'amount': rembourse,
                        'currency_id': currency_id.id,
                        'payment_type': 'outbound',
                        'partner_type': 'customer',
                        'payment_method_id': self.env.ref('account.account_payment_method_manual_out').id,
                        'journal_id': self.env['account.journal'].search([('type', '=', 'cash')], limit=1).id,
                        'ref': ref,
                    })
                    stats['refunds_created'] += 1

            event = self.env['event.event'].search([('name', '=like', f'{event_name}%')], limit=1)
            if not event:
                event = self.env['event.event'].create({
                    'name': event_name,
                })
                stats['events_created'] += 1

            ticket = self.env['event.event.ticket'].search([
                ('name', '=', event_ticket),
                ('event_id', '=', event.id)
            ])
            if not ticket:
                ticket = self.env['event.event.ticket'].create({
                    'event_id': event.id,
                    'name': event_ticket,
                    'product_id': product_id.id,
                })
                stats['tickets_created'] += 1

            event_registration = self.env['event.registration'].search([
                ('event_ticket_id', '=', ticket.id),
                ('event_id', '=', event.id)
            ])
            if not event_registration:
                self.env['event.registration'].create({
                    'create_date': create_date,
                    'email': email,
                    'event_id': event.id,
                    'event_ticket_id': ticket.id,
                    'name': f'{prenom} {nom}',
                    'partner_id': buyer.id,
                    'phone': phone,
                    'sale_status': 'sold' if paid == 'Oui' else 'free' if payment_status == 'Invitation' else 'to_pay',
                    'state': 'done' if scanned == 'Oui' else 'open',
                })
                stats['registrations_created'] += 1

        message = (
            f"{stats['events_created']} événements créés\n"
            f"{stats['registrations_created']} participants créés\n"
            f"{stats['tickets_created']} tickets créés\n"
            f"{stats['cat_created']} catégories créées\n"
            f"{stats['contacts_created']} contacts créés\n"
            f"{stats['product_cat_created']} catégories de produit créées\n"
            f"{stats['products_created']} produits créés\n"
            f"{stats['payments_created']} paiements enregistrés\n"
            f"{stats['refunds_created']} remboursements enregistrés"
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Import terminé",
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
