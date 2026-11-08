
"""
=============================================================================
POSTGRES HA LAB - MODÈLE DES SCÉNARIOS DE TEST
=============================================================================

Ce modèle représente les différents scénarios de validation du cluster
PostgreSQL HA.

Un scénario est une définition d'une opération que l'on souhaite réaliser
sur le cluster : réplication, failover, reconnexion ou réintégration.

IMPORTANT :
    Ce modèle ne contient pas directement les opérations PostgreSQL.
    Il délègue leur exécution à un service spécialisé :
        postgres.ha.test.runner

Cette séparation permet de conserver :
    - une interface Odoo simple ;
    - une logique métier centralisée ;
    - des scénarios indépendants et faciles à maintenir.
=============================================================================
"""

from odoo import api, fields, models


class PostgresHATest(models.Model):
    _name = "postgres.ha.test"
    _description = "Scénario de test PostgreSQL HA"
    _order = "sequence, name"

    # ---------------------------------------------------------------------
    # IDENTIFICATION DU SCÉNARIO
    # ---------------------------------------------------------------------

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
        string="Actif",
        default=True
    )

    # ---------------------------------------------------------------------
    # HISTORIQUE DES EXÉCUTIONS
    # ---------------------------------------------------------------------

    result_ids = fields.One2many(
        comodel_name="postgres.ha.test.result",
        inverse_name="test_id",
        string="Historique des exécutions"
    )

    last_result = fields.Selection(
        selection=[
            ("pending", "En attente"),
            ("running", "En cours"),
            ("success", "Réussi"),
            ("failed", "Échoué"),
            ("error", "Erreur technique"),
            ("cancelled", "Annulé"),
        ],
        string="Dernier résultat",
        compute="_compute_last_result",
        store=True
    )

    last_execution_date = fields.Datetime(
        string="Dernière exécution",
        compute="_compute_last_result",
        store=True
    )

    @api.depends(
        "result_ids",
        "result_ids.status",
        "result_ids.execution_date"
    )
    def _compute_last_result(self):
        """
        Détermine le résultat de l'exécution la plus récente.

        Pourquoi un champ calculé ?
            Un scénario peut posséder plusieurs résultats. Une relation
            One2many ne peut donc pas être directement utilisée comme
            source d'un champ related représentant un résultat unique.

        Le résultat le plus récent est identifié grâce à :
            1. La date d'exécution.
            2. L'identifiant comme critère secondaire.

        store=True permet à Odoo de conserver la valeur calculée en base.
        """

        for test in self:
            last_execution = max(
                test.result_ids,
                key=lambda result: (
                    result.execution_date or fields.Datetime.from_string(
                        "1970-01-01 00:00:00"
                    ),
                    result.id
                ),
                default=False
            )

            test.last_result = (
                last_execution.status if last_execution else False
            )

            test.last_execution_date = (
                last_execution.execution_date if last_execution else False
            )

    # ---------------------------------------------------------------------
    # ACTION D'EXÉCUTION
    # ---------------------------------------------------------------------

    def action_run_test(self):
        """
        Déclenche l'exécution réelle du scénario sélectionné.

        Le modèle délègue volontairement cette opération au service
        postgres.ha.test.runner.

        Exemple :
            L'utilisateur clique sur "Exécuter" pour le test de réplication.
            Le runner identifie le scénario et appelle le service spécialisé
            chargé d'effectuer les opérations sur le cluster.

        Les scénarios non encore implémentés seront explicitement refusés
        par le runner, plutôt que de simuler une exécution réussie.
        """

        self.ensure_one()

        return self.env["postgres.ha.test.runner"].run_test(self)
