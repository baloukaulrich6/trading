# Robot de trading Turtles + Ehlers + veto Claude

Robot Python pour MetaTrader 5 (Exness et HFM), sur graphique journalier.

- **Module Turtles** : suit les tendances (cassure du plus haut ou plus bas de 20 jours).
- **Module contrarien** : achète la panique quand le marché tourne en cycles (RSI sur 2 jours).
- **Détecteur de régime** : l'Even Better Sinewave de John Ehlers choisit le module actif.
- **Risque** : 1 % du capital par trade, 4 positions au maximum, arrêt si le capital perd 20 %.
- **Claude** : simple droit de veto (annonces économiques, événements). Il ne propose jamais de trade.

## Installation (PC Windows)

1. Installe Python 3.11 depuis python.org et coche « Add Python to PATH ».
2. Installe MetaTrader 5 deux fois, dans `C:\MT5_Exness` et `C:\MT5_HFM`.
3. Dans le dossier du robot : `pip install -r requirements.txt`
4. Copie `.env.example` en `.env`, puis remplis les mots de passe et la clé API.
5. Utilise d'abord un **compte démo**.

Si la connexion échoue avec `-10005 (IPC timeout)` et réussit avec un délai plus long, ajoute `MT5_TIMEOUT_MS=1200000` à ton `.env` pour autoriser jusqu'à 20 minutes. Sans ce réglage, le délai est d'une minute.

## Commandes, dans l'ordre

Sur Windows, laisse MetaTrader 5 ouvert et double-clique sur `Ouvrir_Trading.vbs` pour afficher le tableau sans console. L'interface lit les bougies D1 clôturées à l'ouverture, puis chaque minute. Tu peux saisir jusqu'à six capitaux fictifs séparés par des espaces et cliquer sur **Actualiser**. **Tester MT5 et Claude** lance le diagnostic à la demande, avec la clé API de ton `.env`. L'interface fonctionne en lecture seule.

| Commande | Ce qu'elle fait |
| --- | --- |
| `python tests_robot.py` | Teste toute la logique sans MetaTrader (prix inventés) |
| `python verifier_connexion.py` | Vérifie la connexion, les symboles et la taille possible des positions |
| `python tester_api.py` | Vérifie la lecture d'une bougie MT5 et la réponse du modèle Claude sur un exemple fictif à volume nul |
| `python backtest.py` | Teste les stratégies sur l'historique réel du courtier |
| `python tableau_analyse.py --capital 25 50 100 200` | Génère le tableau HTML des signaux D1 et des tailles de position pour quatre capitaux fictifs |
| `python robot.py` | Lance le robot : une fois par jour, vers 7 h (heure de Douala) |

Ouvre `tableau_analyse.html` dans ton navigateur après l'exécution. Le compte peut rester vide. Les capitaux sont exprimés en USD, même sur un compte Cent en USC. Chaque nouvelle exécution actualise le rapport à partir des dernières bougies journalières clôturées. Aucun ordre n'est envoyé.

### Exécution automatique sur Windows

Depuis PowerShell, lance `powershell -NoProfile -ExecutionPolicy Bypass -File .\Installer_Automatique.ps1`. La tâche démarre immédiatement et à chaque ouverture de ta session Windows. Laisse le PC éveillé et le lecteur du projet accessible dans ta session. La tâche relit MT5 chaque minute. Le robot utilise la dernière clôture D1 confirmée par HFM et ne tente qu'une entrée par symbole et par clôture. Il réévalue les signaux si le solde change, et bloque les nouvelles entrées sans fonds ou sans signal admissible.

La tâche lit le fichier `.env`. Pour le réel, active `HFM_ACTIF=oui`, `EXNESS_ACTIF=non`, `CLAUDE_ACTIF=oui`, `MODE=ORDRES` et `COMPTE_REEL_CONFIRME=oui`, puis redémarre la tâche après un changement. Le mode par défaut reste `TEST`. Quand la tâche tourne, utilise l'interface pour l'observer et évite de lancer `robot.py` en parallèle.

Le tableau animé Nkap est accessible à `http://127.0.0.1:8765` depuis le navigateur de la machine où tourne la tâche. Il affiche les positions, l'activité récente et les résultats du jour et de la semaine des opérations identifiées comme celles du robot par MT5. `Ouvrir_Trading.vbs` conserve le tableau Windows. Les nouvelles entrées automatiques sont possibles du lundi au vendredi, de 09 h à minuit par défaut, heure de Douala. Ajuste `HEURE_EXECUTION` et `HEURE_LIMITE` dans `.env` si nécessaire. Utilise `00:00` comme heure de fin pour minuit. Les règles de clôture continuent d'être évaluées hors de cette fenêtre.

Les rapports locaux sont conservés dans `rapports_automatiques`. Pour les recevoir sur Telegram, crée un bot avec @BotFather, mets son jeton dans `TELEGRAM_TOKEN` dans `.env`, envoie un message au bot et lance `python notifications.py` pour retrouver ton `TELEGRAM_CHAT_ID`. Relance la tâche après configuration. Les alertes couvrent les exécutions MT5 identifiées, avec un bilan le soir en semaine et le samedi à partir de 10 h, heure de Douala. Le rapport est calculé dans la devise du compte.

Relance l'installateur avec `-Statut` pour lire le dernier rapport et l'état de la tâche, avec `-Pause` pour désactiver et arrêter la tâche, ou avec `-Desinstaller` pour la retirer. Le lancement de l'installateur sans argument la réactive. Les positions déjà ouvertes restent chez HFM et demeurent visibles dans MT5.

### Déplacer le robot vers OVHcloud

Choisis une offre x64 permettant d'installer **Windows** et d'accéder en Bureau à distance. Vérifie auprès d'OVHcloud que l'offre choisie inclut ou permet une licence Windows compatible. Installe le terminal HFM MT5, Git, Python 3.11 et les dépendances sur le VPS. Clone dans un dossier local, par exemple `C:\Trading`, recrée `.venv`, configure ton `.env` localement et mets à jour `HFM_CHEMIN` avec le chemin du terminal sur le VPS.

Avant de basculer le même compte, mets l'ancienne tâche en pause. Copie `automatique.sqlite3`, `etat.json` s'il existe et tes rapports locaux pendant l'arrêt pour conserver les passages déjà effectués, les alertes déjà envoyées et l'état de risque. Exécute d'abord `tester_api.py` puis la tâche en `MODE=TEST`. Déconnecte la fenêtre RDP sans fermer la session Windows, reconnecte-toi un peu plus tard et vérifie avec `Installer_Automatique.ps1 -Statut` que le rapport a avancé. Après un redémarrage du VPS, ouvre la session Windows pour relancer la tâche. Deux ou trois jours permettent de vérifier la continuité du service, les reconnexions et les alertes, même si aucun signal ne débouche sur un ordre.

### Afficher les décisions dans MetaTrader 5

Dans MT5, ouvre **Fichier → Ouvrir le dossier des données**, copie `SuiviRobot.mq5` dans `MQL5\Indicators`, puis ouvre ce fichier dans MetaEditor et compile-le avec **F7**. Depuis **Navigateur → Indicateurs** dans MT5, ajoute **SuiviRobot** au graphique du symbole. Lance `robot.py` pour publier le dernier état. Le graphique affiche les décisions et les résultats d'envoi, et l'onglet **Trade** affiche les positions exécutées par MT5.

Sur un compte HFM en USC, ouvre les graphiques des symboles Cent, par exemple `XAUUSDc` pour l'or. L'indicateur affiche les tickets ouverts du robot, leur résultat latent et le résultat net des transactions marquées par le robot sur ce symbole depuis 30 jours. L'onglet **Historique** de MT5 reste la référence pour le détail complet du compte.

Le robot effectue un passage par lancement sur les dernières bougies D1 clôturées. En `MODE=ORDRES`, vérifie dans **Outils → Options → Expert Advisors** que le trading algorithmique est autorisé, y compris via l'API Python. Le passage sur un compte non-démo exige également `COMPTE_REEL_CONFIRME=oui`. Le solde, le volume minimal, la marge et les règles du courtier peuvent empêcher l'exécution d'un ordre.

Une nouvelle entrée sur un compte réel requiert aussi `CLAUDE_ACTIF=oui` et un avis favorable de Claude après le contrôle de risque. Les clôtures du robot suivent leurs propres règles et restent indépendantes du veto.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `config.py` | Tous les réglages |
| `indicateurs.py` | ATR, canaux de Donchian, RSI, Even Better Sinewave |
| `strategie.py` | Règles d'entrée et de sortie |
| `risque.py` | Taille des positions et arrêt d'urgence |
| `courtier.py` | Connexion MT5, données et ordres |
| `veto_claude.py` | Veto de Claude avec recherche web |
| `robot.py` | Programme principal |
| `backtest.py` | Test sur l'historique |
| `verifier_connexion.py` | Diagnostic avant de lancer le robot |
| `tests_robot.py` | Tests automatiques |
| `PROMPT_INTEGRATION.md` | Prompt complet pour continuer le développement avec Claude |

## Sécurité

- `MODE=TEST` par défaut : aucun ordre n'est envoyé.
- Sur un serveur réel (nom contenant « Real » ou « Live »), aucun ordre ne part sans `COMPTE_REEL_CONFIRME=oui`.
- Ne partage jamais le fichier `.env`.
- Résultats passés ≠ résultats futurs. La majorité des comptes CFD de particuliers perdent de l'argent.

## Recherche Nkap multi-agents

Installe le paquet avec `python -m pip install -e ".[dev]"`, puis consulte
[la procédure d'export et de validation](docs/exploitation.md). Le rapport de recherche
ne modifie pas les paramètres des lanceurs MT5 existants. L'avancement et les écarts
sont consignés dans [les décisions](docs/decisions.md).
