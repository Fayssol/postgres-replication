# Réplication de base de données PostgreSQL
La réplication est la recopie des mêmes données de façon automatique d'un noeud A à un autre noeud B pour assurer la haute disponibilité des données. Il y en a de plusieurs types, mais nous allons voir la réplication en streaming.

# Architecture et Structure du projet

## Structure
```
postgres-cluster/
├── 📄 docker-compose.yml
├── 🐳 dockerfile
├── 📁 callbacks/
│   ├── 📄 on_role_change.sh
│__ 📄.env
|__ 📄.gitignore
|   |
└___📁 configs/
    ├── 📄 haproxy.cfg
    └── 📄 patroni1.yml
    |__ 📄 patroni2.yml
    |__ 📄 patroni3.yml
```

## Architecture

```
    +---------------------------------+
    |         HAProxy (LB)            | 
    +---------------------------------+
              |
              ↓ (connections PostgreSQL)
    +---------------------------------+
    |         Cluster Patroni         |
    |   (orchestration automatique)   |
    +---------------------------------+
              |
    +---------+---------+---------+
    |         |         |         |
    |         |         |         |
PostgreSQL  PostgreSQL  PostgreSQL
  Node1      Node2      Node3  
(patroni1)  (patroni2)  (patroni3)
```

# Outils utilisés

Cette infrastructure repose sur plusieurs composants essentiels assurant la haute disponibilité, la réplication, la supervision et l’équilibrage des connexions PostgreSQL.

1️⃣ PostgreSQL – Le moteur de base de données

PostgreSQL est le SGBD relationnel utilisé pour stocker les données.
Dans ce projet, chaque nœud Patroni exécute une instance PostgreSQL configurée pour :

- accepter la réplication en streaming,
- jouer le rôle de leader ou replica,
- assurer la continuité en cas de basculement.

```
+------------------------+
|     PostgreSQL         |
|  Stockage des données  |
|  Réplication WAL       |
+------------------------+
```

2️⃣ Patroni – L’orchestrateur du cluster PostgreSQL

Patroni est un outil open-source qui gère la logique du cluster PostgreSQL haute disponibilité :
```
✔ gestion automatique du failover
✔ promotion d’un replica en nouveau leader
✔ configuration de la réplication
✔ supervision continue des nœuds
✔ exécution de scripts lors des transitions (callbacks)
```
Dans ce projet, Patroni est utilisé dans 3 conteneurs (patroni1, patroni2, patroni3).
```
+-------------------------------+
|            Patroni            |
|  - HA automatique             |
|  - Failover & promotion       |
|  - Gestion réplication        |
+-------------------------------+

```

3️⃣ etcd – Le système distribué de consensus (DCS)

Patroni a besoin d’un Distributed Configuration Store (DCS) pour :

- stocker l'état du cluster,
- déterminer quel nœud est leader,
- éviter les split-brain,
- coordonner les actions entre les nœuds.

Ici, le DCS utilisé est etcd, déployé en cluster 3 nœuds.

Fonctionnement :
```
+----------------------------------------+
|                 etcd                   |
|  - Stockage clé-valeur distribué       |
|  - Verrouillage & consensus            |
|  - Détermine le leader Patroni         |
+----------------------------------------+

```

4️⃣ HAProxy – Le Load Balancer pour PostgreSQL

HAProxy sert de point d’entrée unique pour les clients.
Il distribue automatiquement les connexions vers :

- le leader (pour les opérations écriture → backend “pg_primary”)
- les réplicas (pour les lectures → backend “pg_back”)
- Il détecte l’état des nœuds via des “health checks”.
```
Client → HAProxy → Cluster Patroni  → Leader (writes)
                                    → Replicas (reads)

```
C’est grâce à lui que l’application n’a pas besoin de connaître l’IP du leader.

5️⃣ Docker / Docker Compose – Orchestration locale

Chaque composant (etcd, patroni, postgres, haproxy) tourne dans son conteneur Docker.
Les avantages :

- isolation stricte,
- reproductibilité,
- déploiement identique partout (dev, test, prod),
- réseau interne isolé.

```
+-------------------------------+
|           Docker              |
|  - Conteneurs isolés          |
|  - Réseau interne (pnet)      |
|  - Volumes persistance data   |
+-------------------------------+

```

6️⃣ Bash – Scripts d’automatisation (callbacks)

Des scripts Bash sont utilisés pour exécuter des actions automatiques, notamment :

- envoyer un mail lors du basculement du leader,
- consigner les événements,
- exécuter des commandes custom lors des transitions.

Dans ce projet :
📁 callbacks/on_role_change.sh
→ exécuté automatiquement par Patroni lors d’un changement de rôle (promotion / failover).

```
+------------------------------+
|             Bash              |
|  Scripts automatiques         |
|  - Envoi mail failover        |
|  - Logs custom                |
+------------------------------+

```

# Lancement
Allons directement sur la plateforme : https://labs.play-with-docker.com pour lancer notre projet et le tester en ligne.
OU encore mieux dans le codespace de github

## Mettre à jour et installer psql
  
- si dans labs.play-with-docker : 
```
apk update 
apk add postgresql-client
```
- si dans codespace de github
```
sudo apt-get update
sudo apt-get install -y postgresql-client

```
## Clone du projet

```
git clone https://github.com/Fayssol/postgres-replication.git

cd postgres-replication
```

## Création du sous réseau et de l'image personnalisée de patroni:

```
docker network create --driver bridge --subnet 172.18.0.0/24 pnet
docker build -t my-patroni-custom:latest .

```

## Lancer les conteneurs

```
docker compose up -d
```

## verifier le status des instances : `docker compose ps`
```
 ➜ /workspaces/postgres-replication (main) $ docker compose ps
NAME                 IMAGE                            COMMAND                  SERVICE    CREATED          STATUS          PORTS
etcd1-container      openeuler/etcd:3.6.4-oe2403sp1   "etcd"                   etcd1      14 seconds ago   Up 13 seconds   2379-2380/tcp
etcd2-container      openeuler/etcd:3.6.4-oe2403sp1   "etcd"                   etcd2      14 seconds ago   Up 13 seconds   2379-2380/tcp
etcd3-container      openeuler/etcd:3.6.4-oe2403sp1   "etcd"                   etcd3      14 seconds ago   Up 13 seconds   2379-2380/tcp
haproxy-container    haproxy:latest                   "docker-entrypoint.s…"   haproxy    14 seconds ago   Up 10 seconds   0.0.0.0:5432->5435/tcp, [::]:5432->5435/tcp
patroni1-container   my-patroni-custom                "/usr/local/bin/star…"   patroni1   14 seconds ago   Up 11 seconds   8008/tcp, 0.0.0.0:5433->5432/tcp, [::]:5433->5432/tcp
patroni2-container   my-patroni-custom                "/usr/local/bin/star…"   patroni2   14 seconds ago   Up 11 seconds   8008/tcp, 0.0.0.0:5434->5432/tcp, [::]:5434->5432/tcp
patroni3-container   my-patroni-custom                "/usr/local/bin/star…"   patroni3   14 seconds ago   Up 11 seconds   8008/tcp, 0.0.0.0:5435->5432/tcp, [::]:5435->5432/tcp

```

##  Est ce un replica ? : 
- Test via HAProxy (il routera vers le primary)
```
psql -h localhost -p 5432 -U postgres -d postgres -c "SELECT pg_is_in_recovery(), inet_server_addr();"
```
- Test direct sur chaque nœud
```
psql -h localhost -p 5433 -U postgres -d postgres -c "SELECT pg_is_in_recovery();"  # patroni1
psql -h localhost -p 5434 -U postgres -d postgres -c "SELECT pg_is_in_recovery();"  # patroni2
psql -h localhost -p 5435 -U postgres -d postgres -c "SELECT pg_is_in_recovery();"  # patroni3
```
## list des replica : (cette liste peut prendre du temps)
```
psql -h localhost -p 5432 -U postgres -d postgres -c "SELECT client_addr, state, sync_state FROM pg_stat_replication;"

```

## Etat du cluster : 
```
docker exec -it patroni1-container curl http://localhost:8008/cluster

```
ça affiche le role actuel de chaque noeau du cluster (leader ou replica).

## Ecriture : (test de replication)
```
CREATE DATABASE testdb;
\c testdb
CREATE TABLE t1(id SERIAL PRIMARY KEY, message TEXT);
INSERT INTO t1(message) VALUES ('hello from leader');
```
## Test de load balancing  : 
```
export PGPASSWORD='postgres_password'
for i in {1..5}; do
  psql -h localhost -p 5432 -U postgres -d postgres -c "SELECT inet_server_addr();"
done
unset PGPASSWORD

```
## Maintenant testons le basculement automatique
Pour cela nous allons stimuler une panne du master actuel en le stoppant
```
docker stop patroni1-container

```
## etat du cluster : (Vérifier le nouveau primary)
```
docker exec -it patroni2-container curl http://localhost:8009/cluster
```
- vous pouvez refaire te test de replcation histoire de verifier
## Redémarrer l'ancien primary
```
docker start patroni1-container
```

## Pgpool-II : Pooling, Load Balancing et Haute Disponibilité

### 1. Présentation et rôle de Pgpool-II

**Pgpool-II** est un middleware PostgreSQL qui se place entre les applications clientes et les serveurs PostgreSQL. Il apporte plusieurs fonctionnalités :

- **Connection Pooling** : mutualisation et réutilisation des connexions PostgreSQL.
- **Load Balancing** : répartition des requêtes de lecture entre les nœuds disponibles.
- **Health Checking** : surveillance périodique de la disponibilité des serveurs PostgreSQL.
- **Failover Management** : détection des nœuds indisponibles et actualisation de leur état dans le pool.
- **Streaming Replication Awareness** : prise en compte des rôles primaire/réplique et de l'état de réplication.

Dans cette architecture, **Patroni reste responsable de l'élection et de la promotion du nouveau primaire**, tandis que Pgpool-II gère les connexions clientes, le pooling et la répartition des requêtes.

### 2. Pgpool-II vs HAProxy

HAProxy et Pgpool-II peuvent tous deux servir de point d'entrée vers un cluster PostgreSQL, mais leurs responsabilités diffèrent.

| Fonctionnalité | HAProxy | Pgpool-II |
|---|---|---|
| Load balancing TCP | Oui | Oui |
| Connection pooling | Non | Oui |
| Compréhension du protocole PostgreSQL | Non | Oui |
| Répartition des lectures SQL | Non, au niveau connexion | Oui |
| Health checking | Oui, via les endpoints Patroni | Oui, via les connexions PostgreSQL |
| Détection des rôles primaire/réplique | Via les endpoints HTTP Patroni | Native |
| Routage SQL | Non | Oui |

**Pourquoi utiliser Pgpool-II ?**

HAProxy assure principalement le routage réseau et la distribution des connexions. Pgpool-II va plus loin en comprenant le protocole PostgreSQL et en proposant le pooling des connexions ainsi que la répartition des lectures.

### 3. Architecture avec Pgpool-II

L'intégration de Pgpool-II ajoute un point d'accès intelligent devant les trois instances PostgreSQL gérées par Patroni.

```text
                  Applications clientes
                           |
                           v
                       Pgpool-II
                       Port 9999
                           |
              +------------+------------+
              |            |            |
              v            v            v
          Patroni 1    Patroni 2    Patroni 3
          PostgreSQL   PostgreSQL   PostgreSQL
          Replica      Replica      Primary
           Read           Read       Read/Write
              |            |            |
              +------------+------------+
                           |
                      Cluster etcd
                   Gestion du consensus