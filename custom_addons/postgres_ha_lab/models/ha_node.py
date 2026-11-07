"""
===============================================================================
FICHIER : models/ha_node.py
PROJET  : PostgreSQL HA Manager

RESPONSABILITÉ
--------------
Définit le modèle Odoo qui représente un nœud PostgreSQL supervisé.

Un nœud est un serveur PostgreSQL participant à un cluster HA.
Il peut être hébergé dans Docker ou sur un serveur externe.

Les informations sont alimentées automatiquement par le moteur de découverte.
===============================================================================
"""

from odoo import api, fields, models


class PostgresHANode(models.Model):
    """
    Représentation persistante d'un nœud PostgreSQL.

    Le champ docker_id permet d'identifier un conteneur sans dépendre
    de son nom. Le nom du conteneur peut changer, contrairement à son
    identifiant Docker tant que le conteneur existe.
    """

    _name = "postgres.ha.node"
    _description = "Nœud PostgreSQL HA"
    _order = "name"

    # -------------------------------------------------------------------------
    # IDENTIFICATION
    # -------------------------------------------------------------------------

    name = fields.Char(
        string="Nom du nœud",
        required=True,
        index=True,
    )

    host = fields.Char(
        string="Hôte",
        required=True,
        help="Nom DNS ou adresse IP permettant de joindre le serveur.",
    )

    patroni_api_port = fields.Integer(
        string="Port API Patroni",
        default=8008,
        required=True,
    )

    api_url = fields.Char(
        string="URL API Patroni",
        compute="_compute_api_url",
        store=True,
    )

    # -------------------------------------------------------------------------
    # ORIGINE ET IDENTIFICATION DOCKER
    # -------------------------------------------------------------------------

    source = fields.Selection(
        [
            ("docker", "Docker"),
            ("external", "Serveur externe"),
        ],
        string="Source",
        default="docker",
        required=True,
    )

    docker_id = fields.Char(
        string="Identifiant Docker",
        index=True,
        copy=False,
    )

    docker_service = fields.Char(
        string="Service Docker",
    )

    docker_network = fields.Char(
        string="Réseau Docker",
    )

    container_exists = fields.Boolean(
        string="Conteneur présent",
        default=False,
    )

    # -------------------------------------------------------------------------
    # SUPERVISION PATRONI
    # -------------------------------------------------------------------------

    role = fields.Selection(
        [
            ("leader", "Leader"),
            ("replica", "Replica"),
            ("standby_leader", "Standby Leader"),
            ("unknown", "Inconnu"),
        ],
        string="Rôle",
        default="unknown",
        required=True,
    )

    state = fields.Selection(
        [
            ("running", "Actif"),
            ("stopped", "Arrêté"),
            ("unknown", "Inconnu"),
        ],
        string="État",
        default="unknown",
        required=True,
    )

    server_version = fields.Char(
        string="Version PostgreSQL",
    )

    timeline = fields.Integer(
        string="Timeline",
    )

    pending_restart = fields.Boolean(
        string="Redémarrage nécessaire",
    )

    last_check = fields.Datetime(
        string="Dernière vérification",
        readonly=True,
    )

    last_error = fields.Text(
        string="Dernière erreur",
        readonly=True,
    )

    last_status_json = fields.Text(
        string="Dernière réponse Patroni",
        readonly=True,
        help="Réponse JSON brute de l'API Patroni pour faciliter le diagnostic.",
    )

    # -------------------------------------------------------------------------
    # CALCULS
    # -------------------------------------------------------------------------

    @api.depends("host", "patroni_api_port")
    def _compute_api_url(self):
        """
        Construit l'adresse de l'API Patroni à partir de l'hôte et du port.
        """
        for node in self:
            node.api_url = (
                f"http://{node.host}:{node.patroni_api_port}"
                if node.host and node.patroni_api_port
                else False
            )

    # -------------------------------------------------------------------------
    # CONTRAINTES
    # -------------------------------------------------------------------------

    _sql_constraints = [
        (
            "docker_id_unique",
            "unique(docker_id)",
            "Un même conteneur Docker ne peut être associé qu'à un seul nœud.",
        ),
    ]