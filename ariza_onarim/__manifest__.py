{
    'name': 'Arıza Onarım',
    'version': '1.0',
    'category': 'Services',
    'summary': 'Arıza kayıt ve onarım takibi',
    'description': """
        Bu modül, arıza kayıtlarının ve onarım süreçlerinin takibini sağlar.
        Özellikler:
        - Arıza kaydı oluşturma
        - Onarım süreci takibi
        - SMS bildirimleri
        - Raporlama
    """,
    'author': 'Alper Tofta',
    'website': 'https://www.ariza.com',
    'depends': [
        'base',
        'mail',
        'stock',
        'account',
        'product',
        'product_brand',
        'delivery',
        'sms',
        'analytic',
    ],
    'data': [
        'security/security.xml',
        'data/sequence.xml',
        'data/mail_template.xml',
        'security/ir.model.access.csv',
        'views/ariza_views.xml',
        'views/menu_views.xml',
        'reports/report_ariza_kayit.xml',
        'wizards/ariza_kayit_tamamla_wizard_views.xml',
        'wizards/ariza_onarim_bilgi_wizard_views.xml',
    ],
    'icon': 'static/description/icon.png',
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
