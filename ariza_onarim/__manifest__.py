{
    'name': 'Arıza Onarım',
    'version': '1.0.5',
    'category': 'Services',
    'summary': 'Arıza kayıt ve onarım takibi',
    'description': """
        Bu modül, arıza kayıtlarının ve onarım süreçlerinin takibini sağlar.
        
        Özellikler:
        - Müşteri ve mağaza ürünleri için arıza kaydı oluşturma
        - Onarım süreci takibi ve durum yönetimi
        - Otomatik stok transfer işlemleri
        - SMS bildirimleri (3 aşamalı SMS sistemi)
        - Detaylı raporlama ve dashboard görünümleri
        - QR kod desteği
        - Garanti takibi
        - Teknik servis yönetimi
        
        Güvenlik:
        - Kullanıcı ve yönetici grupları
        - Company bazlı kayıt kuralları
        - Güvenli erişim kontrolü
        
        Odoo 15 uyumlu, production-ready modül.
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
    'post_init_hook': 'post_init_hook',
}
