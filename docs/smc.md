# Construction SMC

1. **Signaux.** La confirmation des pivots attend deux bougies de chaque côté par défaut.
   Une cassure de clôture donne un BOS ou un CHoCH selon le dernier sens de structure.
   Une zone FVG directionnelle est valable douze bougies au plus et disparaît lorsqu'elle
   est entièrement comblée. Le score additionne structure (35), FVG (30), déplacement
   (20) et continuité (15). Le seuil initial est 65 sur 100. Le score est une mesure
   de confluence, sans interprétation probabiliste.
2. **Risque.** L'exécuteur utilise le contrôle indépendant et les limites versionnées,
   avec risque de base de 1 %, risque ouvert de 4 % et coupe-circuits. Il recalcule le
   risque auprès de MT5 au moment de l'envoi.
3. **MT5.** L'adaptateur vérifie compte, position existante, marge, stop et contrôle
   préalable avant envoi. Il conserve la référence d'ordre et permet le rapprochement.
   Le déplacement du stop conserve le take-profit et refuse de reculer le stop.
4. **Backtest.** Le profil SMC exige cinq ans de bougies clôturées. Il sépare trois ans
   de formation, un an hors échantillon et un an de réserve. Les paramètres sont fixes
   dans cette première comparaison. Le stop structurel reste ancré au pivot, et une
   ouverture déjà au-delà du stop invalide le signal. Les frais et le glissement sont
   des hypothèses explicites fournies au lancement. Ce profil ne remplace pas le
   walk-forward à trois fenêtres exigé pour l'admission réelle.
5. **Claude.** Le superviseur consomme un bilan via un transport injecté, sous un budget
   réservé. Il produit un résumé, un post-mortem et des alertes, sans envoi ni changement
   de paramètres. L'appel Anthropic réel et sa planification restent à raccorder.
6. **Tableau.** L'export HTML affiche courbe d'équité, win rate, profit factor, drawdown
   et journal du test hors échantillon. Il est distinct du tableau HFM actif.

Sur Windows avec MT5 ouvert, exporte la source avec
`python scripts/exporter_d1.py --courtier HFM --barres 1600`. Vérifie dans le manifeste
la période réellement reçue. Utilise `nkap-backtest --help` pour les unités des coûts.
Le mode `--smc --html rapport_smc.html` génère le tableau. Ne passe `--reserve`
qu'une fois les paramètres et les coûts arrêtés. Aucune méthode de cette branche
n'est reliée à la tâche Windows d'envoi d'ordres.
