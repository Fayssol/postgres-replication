"""
===============================================================================
FICHIER : services/cluster_discovery.py
PROJET  : PostgreSQL HA Manager

RESPONSABILITÉ
--------------
Découvrir automatiquement les nœuds Patroni présents dans Docker et
synchroniser leur état dans les modèles Odoo.

MÉTHODE HYBRIDE
---------------
1. Docker fournit la liste des conteneurs.
2. Les labels permettent d'identifier ceux de notre laboratoire.
3. Le réseau Docker fournit le nom DNS du service.
4. L'API Patroni confirme le rôle et l'état du serveur.
5. Odoo crée ou actualise la fiche du nœud.

IMPORTANT
---------
La présence d'un conteneur ne signifie pas que PostgreSQL fonctionne.
C'est pourquoi la disponibilité est confirmée séparément par Patroni.
===============================================================================
"""

import json
import logging
import os

import requests

from odoo import api, models, fields
from odoo.exceptions import UserError
from .patroni_client import PatroniClient


_logger = logging.getLogger(__name__)


class ClusterDiscovery(models.AbstractModel):
    """
    Service Odoo chargé de la découverte et de la synchronisation.

    Un modèle AbstractModel est utilisé car ce service ne représente pas
    une donnée métier à enregistrer dans la base.
    """

    _name = "postgres.ha.discovery"
    _description = "Service de découverte du cluster PostgreSQL"

    # -------------------------------------------------------------------------
    # CONFIGURATION
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_configuration():
        """
        Lit les paramètres de connexion depuis les variables d'environnement.

        Cela évite de coder des adresses ou des secrets directement dans
        les fichiers Python.
        """
        return {
            "docker_api_url": os.getenv(
                "HA_DOCKER_API_URL",
                "http://docker-socket-proxy:2375",
            ).rstrip("/"),
            "network": os.getenv(
                "HA_DOCKER_NETWORK",
                "pnet",
            ),
            "label": os.getenv(
                "HA_DOCKER_LABEL",
                "ha.manager=postgres-ha-lab",
            ),
        }

    # -------------------------------------------------------------------------
    # DÉCOUVERTE DOCKER
    # -------------------------------------------------------------------------

    def _discover_docker_containers(self):
        """
        Récupère les conteneurs portant le label de notre laboratoire.

        L'endpoint /containers/json?all=1 permet de récupérer aussi les
        conteneurs arrêtés. Ils doivent rester visibles dans Odoo.

        Seules les opérations GET sont utilisées.
        """
        config = self._get_configuration()

        endpoint = f"{config['docker_api_url']}/containers/json"

        try:
            response = requests.get(
                endpoint,
                params={"all": "1"},
                timeout=5,
            )
            response.raise_for_status()

            containers = response.json()

        except requests.exceptions.RequestException as error:
            _logger.exception("Impossible de contacter l'API Docker.")

            raise UserError(
                "La découverte Docker a échoué. "
                "Vérifie le proxy Docker et la configuration réseau. "
                f"Détail : {error}"
            ) from error

        # On filtre localement les conteneurs afin de ne retenir que
        # ceux explicitement marqués comme appartenant à notre laboratoire.
        expected_label = config["label"]

        discovered = []

        for container in containers:
            labels = container.get("Labels") or {}

            key, expected_value = expected_label.split("=", 1)

            if labels.get(key) != expected_value:
                continue

            if labels.get("ha.component") != "patroni":
                continue

            discovered.append(container)

        return discovered

    # -------------------------------------------------------------------------
    # EXTRACTION DES INFORMATIONS DOCKER
    # -------------------------------------------------------------------------

    def _extract_node_information(self, container):
        """
        Transforme une réponse Docker en informations normalisées.

        Le nom DNS privilégié est le nom du service Compose. Si celui-ci
        n'est pas disponible, le nom du conteneur est utilisé.
        """
        config = self._get_configuration()

        labels = container.get("Labels") or {}

        service_name = labels.get("com.docker.compose.service")

        container_names = container.get("Names") or []

        container_name = (
            container_names[0].lstrip("/")
            if container_names
            else container.get("Id", "unknown")[:12]
        )

        host = service_name or container_name

        network_settings = container.get("NetworkSettings") or {}
        networks = network_settings.get("Networks") or {}

        network_information = networks.get(config["network"]) or {}

        ip_address = network_information.get("IPAddress")

        # Les conteneurs doivent appartenir au réseau prévu.
        # Le nom de service Docker est préférable à l'IP, car il reste
        # stable lorsque le conteneur est recréé.
        if not host and ip_address:
            host = ip_address

        try:
            api_port = int(labels.get("ha.api_port", "8008"))
        except (TypeError, ValueError):
            api_port = 8008

        return {
            "name": service_name or container_name,
            "host": host,
            "port": api_port,
            "docker_id": container.get("Id"),
            "docker_service": service_name or container_name,
            "docker_network": config["network"],
            "container_exists": container.get("State") == "running",
            "docker_state": container.get("State"),
        }

    # -------------------------------------------------------------------------
    # NORMALISATION DES RÔLES PATRONI
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_role(role):
        """
        Convertit les rôles Patroni en valeurs connues par Odoo.

        Les valeurs inattendues deviennent 'unknown' afin d'éviter
        qu'une réponse Patroni inhabituelle bloque la synchronisation.
        """
        role = (role or "").lower()

        if role in ("leader", "master"):
            return "leader"

        if role in ("replica", "async", "sync"):
            return "replica"

        if role == "standby_leader":
            return "standby_leader"

        return "unknown"

    # -------------------------------------------------------------------------
    # SYNCHRONISATION D'UN NŒUD
    # -------------------------------------------------------------------------

    def _synchronize_node(self, information):
        """
        Crée ou actualise un nœud dans Odoo.

        L'identifiant Docker sert de clé de rapprochement.
        Une fiche existante est mise à jour au lieu d'être dupliquée.
        """
        Node = self.env["postgres.ha.node"].sudo()

        docker_id = information.get("docker_id")

        node = Node.search(
            [("docker_id", "=", docker_id)],
            limit=1,
        )

        # Si un conteneur a été recréé, son identifiant Docker change.
        # On tente alors un rapprochement par service et source.
        if not node and information.get("docker_service"):
            node = Node.search(
                [
                    ("docker_service", "=", information["docker_service"]),
                    ("source", "=", "docker"),
                ],
                limit=1,
            )

        patroni = PatroniClient(
            f"http://{information['host']}:{information['port']}"
        )

        status = patroni.get_status()

        values = {
            "name": information["name"],
            "host": information["host"],
            "patroni_api_port": information["port"],
            "source": "docker",
            "docker_id": docker_id,
            "docker_service": information["docker_service"],
            "docker_network": information["docker_network"],
            "container_exists": information["container_exists"],
            "last_check": fields.Datetime.now(),
            "role": self._normalize_role(status.get("role")),
            "server_version": status.get("server_version"),
            "timeline": status.get("timeline") or 0,
            "pending_restart": status.get("pending_restart", False),
            "last_error": status.get("error") or False,
            "last_status_json": json.dumps(
                status.get("raw") or {},
                ensure_ascii=False,
                indent=2,
            ),
        }

        # Un conteneur arrêté ou une API Patroni inaccessible ne doit
        # jamais être présenté comme un serveur PostgreSQL opérationnel.
        if not information["container_exists"] or not status["available"]:
            values["state"] = "stopped"
            values["role"] = "unknown"
        elif status.get("state") in ("running", "streaming"):
            values["state"] = "running"
        else:
            values["state"] = "unknown"

        if node:
            node.write(values)
        else:
            Node.create(values)

    # -------------------------------------------------------------------------
    # SYNCHRONISATION GLOBALE
    # -------------------------------------------------------------------------

    @api.model
    def synchronize_cluster(self):
        """
        Point d'entrée principal de la découverte hybride.

        Cette méthode peut être appelée :
        - depuis un bouton Odoo ;
        - depuis une tâche planifiée ;
        - depuis un test automatisé.

        Elle traite chaque conteneur indépendamment pour éviter qu'une
        erreur sur un nœud empêche la supervision des autres.
        """
        containers = self._discover_docker_containers()

        for container in containers:
            try:
                information = self._extract_node_information(container)
                self._synchronize_node(information)

            except Exception:
                _logger.exception(
                    "Échec de synchronisation d'un conteneur Patroni : %s",
                    container.get("Id"),
                )

        return True