{
    'name': 'Arıza Takip',
    'version': '1.0',
    'category': 'Services',
    'summary': 'Arıza takip ve onarım yönetimi',
    'description': """
        Arıza takip ve onarım yönetimi için geliştirilmiş modül.
        Özellikler:
        - Arıza kayıtları
        - Müşteri ürünleri takibi
        - Mağaza ürünleri takibi
        - Teknik servis işlemleri
    """,
    'author': 'Alper Tofta',
    'website': 'https://www.toftamars.com',
    'depends': [
        'base',
        'mail',
        'sale',
        'point_of_sale',
        'stock',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_ariza_kayit.xml',
        'views/ariza_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
