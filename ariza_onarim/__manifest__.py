{
    'name': 'Arıza Onarım',
    'version': '1.0',
    'category': 'Services',
    'summary': 'Arıza kayıt ve onarım takibi',
    'description': """
        Arıza kayıt ve onarım takibi için modül.
        - Arıza kaydı oluşturma
        - Onarım takibi
        - Teslim işlemleri
    """,
    'author': 'Tofta',
    'website': 'https://www.tofta.com',
    'depends': [
        'base',
        'mail',
        'stock',
        'account',
        'product',
        'product_brand',
        'delivery',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/ariza_views.xml',
        'reports/report_ariza_kayit.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
