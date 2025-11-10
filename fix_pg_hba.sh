#!/bin/bash

echo "=== Correction des fichiers pg_hba.conf ==="

# Lignes à ajouter
PG_HBA_LINES="
# Patroni cluster rules - Added by fix script
host    replication     replicator      0.0.0.0/0               md5
host    all             all             0.0.0.0/0               md5
local   replication     replicator                              trust
"

echo "1. Correction de patroni1 (leader)..."
docker exec patroni1-container bash -c "
# Vérifier si les lignes existent déjà
if ! grep -q 'host    replication     replicator      0.0.0.0/0               md5' /var/lib/postgresql/data/pg_hba.conf; then
    echo 'Ajout des règles Patroni dans pg_hba.conf...'
    cat >> /var/lib/postgresql/data/pg_hba.conf << 'EOF'

# Patroni cluster rules - Added by fix script
host    replication     replicator      0.0.0.0/0               md5
host    all             all             0.0.0.0/0               md5
local   replication     replicator                              trust
EOF
    echo '✅ Règles ajoutées avec succès'
else
    echo '✅ Règles déjà présentes'
fi

# Recharger la configuration
echo 'Rechargement de la configuration PostgreSQL...'
psql -U postgres -c \"SELECT pg_reload_conf();\" 2>/dev/null && echo '✅ Configuration rechargée' || echo '❌ Erreur rechargement'
"

echo ""
echo "2. Correction de patroni2 (replica)..."
docker exec patroni2-container bash -c "
# Vérifier si les lignes existent déjà  
if ! grep -q 'local   replication     replicator                              trust' /var/lib/postgresql/data/pg_hba.conf; then
    echo 'Ajout des règles Patroni dans pg_hba.conf...'
    cat >> /var/lib/postgresql/data/pg_hba.conf << 'EOF'

# Patroni cluster rules - Added by fix script
host    replication     replicator      0.0.0.0/0               md5
host    all             all             0.0.0.0/0               md5
local   replication     replicator                              trust
EOF
    echo '✅ Règles ajoutées avec succès'
else
    echo '✅ Règles déjà présentes'
fi

# Recharger la configuration
echo 'Rechargement de la configuration PostgreSQL...'
psql -U postgres -c \"SELECT pg_reload_conf();\" 2>/dev/null && echo '✅ Configuration rechargée' || echo '⚠️  PostgreSQL non démarré (normal pour un réplica)'
"

echo ""
echo "3. Correction de patroni3 (replica)..."
docker exec patroni3-container bash -c "
# Vérifier si les lignes existent déjà
if ! grep -q 'local   replication     replicator                              trust' /var/lib/postgresql/data/pg_hba.conf; then
    echo 'Ajout des règles Patroni dans pg_hba.conf...'
    cat >> /var/lib/postgresql/data/pg_hba.conf << 'EOF'

# Patroni cluster rules - Added by fix script
host    replication     replicator      0.0.0.0/0               md5
host    all             all             0.0.0.0/0               md5
local   replication     replicator                              trust
EOF
    echo '✅ Règles ajoutées avec succès'
else
    echo '✅ Règles déjà présentes'
fi

# Recharger la configuration
echo 'Rechargement de la configuration PostgreSQL...'
psql -U postgres -c \"SELECT pg_reload_conf();\" 2>/dev/null && echo '✅ Configuration rechargée' || echo '⚠️  PostgreSQL non démarré (normal pour un réplica)'
"

echo ""
echo "=== Vérification finale ==="
echo "Contenu de pg_hba.conf sur patroni1 :"
docker exec patroni1-container tail -8 /var/lib/postgresql/data/pg_hba.conf

echo ""
echo "Test de connexion depuis patroni2 vers patroni1 :"
docker exec patroni2-container psql -h patroni1 -U replicator -d postgres -c "SELECT '✅ Connexion réussie' AS test;" 2>/dev/null || echo "❌ Connexion échouée"

echo ""
echo "=== Correction terminée ==="