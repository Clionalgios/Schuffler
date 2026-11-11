#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cadre de test scripté pour Schuffler.

Objectif :
    Jouer de manière reproductible les scénarios du protocole de tests
    (schema_tests.md) et vérifier que chaque version du programme produit la
    sortie attendue. Les scénarios ci-dessous reprennent, ligne à ligne, les
    dix catégories du protocole ; les attendus déjà consignés y sont codés,
    les autres restent des placeholders (None) : le scénario est exécuté et
    la sortie réelle est mesurée et journalée, mais aucune vérification
    d'égalité n'est opérée et aucun échec n'est déclenché. Une fois la valeur
    consolidée dans le protocole, il suffit de la renseigner (dans le
    fichier d'attendus JSON ou ici) pour qu'elle devienne contraignante.

Convention des attendus :
    - attendu absent ou None                : à définir (non contraignant) ;
    - chaîne littérale                      : égalité stricte avec la sortie
                                              (hors sauts de ligne finaux) ;
    - chaîne préfixée par « contient: »     : vérification de sous-chaîne ;
    - code_retour                           : code de sortie du processus.

    Une sortie restée sans attendu n'est signalée que si sa valeur mesurée
    est non triviale (chaîne non vide, code de retour non nul) : une sortie
    vide ne dégrade pas la lisibilité du journal, tandis qu'une valeur
    mesurée inattendue est toujours affichée en clair, de manière à révéler
    un comportement non prévu ou à faciliter le remplissage du protocole.

    Conformément au portage C (divergence documentée dans main.c), les
    messages d'erreur du programme sont attendus sur la sortie d'erreur :
    les attendus d'erreur sont donc attachés à la clé « stderr », la clé
    « stdout » restant réservée à la chaîne transformée et au « 0 ».

Déterminisme :
    Les scénarios portant executions > 1 sont exécutés plusieurs fois ; les
    sorties successives doivent être identiques entre elles, indépendamment
    de toute valeur attendue.

Presse-papiers :
    Windows : lecture et vidage natifs via l'API Win32 (ctypes :
    OpenClipboard/GetClipboardData, EmptyClipboard) — aucun outil
    externe requis, miroir exact de la copie réalisée par le portage C
    (CF_TEXT suffit : l'alphabet de Schuffler est ASCII pur). L'ouverture
    est retentée quelques instants : le service d'historique du
    presse-papiers, un gestionnaire ou un antivirus peut le retenir
    brièvement juste après une copie.
    Linux et autres POSIX : la lecture nécessite l'un des outils
    suivants : xclip, xsel, wl-paste (Wayland) ou pbpaste (macOS). En
    son absence, la vérification du presse-papiers est marquée
    INDÉTERMINÉE (jamais en échec).

Journal en direct et lisibilité :
    - chaque catégorie est annoncée par son en-tête et son comportement
      attendu, tels que décrits dans le protocole ;
    - chaque scénario est journalé au fur et à mesure, numéroté (n/total),
      avec sa durée, sous une balise colorée : [OK] vert, [ÉCHEC] et
      [ERREUR] rouge gras, [À DÉFINIR] jaune, [INDÉTERM.] cyan, [DÉLAI]
      magenta gras, [EN COURS] gris (ligne temporaire réécrite sur un
      terminal interactif, afin de localiser immédiatement un blocage) ;
    - les valeurs affichées sont tronquées pour préserver l'alignement ;
      les valeurs complètes restent disponibles via --enregistrer ;
    - les couleurs sont automatiquement désactivées lorsque la sortie n'est
      pas un terminal (redirection, tube) ou que la variable NO_COLOR est
      posée ; --couleur {auto,toujours,jamais} force le comportement.

Exécution résiliente :
    - chaque exécution s'inscrit dans sa propre session de processus
      (start_new_session) : au dépassement du délai, c'est le groupe de
      processus complet qui est supprimé — programme et sous-processus
      éventuels (xclip lancé par popen) — afin qu'aucun processus orphelin
      ne survive et ne bloque de tube ;
    - sous Windows, l'équivalent est assuré par un groupe de processus
      dédié (CREATE_NEW_PROCESS_GROUP) et par la terminaison de l'arbre
      complet via taskkill /F /T ; la copie Win32 ne laissant aucun
      démon en arrière-plan, les sorties du programme sont simplement
      récoltées jusqu'à fin de flux ;
    - les outils de presse-papiers qui se détachent en arrière-plan (xclip
      laisse un démon servir la sélection) ne bloquent rien : le vidage
      s'exécute sans tube capturé, les sorties du programme sont récoltées
      après sa fin avec un court délai de grâce, et le groupe n'est
      supprimé qu'après la lecture du presse-papiers, sans quoi la
      sélection serait perdue et le presse-papiers paraîtrait vide ;
    - une exception inattendue sur un scénario est capturée, journalée sous
      la balise [ERREUR] et n'interrompt pas la suite ;
    - une interruption (Ctrl+C) interrompt proprement l'exécution en cours,
      journalise le rapport partiel et retourne le code 130 ;
    - si le programme testé est un exécutable Windows (PE, en-tête « MZ »)
      lancé depuis WSL via l'interopérabilité, une [ALERTE] est émise ;
      symétriquement, un exécutable Linux (ELF) lancé depuis Windows —
      l'erreur Win32 193 « %1 n'est pas une application Win32 valide »
      en résulte — est également signalé, avec la compilation native
      à effectuer.

Utilisation :
    python3 schuffler_tests.py --prog ./schuffler
    python3 schuffler_tests.py --prog ./schuffler --categorie "Mode API"
    python3 schuffler_tests.py --prog ./schuffler --enregistrer reel.json
    python3 schuffler_tests.py --prog ./schuffler --attendus attendus.json
    python3 schuffler_tests.py --prog ./schuffler --identifiant api-test
    python3 schuffler_tests.py --prog ./schuffler --couleur toujours
    python schuffler_tests.py --prog ./Schuffler.exe         (Windows)
"""

from __future__ import annotations

import argparse
import ctypes
import dataclasses
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TIMEOUT_PAR_DEFAUT = 10   # secondes par exécution
TIMEOUT_EXTINCTION = 5    # secondes pour récolter un processus tué
TIMEOUT_PP = 5            # secondes pour lire ou vider le presse-papiers
TIMEOUT_RECOLTE = 2       # secondes de grâce pour récolter les sorties
                          # d'un programme terminé dont un descendant
                          # détaché (ex. démon xclip) maintient les tubes
TRONQUE_LIGNE = 60        # troncature des valeurs dans le journal
TRONQUE_ECART = 120       # troncature des valeurs dans les écarts

# Plateforme d'exécution du cadre : les points réellement système (groupe
# de processus, récolte des tubes, presse-papiers) s'aiguillent ici.
EST_WINDOWS = os.name == "nt"

# Format de presse-papiers texte ANSI (équivalent du CF_TEXT de main.c ;
# l'alphabet de Schuffler est ASCII pur, la conversion Unicode est inutile).
CF_TEXT = 1

# Ouverture du presse-papiers Win32 : un voisin peut le retenir quelques
# dizaines de millisecondes après une copie (service d'historique du
# presse-papiers de Windows, gestionnaire, antivirus) ; l'ouverture est
# retentée un court moment avant de conclure à l'indisponibilité.
OUVERTURES_PP = 10        # tentatives d'ouverture du presse-papiers Win32
DELAI_PP_MS = 25          # délai entre deux tentatives, en millisecondes

# Outils de lecture du presse-papiers POSIX, par ordre de préférence.
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
MARQUEUR_DELAI = "<délai dépassé"

# Étiquettes courtes des sorties, pour le journal.
ETIQUETTES = {
    "stdout": "sortie",
    "stderr": "erreur",
    "clipboard": "p.-p.",
    "code_retour": "code",
}

# Catégories du protocole et comportement attendu associé (schema_tests.md).
CATEGORIES = {
    "Sans-mode":
        "En l'absence de toute option de mode, le programme se ferme en "
        "demandant qu'un mode soit indiqué. Si le secret est absent en "
        "argument, il est demandé en saisie invisible.",
    "Mode API":
        "L'option -A renvoie directement la chaîne transformée sur la "
        "sortie standard, sans action sur le presse-papier.",
    "Mode Clipboard":
        "L'option -C envoie la chaîne transformée dans le presse-papier, "
        "sans sortie sur la sortie standard.",
    "Mode combiné":
        "Lorsque les deux options sont passées simultanément, la chaîne "
        "transformée est envoyée à la fois sur la sortie standard et dans "
        "le presse-papier.",
    "Déterminisme":
        "Le même secret combiné aux mêmes options produit toujours le même "
        "mot de passe, quelle que soit l'exécution.",
    "Longueur":
        "La longueur par défaut est de 20 caractères ; la longueur minimale "
        "acceptée est de 4 caractères.",
    "Exclusions":
        "Chaque option d'exclusion retire une classe de caractères de la "
        "transformation ; --exclude-chars est appliquée après tous les jeux.",
    "Spéciaux":
        "--special-set force le jeu de caractères spéciaux ; il peut être "
        "combiné à --exclude-chars, laquelle s'applique en dernier.",
    "Artefact":
        "L'option -a affiche l'artefact de la chaîne transformée (premier "
        "et dernier caractère) : en complément du clair en mode API, à la "
        "place du « 0 » en mode clipboard seul.",
    "Aide et erreurs":
        "-h affiche l'aide et quitte ; une option inconnue doit être "
        "signalée sans produire de transformation.",
}


# ---------------------------------------------------------------------------
# Balises colorées
# ---------------------------------------------------------------------------

def couleurs_actives(mode):
    """Décide de l'emploi des séquences ANSI selon le mode demandé."""
    if mode == "toujours":
        return True
    if mode == "jamais":
        return False
    # Mode auto : couleur sur un terminal interactif, hors NO_COLOR.
    return (os.environ.get("NO_COLOR") is None
            and sys.stdout.isatty())


class Balise:
    """Balises de journal, colorées lorsque la sortie le permet."""

    def __init__(self, actif):
        self.actif = actif

    def _e(self, code, texte):
        if not self.actif:
            return texte
        return f"\033[{code}m{texte}\033[0m"

    def cadre(self, t):
        return self._e("1", t)

    def en_cours(self, t):
        return self._e("2", t)

    def ok(self, t):
        return self._e("32", t)

    def echec(self, t):
        return self._e("1;31", t)

    def a_definir(self, t):
        return self._e("33", t)

    def indetermine(self, t):
        return self._e("36", t)

    def delai(self, t):
        return self._e("1;35", t)

    def alerte(self, t):
        return self._e("1;33", t)


# Statut -> texte de la balise. Largeur fixe pour l'alignement des colonnes.
STATUTS_AFFICHES = {
    "OK": "OK",
    "ECHEC": "ÉCHEC",
    "A_DEFINIR": "À DÉFINIR",
    "INDETERMINE": "INDÉTERM.",
    "DELAI": "DÉLAI",
    "ERREUR": "ERREUR",
    "CADRE": "CADRE",
    "ALERTE": "ALERTE",
    "EN_COURS": "EN COURS",
    "BILAN": "BILAN",
    "INTERRUPTION": "INTERR.",
}


def ligne_balisee(balise, statut, corps, probleme=False):
    """Compose « [<BALISE>] <corps> », la balise étant colorée.

    Lorsque le statut signale un problème (échec, délai, erreur) ou que
    « probleme » est posé, le corps est coloré de la même façon afin
    d'attirer l'œil immédiatement.
    """
    texte = STATUTS_AFFICHES.get(statut, statut)
    couleur = {
        "OK": balise.ok,
        "ECHEC": balise.echec,
        "A_DEFINIR": balise.a_definir,
        "INDETERMINE": balise.indetermine,
        "DELAI": balise.delai,
        "ERREUR": balise.echec,
        "CADRE": balise.cadre,
        "ALERTE": balise.alerte,
        "EN_COURS": balise.en_cours,
        "BILAN": balise.cadre,
        "INTERRUPTION": balise.alerte,
    }.get(statut, (lambda t: t))
    balise_texte = couleur(f"[{texte:^10}]")
    if statut in ("ECHEC", "DELAI", "ERREUR") or probleme:
        return f"{balise_texte} {couleur(corps)}"
    return f"{balise_texte} {corps}"


def tronque(valeur, limite=TRONQUE_LIGNE):
    """Représentation tronquée d'une valeur, pour des lignes lisibles."""
    if valeur is None:
        return "None"
    texte = str(valeur)
    if len(texte) > limite:
        return texte[:limite - 1] + "…"
    return texte


# ---------------------------------------------------------------------------
# Détection de l'environnement
# ---------------------------------------------------------------------------

def est_binaire_windows(chemin):
    """Vrai si « chemin » est un exécutable au format PE (en-tête « MZ »)."""
    try:
        with open(chemin, "rb") as fichier:
            return fichier.read(2) == b"MZ"
    except OSError:
        return False


def est_wsl():
    """Vrai si l'exécution se déroule dans le sous-système Windows (WSL)."""
    try:
        with open("/proc/version", encoding="utf-8") as fichier:
            return "microsoft" in fichier.read().lower()
    except OSError:
        return False


def est_binaire_linux(chemin):
    """Vrai si « chemin » est un exécutable au format ELF (tête « \x7fELF »)."""
    try:
        with open(chemin, "rb") as fichier:
            return fichier.read(4) == b"\x7fELF"
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Presse-papiers natif Windows (API Win32 via ctypes)
# ---------------------------------------------------------------------------

def _pp_win32():
    """Bibliothèques Win32 avec les signatures nécessaires aux poignées.

    Les types de retour sont explicités : en 64 bits, une poignée
    (HGLOBAL, pointeur) laissée au c_int par défaut de ctypes serait
    tronquée et fausserait la lecture du presse-papiers.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    return user32, kernel32


def ouvrir_presse_papiers_win32(user32):
    """Ouvre le presse-papiers en retentant quelques instants.

    OpenClipboard échoue tant qu'un autre processus détient le
    presse-papiers ; le service d'historique de Windows, un gestionnaire
    de presse-papiers ou un antivirus peuvent le retenir brièvement juste
    après une copie. Une lecture immédiate échouerait alors sans raison
    apparente : l'ouverture est réessayée pendant un court moment avant
    de conclure à l'indisponibilité.
    """
    for _ in range(OUVERTURES_PP):
        if user32.OpenClipboard(None):
            return True
        time.sleep(DELAI_PP_MS / 1000)
    return False


def lire_presse_papiers_win32():
    """Lit le presse-papiers via OpenClipboard/GetClipboardData (CF_TEXT).

    Miroir exact de la copie réalisée par le portage C en mode clipboard
    (main.c : SetClipboardData, CF_TEXT) : aucune dépendance externe, aucun
    processus détaché ne survit à la lecture. Le presse-papiers vide ou
    fermé à d'autres formats renvoie une chaîne vide ; None n'est renvoyé
    que si le presse-papiers lui-même est inaccessible (séance sans
    bureau, service). Les sauts de ligne finaux sont retirés, comme pour
    les outils POSIX.
    """
    user32, kernel32 = _pp_win32()
    if not ouvrir_presse_papiers_win32(user32):
        return None
    try:
        poignee = user32.GetClipboardData(CF_TEXT)
        if not poignee:
            return ""
        pointeur = kernel32.GlobalLock(poignee)
        if not pointeur:
            return ""
        try:
            brut = ctypes.string_at(pointeur, kernel32.GlobalSize(poignee))
        finally:
            kernel32.GlobalUnlock(poignee)
        return brut.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    finally:
        user32.CloseClipboard()


def vider_presse_papiers_win32():
    """Vide le presse-papiers via EmptyClipboard (mêmes garanties que la
    lecture : aucun processus détaché, aucune sortie à neutraliser)."""
    user32, _ = _pp_win32()
    if not ouvrir_presse_papiers_win32(user32):
        return
    try:
        user32.EmptyClipboard()
    finally:
        user32.CloseClipboard()


# ---------------------------------------------------------------------------
# Définition des scénarios (protocole schema_tests.md)
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
    # Attendus : clés parmi "stdout", "stderr", "clipboard", "code_retour".
    attendus: dict = dataclasses.field(default_factory=dict)


def S(identifiant, categorie, arguments, secret_stdin=None,
      executions=1, **attendus):
    """Constructeur concis de scénario ; les attendus sont nommés."""
    return Scenario(identifiant, categorie, arguments, secret_stdin,
                    executions, attendus)


ERREUR_SANS_MODE = PREFIX_CONTIENT + "Erreur : aucun mode"
ERREUR_SECRET_VIDE = PREFIX_CONTIENT + "Erreur : aucune chaîne à transformer"
ERREUR_CLE_ABSENTE = PREFIX_CONTIENT + \
    "Erreur : pas de clé transformable passée"
ERREUR_LONGUEUR = PREFIX_CONTIENT + "Longueur invalide"
ERREUR_CATEGORIES = PREFIX_CONTIENT + "Toutes les catégories"
ERREUR_JEU_MANQUANT = PREFIX_CONTIENT + "Jeu de caractères spéciaux manquant"
ERREUR_LISTE_MANQUANTE = PREFIX_CONTIENT + \
    "Liste de caractères à exclure manquante"
ERREUR_OPTION_INCONNUE = PREFIX_CONTIENT + "Option inconnue"
AIDE = PREFIX_CONTIENT + "Usage:"

SCENARIOS = [
    # -- Catégorie 1 : Sans-mode (aucun mode indiqué : refus, aide, code 1)
    S("sans-scanf", "Sans-mode", [], secret_stdin="monsecret",
      stdout="", stderr=ERREUR_SANS_MODE, clipboard="", code_retour=1),
    S("sans-arg", "Sans-mode", ["monsecret"],
      stdout="", stderr=ERREUR_SANS_MODE, clipboard="", code_retour=1),
    S("sans-options", "Sans-mode",
      ["--length", "32", "--no-special", "monsecret"],
      stdout="", stderr=ERREUR_SANS_MODE, clipboard="", code_retour=1),
    S("sans-l4", "Sans-mode", ["-l", "4", "test"],
      stdout="", stderr=ERREUR_SANS_MODE, clipboard="", code_retour=1),

    # -- Catégorie 2 : Mode API ---------------------------------------------
    # Conformément au protocole, le mode API exige le secret en argument :
    # l'entrée standard fournie ne doit pas être consommée (le secret
    # saisi à l'invite n'y est pas accepté), l'erreur est attendue sur la
    # sortie d'erreur — divergence de flux du portage C documentée dans
    # main.c — et le presse-papiers n'est pas touché.
    S("api-scanf", "Mode API", ["-A"], secret_stdin="test",
      stdout="", stderr=ERREUR_CLE_ABSENTE, clipboard="", code_retour=1),
    S("api-test", "Mode API", ["-A", "test"],
      stdout="bafTBVD2lM%ZqIIOAHN6", code_retour=0),
    S("api-test1", "Mode API", ["-A", "test1"],
      stdout="1awABg92YU%JrQ33R*FB", code_retour=0),
    S("api-l50", "Mode API", ["-A", "-l", "50", "test"],
      stdout="b5UdvYAHNFWd!IIOrPnh%Zql3Me2lMeGjlBVDlM4FafTWKN%o6",
      code_retour=0),
    S("api-l4", "Mode API", ["-A", "-l", "4", "test"],
      stdout="Ba%2", code_retour=0),

    # -- Catégorie 3 : Mode Clipboard ---------------------------------------
    S("cb-test", "Mode Clipboard", ["-C", "test"],
      stdout="0", clipboard="bafTBVD2lM%ZqIIOAHN6", code_retour=0),
    S("cb-monsecret", "Mode Clipboard", ["-C", "monsecret"],
      stdout="0", clipboard="Ya+mBqP2Lm%aGUN^i1@s", code_retour=0),
    S("cb-vide", "Mode Clipboard", ["-C"], secret_stdin="",
      stdout="", stderr=ERREUR_SECRET_VIDE, clipboard="", code_retour=1),

    # -- Catégorie 4 : Mode combiné -----------------------------------------
    S("ac-test", "Mode combiné", ["-A", "-C", "test"],
      stdout="bafTBVD2lM%ZqIIOAHN6",
      clipboard="bafTBVD2lM%ZqIIOAHN6", code_retour=0),
    S("ac-l50", "Mode combiné", ["-A", "-C", "-l", "50", "monsecret"],
      stdout="Y$2Wtwi1@YPClUN^jCkO%aGaKjA2LmY@fmBqPt#vga+m%uNaSs",
      clipboard="Y$2Wtwi1@YPClUN^jCkO%aGaKjA2LmY@fmBqPt#vga+m%uNaSs",
      code_retour=0),

    # -- Catégorie 5 : Déterminisme ------------------------------------------
    S("det-api", "Déterminisme", ["-A", "test"], executions=2,
      stdout="bafTBVD2lM%ZqIIOAHN6"),
    S("det-l32", "Déterminisme", ["-A", "-l", "32", "test"], executions=2,
      stdout="b5U2lMeGAHNFBVDlMIIOrafTWK%Zql36"),

    # -- Catégorie 6 : Longueur ----------------------------------------------
    S("lg-defaut", "Longueur", ["-A", "test"],
      stdout="bafTBVD2lM%ZqIIOAHN6"),
    S("lg-20", "Longueur", ["-A", "-l", "20", "test"],
      stdout="bafTBVD2lM%ZqIIOAHN6"),
    S("lg-4", "Longueur", ["-A", "-l", "4", "test"],
      stdout="Ba%2"),
    S("lg-3", "Longueur", ["-A", "-l", "3", "test"],
      stdout="", stderr=ERREUR_LONGUEUR, code_retour=1),
    S("lg-100", "Longueur", ["-A", "-l", "100", "test"],
      stdout="b5UdvYAFOD*5OIIOrPnhVSdeKOu2lMeGjl!6n$StCafTWKN%ozVdxYwX"
             "AHNFWd!N6HLms^%Zql3MeT5!HEuCBVDlM4FTl*ef+tX6"),
    S("lg-non-num", "Longueur", ["-A", "-l", "test"],
      stdout="", stderr=ERREUR_LONGUEUR, code_retour=1),

    # -- Catégorie 7 : Jeux de caractères (exclusions) -----------------------
    S("no-lower", "Exclusions", ["-A", "--no-lower", "test"],
      stdout="IA5A1C3$S0JNXPPCO^1U"),
    S("no-upper", "Exclusions", ["-A", "--no-upper", "test"],
      stdout="ia5a1c3$s0jnxppco^1u"),
    S("no-digits", "Exclusions", ["-A", "--no-digits", "test"],
      stdout="vapTBVD$FhwkKSS#^@ir"),
    S("no-special", "Exclusions", ["-A", "--no-special", "test"],
      stdout="taoTBVD2DduhIRR61Zeo"),
    S("no-lower-upper", "Exclusions",
      ["-A", "--no-lower", "--no-upper", "test"],
      stdout="!007@9!214@36!!@@45!"),
    S("no-trois", "Exclusions",
      ["-A", "--no-lower", "--no-upper", "--no-digits", "test"],
      stdout="#!^!^$$$!#!^&**$&^!$"),
    S("no-quatre", "Exclusions",
      ["-A", "--no-lower", "--no-upper", "--no-digits", "--no-special",
       "test"],
      stdout="", stderr=ERREUR_CATEGORIES, code_retour=1),
    S("exclude-voyelles", "Exclusions",
      ["-A", "--exclude-chars", "aeiou", "-l", "50", "test"],
      stdout="p!ZrF3UW7U1xcSS3wZrB%^FA#1y2A6sQmFB0IvR^KbnY@PXmsd"),

    # -- Catégorie 8 : Jeu de spéciaux personnalisé ---------------------------
    S("sp-simple", "Spéciaux", ["-A", "--special-set", "@#%", "test"],
      stdout="nalTBVD2x4@#COO0ST5f"),
    S("sp-exclude", "Spéciaux",
      ["-A", "--special-set", "@#$%", "--exclude-chars", "#", "test"],
      stdout="nalTBVD2x4@$COO0ST5f"),
    S("sp-l50", "Spéciaux",
      ["-A", "--special-set", "@#%", "-l", "50", "test"],
      stdout="n5UpBYST5RWvdOO0rVnz@#CxcYw2x4qMjDBVDrM@FalT8KTmof"),
    S("sp-vide", "Spéciaux", ["-A", "--special-set", "", "test"],
      stdout="", stderr=ERREUR_JEU_MANQUANT, code_retour=1),

    # -- Catégorie 9 : Artefact -----------------------------------------------
    S("art-api", "Artefact", ["-A", "-a", "test"],
      stdout="bafTBVD2lM%ZqIIOAHN6\nb6", clipboard="", code_retour=0),
    S("art-seul", "Artefact", ["-a", "test"],
      stdout="", stderr=ERREUR_SANS_MODE, clipboard="", code_retour=1),
    S("art-l4", "Artefact", ["-A", "-a", "-l", "4", "test"],
      stdout="Ba%2\nB2", clipboard="", code_retour=0),
    S("art-cb", "Artefact", ["test", "-a", "-C"],
      stdout="b6", clipboard="bafTBVD2lM%ZqIIOAHN6", code_retour=0),

    # -- Catégorie 10 : Aide et erreurs d'appel -------------------------------
    S("aide-courte", "Aide et erreurs", ["-h"],
      stdout=AIDE, code_retour=0),
    S("aide-longue", "Aide et erreurs", ["--help"],
      stdout=AIDE, code_retour=0),
    S("opt-inconnue", "Aide et erreurs", ["--option-inconnue", "test"],
      stdout="", stderr=ERREUR_OPTION_INCONNUE, code_retour=1),
    S("l-sans-valeur", "Aide et erreurs", ["-A", "-l"],
      stdout="", stderr=ERREUR_LONGUEUR, code_retour=1),
    S("sp-sans-valeur", "Aide et erreurs", ["-A", "--special-set"],
      stdout="", stderr=ERREUR_JEU_MANQUANT, code_retour=1),
    S("exclude-sans-valeur", "Aide et erreurs", ["-A", "--exclude-chars"],
      stdout="", stderr=ERREUR_LISTE_MANQUANTE, code_retour=1),
]


# ---------------------------------------------------------------------------
# Cadre d'exécution
# ---------------------------------------------------------------------------

def tuer_groupe(processus, pgid=None):
    """Termine le groupe de processus complet (programme et sous-processus).

    POSIX : l'exécution s'inscrivant dans sa propre session, le programme
    et tous ses descendants (xclip lancé par popen, shells intermédiaires)
    forment un seul groupe : un unique killpg suffit. Le pgid doit être
    fourni lorsque le processus principal a déjà été récolté, car un
    descendant détaché (xclip servant la sélection) peut alors survivre
    seul, et os.getpgid ne fonctionne plus sur un identifiant disparu.

    Windows : l'arbre complet est terminé par taskkill /F /T sur
    l'identifiant du programme (équivalent fonctionnel du killpg :
    programme et sous-processus éventuels) — uniquement si le programme
    vit encore : sur un identifiant disparu, taskkill ne rejoint pas non
    plus les enfants survivants, et l'appel inutile coûtait environ deux
    cents millisecondes par scénario une fois le programme correctement
    terminé. Le pgid n'existe pas sous Windows et est ignoré.
    """
    if EST_WINDOWS:
        if processus.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(processus.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=TIMEOUT_EXTINCTION)
            except (subprocess.SubprocessError, OSError):
                pass
        try:
            processus.kill()
        except OSError:
            pass
        return
    cible = pgid
    if cible is None:
        try:
            cible = os.getpgid(processus.pid)
        except (ProcessLookupError, PermissionError, OSError):
            cible = None
    if cible is not None:
        try:
            os.killpg(cible, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        processus.kill()
    except OSError:
        pass


class CadreDeTest:

    def __init__(self, programme, attendus=None, timeout=TIMEOUT_PAR_DEFAUT):
        self.programme = programme
        self.timeout = timeout
        # Les attendus externes (fichier JSON) priment sur les attendus
        # intégrés : c'est ce qui garantit la comparaison entre versions.
        self.attendus = attendus or {}
        # Presse-papiers : sous Windows, l'API Win32 native (ctypes) sert
        # la lecture et le vidage, sans outil externe ; sous POSIX, les
        # outils en ligne de commande sont détectés comme auparavant.
        self.pp_win32 = EST_WINDOWS
        self.outil_pp = None if EST_WINDOWS else self._detecter_outil_pp()
        # Processus éventuellement en cours, pour l'extinction propre
        # lors d'une interruption (Ctrl+C).
        self.processus_actif = None
        self.pgid_actif = None

    def pp_disponible(self):
        """Vrai si le presse-papiers peut être lu et vidé : nativement
        sous Windows, par outil détecté sous POSIX."""
        return self.pp_win32 or self.outil_pp is not None

    # -- Détection du presse-papiers --------------------------------------

    @staticmethod
    def _detecter_outil_pp():
        for lecture, vidage in zip(OUTILS_LECTURE_PP, OUTILS_VIDAGE_PP):
            if shutil.which(lecture[0]) and shutil.which(vidage[0]):
                return lecture, vidage
        return None

    def lire_presse_papiers(self):
        if self.pp_win32:
            try:
                return lire_presse_papiers_win32()
            except OSError:
                return None
        if self.outil_pp is None:
            return None
        lecture, _ = self.outil_pp
        try:
            resultat = subprocess.run(lecture, capture_output=True,
                                      text=True, timeout=TIMEOUT_PP)
        except subprocess.SubprocessError:
            return None
        if resultat.returncode != 0:
            return None
        return resultat.stdout.rstrip("\n")

    def vider_presse_papiers(self):
        """Vide le presse-papiers.

        Sous Windows, EmptyClipboard ne laisse aucune sortie à
        neutraliser : l'appel natif suffit.

        Les sorties ne sont pas capturées : un outil qui se détache en
        arrière-plan (xclip laisse un démon servir la sélection) en
        retenant les tubes rendrait l'appel bloquant. Dirigées vers
        /dev/null, elles ne retiennent rien et l'appel rend la main dès la
        sortie du processus parent ; le démon, lui, poursuit son office.
        """
        if self.pp_win32:
            try:
                vider_presse_papiers_win32()
            except OSError:
                pass
            return
        if self.outil_pp is None:
            return
        _, vidage = self.outil_pp
        try:
            subprocess.run(vidage, input="", stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=TIMEOUT_PP)
        except subprocess.SubprocessError:
            pass

    # -- Exécution d'un scénario --------------------------------------------

    @staticmethod
    def _recolter(*fluxs):
        """Récolte les sorties du programme une fois celui-ci terminé.

        Un sous-processus détaché (le démon que xclip laisse en arrière-plan
        pour servir la sélection du presse-papiers, par exemple) peut
        maintenir les tubes ouverts indéfiniment : la lecture est donc
        bornée par un délai de grâce, au terme duquel seules les données
        déjà émises par le programme — complètes, puisque le programme est
        fini — sont retenues ; le descendant ne peut quant à lui rien écrire
        d'utile sur ces tubes. Tous les flux sont récoltés ensemble, afin
        que la grâce ne soit décomptée qu'une fois.

        Windows : le portage C copie par l'API Win32 native, sans
        sous-processus ; rien ne survit au programme et ne retient les
        tubes. La lecture bloquante jusqu'à fin de flux suffit — select
        ne connaît pas les tubes sous Windows — et rend immédiatement,
        le programme étant terminé et les données déjà émises.
        """
        if EST_WINDOWS:
            resultats = []
            for flux in fluxs:
                donnees = b""
                if flux is not None:
                    try:
                        donnees = flux.read()
                    except (OSError, ValueError):
                        donnees = b""
                    try:
                        flux.close()
                    except OSError:
                        pass
                resultats.append(
                    donnees.decode("utf-8", errors="replace"))
            return resultats

        canaux = {}
        for flux in fluxs:
            if flux is None:
                continue
            try:
                descripteur = flux.fileno()
                os.set_blocking(descripteur, False)
                canaux[descripteur] = (flux, [])
            except (OSError, ValueError):
                try:
                    flux.close()
                except OSError:
                    pass

        echeance = time.monotonic() + TIMEOUT_RECOLTE
        recoltes = {}
        while canaux:
            restant = echeance - time.monotonic()
            if restant <= 0:
                break
            prets = select.select(list(canaux), [], [], restant)[0]
            if not prets:
                break               # grâce expirée : tubes retenus
            for descripteur in prets:
                flux, morceaux = canaux[descripteur]
                try:
                    bloc = os.read(descripteur, 65536)
                except (BlockingIOError, InterruptedError):
                    continue
                except OSError:
                    bloc = b""
                if bloc:
                    morceaux.append(bloc)
                else:
                    del canaux[descripteur]   # fin de flux : sortie complète
                    recoltes[id(flux)] = b"".join(morceaux)
                    try:
                        flux.close()
                    except OSError:
                        pass

        for flux, morceaux in canaux.values():
            recoltes[id(flux)] = b"".join(morceaux)
            try:
                flux.close()
            except OSError:
                pass

        return [recoltes.get(id(flux), b"").decode("utf-8", errors="replace")
                if flux is not None else "" for flux in fluxs]

    def executer_une_fois(self, scenario, avec_pp=False):
        """Exécute le programme une fois et renvoie les sorties réelles."""
        commande = [self.programme] + scenario.arguments
        entree = b""
        if scenario.secret_stdin is not None:
            entree = (scenario.secret_stdin + "\n").encode("utf-8")

        if avec_pp:
            self.vider_presse_papiers()

        # L'exécution s'inscrit dans son propre groupe : nouvelle session
        # POSIX, groupe de processus dédié sous Windows (l'équivalent de
        # la session pour l'isolation des interruptions ; l'arbre est
        # ensuite terminé par taskkill /T, voir tuer_groupe).
        options_creation = {}
        if EST_WINDOWS:
            options_creation["creationflags"] = \
                subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options_creation["start_new_session"] = True

        try:
            processus = subprocess.Popen(
                commande,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **options_creation,
            )
        except FileNotFoundError:
            return {
                "code_retour": None,
                "stdout": None,
                "stderr": "Programme introuvable : " + self.programme,
            }
        except OSError as exc:
            # Exemple typique : binaire compilé pour un autre système
            # (ELF sous Windows : erreur Win32 193, « %1 n'est pas une
            # application Win32 valide »). Signalé comme échec du
            # scénario, avec la cause exacte, plutôt qu'en exception du
            # cadre.
            return {
                "code_retour": None,
                "stdout": None,
                "stderr": f"Programme non lançable : {exc}",
            }

        # Le pgid est mémorisé tant que le processus vit : une fois le
        # programme récolté, un descendant détaché peut survivre seul
        # dans le groupe, et os.getpgid ne fonctionne plus alors.
        # Windows n'a pas de pgid : tuer_groupe y fonce sur l'arbre.
        pgid = None
        if not EST_WINDOWS:
            try:
                pgid = os.getpgid(processus.pid)
            except (ProcessLookupError, OSError):
                pgid = None

        self.processus_actif = processus
        self.pgid_actif = pgid
        try:
            try:
                processus.stdin.write(entree)
            except (BrokenPipeError, OSError):
                pass
            try:
                processus.stdin.close()
            except OSError:
                pass

            # Le délai borne la vie du programme lui-même ; les sorties
            # sont récoltées ensuite, indépendamment (voir _recolter).
            delai = False
            inarretable = False
            try:
                processus.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                delai = True
                tuer_groupe(processus, pgid)
                try:
                    processus.wait(timeout=TIMEOUT_EXTINCTION)
                except subprocess.TimeoutExpired:
                    inarretable = True

            sortie, erreurs = self._recolter(processus.stdout,
                                             processus.stderr)

            if delai:
                if inarretable:
                    message = "<délai dépassé : processus inarrêtable>"
                else:
                    message = ("<délai dépassé : exécution interrompue de "
                               "force avec ses sous-processus>")
                resultat = {"code_retour": None, "stdout": None,
                            "stderr": message}
            else:
                resultat = {
                    "code_retour": processus.returncode,
                    "stdout": sortie.rstrip("\n"),
                    "stderr": erreurs.rstrip("\n"),
                }
        finally:
            self.processus_actif = None
            self.pgid_actif = None
            if processus.poll() is None:
                tuer_groupe(processus, pgid)

        if avec_pp:
            resultat["clipboard"] = self.lire_presse_papiers()

        # Récolte du groupe APRÈS la lecture du presse-papiers : un démon
        # xclip survit au programme pour servir la sélection ; le supprimer
        # plus tôt viderait le presse-papiers et fausserait le constat.
        tuer_groupe(processus, pgid)
        return resultat

    def executer(self, scenario):
        """Exécute un scénario (une ou plusieurs fois selon `executions`)."""
        attendus = self.attendus.get(
            scenario.identifiant, scenario.attendus)

        # Le presse-papiers est capturé chaque fois qu'il est accessible —
        # nativement sous Windows, par outil détecté sous POSIX : il est
        # systématiquement vidé avant l'exécution, de
        # manière à ce qu'une valeur résiduelle ne soit jamais interprétée
        # comme une sortie du programme.
        avec_pp = self.pp_disponible()

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
        debut = time.monotonic()
        attendus, mesures = self.executer(scenario)
        duree = time.monotonic() - debut
        derniere = mesures[-1]

        verdicts = {}
        details = []
        # Les quatre sorties sont toujours évaluées : une sortie sans attendu
        # déclaré est signalée « à définir », avec la valeur réelle constatée,
        # de manière à faciliter le remplissage du protocole de tests.
        for cle in ("stdout", "stderr", "clipboard", "code_retour"):
            attendu = attendus.get(cle)
            statut = self.evaluer(
                cle, attendu, derniere.get(cle),
                pp_disponible=self.pp_disponible())
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
            "duree": duree,
            "delai_depasse": any(
                (m.get("stderr") or "").startswith(MARQUEUR_DELAI)
                for m in mesures),
        }


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def cles_a_definir(rapport):
    """Clés sans attendu déclaré dont la sortie mesurée est non triviale.

    Une sortie restée vide (ou un code de retour nul) est considérée
    comme une absence d'information : elle n'encombre pas le journal. En
    revanche, toute valeur mesurée non vide sur une sortie sans attendu
    est signalée, car elle peut révéler un comportement non prévu ou une
    valeur à consigner dans le protocole.
    """
    resultat = []
    for cle, attendu, obtenu, _ in rapport["details"]:
        if attendu is not None:
            continue
        if obtenu in ("", 0, None):
            continue
        resultat.append(cle)
    return resultat


def statut_global(rapport):
    """Statut d'ensemble d'un scénario.

    Le statut affiché est celui de la plus grave des sorties dont un attendu
    est déclaré ; un scénario sans aucun attendu est « à définir ». Les
    sorties sans attendu sont signalées à côté du verdict, sans le dégrader.
    Une exécution interrompue pour dépassement de délai prime sur les
    écarts : ceux-ci portent alors sur des sorties incomplètes.
    """
    if "erreur_cadre" in rapport:
        return "ERREUR"
    if rapport.get("delai_depasse"):
        return "DELAI"
    definis = [statut for _, attendu, _, statut in rapport["details"]
               if attendu is not None]
    if "ECHEC" in definis:
        return "ECHEC"
    if not definis:
        return "A_DEFINIR"
    if "INDETERMINE" in definis:
        return "INDETERMINE"
    return "OK"


def formater_duree(duree):
    if duree >= 1.0:
        return f"{duree:.2f} s"
    return f"{duree * 1000:.0f} ms"


def afficher_entete(programme, pp_disponible, balise, total):
    if pp_disponible:
        etat_pp = ("disponible (API Win32)" if EST_WINDOWS
                   else "disponible")
    else:
        etat_pp = "NON disponible (vérifications clipboard indéterminées)"
    print(ligne_balisee(balise, "CADRE",
                        f"Programme testé : {programme}"))
    print(ligne_balisee(balise, "CADRE",
                        f"Presse-papiers  : {etat_pp}"))
    print(ligne_balisee(balise, "CADRE",
                        f"{total} scénarios à exécuter"), flush=True)


def afficher_categorie(categorie, balise):
    """Annonce une catégorie : en-tête puis comportement attendu."""
    print()
    print(ligne_balisee(balise, "CADRE", f"── {categorie} "
                                         f"{'─' * max(1, 44 - len(categorie))}"))
    comportement = CATEGORIES.get(categorie)
    if comportement:
        print(" " * 12 + f"Attendu : {comportement}", flush=True)


def afficher_en_cours(scenario, programme, balise, terminal, numero, total):
    """Ligne temporaire : signalée à l'écran avant l'exécution, uniquement
    sur un terminal interactif (elle est alors réécrite par le verdict).
    Le corps est borné à la largeur du terminal : au-delà, la ligne
    passerait sur plusieurs rangées et l'effacement « \\r\\033[K » du
    verdict ne nettoierait que la dernière, laissant à l'écran un
    fragment périmé de la ligne « EN COURS »."""
    if not terminal:
        return
    commande = " ".join([programme] + scenario.arguments)
    corps = f"{numero}/{total} {scenario.identifiant:<20} {commande}"
    largeur = shutil.get_terminal_size().columns - 13  # balise + espace
    if largeur > 0 and len(corps) >= largeur:
        corps = corps[:largeur - 1] + "…"
    sys.stdout.write("\r\033[K" + ligne_balisee(balise, "EN_COURS", corps))
    sys.stdout.flush()


def afficher_scenario(rapport, programme, balise, terminal, numero, total):
    """Journalise le verdict d'un scénario, immédiatement après exécution."""
    scenario = rapport["scenario"]
    global_ = statut_global(rapport)
    commande = " ".join([programme] + scenario.arguments)
    entete = (f"{numero}/{total} {scenario.identifiant:<20} {commande} "
              f"· {formater_duree(rapport.get('duree', 0.0))}")

    # Sorties sans attendu mais porteuses d'information : signalées sans
    # dégrader le verdict, avec leur valeur constatée.
    manquantes = cles_a_definir(rapport)
    if manquantes and global_ in ("OK", "INDETERMINE", "A_DEFINIR"):
        etiquettes = [ETIQUETTES.get(cle, cle) for cle in manquantes]
        entete += balise.a_definir(f"  · à définir : {', '.join(etiquettes)}")

    if terminal:
        sys.stdout.write("\r\033[K")  # efface la ligne « EN COURS »
    print(ligne_balisee(balise, global_, entete), flush=True)

    retrait = " " * 14
    if "erreur_cadre" in rapport:
        print(retrait + ligne_balisee(
            balise, "ERREUR",
            f"exception du cadre : {rapport['erreur_cadre']}"), flush=True)
        return

    if global_ == "ECHEC":
        for cle, attendu, obtenu, statut in rapport["details"]:
            if statut == "ECHEC":
                etiquette = ETIQUETTES.get(cle, cle)
                print(retrait + ligne_balisee(
                    balise, "ECHEC",
                    f"{etiquette} : attendu {tronque(attendu, TRONQUE_ECART)!r}"
                    f" / obtenu {tronque(obtenu, TRONQUE_ECART)!r}"),
                    flush=True)
    elif global_ == "DELAI":
        print(retrait + ligne_balisee(
            balise, "DELAI",
            "exécution interrompue de force après le délai"),
            flush=True)

    if manquantes:
        derniere = rapport["mesures"][-1] if rapport["mesures"] else {}
        morceaux = [f"{ETIQUETTES.get(cle, cle)}="
                    f"{tronque(derniere.get(cle))!r}" for cle in manquantes]
        print(retrait + ligne_balisee(
            balise, "A_DEFINIR", "constaté : " + " · ".join(morceaux)),
            flush=True)

    if rapport["determinisme"] is not None:
        texte = f"déterminisme : {STATUTS_AFFICHES[rapport['determinisme']]}"
        print(retrait + (ligne_balisee(balise, "ECHEC", texte)
                         if rapport["determinisme"] == "ECHEC" else texte),
              flush=True)


def afficher_bilan(rapports, balise):
    compteurs = {"OK": 0, "ECHEC": 0, "A_DEFINIR": 0, "INDETERMINE": 0,
                 "DELAI": 0, "ERREUR": 0}
    for rapport in rapports:
        compteurs[statut_global(rapport)] += 1
    corps = (f"{len(rapports)} scénarios — "
             f"{compteurs['OK']} OK, {compteurs['ECHEC']} ÉCHEC, "
             f"{compteurs['DELAI']} délais, {compteurs['ERREUR']} erreurs, "
             f"{compteurs['A_DEFINIR']} à définir, "
             f"{compteurs['INDETERMINE']} indéterminés")
    problemes = compteurs["ECHEC"] + compteurs["ERREUR"]
    print()
    print(ligne_balisee(balise, "BILAN", corps, probleme=problemes > 0),
          flush=True)
    return problemes


# ---------------------------------------------------------------------------
# Consignation des sorties réelles
# ---------------------------------------------------------------------------

def enregistrer(rapports, chemin, balise):
    """Écrit les sorties réelles de chaque scénario dans un fichier JSON.

    Ce fichier sert de base de remplissage du protocole de tests : une fois
    les valeurs validées, elles peuvent être recopiées dans le fichier
    d'attendus pour devenir contraignantes.
    """
    donnees = {}
    for rapport in rapports:
        scenario = rapport["scenario"]
        derniere = rapport["mesures"][-1] if rapport["mesures"] else {}
        entree = {
            "categorie": scenario.categorie,
            "commande": scenario.arguments,
            "code_retour": derniere.get("code_retour"),
            "stdout": derniere.get("stdout"),
            "stderr": derniere.get("stderr"),
        }
        if "clipboard" in derniere:
            entree["clipboard"] = derniere.get("clipboard")
        donnees[scenario.identifiant] = entree
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(donnees, fichier, indent=2, ensure_ascii=False)
    print(ligne_balisee(balise, "CADRE",
                        f"Sorties réelles consignées dans : {chemin}"),
          flush=True)


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
    analyseur.add_argument(
        "--couleur", choices=("auto", "toujours", "jamais"), default="auto",
        help="balises colorées : auto (terminal interactif, défaut), "
             "toujours ou jamais (NO_COLOR est également respecté)")
    arguments = analyseur.parse_args(argv)

    balise = Balise(couleurs_actives(arguments.couleur))
    terminal = sys.stdout.isatty()

    if not os.path.exists(arguments.prog) \
            and shutil.which(arguments.prog) is None:
        print(ligne_balisee(balise, "ECHEC",
                            f"Programme introuvable : {arguments.prog}"),
              flush=True)
        return 2

    # Avertissement ciblé : un binaire Windows testé depuis WSL via
    # l'interopérabilité ne reçoit pas de manière fiable les tubes
    # redirigés ; les scénarios d'invite (saisie invisible du secret)
    # peuvent alors se bloquer jusqu'au délai, un à un.
    if est_binaire_windows(arguments.prog) and est_wsl():
        print(ligne_balisee(
            balise, "ALERTE",
            f"« {arguments.prog} » est un exécutable Windows (PE) lancé "
            "depuis WSL via l'interopérabilité : les entrées/sorties "
            "redirigées (tubes) ne fonctionnent pas de manière fiable dans "
            "cette configuration. Testez plutôt la compilation Linux du "
            "programme, ou exécutez ce cadre depuis un interpréteur Python "
            "Windows."), flush=True)

    # Avertissement symétrique : un binaire Linux testé depuis Windows ne
    # se lance pas du tout (erreur Win32 193, « %1 n'est pas une
    # application Win32 valide ») — c'est le signe d'un exécutable compilé
    # sous WSL et non d'un défaut du programme ou du cadre.
    if est_binaire_linux(arguments.prog) and EST_WINDOWS:
        print(ligne_balisee(
            balise, "ALERTE",
            f"« {arguments.prog} » est un exécutable Linux (ELF) : Windows "
            "ne peut pas le lancer (erreur Win32 193, « %1 n'est pas une "
            "application Win32 valide »). Compilez une version native : "
            "cl /O2 /Fe:Schuffler.exe main.c (invite de commandes "
            "Visual Studio) ou gcc -O2 -Wall -Wextra -o Schuffler.exe "
            "main.c (MinGW), puis relancez avec --prog ./Schuffler.exe"),
            flush=True)

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
        print("Aucun scénario ne correspond aux critères indiqués.",
              flush=True)
        return 2

    total = len(scenarios)
    afficher_entete(arguments.prog, cadre.pp_disponible(), balise, total)

    rapports = []
    interrompu = False
    categorie_courante = None
    try:
        for numero, scenario in enumerate(scenarios, 1):
            if scenario.categorie != categorie_courante:
                categorie_courante = scenario.categorie
                afficher_categorie(categorie_courante, balise)
            afficher_en_cours(scenario, arguments.prog, balise, terminal,
                              numero, total)
            try:
                rapport = cadre.verifier(scenario)
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # résilience : un scénario défaillant
                rapport = {             # n'interrompt jamais la suite
                    "scenario": scenario,
                    "mesures": [],
                    "details": [],
                    "determinisme": None,
                    "duree": 0.0,
                    "erreur_cadre": repr(exc),
                }
            rapports.append(rapport)
            afficher_scenario(rapport, arguments.prog, balise, terminal,
                              numero, total)
    except KeyboardInterrupt:
        interrompu = True
        if cadre.processus_actif is not None:
            tuer_groupe(cadre.processus_actif, cadre.pgid_actif)
        if terminal:
            sys.stdout.write("\r\033[K")
        print(ligne_balisee(
            balise, "INTERRUPTION",
            f"Ctrl+C : {len(rapports)}/{total} scénarios "
            "exécutés ; rapport partiel ci-dessous."), flush=True)

    if not rapports:
        print("Aucun scénario n'a été exécuté.", flush=True)
        return 130 if interrompu else 2

    problemes = afficher_bilan(rapports, balise)

    if arguments.enregistrer:
        enregistrer(rapports, arguments.enregistrer, balise)

    if interrompu:
        return 130
    return 1 if problemes else 0


if __name__ == "__main__":
    sys.exit(main())