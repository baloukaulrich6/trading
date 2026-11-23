# Adaptation et validation

Le walk-forward entraîne le choix EBSW/ER sur une fenêtre ancrée d'au moins trois ans
et teste l'année suivante. Les douze derniers mois sont exclus de cette sélection.
Le rapport compare les règles seules à une variante avec Filtre et Analyste. Il
n'invente ni données météo ni réponses Claude historiques.

Le registre SQLite accepte des paramètres bornés et exige un résultat d'évaluation
admissible, une confirmation humaine et quatre semaines positives en mode fantôme.
La rétrogradation restaure la version précédente et indique un facteur de risque de
0,5. Le lancement et le suivi des campagnes fantômes ne sont pas encore automatisés.
