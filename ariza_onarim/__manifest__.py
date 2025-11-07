{
    'name': 'Arıza Onarım',
    'version': '1.0.3',
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
    'website': 'https://github.com/toftamars',
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
        'data/system_parameters.xml',
        'data/sequence.xml',
        'data/cron.xml',
        'security/ir.model.access.csv',
        'views/menu_views.xml',
        'views/ariza_kayit_views.xml',
        'views/ariza_views.xml',
        'reports/report_ariza_kayit.xml',
        'wizards/ariza_kayit_tamamla_wizard_views.xml',
        'wizards/ariza_onarim_bilgi_wizard_views.xml',
        'wizards/ariza_teslim_wizard_views.xml',
        'wizards/kullanim_talimatlari_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ariza_onarim/static/src/js/debranding_guard.js',
        ],
    },
    'icon': 'static/description/icon.png',
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
