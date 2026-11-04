
from odoo import models, fields


class PostgresHANode(models.Model):
    _name = "postgres.ha.node"
    _description = "Nœud PostgreSQL HA"
    _order = "name"

    name = fields.Char(
        string="Nom du nœud",
        required=True
    )

    host = fields.Char(
        string="Hôte",
        required=True
    )

    patroni_api_port = fields.Integer(
        string="Port API Patroni",
        default=8008,
        required=True
    )

    role = fields.Selection(
        [
            ("leader", "Leader"),
            ("replica", "Replica"),
            ("unknown", "Inconnu"),
        ],
        string="Rôle",
        default="unknown",
        required=True
    )

    state = fields.Selection(
        [
            ("running", "En fonctionnement"),
            ("stopped", "Arrêté"),
            ("unknown", "Inconnu"),
        ],
        string="État",
        default="unknown",
        required=True
    )

    last_check = fields.Datetime(
        string="Dernière vérification",
        readonly=True
    )
