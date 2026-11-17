# README : Schuffler — portage C

Le portage C est la déclinaison en langage C de Schuffler : un générateur de mot de passe déterministe où le même secret et les mêmes options produisent toujours le même mot de passe, sorties et codes de retour compris, en conformité avec le script d'origine. Il tient en une seule unité de compilation, `srcs/c/main.c`, compilable et opérable individuellement, sans faire usage des autres sources du projet.

## Périmètre

- Une seule unité de compilation : `srcs/c/main.c`, sans bibliothèque externe pour la transformation. SHA-256 y est embarqué (FIPS 180-4, validé contre hashlib de Python sur 214 vecteurs, dont toutes les tailles de bloc frontières) et remplace l'appel à `sha256sum` du script d'origine.
- L'interface de commande (modes, options, conventions de sortie) est commune à tous les portages : elle est documentée dans le README maître, à la racine du projet. Le présent README documente ce qui est propre au portage : la compilation, les dépendances et les divergences vis-à-vis du script d'origine.

## Compilation

La commande de compilation est la même sous Linux et sous Windows : mêmes options, mêmes fichiers sources. Seuls diffèrent le compilateur appelé, le nom du binaire produit (l'extension `.exe` sous Windows) et les séparateurs de chemins. Dans les deux cas, la commande s'exécute depuis le répertoire racine du projet et place le binaire dans le répertoire `bin/`, non versionné.

### Protocole Linux

Prérequis :

- un compilateur C : `cc`, `gcc` ou `clang` ;
- une libc conforme POSIX.1-2008 (`sigaction`, `termios`, `popen`), fournie par tout système contemporain ;
- en mode clipboard uniquement : `xclip` (équivalence avec le script d'origine), à défaut `xsel` (X11), `wl-copy` (Wayland) ou `pbcopy` (macOS), essayés dans cet ordre en repli automatique ;
- à des fins de validation : une installation Python 3 fonctionnelle.

Commande :

```bash
$ cc -O2 -Wall -Wextra -o bin/schuffler srcs/c/main.c
```

### Protocole Windows

Prérequis :

- un compilateur C : MinGW-w64 (`gcc`) ou MSVC (`cl`) ;
- aucune dépendance externe pour le presse-papiers : l'API Win32 est employée en natif ;
- à des fins de validation : une installation Python 3 fonctionnelle.

Commande (identique au protocole Linux, l'extension mise à part) :

```bat
> gcc -O2 -Wall -Wextra -o bin\schuffler.exe srcs\c\main.c
```

Variantes acceptées :

```bash
$ cl /O2 /Fe:bin\schuffler.exe srcs\c\main.c                              # MSVC
$ x86_64-w64-mingw32-gcc -O2 -Wall -Wextra -o bin/schuffler.exe srcs/c/main.c   # cross-compilation depuis Linux
```

### Vérification

Une fois compilé, le binaire peut être confronté au vecteur de référence du protocole de tests (catégorie 2) :

```bash
$ ./bin/schuffler -A test
bafTBVD2lM%ZqIIOAHN6
```

## Particularités de chaque plateforme

### Linux et autres systèmes POSIX

- Saisie invisible du secret : `termios`, suppression de l'écho.
- Interruption (Ctrl-C) : `sigaction` ; elle déclenche le nettoyage sécurisé avant la sortie (code 1).
- Presse-papiers : outils externes essayés dans l'ordre `xclip`, `xsel`, `wl-copy`, `pbcopy` ; le premier qui réussit l'emporte.
- Effacement automatique : sous-routine détachée obtenue par `fork` et `setsid` ; les canaux hérités sont clos, elle survit au terminal comme à la fin du programme.

### Windows

- Presse-papiers natif par l'API Win32 (`CF_TEXT` : l'alphabet de Schuffler est ASCII pur), sans outil externe.
- Saisie invisible du secret : mode console (`ENABLE_ECHO_INPUT`).
- Effacement automatique : le programme se relance lui-même en processus détaché (`CreateProcess`, `DETACHED_PROCESS`) au moyen de l'option interne `--erase-worker`, absente de l'aide.
- Sorties redirigées (tubes, fichiers) forcées en mode binaire : les octets produits sont identiques à la compilation POSIX ; la console conserve le mode texte à l'interactif.

## Effacement automatique du presse-papiers

En mode clipboard, l'option `-e`/`--erase-after N` est obligatoire (minimum 1, lecture décimale stricte à l'identique de `--length`, la dernière valeur valide l'emporte) et refusée hors de ce mode. Le délai accordé est annoncé sur la sortie standard (« Le presse-papiers sera effacé dans N seconde(s) »), puis la console est aussitôt rendue : l'effacement est opéré à l'échéance par une sous-routine détachée, qui survit à la fin du programme — une interruption (Ctrl-C) après celle-ci n'a plus de prise sur elle. En cas d'échec de la programmation, repli en avant-plan : le délai s'écoule dans le programme, la console n'est pas rendue, l'effacement reste garanti.

## Divergences documentées vis-à-vis du script d'origine

Le portage conserve à dessein les particularités du script : quirk de « -- » (le reste de la ligne est ignoré), sémantique du « read » sans `-r` (antislashs, continuation de ligne, rognage IFS), arrêt fatal sur alphabet de classe vide (équivalent de la division par zéro du script), et seul le premier argument positionnel est retenu. Les divergences assumées sont les suivantes :

- Flux : tous les messages d'erreur, ainsi que l'aide affichée à leur suite, sont écrits sur la sortie d'erreur ; la sortie standard reste réservée à la chaîne transformée, au « 0 » du mode clipboard seul, à l'artefact, au délai annoncé et à l'aide demandée explicitement.
- Analyse : la valeur de `--length` comme celle de `--erase-after` n'est jamais lue dans une notation suggérée par son écriture (ni octale, ni hexadécimale, ni binaire) ; un zéro initial est retiré et la valeur lue en décimal ; toute lettre refuse la commande.
- Agrégation : `--exclude-chars` et `--special-set` sont répétables, les valeurs successives agglomérées, les doublons éliminés ; `--length` et `--erase-after` retiennent la dernière valeur valide passée.
- Appel : le mode API exige le secret en argument ; une chaîne transformable vide compte pour une absence de chaîne.

## Hygiène mémoire

Le secret n'est jamais écrit sur le disque. Les espaces de travail sensibles (secret saisi, secret en service, mot de passe brut et permuté, condensat) sont effacés puis libérés en sortie — l'original du secret dans la ligne de commande compris —, l'effacement étant résistant aux optimisations du compilateur. La sous-routine d'effacement efface de même les secrets de sa mémoire avant d'attendre son délai.

## Tests

Le portage se valide par le cadre de test commun, depuis la racine du projet :

```bash
$ python3 ./tests/validation.py --prog ./bin/schuffler          # Linux
> python3 tests\validation.py --prog bin\schuffler.exe          # Windows
```

Le protocole complet est consigné dans `tests/SCHEMA_DE_TESTS.md` : treize catégories, de l'absence de mode à l'effacement automatique du presse-papiers.