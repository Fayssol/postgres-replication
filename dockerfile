# Partir de l'image Patroni existante
FROM d2cio/patroni:latest

# Installer le paquet python-etcd (le nom du paquet peut varier selon l'OS)
# Vous pourriez avoir besoin de 'python3-etcd' ou 'python-etcd' ou 'etcd3'
#RUN apt-get update && apt-get install -y python3-etcd
# OU si vous utilisez pip :
# RUN pip install python-etcd

RUN pip install patroni[etcd3]