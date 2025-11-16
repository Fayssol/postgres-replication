#!/bin/bash

# Lire les variables d'environnement
SMTP_SERVER="${SMTP_SERVER}"
SMTP_PORT="${SMTP_PORT}"
FROM_EMAIL="${FROM_EMAIL}"
TO_EMAIL="${TO_EMAIL}"
SMTP_USERNAME="${SMTP_USERNAME}"
SMTP_PASSWORD="${SMTP_PASSWORD}"

# Variables passées par Patroni
ROLE=$1           # Nouveau rôle (master, replica, etc.)
SCOPE=$2          # Nom du cluster
PREVIOUS_ROLE=$3  # Rôle précédent

# Journalisation
echo "$(date) - Role change: Node $(hostname) - Previous: $PREVIOUS_ROLE, New: $ROLE, Scope: $SCOPE" >> /var/log/patroni/callbacks.log

# ENVOYER UN EMAIL UNIQUEMENT LORS D'UN BASculeMENT
if [ "$ROLE" = "master" ] && [ "$PREVIOUS_ROLE" = "replica" ]; then
    # Cas 1: Un replica devient master (basculement)
    SUBJECT="🔄 PATRONI BASculeMENT: Nouveau Master Élu - Cluster $SCOPE"
    MESSAGE="Un basculement a eu lieu dans le cluster Patroni.
    
📊 DÉTAILS DU BASculeMENT :
- Ancien Master: $PREVIOUS_ROLE
- Nouveau Master: $ROLE  
- Cluster: $SCOPE
- Nœud: $(hostname)
- Heure: $(date)

Le cluster fonctionne maintenant avec $(hostname) comme nœud principal."

elif [ "$ROLE" = "replica" ] && [ "$PREVIOUS_ROLE" = "master" ]; then
    # Cas 2: Le master redevient replica (rétablissement)
    SUBJECT="✅ PATRONI RÉTABLISSEMENT: Ancien Master de Retour - Cluster $SCOPE"
    MESSAGE="L'ancien master s'est rétabli comme replica.
    
📊 DÉTAILS DU RÉTABLISSEMENT :
- Rôle précédent: $PREVIOUS_ROLE
- Rôle actuel: $ROLE
- Cluster: $SCOPE  
- Nœud: $(hostname)
- Heure: $(date)

Le nœud $(hostname) est maintenant de retour en tant que replica."

else
    # Ignorer les autres changements de rôle
    echo "$(date) - Role change ignored: $PREVIOUS_ROLE -> $ROLE" >> /var/log/patroni/callbacks.log
    exit 0
fi

# Envoyer l'email
echo "Tentative d'envoi d'email: $SUBJECT" >> /var/log/patroni/callbacks.log

sendEmail -f "$FROM_EMAIL" \
    -t "$TO_EMAIL" \
    -u "$SUBJECT" \
    -m "$MESSAGE" \
    -s "$SMTP_SERVER:$SMTP_PORT" \
    -xu "$SMTP_USERNAME" \
    -xp "$SMTP_PASSWORD" \
    -o tls=yes 2>&1 >> /var/log/patroni/callbacks.log

if [ $? -eq 0 ]; then
    echo "$(date) - Email sent successfully" >> /var/log/patroni/callbacks.log
else
    echo "$(date) - Failed to send email" >> /var/log/patroni/callbacks.log
fi

exit 0