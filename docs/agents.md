# Relais des agents

| Agent | Mission et sortie | Limite |
|---|---|---|
| Chef d'orchestre | Applique le relais et trace le résultat | Aucune décision propre |
| Éclaireur | Transmet le signal et les métriques du marché | Aucun ordre ni classement |
| Météo | Explique l'aversion au risque de cinq marchés | Aucun veto direct |
| Filtre | Rejette spreads, chocs, cassures dépassées, pauses, marchés fermés et expositions incompatibles | Aucun dimensionnement |
| Analyste | Note la fréquence de gains et l'espérance nette en R du même module | Rejette moins de 100 observations ou une espérance ≤ 0,1 R |
| Trésorier | Propose un lot dans les plafonds de risque et réduit la taille en contexte défavorable | Aucun envoi |
| Veto | Autorise ou bloque une proposition | Aucune modification de l'ordre |
| Exécuteur | Réserve l'identifiant, transmet au courtier injecté et rapproche les réponses incertaines | Pas de doublon ni d'ordre sans stop |
| Gardien | Propose le prix d'entrée à +1 R et un stop suiveur à partir de +2 R | Aucun recul de stop ni ouverture |
| Greffier | Conserve le relais dans SQLite et exporte les décisions en CSV | Aucune modification des décisions |
| Chercheur | La frontière de proposition est limitée aux paramètres permis | Appels hebdomadaires et génération automatique à raccorder |
