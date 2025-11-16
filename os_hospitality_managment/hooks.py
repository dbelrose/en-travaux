def post_init_hook(cr, registry):
    cr.execute("""
        UPDATE res_company
           SET hm_booking_enabled = TRUE
         WHERE hm_booking_enabled IS NULL
    """)
