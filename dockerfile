# Dockerfile.patroni-custom
FROM ubuntu:22.04

# Variables d'environnement
ENV DEBIAN_FRONTEND=noninteractive \
    PG_VERSION=14 \
    PATRONI_VERSION=3.2.0 \
    ETCD_VERSION=3.6.4

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    lsb-release \
    software-properties-common \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Ajouter le dépôt PostgreSQL
RUN curl https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - \
    && echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list

# Installer PostgreSQL et dépendances
RUN apt-get update && apt-get install -y \
    postgresql-${PG_VERSION} \
    postgresql-client-${PG_VERSION} \
    postgresql-contrib-${PG_VERSION} \
    postgresql-${PG_VERSION}-repack \
    postgresql-${PG_VERSION}-postgis-3 \
    pgbouncer \
    && rm -rf /var/lib/apt/lists/*

# Installer etcdctl (client etcd)
RUN wget https://github.com/etcd-io/etcd/releases/download/v${ETCD_VERSION}/etcd-v${ETCD_VERSION}-linux-amd64.tar.gz \
    && tar -xzf etcd-v${ETCD_VERSION}-linux-amd64.tar.gz \
    && cp etcd-v${ETCD_VERSION}-linux-amd64/etcdctl /usr/local/bin/ \
    && rm -rf etcd-v${ETCD_VERSION}-linux-amd64*

# Installer Patroni et dépendances Python
RUN pip3 install --no-cache-dir \
    patroni[etcd3]==${PATRONI_VERSION} \
    psycopg2-binary \
    python-consul \
    python-etcd \
    PyYAML \
    click \
    boto \
    pytest

# Créer les répertoires nécessaires
RUN mkdir -p /var/lib/postgresql/data \
    && mkdir -p /var/run/postgresql \
    && mkdir -p /etc/patroni \
    && mkdir -p /var/log/patroni \
    && mkdir -p /var/lib/postgresql/wal_archive

# Configurer les permissions PostgreSQL
RUN chown -R postgres:postgres /var/lib/postgresql \
    && chown -R postgres:postgres /var/run/postgresql \
    && chown -R postgres:postgres /var/log/patroni \
    && chown -R postgres:postgres /var/lib/postgresql/data \
    && chown -R postgres:postgres /var/lib/postgresql/wal_archive
RUN chmod 700 /var/lib/postgresql/data \
    && chmod 750 /var/run/postgresql
# Installer sendEmail et les dépendances
RUN apt-get update && apt-get install -y \
    sendemail \
    libio-socket-ssl-perl \
    libnet-ssleay-perl \
    && rm -rf /var/lib/apt/lists/*

# Créer les répertoires pour les callbacks et logs
RUN mkdir -p /etc/patroni/callbacks /var/log/patroni

# Copier le script de callback
COPY callbacks/on_role_change.sh /etc/patroni/callbacks/

# Rendre le script exécutable
RUN chmod +x /etc/patroni/callbacks/on_role_change.sh

# Créer l'utilisateur pour les logs
RUN chown -R postgres:postgres /var/log/patroni    
# Installer outils supplémentaires
RUN apt-get update && apt-get install -y \
    psmisc \
    vim \
    net-tools \
    iputils-ping \
    dnsutils \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Créer un script de santé
RUN echo '#!/bin/bash\n\
pg_isready -U postgres -h 127.0.0.1 -p 5432\n\
exit $?' > /usr/local/bin/healthcheck.sh \
    && chmod +x /usr/local/bin/healthcheck.sh

RUN echo '#!/bin/bash\nset -e\n\n# Laisser Patroni gérer initdb automatiquement\nexec patroni /etc/patroni/patroni.yml' > /usr/local/bin/start-patroni.sh && chmod +x /usr/local/bin/start-patroni.sh

# Nettoyer le cache
RUN apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Utiliser l'utilisateur postgres
USER postgres

# Répertoire de travail
WORKDIR /var/lib/postgresql

# Exposition des ports
EXPOSE 5432 8008

# Point d'entrée
ENTRYPOINT ["/usr/local/bin/start-patroni.sh"]