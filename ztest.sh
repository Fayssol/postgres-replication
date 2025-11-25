# Le déploiement du cluster avec Docker Compose
  ## up
docker compose up -d
  ## etat du cluster
docker exec -it patroni1-container curl http://localhost:8008/cluster






# vérification de la réplication
  ## Ecriture : (test de replication)
CREATE DATABASE testdb;
\c testdb
CREATE TABLE t1(id SERIAL PRIMARY KEY, message TEXT);
INSERT INTO t1(message) VALUES ('hello from leader');





#  redistribution des connexions via HAProxy
  ## connexions de lectures (redistribution sur les deux replicas)

export PGPASSWORD='postgres_password'
for i in {1..5}; do
  psql -h localhost -p 5432 -U postgres -d postgres -c "SELECT inet_server_addr();"
done
unset PGPASSWORD

  ##connexions d'ecriture (uniquement sur le leader)
export PGPASSWORD='postgres_password'

for i in {1..5}; do
  psql -h localhost -p 5436 -U postgres -d test \
  -c "INSERT INTO t1(message) VALUES ('hello from leader'); SELECT inet_server_addr(), now();"
done

unset PGPASSWORD






#   simulation d’un failover automatique
  ## test failover
docker stop patroni1-container
  --callback

  ## retour ancien leader
docker start patroni1-container