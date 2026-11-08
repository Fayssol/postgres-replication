from odoo import fields, models


class PostgresHATest(models.Model):
    _name = "postgres.ha.test"
    _description = "Scénario de test PostgreSQL HA"
    _order = "sequence, name"

    name = fields.Char(
        string="Nom du test",
        required=True
    )

    code = fields.Selection(
        selection=[
            ("replication", "Réplication"),
            ("failover", "Failover"),
            ("reconnection", "Reconnexion"),
            ("rejoin", "Réintégration"),
        ],
        string="Type de test",
        required=True
    )

    description = fields.Text(
        string="Description"
    )

    sequence = fields.Integer(
        string="Ordre",
        default=10
    )

    active = fields.Boolean(
        default=True
    )

    result_ids = fields.One2many(
        comodel_name="postgres.ha.test.result",
        inverse_name="test_id",
        string="Historique des exécutions"
    )

    last_result = fields.Selection(
        related="result_ids.status",
        string="Dernier résultat",
        readonly=True
    )