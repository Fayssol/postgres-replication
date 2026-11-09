
"""
===============================================================================
SCÉNARIO : RECONNEXION PGPOOL
===============================================================================

Vérifie que l'application peut ouvrir une connexion PostgreSQL via Pgpool,
fermer cette connexion, puis en ouvrir une nouvelle.

Les connexions passent réellement par le service Pgpool-II.
===============================================================================
"""

from ..postgres_client import connect_to_pgpool
from .base_test import BaseHATest


class ReconnectionTest(BaseHATest):

    def run(self):
        details = []

        # Première connexion via Pgpool.
        first_connection = None

        try:
            first_connection = connect_to_pgpool(
                "postgres_ha_lab_reconnection_1"
            )

            with first_connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        1,
                        current_database(),
                        pg_is_in_recovery(),
                        inet_server_addr()::text
                """)
                first_result = cursor.fetchone()

            if first_result[0] != 1:
                raise RuntimeError("La première requête SQL a échoué.")

            details.append(
                "Première connexion Pgpool : opérationnelle."
            )
            details.append(
                f"Base : {first_result[1]}, "
                f"serveur : {first_result[3]}, "
                f"Replica : {first_result[2]}"
            )

        finally:
            if first_connection is not None:
                first_connection.close()

        details.append("Première connexion fermée correctement.")

        # Deuxième connexion : elle doit fonctionner indépendamment
        # de la première session qui vient d'être fermée.
        second_connection = None

        try:
            second_connection = connect_to_pgpool(
                "postgres_ha_lab_reconnection_2"
            )

            with second_connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                second_result = cursor.fetchone()

            if not second_result or second_result[0] != 1:
                raise RuntimeError(
                    "La deuxième connexion n'a pas exécuté SELECT 1."
                )

            details.append(
                "Deuxième connexion Pgpool : opérationnelle."
            )

        finally:
            if second_connection is not None:
                second_connection.close()

        return {
            "status": "success",
            "leader_before": False,
            "leader_after": False,
            "details": "\n".join(details),
        }
