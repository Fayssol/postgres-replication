# Dockerfile.patroni-custom
FROM ubuntu:22.04

# Variables d'environnement
ENV DEBIAN_FRONTEND=noninteractive \
    PG_VERSION=14 \
    PATRONI_VERSION=3.2.0 \
    ETCD_VERSION=3.6.4

# 1. Installation de tous les packages système et dépendances
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
    sendemail \
    libio-socket-ssl-perl \
    libnet-ssleay-perl \
    psmisc \
    vim \
    net-tools \
    iputils-ping \
    dnsutils \
    jq \
    && curl https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - \
    && echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y \
        postgresql-${PG_VERSION} \
        postgresql-client-${PG_VERSION} \
        postgresql-contrib-${PG_VERSION} \
        postgresql-${PG_VERSION}-repack \
        postgresql-${PG_VERSION}-postgis-3 \
        pgbouncer \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 2. Installation etcdctl, Patroni et création des répertoires
RUN wget https://github.com/etcd-io/etcd/releases/download/v${ETCD_VERSION}/etcd-v${ETCD_VERSION}-linux-amd64.tar.gz \
    && tar -xzf etcd-v${ETCD_VERSION}-linux-amd64.tar.gz \
    && cp etcd-v${ETCD_VERSION}-linux-amd64/etcdctl /usr/local/bin/ \
    && rm -rf etcd-v${ETCD_VERSION}-linux-amd64* etcd-v${ETCD_VERSION}-linux-amd64.tar.gz \
    && pip3 install --no-cache-dir \
        patroni[etcd3]==${PATRONI_VERSION} \
        psycopg2-binary \
        python-consul \
        python-etcd \
        PyYAML \
        click \
        boto \
        pytest \
    && mkdir -p /var/lib/postgresql/data \
        /var/run/postgresql \
        /etc/patroni \
        /var/log/patroni \
        /var/lib/postgresql/wal_archive \
        /etc/patroni/callbacks

# 3. Configuration des permissions et scripts
RUN chown -R postgres:postgres /var/lib/postgresql \
        /var/run/postgresql \
        /var/log/patroni \
        /var/lib/postgresql/data \
        /var/lib/postgresql/wal_archive \
    && chmod 700 /var/lib/postgresql/data \
    && chmod 750 /var/run/postgresql \
    && echo '#!/bin/bash\npg_isready -U postgres -h 127.0.0.1 -p 5432\n\nexit $?' > /usr/local/bin/healthcheck.sh \
    && chmod +x /usr/local/bin/healthcheck.sh \
    && echo '#!/bin/bash\nset -e\n\n# Laisser Patroni gérer initdb automatiquement\nexec patroni /etc/patroni/patroni.yml' > /usr/local/bin/start-patroni.sh \
    && chmod +x /usr/local/bin/start-patroni.sh

# Copier le script de callback (fait une couche séparée pour optimiser le cache)
COPY callbacks/on_role_change.sh /etc/patroni/callbacks/
RUN chmod +x /etc/patroni/callbacks/on_role_change.sh \
    && chown -R postgres:postgres /var/log/patroni

# Utiliser l'utilisateur postgres
USER postgres

# Répertoire de travail
WORKDIR /var/lib/postgresql

# Exposition des ports
EXPOSE 5432 8008

# Point d'entrée
ENTRYPOINT ["/usr/local/bin/start-patroni.sh"]