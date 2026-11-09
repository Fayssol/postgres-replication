# PostgreSQL HA Lab — Supervision et tests de haute disponibilité avec Odoo 18

<p align="center">

**Une plateforme de démonstration et de supervision d'un cluster PostgreSQL hautement disponible, pilotée depuis une interface Odoo 18.**

</p>

<p align="center">

![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14-4169E1?logo=postgresql&logoColor=white)
![Patroni](https://img.shields.io/badge/Patroni-HA-blue)
![Pgpool--II](https://img.shields.io/badge/Pgpool--II-Connection%20Pooling-orange)
![Docker](https://img.shields.io/badge/Docker-Containers-2496ED?logo=docker&logoColor=white)
![Odoo](https://img.shields.io/badge/Odoo-18-714B67?logo=odoo&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)

</p>

---

## 1. Présentation du projet

**PostgreSQL HA Lab** est un projet personnel visant à concevoir, déployer et superviser une infrastructure PostgreSQL hautement disponible (*High Availability*).

L'objectif est de mettre en œuvre une architecture distribuée capable de maintenir l'accès aux données malgré la défaillance d'un nœud, tout en offrant des mécanismes de réplication, de basculement automatique ou contrôlé et de reconnexion.

Le projet associe une infrastructure Docker composée de plusieurs services spécialisés à un module personnalisé développé pour **Odoo 18**.

L'interface Odoo constitue un point central de supervision et d'interaction avec le cluster. Elle permet notamment de visualiser les nœuds, de suivre leur état et de lancer des scénarios de tests directement sur l'infrastructure réelle.

Ce projet est avant tout un laboratoire technique : les opérations de test ne sont pas de simples simulations. Elles interagissent directement avec les services PostgreSQL et les composants du cluster.

## 2. Objectifs techniques

Les principaux objectifs sont :

- Concevoir un cluster PostgreSQL composé de plusieurs instances.
- Mettre en place une réplication entre les instances PostgreSQL.
- Utiliser Patroni pour orchestrer la haute disponibilité et gérer les rôles des nœuds.
- Utiliser etcd comme mécanisme de coordination et de stockage de l'état du cluster.
- Intégrer Pgpool-II pour la gestion des connexions PostgreSQL.
- Utiliser HAProxy comme point d'accès et de distribution du trafic.
- Développer un module Odoo 18 pour superviser l'infrastructure.
- Exécuter des tests techniques directement sur le cluster.
- Étudier les mécanismes de notification lors des changements de rôle et des événements HA.

## 3. Architecture technique

### Vue d'ensemble

```mermaid
flowchart TB
    USER["Administrateur / Développeur"]
    ODOO["Odoo 18<br/>PostgreSQL HA Manager"]

    subgraph INFRA["Infrastructure Docker"]
        subgraph COORD["Coordination"]
            E1["etcd 1"]
            E2["etcd 2"]
            E3["etcd 3"]
        end

        subgraph PG["Cluster PostgreSQL"]
            P1["Patroni 1<br/>PostgreSQL"]
            P2["Patroni 2<br/>PostgreSQL"]
            P3["Patroni 3<br/>PostgreSQL"]
        end

        PGPOOL["Pgpool-II"]
        HAPROXY["HAProxy"]
    end

    USER --> ODOO
    ODOO -->|"API REST Patroni"| P1
    ODOO -->|"API REST Patroni"| P2
    ODOO -->|"API REST Patroni"| P3
    ODOO -->|"Connexion SQL directe"| P1
    ODOO -->|"Connexion SQL directe"| P2
    ODOO -->|"Connexion SQL directe"| P3
    ODOO -->|"Connexion applicative"| PGPOOL

    P1 <--> E1
    P1 <--> E2
    P1 <--> E3
    P2 <--> E1
    P2 <--> E2
    P2 <--> E3
    P3 <--> E1
    P3 <--> E2
    P3 <--> E3

    P1 <-->|"Réplication"| P2
    P2 <-->|"Réplication"| P3
    P3 <-->|"Réplication"| P1

    PGPOOL --> P1
    PGPOOL --> P2
    PGPOOL --> P3
    HAPROXY --> P1
    HAPROXY --> P2
    HAPROXY --> P3