
"""
===============================================================================
SCÉNARIO : RÉINTÉGRATION DE L'ANCIEN LEADER
===============================================================================

Après un failover, l'ancien Leader doit rejoindre le cluster comme Replica.

Ce scénario vérifie :
    - que le dernier failover a bien un ancien Leader identifié ;
    - que cet ancien Leader est redevenu Replica ;
    - que son récepteur WAL est en état streaming ;
    - que tous les Replicas du cluster reçoivent les WAL.

Aucune reconstruction destructive n'est lancée.
===============================================================================
"""

from .base_test import BaseHATest
from ..postgres_client import (
    get_postgres_nodes,
    check_node_connection,
    connect_to_node,
)


class RejoinTest(BaseHATest):

    def _check_streaming(self, host):
        """
        Vérifie que le nœud reçoit les WAL depuis son serveur primaire.
        """
        connection = connect_to_node(host)

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        status,
                        sender_host,
                        sender_port,
                        written_lsn,
                        flushed_lsn,
                        latest_end_lsn
                    FROM pg_stat_wal_receiver
                """)

                return cursor.fetchone()

        finally:
            connection.close()

    def run(self):
        details = []
        nodes = get_postgres_nodes()

        # Retrouver le dernier ancien Leader à partir de l'historique Odoo.
        failover_test = self.env["postgres.ha.test"].search([
            ("code", "=", "failover"),
        ], limit=1)

        if not failover_test:
            raise RuntimeError(
                "Aucun scénario Failover n'existe dans Odoo."
            )

        last_failover = self.env["postgres.ha.test.result"].search([
            ("test_id", "=", failover_test.id),
            ("status", "=", "success"),
            ("leader_before", "!=", False),
        ], order="execution_date desc, id desc", limit=1)

        if not last_failover:
            raise RuntimeError(
                "Aucun failover réussi avec ancien Leader identifié. "
                "Exécutez d'abord le scénario Failover."
            )

        old_leader_node = last_failover.leader_before

        # Le nom DNS Docker est préféré à l'adresse IP.
        old_leader = (
            old_leader_node.docker_service
            or old_leader_node.host
        )

        if old_leader not in nodes:
            raise RuntimeError(
                f"L'ancien Leader '{old_leader}' n'est pas présent "
                "dans HA_POSTGRES_NODES."
            )

        details.append(f"Ancien Leader à contrôler : {old_leader}")

        # Vérifier tous les nœuds et leur rôle SQL.
        statuses = {}

        for host in nodes:
            status = check_node_connection(host)

            if not status.get("available"):
                raise RuntimeError(
                    f"Le nœud {host} est indisponible : "
                    f"{status.get('error')}"
                )

            statuses[host] = status

        leaders = [
            host for host, status in statuses.items()
            if status["role"] == "leader"
        ]

        if len(leaders) != 1:
            raise RuntimeError(
                f"Le cluster doit avoir un seul Leader. Détectés : {leaders}"
            )

        current_leader = leaders[0]

        if old_leader == current_leader:
            raise RuntimeError(
                "L'ancien Leader est encore Leader. "
                "La bascule n'a pas permis sa réintégration."
            )

        if statuses[old_leader]["role"] != "replica":
            raise RuntimeError(
                f"L'ancien Leader {old_leader} n'est pas redevenu Replica."
            )

        # Contrôler l'état du récepteur WAL de chaque Replica.
        for host, status in statuses.items():
            if status["role"] != "replica":
                continue

            receiver = self._check_streaming(host)

            if not receiver:
                raise RuntimeError(
                    f"Aucun récepteur WAL actif sur le Replica {host}."
                )

            wal_status = receiver[0]

            if wal_status != "streaming":
                raise RuntimeError(
                    f"Le Replica {host} n'est pas en streaming WAL : "
                    f"{wal_status}"
                )

            details.append(
                f"{host} : Replica, WAL streaming depuis {receiver[1]}."
            )

        details.append(
            f"Ancien Leader {old_leader} réintégré comme Replica."
        )
        details.append(
            f"Leader actuel : {current_leader}."
        )

        return {
            "status": "success",
            "leader_before": old_leader,
            "leader_after": current_leader,
            "details": "\n".join(details),
        }
