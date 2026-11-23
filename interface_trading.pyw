"""Interface locale de lecture et de simulation pour MetaTrader 5."""
import json
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import messagebox, ttk

ETAT_AUTOMATIQUE = Path(__file__).with_name("automatique_etat.json")


class Compagnon(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        fond = "#13243a"
        self.dessin = tk.Canvas(self, width=90, height=96, bg=fond, highlightthickness=0)
        self.dessin.pack(side="left")
        self.dessin.create_oval(20, 76, 70, 84, fill="#0b1424", outline="")
        self.dessin.create_line(45, 20, 45, 34, fill="#7cc9f8", width=3, tags="robot")
        self.signal = self.dessin.create_oval(40, 15, 50, 25, fill="#f6af69", outline="", tags="robot")
        self.dessin.create_rectangle(18, 34, 72, 70, fill="#36658a", outline="#7cc9f8", width=2, tags="robot")
        self.dessin.create_rectangle(25, 41, 65, 61, fill="#102132", outline="", tags="robot")
        for x in (34, 50):
            self.dessin.create_oval(x, 46, x + 6, 53, fill="#c2f6ff", outline="", tags="robot")
        self.texte = tk.StringVar()
        tk.Label(self, textvariable=self.texte, bg=fond, fg="#eaf6ff", font=("Segoe UI", 11),
                 anchor="w", justify="left", padx=12, wraplength=650).pack(side="left", fill="both", expand=True)
        self.pas = 0
        self.actif = False
        self.lire()
        self.animer()

    def lire(self):
        try:
            etat = json.loads(ETAT_AUTOMATIQUE.read_text(encoding="utf-8"))
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(etat["heure"])).total_seconds()
            self.actif = age < 180
            lignes = [f"Automatique · {etat['mode']} · {etat['statut']}" if self.actif
                      else f"Dernier rapport · {etat['mode']} · mise à jour en attente"]
            for rapport in etat["rapports"]:
                net = rapport["resultat"]
                resultat = f"{net:+.2f} {rapport['devise']}" if net is not None else "indisponible"
                semaine = rapport.get("resultat_semaine")
                hebdo = f"{semaine:+.2f} {rapport['devise']}" if semaine is not None else "indisponible"
                lignes.append(f"{rapport['courtier']}  |  {rapport['positions']} position(s) du robot"
                              f"  |  Jour : {resultat}  |  Semaine : {hebdo}")
            self.texte.set("\n".join(lignes))
        except (OSError, ValueError, KeyError):
            self.actif = False
            self.texte.set("Surveillance automatique en attente d’un premier rapport.")
        self.after(3000, self.lire)

    def animer(self):
        self.pas = (self.pas + 1) % 8
        self.dessin.move("robot", 0, -1 if self.pas < 4 else 1)
        self.dessin.itemconfigure(self.signal, fill="#72ded0" if self.actif else "#f6af69")
        self.after(170, self.animer)


def charger_analyse(scenarios):
    import config as C
    from tableau_analyse import colonnes_analyse, relever_courtier

    comptes, lignes = [], []
    for conf in C.COURTIERS:
        if not conf["actif"]:
            continue
        nom = conf["nom"]
        try:
            resume, marches = relever_courtier(conf, scenarios)
            comptes.append(f"{nom} · {resume}")
            lignes.extend((nom, *marche) for marche in marches)
        except (OSError, RuntimeError, ValueError) as erreur:
            comptes.append(f"{nom} · Analyse indisponible ({erreur})")
    if not comptes:
        comptes.append("Active HFM_ACTIF ou EXNESS_ACTIF dans .env.")
    return ("Courtier", *colonnes_analyse(scenarios)), lignes, "\n".join(comptes)


class Interface:
    def __init__(self, fenetre):
        self.fenetre = fenetre
        self.resultats = Queue()
        self.occupe = False
        self.prochaine_analyse = None
        fenetre.title("Analyse MT5")
        fenetre.geometry("1260x670")
        fenetre.minsize(760, 490)

        panneau = ttk.Frame(fenetre, padding=20)
        panneau.pack(fill="both", expand=True)
        ttk.Label(panneau, text="Analyse MT5", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(panneau, text="Lecture seule · Dernières bougies D1 clôturées · Aucun ordre").pack(anchor="w", pady=(0, 14))
        Compagnon(panneau).pack(fill="x", pady=(0, 12))
        outils = ttk.Frame(panneau)
        outils.pack(fill="x")
        ttk.Label(outils, text="Capitaux fictifs (USD)").pack(side="left")
        self.capitaux = ttk.Entry(outils, width=24)
        self.capitaux.insert(0, "5.02 25 100 200")
        self.capitaux.pack(side="left", padx=8)
        self.actualiser = ttk.Button(outils, text="Actualiser", command=self.analyser)
        self.actualiser.pack(side="left", padx=4)
        self.diagnostic = ttk.Button(outils, text="Tester MT5 et Claude", command=self.tester_api)
        self.diagnostic.pack(side="left", padx=4)

        self.resume = tk.StringVar()
        ttk.Label(panneau, textvariable=self.resume, wraplength=690).pack(anchor="w", pady=(12, 6))
        grille = ttk.Frame(panneau)
        grille.pack(fill="both", expand=True)
        grille.columnconfigure(0, weight=1)
        grille.rowconfigure(0, weight=1)
        self.tableau = ttk.Treeview(grille, show="headings")
        barre_x = ttk.Scrollbar(grille, orient="horizontal", command=self.tableau.xview)
        barre_y = ttk.Scrollbar(grille, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(xscrollcommand=barre_x.set, yscrollcommand=barre_y.set)
        self.tableau.grid(row=0, column=0, sticky="nsew")
        barre_x.grid(row=1, column=0, sticky="ew")
        barre_y.grid(row=0, column=1, sticky="ns")

        self.statut = tk.StringVar()
        ttk.Label(panneau, textvariable=self.statut, wraplength=690).pack(anchor="w", pady=(10, 4))
        self.rapport_api = tk.StringVar()
        ttk.Label(panneau, textvariable=self.rapport_api, wraplength=690).pack(anchor="w")
        ttk.Label(panneau, text="Capital minimal estimé au stop, hors marge et frais. Actualisation chaque minute.").pack(anchor="w")
        fenetre.after(150, self.lire_resultat)
        self.analyser()

    def analyser(self):
        from argparse import ArgumentTypeError

        if self.occupe:
            return
        if self.prochaine_analyse is not None:
            self.fenetre.after_cancel(self.prochaine_analyse)
            self.prochaine_analyse = None
        try:
            from tableau_analyse import capital_positif

            scenarios = [capital_positif(v) for v in self.capitaux.get().split()]
            if not 1 <= len(scenarios) <= 6:
                raise ValueError("Saisis de 1 à 6 montants séparés par des espaces.")
        except (ArgumentTypeError, ImportError, ValueError) as erreur:
            self.statut.set(str(erreur))
            return
        self.demarrer("analyse", charger_analyse, scenarios)

    def tester_api(self):
        from tester_api import diagnostic

        self.demarrer("api", diagnostic)

    def demarrer(self, operation, fonction, *args):
        self.occupe = True
        self.actualiser.state(["disabled"])
        self.diagnostic.state(["disabled"])
        self.statut.set("Connexion et lecture en cours…" if operation == "analyse" else "Diagnostic en cours…")

        def executer():
            try:
                self.resultats.put((operation, fonction(*args), None))
            except Exception as erreur:
                self.resultats.put((operation, None, str(erreur)))

        Thread(target=executer, daemon=True).start()

    def lire_resultat(self):
        try:
            operation, resultat, erreur = self.resultats.get_nowait()
        except Empty:
            self.fenetre.after(150, self.lire_resultat)
            return
        self.occupe = False
        self.actualiser.state(["!disabled"])
        self.diagnostic.state(["!disabled"])
        if erreur:
            self.statut.set(f"Erreur : {erreur}")
        elif operation == "analyse":
            colonnes, lignes, resume = resultat
            self.resume.set(resume)
            self.tableau.delete(*self.tableau.get_children())
            identifiants = [str(i) for i in range(len(colonnes))]
            self.tableau.configure(columns=identifiants)
            for identifiant, titre in zip(identifiants, colonnes):
                self.tableau.heading(identifiant, text=titre)
                self.tableau.column(identifiant, width=250 if titre == "Signal" else max(82, 9 * len(titre)), stretch=False)
            for ligne in lignes:
                self.tableau.insert("", "end", values=ligne)
            self.statut.set(f"Dernière lecture à {datetime.now():%H:%M:%S} (heure du PC).")
        else:
            code, messages = resultat
            self.rapport_api.set("\n".join(messages))
            self.statut.set("Diagnostic réussi." if code == 0 else "Diagnostic terminé avec erreur.")
        if self.prochaine_analyse is not None:
            self.fenetre.after_cancel(self.prochaine_analyse)
        self.prochaine_analyse = self.fenetre.after(60_000, self.analyser)
        self.fenetre.after(150, self.lire_resultat)


if __name__ == "__main__":
    racine = tk.Tk()
    try:
        Interface(racine)
        racine.mainloop()
    except Exception as erreur:
        messagebox.showerror("Analyse MT5", str(erreur))
