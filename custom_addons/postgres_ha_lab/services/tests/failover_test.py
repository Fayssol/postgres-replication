
"""
===============================================================================
SCÉNARIO : FAILOVER / SWITCHOVER
===============================================================================

Effectue une véritable bascule contrôlée du Leader vers un Replica.

IMPORTANT :
    Ce scénario modifie réellement le rôle des nœuds PostgreSQL.
    Il ne doit être exécuté que sur un cluster de laboratoire ou
    dans une fenêtre de maintenance autorisée.
===============================================================================
"""

import os
import time

from .base_test import BaseHATest
from ..postgres_client import (
    get_postgres_nodes,
    check_node_connection,
)
from ..patroni_client import PatroniClient


class FailoverTest(BaseHATest):

    def run(self):
        timeout = int(os.environ.get("HA_FAILOVER_TIMEOUT_SECONDS", "90"))
        interval = 2

        nodes = get_postgres_nodes()
        snapshot = {}

        # 1. Identifier les rôles réels à partir de PostgreSQL.
        for host in nodes:
            status = check_node_connection(host)

            if not status.get("available"):
                raise RuntimeError(
                    f"Le nœud {host} est indisponible : "
                    f"{status.get('error')}"
                )

            patroni = PatroniClient(
                f"http://{host}:"
                f"{int(os.environ.get('HA_PATRONI_API_PORT', '8008'))}"
            ).get_status()

            if not patroni.get("available"):
                raise RuntimeError(
                    f"API Patroni indisponible sur {host}."
                )

            snapshot[host] = {
                "sql": status,
                "patroni": patroni,
            }

        leaders = [
            host for host, data in snapshot.items()
            if data["sql"]["role"] == "leader"
        ]

        replicas = [
            host for host, data in snapshot.items()
            if data["sql"]["role"] == "replica"
        ]

        if len(leaders) != 1:
            raise RuntimeError(
                f"État initial incohérent : {len(leaders)} Leader(s) détecté(s)."
            )

        if not replicas:
            raise RuntimeError("Aucun Replica disponible pour le switchover.")

        old_leader = leaders[0]
        candidate = replicas[0]

        leader_patroni_name = snapshot[old_leader]["patroni"]["name"]
        candidate_patroni_name = snapshot[candidate]["patroni"]["name"]

        #if not leader_patroni_name or not candidate_patroni_name:
        #    raise RuntimeError("Impossible d'identifier les noms Patroni.")
        if not leader_patroni_name or not candidate_patroni_name:
            raise RuntimeError(
                "Impossible d'identifier les noms Patroni.\n"
                f"Leader SQL : {old_leader}\n"
                f"Réponse Patroni Leader : "
                f"{snapshot[old_leader]['patroni']}\n"
                f"Replica SQL : {candidate}\n"
                f"Réponse Patroni Replica : "
                f"{snapshot[candidate]['patroni']}"
            )

        details = [
            f"Leader initial : {old_leader} ({leader_patroni_name})",
            f"Replica candidat : {candidate} ({candidate_patroni_name})",
            "Demande de switchover envoyée à Patroni.",
        ]

        # 2. Demander la bascule au Leader actuel.
        client = PatroniClient(
            f"http://{old_leader}:"
            f"{int(os.environ.get('HA_PATRONI_API_PORT', '8008'))}"
        )

        request_result = client.switchover(
            leader_patroni_name,
            candidate_patroni_name,
        )

        details.append(
            f"Réponse Patroni HTTP : {request_result['http_status']}"
        )

        # 3. Attendre que le candidat devienne effectivement Leader.
        deadline = time.monotonic() + timeout
        new_leader = None

        while time.monotonic() < deadline:
            current_leaders = []

            for host in nodes:
                status = check_node_connection(host)

                if status.get("available") and status.get("role") == "leader":
                    current_leaders.append(host)

            if current_leaders == [candidate]:
                new_leader = candidate
                break

            time.sleep(interval)

        if not new_leader:
            raise RuntimeError(
                "La bascule n'a pas été confirmée dans le délai imparti. "
                "Consultez les logs Patroni et vérifiez l'état du cluster."
            )

        # 4. Vérifier qu'il n'existe toujours qu'un seul Leader.
        final_leaders = [
            host for host in nodes
            if (
                (status := check_node_connection(host)).get("available")
                and status.get("role") == "leader"
            )
        ]

        if final_leaders != [candidate]:
            raise RuntimeError(
                f"État final inattendu : Leaders détectés = {final_leaders}"
            )

        details.append(f"Nouveau Leader confirmé : {new_leader}")
        details.append(f"Ancien Leader : {old_leader}")

        return {
            "status": "success",
            "leader_before": old_leader,
            "leader_after": new_leader,
            "details": "\n".join(details),
        }
