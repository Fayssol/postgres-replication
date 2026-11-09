"""
===============================================================================
FICHIER : services/patroni_client.py
PROJET  : PostgreSQL HA Manager
VERSION : 1.0.0

RESPONSABILITÉ
--------------
Ce module centralise les communications HTTP avec l'API REST de Patroni.

Patroni expose une API REST qui permet notamment de connaître :
- le nom du nœud ;
- son rôle (leader, replica, etc.) ;
- son état ;
- sa version PostgreSQL ;
- certaines informations de réplication.

PRINCIPE DE CONCEPTION
----------------------
Ce fichier ne connaît pas Odoo et ne modifie aucune donnée en base.

Il reçoit une adresse, interroge Patroni et retourne un résultat Python.
Cette séparation facilite les tests et la maintenance du code.

DOCUMENTATION
-------------
API officielle Patroni :
https://patroni.readthedocs.io/en/latest/rest_api.html
===============================================================================
"""

import logging

import requests

_logger = logging.getLogger(__name__)


class PatroniClient:
    """
    Client HTTP permettant d'interroger un serveur Patroni.

    Exemple :
        client = PatroniClient("http://patroni1:8008")
        result = client.get_status()
    """

    def __init__(self, base_url, timeout=3):
        """
        Initialise le client.

        :param base_url: Adresse de l'API REST Patroni.
        :param timeout: Durée maximale d'attente en secondes.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
    def get_status(self):
        """
        Récupère l'état du nœud auprès de l'API REST Patroni.

        IMPORTANT :
        Patroni retourne les informations d'identification du membre
        dans l'objet imbriqué "patroni".

        Exemple de réponse :
        {
            "state": "running",
            "role": "master",
            "patroni": {
                "version": "3.2.0",
                "scope": "mycluster",
                "name": "pg2"
            }
        }
        """
        try:
            response = requests.get(
                f"{self.base_url}/patroni",
                timeout=self.timeout
            )

            response.raise_for_status()
            data = response.json()

            # Les métadonnées Patroni sont imbriquées dans la réponse.
            patroni_metadata = data.get("patroni") or {}

            # Compatibilité : on accepte aussi un éventuel nom à la racine.
            node_name = (
                data.get("name")
                or patroni_metadata.get("name")
            )

            return {
                "available": True,
                "name": node_name,
                "role": data.get("role", "unknown"),
                "state": data.get("state", "unknown"),
                "server_version": data.get("server_version"),
                "timeline": data.get("timeline"),
                "pending_restart": data.get("pending_restart", False),
                "raw": data,
                "error": False,
            }

        except requests.exceptions.Timeout as exc:
            error = f"Timeout API Patroni : {exc}"

        except requests.exceptions.ConnectionError as exc:
            error = f"Connexion API Patroni impossible : {exc}"

        except requests.exceptions.RequestException as exc:
            error = f"Erreur HTTP Patroni : {exc}"

        except ValueError as exc:
            error = f"Réponse JSON Patroni invalide : {exc}"

        return {
            "available": False,
            "name": None,
            "role": "unknown",
            "state": "unknown",
            "server_version": None,
            "timeline": None,
            "pending_restart": False,
            "raw": {},
            "error": error,
        }

    def switchover(self, leader_name, candidate_name):
        """
        Demande à Patroni un switchover contrôlé.

        Le switchover transfère le rôle de Leader vers un Replica choisi.
        Contrairement à un arrêt brutal du conteneur, cette opération
        permet à Patroni d'organiser proprement la transition.

        Args:
            leader_name: Nom Patroni du Leader actuel (ex: pg1).
            candidate_name: Nom Patroni du Replica candidat (ex: pg2).

        Returns:
            dict: Résultat HTTP de la demande.

        Raises:
            RuntimeError: Si Patroni refuse ou ne reçoit pas la demande.
        """
        import os

        endpoint = f"{self.base_url}/switchover"

        # L'authentification est facultative. Elle doit être activée
        # si l'API REST Patroni est protégée par HTTP Basic Auth.
        username = os.environ.get("HA_PATRONI_USERNAME")
        password = os.environ.get("HA_PATRONI_PASSWORD")

        auth = (username, password) if username and password else None

        payload = {
            "leader": leader_name,
            "candidate": candidate_name,
        }

        try:
            response = requests.post(
                endpoint,
                json=payload,
                timeout=10,
                auth=auth,
                headers={"Accept": "application/json"},
            )

            if not response.ok:
                raise RuntimeError(
                    f"Patroni a refusé le switchover "
                    f"({response.status_code}) : {response.text[:1000]}"
                )

            return {
                "success": True,
                "http_status": response.status_code,
                "message": response.text,
            }

        except requests.exceptions.RequestException as error:
            raise RuntimeError(
                f"Impossible de demander le switchover à Patroni : {error}"
            ) from error

    @staticmethod
    def _unavailable_result(message):
        """
        Construit une réponse normalisée lorsqu'un nœud est inaccessible.

        L'utilisation d'un format commun évite aux autres modules d'avoir
        à gérer plusieurs structures de résultats différentes.
        """
        return {
            "available": False,
            "name": None,
            "role": "unknown",
            "state": "unknown",
            "server_version": None,
            "timeline": None,
            "pending_restart": False,
            "raw": {},
            "error": message,
        }