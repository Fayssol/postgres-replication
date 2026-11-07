{
    'name': 'PostgreSQL HA Manager',
    'version': '18.0.1.0.0',
    'category': 'Administration',
    'summary': 'Supervision et gestion d’un cluster PostgreSQL haute disponibilité',
    'depends': ['base'],
    'data': [
        "security/ir.model.access.csv",
        "views/ha_node_views.xml",
        "views/menu_views.xml",
        "data/ir_cron.xml",
    ],
    'installable': True,
    'application': True,
}