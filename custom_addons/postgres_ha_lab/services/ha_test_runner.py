
"""
=============================================================================
POSTGRES HA LAB - MOTEUR CENTRAL D'EXÉCUTION
=============================================================================

Ce service Odoo centralise le lancement de tous les scénarios HA.

Il ne réalise pas lui-même les opérations PostgreSQL.
Il délègue chaque opération à la classe spécialisée correspondante.

Responsabilités :
    1. Recevoir le scénario demandé par l'utilisateur.
    2. Vérifier que son implémentation existe.
    3. Créer un enregistrement d'historique.
    4. Exécuter le scénario.
    5. Enregistrer le résultat et sa durée.
    6. Retourner une notification à l'interface Odoo.

IMPORTANT :
    Un scénario non implémenté ne doit jamais être présenté comme réussi.
=============================================================================
"""

import time
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .tests.replication_test import ReplicationTest

from .tests.failover_test import FailoverTest
from .tests.reconnection_test import ReconnectionTest
from .tests.rejoin_test import RejoinTest


_logger = logging.getLogger(__name__)


class PostgresHATestRunner(models.AbstractModel):
    _name = "postgres.ha.test.runner"
    _description = "Moteur d'exécution des tests PostgreSQL HA"

    
    def _get_node_record(self, host):
        """
        Retrouve un nœud Odoo à partir de son nom DNS ou de son hôte.

        Si aucun hôte n'est fourni, retourne un recordset vide.
        Cela évite de sélectionner accidentellement un autre nœud.
        """

        if not host:
            return self.env["postgres.ha.node"]

        return self.env["postgres.ha.node"].search([
            "|",
            ("docker_service", "=", host),
            ("host", "=", host),
        ], limit=1)


    
    def _get_scenario(self, test):
        """
        Associe le code Odoo à la classe Python qui exécute le scénario.

        Chaque scénario est indépendant. Le runner ne connaît pas les
        détails des opérations SQL ou des appels REST qu'il déclenche.
        """

        scenarios = {
            "replication": ReplicationTest,
            "failover": FailoverTest,
            "reconnection": ReconnectionTest,
            "rejoin": RejoinTest,
        }

        scenario_class = scenarios.get(test.code)

        if not scenario_class:
            raise UserError(_(
                "Aucune implémentation n'existe pour le scénario '%s'."
            ) % test.display_name)

        return scenario_class(self.env)


    def run_test(self, test):
        """
        Exécute un scénario et conserve son résultat dans Odoo.

        Args:
            test:
                Enregistrement postgres.ha.test à exécuter.

        Returns:
            dict:
                Action Odoo affichant une notification à l'utilisateur.

        Les erreurs du scénario sont enregistrées dans l'historique.
        Elles ne sont pas propagées après la création du résultat afin
        d'éviter de perdre le compte rendu technique.
        """

        test.ensure_one()

        # Vérifier que le scénario est actif.
        if not test.active:
            raise UserError(_(
                "Ce scénario est archivé et ne peut pas être exécuté."
            ))

        # Vérifier l'existence de son implémentation avant de créer
        # un résultat d'exécution.
        scenario = self._get_scenario(test)

        # Mesurer la durée réelle avec une horloge monotone.
        # Contrairement à l'heure système, elle n'est pas affectée
        # par un changement de date ou d'heure pendant le test.
        start_time = time.monotonic()
        execution_date = fields.Datetime.now()

        # Chaque lancement crée un nouvel enregistrement.
        result = self.env["postgres.ha.test.result"].create({
            "name": _("%s - %s") % (
                test.name,
                fields.Datetime.to_string(execution_date),
            ),
            "test_id": test.id,
            "status": "running",
            "execution_date": execution_date,
        })

        try:
            # Exécution réelle du scénario sur le cluster.
            report = scenario.run()

            end_time = time.monotonic()
            finished_date = fields.Datetime.now()

            # Récupérer les nœuds Odoo correspondants aux noms DNS
            # renvoyés par le scénario.
            leader_before = self._get_node_record(
                report.get("leader_before")
            )

            leader_after = self._get_node_record(
                report.get("leader_after")
            )

            # Enregistrer le résultat final.
            result.write({
                "status": report["status"],
                "finished_date": finished_date,
                "duration": round(end_time - start_time, 2),
                "leader_before": leader_before.id or False,
                "leader_after": leader_after.id or False,
                "details": report.get("details", ""),
                "error_message": False,
            })

            if report["status"] == "success":
                notification_type = "success"
                message = _("Le scénario a été exécuté avec succès.")
            else:
                notification_type = "warning"
                message = _("Le scénario a échoué. Consultez son rapport.")

        except Exception as error:
            # Conserver les informations de l'exception dans les logs
            # techniques Odoo et dans l'historique du scénario.
            _logger.exception(
                "Erreur pendant l'exécution du scénario HA %s",
                test.display_name,
            )

            end_time = time.monotonic()
            finished_date = fields.Datetime.now()

            result.write({
                "status": "error",
                "finished_date": finished_date,
                "duration": round(end_time - start_time, 2),
                "error_message": str(error),
                "details": _(
                    "Une erreur technique a interrompu le scénario. "
                    "Consultez le message d'erreur et les logs Odoo."
                ),
            })

            notification_type = "danger"
            message = _("Une erreur technique est survenue.")

        # Afficher une notification dans l'interface Odoo.
        # L'historique complet reste consultable depuis le menu dédié.
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Test PostgreSQL HA"),
                "message": message,
                "type": notification_type,
                "sticky": True,
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": "postgres.ha.test.result",
                    "res_id": result.id,
                    "views": [[False, "form"]],
                    "target": "current",
                },
            },
        }
