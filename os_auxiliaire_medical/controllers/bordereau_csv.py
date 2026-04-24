import csv
import io

from odoo import http
from odoo.http import request, content_disposition


class BordereauCsvController(http.Controller):

    @http.route('/cps/bordereau/<int:bordereau_id>/csv',
                type='http', auth='user', methods=['GET'])
    def export_csv(self, bordereau_id, **kwargs):
        bordereau = request.env['cps.bordereau'].browse(bordereau_id)
        if not bordereau.exists():
            return request.not_found()

        data = bordereau.get_export_data()

        # ── Écriture CSV ──────────────────────────────────────────────────
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        # En-tête document
        writer.writerow(['Bordereau', bordereau.name])
        writer.writerow(['Praticien', data['praticien_nom']])
        writer.writerow(['Imprimé le', data['date_impression']])
        writer.writerow([])

        # En-têtes colonnes – libellés corrigés + NOM PRENOM (sans colonne Total)
        writer.writerow([
            'Date',
            data['label_nom_prenom'],           # NOM PRENOM
            'Nb actes',
            data['label_part_cps'],             # Part CPS
            data['label_part_patient'],         # Part patient
        ])

        # Lignes – montants avec virgule
        for row in data['rows']:
            writer.writerow([
                row['date'],
                row['nom_prenom'],              # en majuscules
                row['nb_actes'],
                row['part_cps'],               # virgule décimale
                row['part_patient'],           # virgule décimale
            ])

        # Totaux
        writer.writerow([])
        writer.writerow([
            'TOTAL', '', '',
            data['total_cps'],
            data['total_patient'],
        ])

        csv_bytes = output.getvalue().encode('utf-8-sig')  # BOM pour Excel

        filename = f"Bordereau_{bordereau.name.replace('/', '_')}.csv"
        return request.make_response(
            csv_bytes,
            headers=[
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', content_disposition(filename)),
                ('Content-Length', len(csv_bytes)),
            ],
        )
