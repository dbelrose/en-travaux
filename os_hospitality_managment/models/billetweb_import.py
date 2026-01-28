import datetime

from odoo import models, fields, api, _
import base64
import csv
from io import StringIO
from odoo.exceptions import UserError
from datetime import datetime
from odoo.fields import Date


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
