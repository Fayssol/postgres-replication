#!/bin/bash

# Script de notification pour Patroni
# Usage: appelé automatiquement par Patroni lors des changements de rôle

set -e

LOG_FILE="/var/log/patroni_notifications.log"
CONFIG_FILE="/scripts/notify_config.conf"

# Charger la configuration
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    # Valeurs par défaut
    SMTP_SERVER="smtp.gmail.com"
    SMTP_PORT="587"
    SMTP_USER="your-email@gmail.com"
    SMTP_PASSWORD="your-app-password"
    ADMIN_EMAIL="admin@company.com"
    CLUSTER_NAME="postgres-cluster"
fi

# Variables passées par Patroni
ROLE=$1
SCOPE=$2
PREVIOUS_ROLE=$3
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
HOSTNAME=$(hostname -f || hostname)

# Journalisation
echo "[$TIMESTAMP] Role change: Scope=$SCOPE, Host=$HOSTNAME, Previous=$PREVIOUS_ROLE, New=$ROLE" >> "$LOG_FILE"

# Fonction d'envoi d'email
send_email() {
    local subject=$1
    local message=$2
    
    # Construction de l'email
    email_content="From: Patroni Alert <$SMTP_USER>
To: $ADMIN_EMAIL
Subject: $subject
Date: $(date -R)

$message

---
Cluster: $CLUSTER_NAME
Host: $HOSTNAME
Timestamp: $TIMESTAMP
"

    # Envoi via curl
    echo "$email_content" | curl -s \
        --url "smtp://$SMTP_SERVER:$SMTP_PORT" \
        --ssl-reqd \
        --mail-from "$SMTP_USER" \
        --mail-rcpt "$ADMIN_EMAIL" \
        --user "$SMTP_USER:$SMTP_PASSWORD" \
        --upload-file - \
        --insecure
        
    local result=$?
    if [ $result -eq 0 ]; then
        echo "[$TIMESTAMP] Email sent successfully: $subject" >> "$LOG_FILE"
    else
        echo "[$TIMESTAMP] ERROR: Failed to send email (code: $result)" >> "$LOG_FILE"
    fi
}

# Gestion des différents scénarios
case "$ROLE" in
    "master")
        if [ "$PREVIOUS_ROLE" != "master" ]; then
            # Failover détecté
            SUBJECT="🚨 PostgreSQL Failover - $CLUSTER_NAME"
            MESSAGE="Un failover a été effectué sur le cluster PostgreSQL.

Détails:
- Nouveau Master: $HOSTNAME
- Ancien Rôle: $PREVIOUS_ROLE
- Cluster: $SCOPE

Action requise: Vérifier l'état du cluster et la cause du failover."
            
            send_email "$SUBJECT" "$MESSAGE"
        else
            echo "[$TIMESTAMP] Master role maintained, no notification needed" >> "$LOG_FILE"
        fi
        ;;
        
    "replica")
        if [ "$PREVIOUS_ROLE" == "master" ]; then
            # Déchéance du master
            SUBJECT="⚠️ PostgreSQL Master Demotion - $CLUSTER_NAME"
            MESSAGE="Le nœud a perdu son rôle de master.

Détails:
- Nœud: $HOSTNAME
- Nouveau Rôle: $ROLE
- Cluster: $SCOPE

Vérification: S'assurer qu'un nouveau master a été élu."
            
            send_email "$SUBJECT" "$MESSAGE"
        fi
        ;;
        
    "uninitialized")
        SUBJECT="🔴 PostgreSQL Node Uninitialized - $CLUSTER_NAME"
        MESSAGE="Le nœud PostgreSQL est dans un état non initialisé.

Détails:
- Nœud: $HOSTNAME
- Cluster: $SCOPE

Action: Investigation requise."
        
        send_email "$SUBJECT" "$MESSAGE"
        ;;
        
    *)
        echo "[$TIMESTAMP] Unknown role: $ROLE" >> "$LOG_FILE"
        ;;
esac

exit 0