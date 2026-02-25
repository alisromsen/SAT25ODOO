{
    'name': 'Descarga Masiva de CFDI',
    'version': '0.1',
    'author': 'Bei consulting',
    'website': 'http://bei.mx',
    'category': 'Accounting',
    'description': """
        Descarga los CFDI del portal del SAT a la base de datos de 
        Odoo para su procesamiento y administración
    """,
    'depends': ['account',
                'l10n_mx_edi',
                'sale',
                'sale_management',
                'purchase',
                'account_accountant',
                'base',
                ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'wizard/descarga_x_dia_wizard.xml',
        'wizard/cfdi_invoice.xml',
        'views/esignature_view.xml',
        'views/ir_attachment_view.xml',
        'views/account_move_view.xml',
        'views/res_company_view.xml',
        'wizard/import_invoice_process_message.xml',
        'views/account_tax_view.xml',
        'views/verifica_descarga.xml',
        'views/bei_partner.xml',
        'data/menus.xml',
        #'security/l10n_mx_edi_esignature.xml',
    ],
    'qweb': [],
    'installable': True,
    'license': 'LGPL-3',
}

