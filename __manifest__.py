# coding=utf-8

{
    'name': 'SRM Purchase Collaboration',
    'version': '1.0',
    'summary': '2',
    'description': """""",
    'author': 'Cognichain',
    'website': 'http://www.cognichain.com/',
    'depends': ['purchase', 'stock', 'website'],
    'data': [
        'security/res_groups.xml',
        'security/ir_rule.xml',
        'security/ir.model.access.csv',

        'views/templates.xml',
        # 'views/new_res_config_settings_views.xml',

        'views/portal/purchase_portal_templates.xml',
        'views/portal/home.xml',
        'views/portal/purchase_quote.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'application': True,
    'installable': True,
    'auto_install': False,
}
