# README : Schuffler

Schuffler est un outil de transformation déterministe de chaînes de caractères, principalement destiné à la génération de mots de passe : un secret, combiné à des paramètres, produit toujours la même chaîne transformée, quel que soit le portage employé. Le projet est conçu pour être résilient, adaptable et exportable.

## Principe

- Déterminisme : le même secret et les mêmes options produisent toujours la même sortie, d'une exécution à l'autre comme d'un portage à l'autre.
- Portabilité : le programme est décliné en plusieurs langages, chacun compilable et opérable individuellement, sans faire usage des autres sources du projet. Tous les portages se conforment à une interface et à un protocole de tests communs.
- Autonomie : aucun stockage, aucun état persistant. Le secret n'est jamais écrit sur le disque et les espaces de travail sensibles sont effacés en sortie.
- Sobriété : aucune dépendance externe pour la transformation elle-même ; seules certaines cibles (presse-papiers) recourent à des outils du système.

## Chaîne de transformation

La transformation est commune à tous les portages et se déroule comme suit :

1. Lecture du secret : argument positionnel, sinon saisie invisible sur l'entrée standard (mode clipboard seul ; le mode API exige le secret en argument).
2. Construction de l'alphabet selon les options et les exclusions (minuscules, majuscules, chiffres, spéciaux).
3. Expansion déterministe : SHA-256 de « secret:compteur » ; chaque paire hexadécimale donne un octet, projeté sur l'alphabet par modulo.
4. Injection forcée d'un caractère par classe active (positions 0 à 3), afin que chaque classe conservée figure au moins une fois.
5. Permutation déterministe du résultat.
6. Sortie selon le mode demandé (sortie standard, presse-papiers, ou les deux).
7. Effacement automatique (mode clipboard) : le délai accordé — obligatoire, option -e/--erase-after — est annoncé sur la sortie standard ; le programme rend aussitôt la console, l'effacement est programmé en sous-routine détachée qui survit à sa fin.

## Interface commune

Quel que soit le portage, la ligne de commande et le comportement sont identiques.

### Modes

Aucun mode n'est appliqué par défaut : l'option `-A` ou `-C` est obligatoire ; à défaut, la transformation est refusée (message d'erreur puis aide, code de retour 1).

| Option | Mode | Effet |
| :---: | :---: | :---: |
| `-A`, `--API` | API | La chaîne transformée est écrite en clair sur la sortie standard. Le secret doit être passé en argument. |
| `-C`, `--clipboard` | Clipboard | La chaîne transformée est copiée dans le presse-papiers ; seul un « 0 » est affiché sur la sortie standard. Notez que le mode clipboard nécessite l'option `-e` ou `--erase-after` pour l'effacement automatique. |
| `-A -C` | Combiné | La chaîne est envoyée à la fois sur la sortie standard et dans le presse-papiers, sans le « 0 » du mode clipboard seul. Implique l'usage de l'option `-e` ou `--erase-after`. |

### Options

| Option | Effet |
| :---: | :---: |
| `-l`, `--length N` | Longueur du mot de passe (minimum 4, défaut 20). Aucune notation de numération suggérée par l'écriture n'est interprétée ; la dernière valeur valide l'emporte en cas de répétition. |
| `--no-lower` | Exclure les minuscules \[a-z\]. |
| `--no-upper` | Exclure les majuscules \[A-Z\]. |
| `--no-digits` | Exclure les chiffres \[0-9\]. |
| `--no-special` | Exclure les caractères spéciaux. |
| `--special-set "<jeu>"` | Forcer le jeu de caractères spéciaux. Option répétable : les jeux successifs sont agglomérés, les doublons éliminés. |
| `--exclude-chars "<liste>"` | Exclure explicitement certains caractères, après tous les jeux. Option répétable, même agrégation. |
| `-e, --erase-after N` | Délai, en secondes, avant l'effacement automatique du presse-papiers après l'affichage du résultat. Obligatoire en mode clipboard (-C), refusée hors de ce mode. Minimum 1 ; lecture décimale stricte à l'identique de -l, la dernière valeur valide l'emporte. Le délai accordé est annoncé sur la sortie standard, puis la console est rendue : l'effacement est opéré à l'échéance par une sous-routine détachée, qui survit à la fin du programme. |
| `-a`, `--artefact` | Afficher l'artefact de la chaîne (premier et dernier caractère) : en complément du clair en mode API, à la place du « 0 » en mode clipboard seul. Le presse-papiers reçoit toujours la chaîne complète. |
| `-h`, `--help` | Afficher l'aide et quitter. |

### Conventions de sortie

- La sortie standard est réservée à la chaîne transformée (mode `-A`), au « 0 » du mode clipboard seul, à l'artefact, au délai d'effacement annoncé à l'émission (option `-e`, mode clipboard) et à l'aide demandée explicitement. Aucun message d'erreur n'y figure jamais.
- La sortie d'erreur porte tous les messages d'erreur, ainsi que l'aide affichée à la suite d'une erreur.
- Code de retour : 0 en cas de succès, 1 en cas d'erreur.
- Le secret ne peut pas commencer par un tiret ; seul le premier argument positionnel est retenu ; tout ce qui suit « -- » est ignoré.

### Exemples

```bash
$ schuffler -A monsecret
$ schuffler -C monsecret
$ schuffler -A --length 32 --no-special monsecret
$ schuffler -C --special-set '@#%' --exclude-chars '#' monsecret
$ schuffler -A -C monsecret
$ schuffler -C -a monsecret
```

## Structure du dépôt

```
Schuffler/
├── README.md             # Ce document : périmètre, interface et protocole communs
├── srcs/                 # Sources, un sous-répertoire par portage linguistique
│   └── c/                # Portage C (main.c + README propre au portage)
├── tests/                # Protocole de tests commun et cadre de validation
│   ├── SCHEMA_DE_TESTS.md
│   └── validation.py
└── hooks/                # Hooks Git (pre-commit : refus des fichiers .exe)
```

Chaque portage dispose de son propre README, qui documente sa méthode de compilation, ses dépendances propres et ses éventuelles divergences documentées vis-à-vis du script d'origine.

## Compilation

La méthode de compilation dépend du portage employé : la commande à appliquer est indiquée dans le README propre à chaque version linguistique du projet. Dans tous les cas, la commande de compilation doit être exécutée depuis le répertoire racine du projet, et le binaire produit est placé dans le répertoire `bin/`, non versionné.

À titre d'illustration, pour le portage C :

```bash
$ cc -O2 -Wall -Wextra -o bin/schuffler srcs/c/main.c        # Linux
$ cl /O2 /Fe:bin\schuffler.exe srcs\c\main.c                   # Windows (MSVC)
```

## Tests

Les tests sont les épreuves de validation du programme et de ses options, quel que soit le langage employé. Chaque portage doit, en définitive, se comporter de la même façon.

Le protocole complet est consigné dans `tests/SCHEMA_DE_TESTS.md` ; le cadre de test scripté le joue de manière reproductible contre n'importe quel binaire compilé :

```bash
$ python3 ./tests/validation.py --prog ./bin/schuffler
```

Options utiles du cadre de test : `--categorie` et `--identifiant` pour restreindre l'exécution, `--enregistrer` pour consigner les sorties réelles en JSON (base de remplissage du protocole), `--attendus` pour imposer un fichier d'attendus qui prime sur les attendus intégrés, `--timeout` et `--couleur` pour le réglage du cadre. Les scénarios portant plusieurs exécutions vérifient de surcroît le déterminisme.

### Prérequis

- Installation Python fonctionnelle.
- Binaire Schuffler compilé et accessible dans le répertoire `bin/` du projet.
- Le répertoire racine du projet doit être le répertoire de travail du terminal de commandes.
- Sous POSIX, la vérification du presse-papiers requiert l'un des outils suivants : xclip, xsel, wl-paste ou pbpaste ; à défaut, elle est marquée indéterminée, jamais en échec. Sous Windows, la vérification est native et ne requiert aucun outil.

## Ajouter un portage

Le projet est extensible par construction. Tout nouveau portage linguistique doit :

1. se conformer à l'interface commune et au protocole de tests, sans dépendre des autres sources du projet ;
2. être compilable et opérable individuellement, depuis la racine du projet ;
3. disposer de son propre README dans son sous-répertoire de `srcs/`, documentant la compilation, les dépendances et toute divergence documentée ;
4. passer le cadre de test sans écart : `python3 ./tests/validation.py --prog ./bin/<binaire>`.

## Règles du dépôt

- Aucun binaire n'est versionné : `bin/` et les exécutables sont ignorés par Git ; le hook `pre-commit` refuse en outre tout fichier `.exe`.
- Les secrets utilisés dans les tests et la documentation sont factices ; aucun secret réel ne doit figurer dans le dépôt.