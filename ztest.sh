## Le déploiement du cluster avec Docker Compose
**** up
docker compose up -d
**** etat du cluster
docker exec -it patroni1-container curl http://localhost:8008/cluster






## vérification de la réplication
***** Ecriture : (test de replication)
CREATE DATABASE testdb;
\c testdb
CREATE TABLE t1(id SERIAL PRIMARY KEY, message TEXT);
INSERT INTO t1(message) VALUES ('hello from leader');





##  redistribution des connexions via HAProxy
***** LB
export PGPASSWORD='postgres_password'
for i in {1..5}; do
  psql -h localhost -p 5432 -U postgres -d postgres -c "SELECT inet_server_addr();"
done
unset PGPASSWORD







##   simulation d’un failover automatique
**** test failover
docker stop patroni1-container
  --callback

***** docker start patroni1-container