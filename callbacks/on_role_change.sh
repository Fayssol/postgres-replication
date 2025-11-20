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

# Log de débogage - voir tous les arguments
echo "$(date) - DEBUG: All args: $@" >> /var/log/patroni/callbacks.log

# Détection automatique du format des arguments
# Format 1: $1=cluster_name, $2=role, $3=action, $4=scope
# Format 2: $1=action, $2=role, $3=cluster_name, $4=scope

if [ "$1" = "on_role_change" ] || [ "$1" = "on_start" ] || [ "$1" = "on_stop" ] || [ "$1" = "on_restart" ]; then
    # Format 2 détecté: action, role, cluster_name, scope
    ACTION="$1"
    ROLE="$2"
    CLUSTER_NAME="$3"
    SCOPE="$4"
    echo "$(date) - DEBUG: Format 2 detected - Action=$ACTION, Role=$ROLE, Cluster=$CLUSTER_NAME, Scope=$SCOPE" >> /var/log/patroni/callbacks.log
else
    # Format 1 par défaut: cluster_name, role, action, scope
    CLUSTER_NAME="$1"
    ROLE="$2"
    ACTION="$3"
    SCOPE="$4"
    echo "$(date) - DEBUG: Format 1 detected - Cluster=$CLUSTER_NAME, Role=$ROLE, Action=$ACTION, Scope=$SCOPE" >> /var/log/patroni/callbacks.log
fi

# Journalisation
echo "$(date) - Callback: Cluster=$CLUSTER_NAME, Role=$ROLE, Action=$ACTION, Scope=$SCOPE, Node=$(hostname)" >> /var/log/patroni/callbacks.log

# ENVOYER UN EMAIL UNIQUEMENT LORS D'UN CHANGEMENT DE RÔLE VERS MASTER
if [ "$ACTION" = "on_role_change" ] && [ "$ROLE" = "master" ]; then
    # Déterminer le nom du nœud
    case "$(hostname)" in
        "patroni1-container"|*"1"*) NODE_NAME="patroni1" ;;
        "patroni2-container"|*"2"*) NODE_NAME="patroni2" ;;
        "patroni3-container"|*"3"*) NODE_NAME="patroni3" ;;
        *) NODE_NAME="$(hostname)" ;;
    esac
    
    SUBJECT="🔄 PATRONI ALERT: Basculement - $NODE_NAME est le nouveau Master"
    MESSAGE="🚨 UN BASculeMENT a été détecté dans le cluster Patroni.

🔍 **DÉTAILS TECHNIQUES :**
- 📊 Cluster: $CLUSTER_NAME
- ⬆️ Nouveau Master: $NODE_NAME
- 🖥️ Nœud: $(hostname)
- 🕐 Heure: $(date)

📈 **IMPLICATIONS :**
- Le cluster a automatiquement élu $NODE_NAME comme nœud principal
- La réplication vers les autres nœuds va reprendre
- Aucune intervention manuelle requise

💡 **ACTIONS RECOMMANDÉES :**
1. Surveiller les performances du nouveau master
2. Vérifier la synchronisation des replicas
3. Investiguer la cause du basculement"

    # Envoyer l'email
    echo "$(date) - 🚨 BASCULEMENT DÉTECTÉ - Envoi d'email..." >> /var/log/patroni/callbacks.log

    sendEmail -f "$FROM_EMAIL" \
        -t "$TO_EMAIL" \
        -u "$SUBJECT" \
        -m "$MESSAGE" \
        -s "$SMTP_SERVER:$SMTP_PORT" \
        -xu "$SMTP_USERNAME" \
        -xp "$SMTP_PASSWORD" \
        -o tls=yes 2>&1 >> /var/log/patroni/callbacks.log

    if [ $? -eq 0 ]; then
        echo "$(date) - ✅ Email sent successfully" >> /var/log/patroni/callbacks.log
    else
        echo "$(date) - ❌ Failed to send email" >> /var/log/patroni/callbacks.log
    fi

elif [ "$ACTION" = "on_role_change" ] && [ "$ROLE" = "replica" ]; then
    # Log mais pas d'email pour les devenirs replica
    echo "$(date) - ℹ️  Node became replica - no email sent" >> /var/log/patroni/callbacks.log
else
    echo "$(date) - 🔇 Action ignored: $ACTION (Role: $ROLE)" >> /var/log/patroni/callbacks.log
fi

exit 0