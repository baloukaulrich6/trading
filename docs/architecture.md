# Architecture

```mermaid
flowchart LR
  MT5[Terminal Windows] --> Export[Export D1 en lecture seule]
  Export --> Cache[Import validé et cache SQLite]
  Cache --> Test[Backtest net et walk-forward]
  Cache --> E[Éclaireur]
  E --> F[Filtre]
  F --> A[Analyste]
  A --> T[Trésorier]
  T --> V[Veto injecté]
  V --> X[Exécuteur à courtier injecté]
  X --> R[Rapprochement SQLite]
  E --> J[Greffier]
  X -. intégration à terminer .-> MT5
```

Le pipeline de recherche et l'exécuteur injecté sont séparés des lanceurs historiques.
L'ancien service Windows, son tableau et ses notifications continuent d'utiliser leurs
points d'entrée historiques. Les résultats de recherche ne changent pas le robot en service.
