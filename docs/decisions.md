# Décisions d'architecture

## Migration progressive

Le paquet `src/nkap` accueille les nouveaux composants. Les lanceurs MT5, l'interface et les scripts historiques restent disponibles pendant la migration. La recherche n'a aucune route vers un compte de courtage.

Le dossier `config/` contient l'univers, le champion initial et les limites. L'ancien `config.py` continue d'alimenter les lanceurs historiques pendant leur migration. `CODEX.md` porte les consignes et `CLAUDE.md` y renvoie.

## Admission réelle

La recherche n'a pas reçu de série HFM avec coûts historiques ni de preuve d'une semaine en
démo. La variante multi-agents ne peut donc pas être admise en réel. La couverture de code
et les résultats sur données synthétiques vérifient le comportement du moteur, et ne mesurent
pas sa rentabilité.

Le registre Claude fonctionne avec un transport injecté. L'accès aux tarifs officiels a été
refusé depuis le cloud. Le transport Anthropic réel, le cache et le traitement Batch restent
à valider avant de comptabiliser des appels de production dans le nouveau budget.
