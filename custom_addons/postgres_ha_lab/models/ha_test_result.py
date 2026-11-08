from odoo import fields, models


class PostgresHATestResult(models.Model):
    _name = "postgres.ha.test.result"
    _description = "Résultat d'exécution d'un test PostgreSQL HA"
    _order = "execution_date desc, id desc"

    name = fields.Char(
        string="Référence",
        required=True,
        default="Nouvelle exécution"
    )

    test_id = fields.Many2one(
        comodel_name="postgres.ha.test",
        string="Scénario",
        required=True,
        ondelete="cascade"
    )

    status = fields.Selection(
        selection=[
            ("pending", "En attente"),
            ("running", "En cours"),
            ("success", "Réussi"),
            ("failed", "Échoué"),
            ("error", "Erreur technique"),
            ("cancelled", "Annulé"),
        ],
        string="Résultat",
        default="pending",
        required=True
    )

    execution_date = fields.Datetime(
        string="Date d'exécution",
        default=fields.Datetime.now,
        required=True
    )

    duration = fields.Float(
        string="Durée (secondes)",
        digits=(10, 2)
    )

    leader_before = fields.Many2one(
        comodel_name="postgres.ha.node",
        string="Leader avant le test"
    )

    leader_after = fields.Many2one(
        comodel_name="postgres.ha.node",
        string="Leader après le test"
    )

    details = fields.Text(
        string="Détails techniques"
    )

    error_message = fields.Text(
        string="Message d'erreur"
    )