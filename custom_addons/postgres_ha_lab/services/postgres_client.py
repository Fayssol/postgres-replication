"""
=============================================================================
POSTGRES_HA_LAB - CLIENT DE CONNEXION POSTGRESQL
=============================================================================

Rôle :
    Ce module centralise les connexions directes aux différents serveurs
    PostgreSQL du cluster supervisé par Patroni.

Pourquoi ce fichier existe-t-il ?
    Les tests HA doivent pouvoir interroger individuellement chaque nœud.
    Nous ne devons donc pas dépendre exclusivement de Pgpool-II.

Responsabilités :
    - Lire les paramètres de connexion depuis les variables d'environnement.
    - Se connecter à un nœud PostgreSQL précis.
    - Vérifier la disponibilité de chaque serveur.
    - Identifier si le serveur est en récupération (Replica) ou non (Leader).
    - Remonter des erreurs compréhensibles aux autres composants Odoo.

Sécurité :
    - Aucun mot de passe n'est écrit en dur dans ce fichier.
    - Les identifiants sont transmis par l'environnement du conteneur Odoo.
    - Les hôtes sont limités à ceux déclarés dans HA_POSTGRES_NODES.

Dépendance :
    psycopg2, déjà utilisé par Odoo pour ses connexions PostgreSQL.
=============================================================================
"""

import os
import psycopg2


class PostgreSQLConnectionError(Exception):
    """
    Exception spécifique aux problèmes de connexion PostgreSQL.

    Elle permet aux autres services du module de distinguer une erreur
    de connexion d'une erreur métier ou d'une erreur de test HA.
    """
    pass


def get_postgres_config():
    """
    Récupère la configuration PostgreSQL depuis l'environnement.

    Returns:
        dict: Paramètres de connexion nécessaires à psycopg2.

    Raises:
        PostgreSQLConnectionError: Si une variable obligatoire manque.
    """

    required_variables = [
        "HA_POSTGRES_USER",
        "HA_POSTGRES_PASSWORD",
        "HA_POSTGRES_DB",
    ]

    # Vérifier que les variables indispensables sont bien définies.
    missing = [
        variable
        for variable in required_variables
        if not os.environ.get(variable)
    ]

    if missing:
        raise PostgreSQLConnectionError(
            "Configuration PostgreSQL incomplète. "
            f"Variables manquantes : {', '.join(missing)}"
        )

    return {
        "user": os.environ["HA_POSTGRES_USER"],
        "password": os.environ["HA_POSTGRES_PASSWORD"],
        "database": os.environ["HA_POSTGRES_DB"],
        "port": int(os.environ.get("HA_POSTGRES_PORT", "5432")),
        "connect_timeout": int(
            os.environ.get("HA_POSTGRES_CONNECT_TIMEOUT", "5")
        ),
    }


def get_postgres_nodes():
    """
    Retourne la liste des noms DNS des nœuds PostgreSQL autorisés.

    Exemple :
        HA_POSTGRES_NODES=patroni1,patroni2,patroni3

    Returns:
        list[str]: Les noms DNS des nœuds.
    """

    raw_nodes = os.environ.get(
        "HA_POSTGRES_NODES",
        "patroni1,patroni2,patroni3"
    )

    return [
        node.strip()
        for node in raw_nodes.split(",")
        if node.strip()
    ]


def connect_to_node(host):
    """
    Ouvre une connexion directe vers un nœud PostgreSQL.

    Important :
        Cette fonction ne passe pas par Pgpool-II.
        Elle permet de contrôler précisément le serveur interrogé.

    Args:
        host (str): Nom DNS du nœud, par exemple patroni1.

    Returns:
        psycopg2.extensions.connection:
            Connexion PostgreSQL ouverte.

    Raises:
        PostgreSQLConnectionError:
            Si le nœud n'est pas autorisé ou si la connexion échoue.
    """

    # Empêcher une connexion vers un hôte arbitraire.
    allowed_nodes = get_postgres_nodes()

    if host not in allowed_nodes:
        raise PostgreSQLConnectionError(
            f"Le nœud '{host}' ne figure pas dans la configuration "
            "des nœuds PostgreSQL autorisés."
        )

    config = get_postgres_config()

    try:
        connection = psycopg2.connect(
            host=host,
            port=config["port"],
            dbname=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=config["connect_timeout"],
            application_name="postgres_ha_lab",
        )

        return connection

    except psycopg2.Error as error:
        # Ne jamais inclure le mot de passe dans le message d'erreur.
        raise PostgreSQLConnectionError(
            f"Impossible de se connecter au nœud {host}. "
            f"Détail PostgreSQL : {error}"
        ) from error


def check_node_connection(host):
    """
    Vérifie qu'un nœud PostgreSQL accepte les connexions et retourne
    quelques informations permettant d'identifier son rôle.

    La requête SQL est volontairement en lecture seule.

    Args:
        host (str): Nœud à contrôler.

    Returns:
        dict: Informations sur le serveur interrogé.
    """

    connection = None

    try:
        connection = connect_to_node(host)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    current_database(),
                    current_user,
                    pg_is_in_recovery(),
                    current_setting('server_version'),
                    inet_server_addr()::text
            """)

            row = cursor.fetchone()

        # pg_is_in_recovery() :
        # True  = serveur en récupération (généralement Replica).
        # False = serveur primaire (généralement Leader).
        is_replica = row[2]

        return {
            "host": host,
            "available": True,
            "database": row[0],
            "user": row[1],
            "role": "replica" if is_replica else "leader",
            "server_version": row[3],
            "server_address": row[4],
            "error": False,
        }

    except PostgreSQLConnectionError as error:
        return {
            "host": host,
            "available": False,
            "role": "unknown",
            "error": str(error),
        }

    except psycopg2.Error as error:
        return {
            "host": host,
            "available": False,
            "role": "unknown",
            "error": str(error),
        }

    finally:
        # Fermer systématiquement la connexion, même en cas d'erreur.
        if connection is not None:
            connection.close()


def connect_to_pgpool(application_name="postgres_ha_lab"):
    """
    Ouvre une connexion PostgreSQL en passant par Pgpool-II.

    Contrairement à connect_to_node(), cette fonction ne cible pas
    un serveur précis. C'est Pgpool qui choisit le serveur PostgreSQL
    auquel transmettre la connexion.

    Variables d'environnement :
        HA_PGPOOL_HOST : nom DNS du service Pgpool (défaut : pgpool)
        HA_PGPOOL_PORT : port Pgpool (défaut : 9999)

    Returns:
        Connexion psycopg2 ouverte.

    Raises:
        PostgreSQLConnectionError en cas d'échec.
    """
    import os

    config = get_postgres_config()

    host = os.environ.get("HA_PGPOOL_HOST", "pgpool")
    port = int(os.environ.get("HA_PGPOOL_PORT", "9999"))

    try:
        return psycopg2.connect(
            host=host,
            port=port,
            dbname=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=config["connect_timeout"],
            application_name=application_name,
        )

    except psycopg2.Error as error:
        raise PostgreSQLConnectionError(
            f"Impossible de se connecter à Pgpool-II ({host}:{port}) : "
            f"{error}"
        ) from error
