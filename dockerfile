# Utiliser une image Python 3.11 récente et slim (légère)
FROM python:3.11-slim-bookworm

# Installer les dépendances système nécessaires pour Patroni et PostgreSQL
# apt-get update fonctionnera car Bookworm est maintenu
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    gcc \
    # Ajoutez d'autres dépendances si nécessaire (etcd dépend de libffi)
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Installer Patroni avec le support etcd via pip
# Utilisez la syntaxe correcte "patroni[etcd]"
RUN pip install "patroni[etcd3]"

# Définir le point d'entrée ou d'autres configurations spécifiques si nécessaire
# Par exemple, pour définir l'utilisateur et le répertoire de travail
WORKDIR /home/patroni
USER nobody 
# Le reste de votre configuration Docker Compose reste le même