
"""
=============================================================================
POSTGRES HA LAB - TEST DE RÉPLICATION
=============================================================================

Objectif :
    Vérifier que les données écrites sur le Leader sont effectivement
    répliquées sur tous les Replicas du cluster PostgreSQL.

Principe :
    1. Interroger directement tous les nœuds PostgreSQL.
    2. Identifier le Leader et les Replicas.
    3. Créer une table dédiée aux sondes de réplication si nécessaire.
    4. Insérer un identifiant unique sur le Leader.
    5. Interroger individuellement chaque Replica.
    6. Attendre l'arrivée de la donnée si la réplication est asynchrone.

Table utilisée :
    ha_lab.replication_probe

Sécurité et précautions :
    - Aucune table métier n'est modifiée.
    - Les écritures sont effectuées uniquement sur le Leader identifié.
    - Les Replicas sont interrogés en lecture seule.
    - Chaque exécution possède un identifiant UUID unique.
    - Les sondes sont conservées pour faciliter les diagnostics.

Important :
    Ce test valide la réplication physique/logique visible par les
    connexions PostgreSQL utilisées par le laboratoire. Il ne mesure pas
    à lui seul la durabilité après une panne brutale.
=============================================================================
"""

import time
import uuid

from psycopg2 import Error as PostgreSQLError

from .base_test import BaseHATest
from ..postgres_client import (
    get_postgres_nodes,
    connect_to_node,
    check_node_connection,
)


class ReplicationTest(BaseHATest):
    """
    Implémentation du scénario de réplication PostgreSQL.
    """

    # Nom du schéma réservé aux tests du laboratoire.
    SCHEMA_NAME = "ha_lab"

    # Table contenant les données de vérification.
    TABLE_NAME = "replication_probe"

    # Durée maximale d'attente de la réplication, en secondes.
    DEFAULT_TIMEOUT = 15

    # Fréquence de vérification des Replicas, en secondes.
    POLL_INTERVAL = 1

    def _identify_cluster_nodes(self):
        """
        Identifie le Leader et les Replicas à partir des informations SQL.

        pg_is_in_recovery() est utilisé par check_node_connection() :
            False : serveur primaire (Leader).
            True  : serveur en récupération (Replica).

        Returns:
            tuple:
                leader (str): Nom DNS du Leader.
                replicas (list[str]): Noms DNS des Replicas.

        Raises:
            RuntimeError: Si le cluster ne présente pas une topologie valide.
        """

        nodes = get_postgres_nodes()

        if len(nodes) < 2:
            raise RuntimeError(
                "Au moins deux nœuds PostgreSQL sont nécessaires "
                "pour tester la réplication."
            )

        leader = None
        replicas = []

        for host in nodes:
            status = check_node_connection(host)

            if not status.get("available"):
                raise RuntimeError(
                    f"Le nœud {host} est inaccessible : "
                    f"{status.get('error')}"
                )

            if status.get("role") == "leader":
                if leader:
                    raise RuntimeError(
                        "Plusieurs Leaders PostgreSQL ont été détectés. "
                        "Le cluster présente une incohérence."
                    )

                leader = host

            elif status.get("role") == "replica":
                replicas.append(host)

        if not leader:
            raise RuntimeError(
                "Aucun Leader PostgreSQL n'a été détecté."
            )

        if not replicas:
            raise RuntimeError(
                "Aucun Replica PostgreSQL n'a été détecté."
            )

        return leader, replicas

    def _prepare_probe_table(self, leader):
        """
        Prépare l'espace SQL réservé aux sondes de réplication.

        Les instructions CREATE sont exécutées sur le Leader.
        Le schéma et la table seront ensuite répliqués vers les Replicas.

        La création est idempotente : relancer le test ne recrée pas
        inutilement les objets déjà présents.
        """

        connection = None

        try:
            connection = connect_to_node(leader)

            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE SCHEMA IF NOT EXISTS ha_lab;
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS
                    ha_lab.replication_probe (
                        execution_token UUID PRIMARY KEY,
                        test_name VARCHAR(100) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)

            connection.commit()

        except PostgreSQLError:
            if connection:
                connection.rollback()
            raise

        finally:
            if connection:
                connection.close()

    def _insert_probe(self, leader, execution_token):
        """
        Insère une sonde unique sur le Leader.

        L'identifiant UUID permet de distinguer sans ambiguïté chaque
        exécution, même si plusieurs tests sont lancés successivement.
        """

        connection = None

        try:
            connection = connect_to_node(leader)

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO ha_lab.replication_probe (
                        execution_token,
                        test_name
                    )
                    VALUES (%s, %s);
                """, (
                    str(execution_token),
                    "Test de réplication PostgreSQL HA"
                ))

            # Indispensable : la transaction doit être validée pour que
            # la donnée puisse être répliquée vers les autres serveurs.
            connection.commit()

        except PostgreSQLError:
            if connection:
                connection.rollback()
            raise

        finally:
            if connection:
                connection.close()

    def _check_replica(self, replica, execution_token):
        """
        Vérifie si un Replica possède la sonde insérée sur le Leader.

        Cette méthode ne réalise aucune écriture sur le Replica.

        Returns:
            bool:
                True si la sonde est présente.
                False si elle n'est pas encore visible.
        """

        connection = None

        try:
            connection = connect_to_node(replica)

            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM ha_lab.replication_probe
                        WHERE execution_token = %s
                    );
                """, (str(execution_token),))

                result = cursor.fetchone()

                return result[0]

        finally:
            if connection:
                connection.close()

    def _wait_for_replication(self, replicas, execution_token):
        """
        Attend que tous les Replicas reçoivent la sonde.

        La réplication peut être asynchrone. Il est donc possible que la
        donnée ne soit pas immédiatement visible après le commit du Leader.

        Le contrôle est répété jusqu'à :
            - ce que tous les Replicas aient reçu la donnée ;
            - ou que le délai maximal soit dépassé.

        Returns:
            dict:
                Résultat individuel pour chaque Replica.
        """

        import os

        timeout = int(
            os.environ.get(
                "HA_REPLICATION_WAIT_SECONDS",
                self.DEFAULT_TIMEOUT
            )
        )

        deadline = time.monotonic() + timeout

        results = {
            replica: {
                "received": False,
                "error": None,
            }
            for replica in replicas
        }

        while time.monotonic() < deadline:

            for replica in replicas:

                # Ne plus interroger un Replica ayant déjà reçu la donnée.
                if results[replica]["received"]:
                    continue

                try:
                    received = self._check_replica(
                        replica,
                        execution_token
                    )

                    results[replica]["received"] = received
                    results[replica]["error"] = None

                except Exception as error:
                    # Une erreur temporaire de connexion est conservée
                    # dans le résultat et le contrôle sera retenté.
                    results[replica]["error"] = str(error)

            # Si tous les Replicas ont reçu la donnée, le test est terminé.
            if all(
                result["received"]
                for result in results.values()
            ):
                break

            time.sleep(self.POLL_INTERVAL)

        return results

    def run(self):
        """
        Exécute le test complet de réplication.

        Cette méthode constitue le point d'entrée du scénario.

        Returns:
            dict:
                status : success ou failed
                details : rapport technique
                leader_before : nom DNS du Leader avant le test
                leader_after : nom DNS du Leader après le test

        Une erreur technique est propagée au moteur central, qui sera
        responsable de l'enregistrer dans l'historique Odoo.
        """

        execution_token = uuid.uuid4()

        # Étape 1 : identifier la topologie réelle du cluster.
        leader, replicas = self._identify_cluster_nodes()

        # Étape 2 : préparer la table réservée au laboratoire.
        self._prepare_probe_table(leader)

        # Étape 3 : écrire une sonde sur le Leader.
        self._insert_probe(leader, execution_token)

        # Étape 4 : attendre la réplication vers tous les Replicas.
        replica_results = self._wait_for_replication(
            replicas,
            execution_token
        )

        # Étape 5 : construire un rapport lisible.
        details = [
            "TEST DE RÉPLICATION POSTGRESQL",
            "=" * 45,
            f"Identifiant de sonde : {execution_token}",
            f"Leader identifié : {leader}",
            f"Nombre de Replicas : {len(replicas)}",
            "",
            "Résultats par Replica :",
        ]

        for replica, result in replica_results.items():

            if result["received"]:
                details.append(
                    f"[OK] {replica} : donnée reçue."
                )
            else:
                details.append(
                    f"[ÉCHEC] {replica} : donnée non reçue."
                )

                if result["error"]:
                    details.append(
                        f"       Dernière erreur : {result['error']}"
                    )

        success = all(
            result["received"]
            for result in replica_results.values()
        )

        details.extend([
            "",
            f"Résultat global : {'RÉUSSI' if success else 'ÉCHOUÉ'}",
        ])

        return {
            "status": "success" if success else "failed",
            "details": "\n".join(details),
            "leader_before": leader,
            "leader_after": leader,
        }
