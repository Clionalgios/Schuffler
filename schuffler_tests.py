#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# python3 schuffler_tests.py --prog ./schuffler.sh
# python3 schuffler_tests.py --prog ./v2/schuffler.sh --attendus attendus.json
# python3 schuffler_tests.py --prog ./schuffler.sh --categorie "Mode API"
# python3 schuffler_tests.py --prog ./schuffler.sh --enregistrer reel.json

"""
Cadre de test scripté pour Schuffler.

Objectif :
    Jouer de manière reproductible les scénarios du schéma de test et vérifier
    que chaque version du programme produit la sortie attendue. Les sorties non
    encore définies sont représentées par la valeur None (placeholder) : le
    scénario est exécuté et la sortie réelle est mesurée et consignée, mais
    aucune vérification d'égalité n'est opérée et aucun échec n'est déclenché.
    Une fois la valeur consolidée dans le schéma de test, il suffit de la
    renseigner (dans la constante A_DEFINIR remplacée, ou dans le fichier
    d'attendus JSON) pour qu'elle devienne contraignante.

Convention des attendus :
    - attendu absent ou None                : à définir (non contraignant) ;
    - chaîne littérale                      : égalité stricte avec la sortie
                                              (hors saut de ligne final) ;
    - chaîne préfixée par « contient: »     : vérification de sous-chaîne ;
    - code_retour                           : code de sortie du processus.

Déterminisme :
    Les scénarios portant executions > 1 sont exécutés plusieurs fois ; les
    sorties successives doivent être identiques entre elles, indépendamment
    de toute valeur attendue.

Presse-papiers :
    La lecture du presse-papiers nécessite l'un des outils suivants :
    xclip, xsel, wl-paste (Wayland) ou pbpaste (macOS). En son absence, la
    vérification du presse-papiers est marquée INDÉTERMINÉE (jamais en échec).

Utilisation :
    python schuffler_tests.py --prog ./schuffler.sh
    python schuffler_tests.py --prog ./schuffler.sh --categorie "Mode API"
    python schuffler_tests.py --prog ./schuffler.sh --enregistrer reel.json
    python schuffler_tests.py --prog ./schuffler.sh --attendus attendus.json
    python schuffler_tests.py --prog ./schuffler.sh --identifiant api-test
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import subprocess
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TIMEOUT_PAR_DEFAUT = 10  # secondes par exécution

# Outils de lecture du presse-papiers, par ordre de préférence.
OUTILS_LECTURE_PP = [
    ["xclip", "-o", "-selection", "clipboard"],
    ["xsel", "-ob"],
    ["wl-paste", "--no-newline"],
    ["pbpaste"],
]

# Commandes de vidage du presse-papiers associées, même ordre.
OUTILS_VIDAGE_PP = [
    ["xclip", "-selection", "clipboard", "/dev/null"],
    ["xsel", "-bc"],
    ["wl-copy", "--clear"],
    ["pbcopy"],
]

PREFIX_CONTIENT = "contient:"


# ---------------------------------------------------------------------------
# Définition des scénarios
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Scenario:
    identifiant: str
    categorie: str
    arguments: list
    # Secret fourni à l'invite (saisie invisible). None si le secret est
    # passé en argument ou si aucun secret n'est fourni.
    secret_stdin: Optional[str] = None
    # Nombre d'exécutions ( > 1 : contrôle du déterminisme).
    executions: int = 1
    # Attendus : clés parmi "stdout", "clipboard", "code_retour".
    attendus: dict = dataclasses.field(default_factory=dict)


def S(identifiant, categorie, arguments, secret_stdin=None,
      executions=1, **attendus):
    """Constructeur concis de scénario ; les attendus sont nommés."""
    return Scenario(identifiant, categorie, arguments, secret_stdin,
                    executions, attendus)


SCENARIOS = [
    # -- Catégorie 1 : Sans-mode (mode par défaut, presse-papiers) ---------
    S("s01", "Sans-mode", [], secret_stdin="monsecret"),
    S("s02", "Sans-mode", ["monsecret"]),
    S("s03", "Sans-mode", ["--length", "32", "--no-special", "monsecret"]),
    S("s04", "Sans-mode", ["-l", "4", "test"]),

    # -- Catégorie 2 : Mode API ---------------------------------------------
    S("api-sans-cle", "Mode API", ["-A"], secret_stdin="test",
      stdout=PREFIX_CONTIENT + "Erreur"),
    S("api-scanf", "Mode API", ["-A"], secret_stdin="monsecret"),
    S("api-test", "Mode API", ["-A", "test"],
      stdout="bafTBVD2lM%ZqIIOAHN6", code_retour=0),
    S("api-test1", "Mode API", ["-A", "test1"],
      stdout="1awABg92YU%JrQ33R*FB"),
    S("api-l50", "Mode API", ["-A", "-l", "50", "test"],
      stdout="b5UdvYAHNFWd!IIOrPnh%Zql3Me2lMeGjlBVDlM4FafTWKN%o6"),
    S("api-l4", "Mode API", ["-A", "-l", "4", "test"],
      stdout="Ba%2"),

    # -- Catégorie 3 : Mode Clipboard ---------------------------------------
    S("cb-defaut", "Mode Clipboard", ["test"],
      clipboard="bafTBVD2lM%ZqIIOAHN6"),
    S("cb-test", "Mode Clipboard", ["-C", "test"]),
    S("cb-monsecret", "Mode Clipboard", ["-C", "monsecret"]),
    S("cb-scanf", "Mode Clipboard", ["-C"], secret_stdin="monsecret"),

    # -- Catégorie 4 : Mode combiné -----------------------------------------
    S("ac-test", "Mode combiné", ["-A", "-C", "test"]),
    S("ca-test", "Mode combiné", ["-C", "-A", "test"]),
    S("ac-l50", "Mode combiné", ["-A", "-C", "-l", "50", "monsecret"]),

    # -- Catégorie 5 : Déterminisme ------------------------------------------
    S("det-api", "Déterminisme", ["-A", "test"], executions=2),
    S("det-l32", "Déterminisme", ["-A", "-l", "32", "test"], executions=2),

    # -- Catégorie 6 : Longueur ----------------------------------------------
    S("lg-20", "Longueur", ["-A", "-l", "20", "test"]),
    S("lg-4", "Longueur", ["-A", "-l", "4", "test"]),
    S("lg-3", "Longueur", ["-A", "-l", "3", "test"]),
    S("lg-100", "Longueur", ["-A", "-l", "100", "test"]),
    S("lg-non-num", "Longueur", ["-A", "-l", "abc", "test"]),

    # -- Catégorie 7 : Jeux de caractères (exclusions) -----------------------
    S("no-lower", "Exclusions", ["-A", "--no-lower", "test"]),
    S("no-upper", "Exclusions", ["-A", "--no-upper", "test"]),
    S("no-digits", "Exclusions", ["-A", "--no-digits", "test"]),
    S("no-special", "Exclusions", ["-A", "--no-special", "test"]),
    S("no-lower-upper", "Exclusions",
      ["-A", "--no-lower", "--no-upper", "test"]),
    S("no-trois", "Exclusions",
      ["-A", "--no-lower", "--no-upper", "--no-digits", "test"]),
    S("no-quatre", "Exclusions",
      ["-A", "--no-lower", "--no-upper", "--no-digits", "--no-special",
       "test"]),
    S("exclude-voyelles", "Exclusions",
      ["-A", "--exclude-chars", "aeiou", "-l", "50", "test"]),

    # -- Catégorie 8 : Jeu de spéciaux personnalisé ---------------------------
    S("sp-simple", "Spéciaux", ["-A", "--special-set", "@#%", "test"]),
    S("sp-exclude", "Spéciaux",
      ["-A", "--special-set", "@#$%", "--exclude-chars", "#", "test"]),
    S("sp-l50", "Spéciaux",
      ["-A", "--special-set", "@#%", "-l", "50", "test"]),
    S("sp-vide", "Spéciaux", ["-A", "--special-set", "", "test"]),

    # -- Catégorie 9 : Artefact -----------------------------------------------
    S("art-api", "Artefact", ["-A", "-a", "test"]),
    S("art-cb", "Artefact", ["-a", "test"]),
    S("art-l4", "Artefact", ["-A", "-a", "-l", "4", "test"]),

    # -- Catégorie 10 : Aide et erreurs d'appel -------------------------------
    S("aide-courte", "Aide et erreurs", ["-h"]),
    S("aide-longue", "Aide et erreurs", ["--help"]),
    S("opt-inconnue", "Aide et erreurs", ["--option-inconnue", "test"]),
    S("l-sans-valeur", "Aide et erreurs", ["-A", "-l"]),
    S("sp-sans-valeur", "Aide et erreurs", ["-A", "--special-set"]),
    S("exclude-sans-valeur", "Aide et erreurs", ["-A", "--exclude-chars"]),
]


# ---------------------------------------------------------------------------
# Cadre d'exécution
# ---------------------------------------------------------------------------

class CadreDeTest:

    def __init__(self, programme, attendus=None, timeout=TIMEOUT_PAR_DEFAUT):
        self.programme = programme
        self.timeout = timeout
        # Les attendus externes (fichier JSON) priment sur les attendus
        # intégrés : c'est ce qui garantit la comparaison entre versions.
        self.attendus = attendus or {}
        self.outil_pp = self._detecter_outil_pp()

    # -- Détection du presse-papiers --------------------------------------

    @staticmethod
    def _detecter_outil_pp():
        for lecture, vidage in zip(OUTILS_LECTURE_PP, OUTILS_VIDAGE_PP):
            if shutil.which(lecture[0]) and shutil.which(vidage[0]):
                return lecture, vidage
        return None

    def lire_presse_papiers(self):
        if self.outil_pp is None:
            return None
        lecture, _ = self.outil_pp
        resultat = subprocess.run(lecture, capture_output=True, text=True)
        if resultat.returncode != 0:
            return None
        return resultat.stdout.rstrip("\n")

    def vider_presse_papiers(self):
        if self.outil_pp is None:
            return
        _, vidage = self.outil_pp
        try:
            subprocess.run(vidage, input="", capture_output=True,
                           text=True, timeout=5)
        except subprocess.SubprocessError:
            pass

    # -- Exécution d'un scénario --------------------------------------------

    def executer_une_fois(self, scenario, avec_pp=False):
        """Exécute le programme une fois et renvoie les sorties réelles."""
        commande = [self.programme] + scenario.arguments
        entree = ""
        if scenario.secret_stdin is not None:
            entree = scenario.secret_stdin + "\n"

        if avec_pp:
            self.vider_presse_papiers()

        try:
            proc = subprocess.run(
                commande,
                input=entree,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            resultat = {
                "code_retour": proc.returncode,
                "stdout": proc.stdout.rstrip("\n"),
                "stderr": proc.stderr.rstrip("\n"),
            }
        except subprocess.TimeoutExpired:
            resultat = {
                "code_retour": None,
                "stdout": None,
                "stderr": "<délai dépassé>",
            }

        if avec_pp:
            resultat["clipboard"] = self.lire_presse_papiers()
            if resultat["clipboard"] is None and self.outil_pp is None:
                # Outil de lecture indisponible : la valeur est inconnue.
                pass
        return resultat

    def executer(self, scenario):
        """Exécute un scénario (une ou plusieurs fois selon `executions`)."""
        attendus = self.attendus.get(
            scenario.identifiant, scenario.attendus)

        # Le presse-papiers est capturé chaque fois qu'un outil de lecture est
        # disponible : il est systématiquement vidé avant l'exécution, de
        # manière à ce qu'une valeur résiduelle ne soit jamais interprétée
        # comme une sortie du programme.
        avec_pp = self.outil_pp is not None

        mesures = []
        for _ in range(scenario.executions):
            mesures.append(self.executer_une_fois(scenario, avec_pp=avec_pp))
        return attendus, mesures

    # -- Évaluation ---------------------------------------------------------

    @staticmethod
    def evaluer(cle, attendu, obtenu, pp_disponible):
        """Renvoie un statut parmi OK, ECHEC, A_DEFINIR, INDETERMINE."""
        if attendu is None:
            return "A_DEFINIR"
        if cle == "clipboard" and not pp_disponible:
            return "INDETERMINE"
        if obtenu is None:
            return "ECHEC"
        if isinstance(attendu, str) and attendu.startswith(PREFIX_CONTIENT):
            motif = attendu[len(PREFIX_CONTIENT):]
            return "OK" if motif in obtenu else "ECHEC"
        if attendu == obtenu:
            return "OK"
        return "ECHEC"

    def verifier(self, scenario):
        """Exécute puis évalue un scénario ; renvoie un rapport détaillé."""
        attendus, mesures = self.executer(scenario)
        derniere = mesures[-1]

        verdicts = {}
        details = []
        # Les trois sorties sont toujours évaluées : une sortie sans attendu
        # déclaré est signalée « à définir », avec la valeur réelle constatée,
        # de manière à faciliter le remplissage du schéma de test.
        for cle in ("stdout", "clipboard", "code_retour"):
            attendu = attendus.get(cle)
            statut = self.evaluer(
                cle, attendu, derniere.get(cle),
                pp_disponible=self.outil_pp is not None)
            verdicts[cle] = statut
            details.append((cle, attendu, derniere.get(cle), statut))

        # Contrôle du déterminisme : toutes les exécutions doivent coïncider.
        determinisme = None
        if scenario.executions > 1:
            signatures = {
                json.dumps({k: m.get(k) for k in ("stdout", "clipboard")},
                           sort_keys=True)
                for m in mesures
            }
            determinisme = "OK" if len(signatures) == 1 else "ECHEC"

        return {
            "scenario": scenario,
            "mesures": mesures,
            "details": details,
            "verdicts": verdicts,
            "determinisme": determinisme,
        }


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

STATUTS_AFFICHES = {
    "OK": "OK",
    "ECHEC": "ECHEC",
    "A_DEFINIR": "à définir",
    "INDETERMINE": "indéterminé",
}


def statut_global(rapport):
    statuts = {s for _, _, _, s in rapport["details"]}
    if "ECHEC" in statuts:
        return "ECHEC"
    if "A_DEFINIR" in statuts:
        return "A_DEFINIR"
    if "INDETERMINE" in statuts:
        return "INDETERMINE"
    return "OK"


def afficher_rapport(rapports, programme, pp_disponible):
    etat_pp = ("disponible" if pp_disponible
               else "NON disponible (vérifications clipboard indéterminées)")
    print(f"Programme testé : {programme}")
    print(f"Presse-papiers  : {etat_pp}")
    print("=" * 78)

    compteurs = {"OK": 0, "ECHEC": 0, "A_DEFINIR": 0, "INDETERMINE": 0}
    for rapport in rapports:
        scenario = rapport["scenario"]
        global_ = statut_global(rapport)
        compteurs[global_] = compteurs.get(global_, 0) + 1

        commande = " ".join([programme] + scenario.arguments)
        print(f"[{STATUTS_AFFICHES.get(global_, global_):^12}] "
              f"{scenario.identifiant:<22} {commande}")

        for cle, attendu, obtenu, statut in rapport["details"]:
            print(f"{'':>16}{cle:<12} "
                  f"statut={STATUTS_AFFICHES.get(statut, statut)}")
            if statut == "ECHEC":
                print(f"{'':>28}attendu : {attendu!r}")
                print(f"{'':>28}obtenu  : {obtenu!r}")
            elif statut == "A_DEFINIR":
                print(f"{'':>28}valeur réelle constatée : {obtenu!r}")
            elif statut == "INDETERMINE":
                print(f"{'':>28}outil de lecture du presse-papiers absent")

        if rapport["determinisme"] is not None:
            print(f"{'':>16}{'déterminisme':<12} statut="
                  f"{STATUTS_AFFICHES[rapport['determinisme']]}")
        print("-" * 78)

    total = len(rapports)
    print("Bilan : {total} scénarios — "
          "{ok} conformes, {ech} en échec, "
          "{adef} à définir, {ind} indéterminés.".format(
              total=total,
              ok=compteurs.get("OK", 0),
              ech=compteurs.get("ECHEC", 0),
              adef=compteurs.get("A_DEFINIR", 0),
              ind=compteurs.get("INDETERMINE", 0)))
    return compteurs.get("ECHEC", 0)


# ---------------------------------------------------------------------------
# Consignation des sorties réelles
# ---------------------------------------------------------------------------

def enregistrer(rapports, chemin):
    """Écrit les sorties réelles de chaque scénario dans un fichier JSON.

    Ce fichier sert de base de remplissage du schéma de test : une fois les
    valeurs validées, elles peuvent être recopiées dans le fichier d'attendus
    pour devenir contraignantes.
    """
    donnees = {}
    for rapport in rapports:
        scenario = rapport["scenario"]
        derniere = rapport["mesures"][-1]
        entree = {
            "categorie": scenario.categorie,
            "commande": scenario.arguments,
            "code_retour": derniere.get("code_retour"),
            "stdout": derniere.get("stdout"),
        }
        if "clipboard" in derniere:
            entree["clipboard"] = derniere.get("clipboard")
        donnees[scenario.identifiant] = entree
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(donnees, fichier, indent=2, ensure_ascii=False)
    print(f"Sorties réelles consignées dans : {chemin}")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def charger_attendus(chemin):
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)


def main(argv=None):
    analyseur = argparse.ArgumentParser(
        description="Cadre de test scripté pour Schuffler.")
    analyseur.add_argument(
        "--prog", default="schuffler.sh",
        help="chemin vers la version du programme à tester (défaut : "
             "schuffler.sh)")
    analyseur.add_argument(
        "--attendus", default=None,
        help="fichier JSON d'attendus (prime sur les attendus intégrés)")
    analyseur.add_argument(
        "--enregistrer", default=None,
        help="écrire les sorties réelles dans ce fichier JSON")
    analyseur.add_argument(
        "--categorie", default=None, action="append",
        help="limiter l'exécution à une catégorie (répétable)")
    analyseur.add_argument(
        "--identifiant", default=None, action="append",
        help="limiter l'exécution à un identifiant de scénario (répétable)")
    analyseur.add_argument(
        "--timeout", type=int, default=TIMEOUT_PAR_DEFAUT,
        help="délai maximal par exécution, en secondes")
    arguments = analyseur.parse_args(argv)

    attendus_externes = {}
    if arguments.attendus:
        attendus_externes = charger_attendus(arguments.attendus)

    cadre = CadreDeTest(arguments.prog, attendus_externes,
                        timeout=arguments.timeout)

    scenarios = SCENARIOS
    if arguments.categorie:
        scenarios = [s for s in scenarios
                     if s.categorie in arguments.categorie]
    if arguments.identifiant:
        scenarios = [s for s in scenarios
                     if s.identifiant in arguments.identifiant]
    if not scenarios:
        print("Aucun scénario ne correspond aux critères indiqués.")
        return 2

    rapports = [cadre.verifier(s) for s in scenarios]
    echecs = afficher_rapport(rapports, arguments.prog,
                              cadre.outil_pp is not None)

    if arguments.enregistrer:
        enregistrer(rapports, arguments.enregistrer)

    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())