# Décisions d'architecture

## Migration progressive

Le paquet `src/nkap` accueille les nouveaux composants. Les lanceurs MT5, l'interface et les scripts historiques restent disponibles pendant la migration. La recherche n'a aucune route vers un compte de courtage.

Le dossier `config/` contient l'univers, le champion initial et les limites. L'ancien `config.py` continue d'alimenter les lanceurs historiques pendant leur migration. `CODEX.md` porte les consignes et `CLAUDE.md` y renvoie.
