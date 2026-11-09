
"""
=============================================================================
POSTGRES HA LAB - MODÈLE DES RÉSULTATS DE TEST
=============================================================================

Ce modèle conserve l'historique des exécutions des scénarios PostgreSQL HA.

Chaque clic sur le bouton "Exécuter" doit produire un nouvel enregistrement.

Exemple :
    Test de réplication
        ├── Exécution 1 : Réussie
        ├── Exécution 2 : Échouée
        └── Exécution 3 : Réussie

Les résultats ne sont jamais remplacés par l'exécution suivante.

Cela permet de suivre l'évolution de la fiabilité du cluster dans le temps.
=============================================================================
"""

from odoo import fields, models


class PostgresHATestResult(models.Model):
    _name = "postgres.ha.test.result"
    _description = "Résultat d'exécution d'un test PostgreSQL HA"
    _order = "execution_date desc, id desc"

    # ---------------------------------------------------------------------
    # IDENTIFICATION
    # ---------------------------------------------------------------------

    name = fields.Char(
        string="Référence",
        required=True,
        default="Nouvelle exécution",
        copy=False
    )

    test_id = fields.Many2one(
        comodel_name="postgres.ha.test",
        string="Scénario",
        required=True,
        ondelete="cascade",
        index=True
    )

    # ---------------------------------------------------------------------
    # ÉTAT DE L'EXÉCUTION
    # ---------------------------------------------------------------------

    status = fields.Selection(
        selection=[
            ("pending", "En attente"),
            ("running", "En cours"),
            ("success", "Réussi"),
            ("failed", "Échoué"),
            ("error", "Erreur technique"),
            ("cancelled", "Annulé"),
        ],
        string="Résultat",
        default="pending",
        required=True,
        index=True
    )

    execution_date = fields.Datetime(
        string="Début de l'exécution",
        default=fields.Datetime.now,
        required=True,
        index=True
    )

    finished_date = fields.Datetime(
        string="Fin de l'exécution"
    )

    duration = fields.Float(
        string="Durée (secondes)",
        digits=(10, 2),
        help="Temps total écoulé entre le début et la fin du test."
    )

    # ---------------------------------------------------------------------
    # INFORMATIONS SUR LE LEADER
    # ---------------------------------------------------------------------

    leader_before = fields.Many2one(
        comodel_name="postgres.ha.node",
        string="Leader avant le test"
    )

    leader_after = fields.Many2one(
        comodel_name="postgres.ha.node",
        string="Leader après le test"
    )

    # ---------------------------------------------------------------------
    # RAPPORT TECHNIQUE
    # ---------------------------------------------------------------------

    details = fields.Text(
        string="Détails techniques",
        help=(
            "Compte rendu détaillé de l'exécution : "
            "opérations réalisées, nœuds vérifiés et résultats obtenus."
        )
    )

    error_message = fields.Text(
        string="Message d'erreur",
        help="Message technique lorsqu'une opération ne peut pas aboutir."
    )
