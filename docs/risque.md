# Limites de risque

Le module `nkap.risque` contrôle le budget par position, le risque cumulé, le nombre de
positions, l'exposition au même actif dans le même sens, les pertes du jour, les séries
de pertes et le recul depuis le sommet. Les références de capital et le risque ouvert
sont des entrées injectées par l'appelant. Des valeurs inconnues empêchent une entrée.

L'exécuteur de recherche vérifie le type et l'identité du compte ainsi que le stop. Une
réponse ambiguë bloque les nouveaux envois de ce compte jusqu'au rapprochement. Le mode
REEL de ce composant exige une preuve de validation. Les lanceurs historiques utilisant
`MODE=ORDRES` restent séparés et ne constituent pas une validation de ces règles.
