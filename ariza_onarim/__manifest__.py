{
    'name': 'Arıza ve Onarım Yönetimi',
    'version': '1.0',
    'category': 'Services/Repair',
    'summary': 'Arıza ve Onarım İşlemlerinin Yönetimi',
    'description': """
        Bu modül, şirketlerin arıza ve onarım süreçlerini yönetmelerine yardımcı olur.
        Özellikler:
        * Arıza kayıtları
        * Onarım takibi
        * Teknik servis yönetimi
        * Müşteri iletişimi
        * Stok transfer yönetimi
        * Detaylı raporlama
        * Dashboard görünümü
        * QR kod desteği
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'mail', 'stock', 'sale', 'point_of_sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/ariza_views.xml',
        'views/report_views.xml',
        'views/dashboard_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['qrcode'],
    },
}
