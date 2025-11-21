#!/bin/bash

# Lire les variables d'environnement
SMTP_SERVER="${SMTP_SERVER}"
SMTP_PORT="${SMTP_PORT}"
FROM_EMAIL="${FROM_EMAIL}"
TO_EMAIL="${TO_EMAIL}"
SMTP_USERNAME="${SMTP_USERNAME}"
SMTP_PASSWORD="${SMTP_PASSWORD}"

# Vérifier que toutes les variables sont définies
if [ -z "$SMTP_SERVER" ] || [ -z "$SMTP_USERNAME" ] || [ -z "$SMTP_PASSWORD" ]; then
    echo "$(date) - ERROR: Variables SMTP manquantes!" >> /var/log/patroni/callbacks.log
    exit 1
fi

# FORMAT OFFICIEL Patroni 3.2.0: action, role, cluster_name
ACTION="$1"        # "on_role_change"
ROLE="$2"          # "master" ou "replica"  
CLUSTER_NAME="$3"  # "mycluster"

# Journalisation 
echo "$(date) - CALLBACK: $ACTION, $ROLE, $CLUSTER_NAME" >> /var/log/patroni/callbacks.log

# ENVOYER UN EMAIL UNIQUEMENT LORS D'UN CHANGEMENT DE RÔLE VERS MASTER
if [ "$ACTION" = "on_role_change" ] && [ "$ROLE" = "master" ]; then
    
    SUBJECT="🔄 PATRONI: Basculement détecté"
    MESSAGE="Un basculement a eu lieu dans le cluster Patroni.

- Cluster: $CLUSTER_NAME
- Heure: $(date)

Le système a automatiquement élu un nouveau nœud principal.
Aucune action immédiate requise."

    echo "$(date) - 📧 Envoi email basculement" >> /var/log/patroni/callbacks.log

    # Envoyer l'email
    sendEmail -f "$FROM_EMAIL" \
        -t "$TO_EMAIL" \
        -u "$SUBJECT" \
        -m "$MESSAGE" \
        -s "$SMTP_SERVER:$SMTP_PORT" \
        -xu "$SMTP_USERNAME" \
        -xp "$SMTP_PASSWORD" \
        -o tls=yes 2>&1 >> /var/log/patroni/callbacks.log

    if [ $? -eq 0 ]; then
        echo "$(date) - ✅ Email sent" >> /var/log/patroni/callbacks.log
    else
        echo "$(date) - ❌ Failed to send email" >> /var/log/patroni/callbacks.log
    fi

else
    echo "$(date) - 🔇 Ignored: $ACTION $ROLE" >> /var/log/patroni/callbacks.log
fi

exit 0