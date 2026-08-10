{
    'name': 'Custom Contact Extension',
    'version': '19.0.1.0.0',
    'category': 'Base',
    'summary': 'Extends standard res.partner with custom fields and logic',
    'description': """
Custom Contact Extension
========================

Adds VIP and instructor-bio fields to ``res.partner``, plus a rule that marks
a contact as VIP when their bio mentions "vip" or "partner". The rule is
enforced in ``create()``/``write()`` as well as in an onchange, so it also
applies to imports, API calls and automations that bypass the UI.
""",
    'author': 'Ammar Ibrahim',
    'depends': ['base'],
    'data': [
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}