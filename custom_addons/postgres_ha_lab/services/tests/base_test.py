
"""
=============================================================================
POSTGRES HA LAB - CLASSE DE BASE DES SCÉNARIOS
=============================================================================

Tous les scénarios de test du cluster doivent hériter de BaseHATest.

Cette classe définit le contrat commun que chaque scénario doit respecter.

Un scénario doit notamment :
    - recevoir l'environnement Odoo ;
    - exécuter ses opérations sur le cluster ;
    - retourner un résultat structuré au moteur central.

Les opérations spécifiques (réplication, failover, etc.) seront définies
dans des classes séparées.

Cette approche facilite l'ajout de nouveaux scénarios à l'avenir.
=============================================================================
"""


class BaseHATest:
    """
    Classe mère de tous les scénarios PostgreSQL HA.

    Attributs :
        env:
            Environnement Odoo permettant d'accéder aux modèles et services.

    Chaque classe fille doit implémenter la méthode run().
    """

    def __init__(self, env):
        self.env = env

    def run(self):
        """
        Exécute le scénario.

        Cette méthode doit être redéfinie par chaque scénario concret.

        Returns:
            dict:
                status : success ou failed
                details : compte rendu technique
                leader_before : nom DNS du Leader avant le test
                leader_after : nom DNS du Leader après le test

        Raises:
            NotImplementedError:
                Si une classe fille ne définit pas sa propre méthode run().
        """
        raise NotImplementedError(
            "Chaque scénario doit implémenter sa propre méthode run()."
        )
