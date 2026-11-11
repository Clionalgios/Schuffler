# Tests

Les tests sont les épreuves de validation du programme et de ses options, quels que soient le langage employé. Chaque version du programme doit en définitive se comporter de la même façon, afin de garder la meilleure portabilité du programme.

Chaque catégorie ci-dessous reprend un aspect du fonctionnement déclaré du programme. Les colonnes « Sortie standard » et « Clipboard » sont laissées vides : elles doivent être complétées à partir de la transformation produite par Schuffler, afin de vérifier que les valeurs obtenues demeurent bien celles qui sont consignées.

## Catégorie 1 — Sans-mode (mode par défaut)

Comportement attendu : en l'absence de toute option de mode, le programme se ferme en demandant qu'un mode soit indiqué. Si le secret est absent en argument, il est demandé en saisie invisible.

|                     Commande                     | Entrée `scanf` | Sortie standard | Clipboard |
| :----------------------------------------------: | -------------- | --------------- | --------- |
|                  `./Schuffler`                   | *Entrée*       | *Menu d'aide*   | *Rien*    |
|             `./Schuffler monsecret`              | *Bypassed*     | *Menu d'aide*   | *Rien*    |
| `./Schuffler --length 32 --no-special monsecret` | *Bypassed*     | *Menu d'aide*   | *Rien*    |
|             `./Schuffler -l 4 test`              | *Bypassed*     | *Menu d'aide*   | *Rien*    |

## Catégorie 2 — Mode API

Comportement attendu : l'option `-A` renvoie directement la chaîne transformée sur la sortie standard, sans action sur le presse-papier.

|          Commande           | Entrée `scanf` | Sortie standard                                           |
| :-------------------------: | -------------- | --------------------------------------------------------- |
|      `./Schuffler -A`       | *Entrée*       | Erreur : pas de clé transformable passée<br>*Menu `help`* |
|    `./Schuffler -A test`    | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                                    |
|   `./Schuffler -A test1`    | *Bypassed*     | `1awABg92YU%JrQ33R*FB`                                    |
| `./Schuffler -A -l 50 test` | *Bypassed*     | `b5UdvYAHNFWd!IIOrPnh%Zql3Me2lMeGjlBVDlM4FafTWKN%o6`      |
| `./Schuffler -A -l 4 test`  | *Bypassed*     | `Ba%2`                                                    |


## Catégorie 3 — Mode Clipboard

Comportement attendu : l'option `-C` envoie la chaîne transformée dans le presse-papier, sans sortie sur la sortie standard.

|                  Commande                   | Entrée     | Sortie        | Clipboard            |
| :-----------------------------------------: | ---------- | ------------- | -------------------- |
|            `./Schuffler -C test`            | *Bypassed* | 0             | bafTBVD2lM%ZqIIOAHN6 |
|         `./Schuffler -C monsecret`          | *Bypassed* | 0             | Ya+mBqP2Lm%aGUN^i1@s |
| `./Schuffler -C` (secret fourni à l'invite) | *Entrée*   | *Menu d'aide* | *Vide*               |

## Catégorie 4 — Mode combiné (`-A` et `-C`)

Comportement attendu : lorsque les deux options sont passées simultanément, la chaîne transformée est envoyée à la fois sur la sortie standard et dans le presse-papier.

|              Commande               | Entrée `scanf` | Sortie standard                                    | Clipboard                                          |
| :---------------------------------: | -------------- | -------------------------------------------------- | -------------------------------------------------- |
|      `./Schuffler -A -C test`       | *Bypassed*     | bafTBVD2lM%ZqIIOAHN6                               | bafTBVD2lM%ZqIIOAHN6                               |
| `./Schuffler -A -C -l 50 monsecret` | *Bypassed*     | Y$2Wtwi1@YPClUN^jCkO%aGaKjA2LmY@fmBqPt#vga+m%uNaSs | Y$2Wtwi1@YPClUN^jCkO%aGaKjA2LmY@fmBqPt#vga+m%uNaSs |

## Catégorie 5 — Déterminisme

Comportement attendu : le même secret combiné aux mêmes options produit toujours le même mot de passe, quelle que soit l'exécution.

|                        Commande                        | Entrée `scanf` | Sortie standard                                                                                                |
| :----------------------------------------------------: | -------------- | -------------------------------------------------------------------------------------------------------------- |
|         `./Schuffler -A test` (1re exécution)          | *Bypassed*     | bafTBVD2lM%ZqIIOAHN6                                                                                           |
|          `./Schuffler -A test` (2e exécution)          | *Bypassed*     | bafTBVD2lM%ZqIIOAHN6                                                                                           |
| `./Schuffler -A -l 32 test` (2 exécutions successives) | *Bypassed*     | Première exécution : b5U2lMeGAHNFBVDlMIIOrafTWK%Zql36<br>Deuxième exécution : b5U2lMeGAHNFBVDlMIIOrafTWK%Zql36 |


## Catégorie 6 — Longueur du mot de passe

Comportement attendu : la longueur par défaut est de 20 caractères ; la longueur minimale acceptée est de 4 caractères.

|                     Commande                     | Entrée `scanf` | Sortie standard                                                                                      |
| :----------------------------------------------: | -------------- | ---------------------------------------------------------------------------------------------------- |
| `./Schuffler -A test` (longueur par défaut : 20) | *Bypassed*     | bafTBVD2lM%ZqIIOAHN6                                                                                 |
|           `./Schuffler -A -l 20 test`            | *Bypassed*     | bafTBVD2lM%ZqIIOAHN6                                                                                 |
|            `./Schuffler -A -l 4 test`            | *Bypassed*     | Ba%2                                                                                                 |
|   `./Schuffler -A -l 3 test` (sous le minimum)   | *Bypassed*     | Longueur invalide                                                                                    |
|           `./Schuffler -A -l 100 test`           | *Bypassed*     | b5UdvYAFOD*5OIIOrPnhVSdeKOu2lMeGjl!6n$StCafTWKN%ozVdxYwXAHNFWd!N6HLms^%Zql3MeT5!HEuCBVDlM4FTl*ef+tX6 |
| `./Schuffler -A -l test` (valeur non numérique)  | *Bypassed*     | Longueur invalide                                                                                    |

## Catégorie 7 — Jeux de caractères (exclusions)

Comportement attendu : chaque option d'exclusion retire une classe de caractères de la transformation ; `--exclude-chars` est appliquée après tous les jeux.

|                                    Commande                                     | Entrée `scanf` | Sortie standard                                    |
| :-----------------------------------------------------------------------------: | -------------- | -------------------------------------------------- |
|                        `./Schuffler -A --no-lower test`                         | *Bypassed*     | IA5A1C3$S0JNXPPCO^1U                               |
|                        `./Schuffler -A --no-upper test`                         | *Bypassed*     | ia5a1c3$s0jnxppco^1u                               |
|                        `./Schuffler -A --no-digits test`                        | *Bypassed*     | vapTBVD$FhwkKSS#^@ir                               |
|                       `./Schuffler -A --no-special test`                        | *Bypassed*     | taoTBVD2DduhIRR61Zeo                               |
|                   `./Schuffler -A --no-lower --no-upper test`                   | *Bypassed*     | !007@9!214@36!!@@45!                               |
|             `./Schuffler -A --no-lower --no-upper --no-digits test`             | *Bypassed*     | #!^!^$$$!#!^&**$&^!$                               |
| `./Schuffler -A --no-lower --no-upper --no-digits --no-special test` (jeu vide) | *Bypassed*     | Toutes les catégories ont été exclues              |
|               `./Schuffler -A --exclude-chars 'aeiou' -l 50 test`               | *Bypassed*     | p!ZrF3UW7U1xcSS3wZrB%^FA#1y2A6sQmFB0IvR^KbnY@PXmsd |

## Catégorie 8 — Jeu de caractères spéciaux personnalisé

Comportement attendu : `--special-set` force le jeu de caractères spéciaux ; il peut être combiné à `--exclude-chars`, laquelle s'applique en dernier.

|                            Commande                            | Entrée `scanf` | Sortie standard                                    |
| :------------------------------------------------------------: | -------------- | -------------------------------------------------- |
|           `./Schuffler -A --special-set '@#%' test`            | *Bypassed*     | nalTBVD2x4@#COO0ST5f                               |
| `./Schuffler -A --special-set '@#$%' --exclude-chars '#' test` | *Bypassed*     | nalTBVD2x4@$COO0ST5f                               |
|        `./Schuffler -A --special-set '@#%' -l 50 test`         | *Bypassed*     | n5UpBYST5RWvdOO0rVnz@#CxcYw2x4qMjDBVDrM@FalT8KTmof |
|   `./Schuffler -A --special-set '' test` (jeu spécial vide)    | *Bypassed*     | Jeu de caractères spéciaux manquant                |

## Catégorie 9 — Artefact

Comportement attendu : l'option `-a` affiche l'artefact de la chaîne transformée (premier et dernier caractère).

|           Commande            | Entrée `scanf` | Sortie standard                     | Clipboard            |
| :---------------------------: | -------------- | ----------------------------------- | -------------------- |
|   `./Schuffler -A -a test`    | *Bypassed*     | bafTBVD2lM%ZqIIOAHN6<br>b6          | *Vide*               |
|     `./Schuffler -a test`     | *Bypassed*     | *Menu d'aide* (pas de mode indiqué) | *Vide*               |
| `./Schuffler -A -a -l 4 test` | *Bypassed*     | Ba%2<br>B2                          | *Vide*               |
|    ./Schuffler test -a -C     | *Bypassed*     | b6                                  | bafTBVD2lM%ZqIIOAHN6 |


## Catégorie 10 — Aide et erreurs d'appel

Comportement attendu : `-h` affiche l'aide et quitte ; une option inconnue doit être signalée sans produire de transformation.

|                      Commande                      | Entrée `scanf` | Sortie standard                         |
| :------------------------------------------------: | -------------- | --------------------------------------- |
|                  `./Schuffler -h`                  | *Bypassed*     | *Menu d'aide*                           |
|                `./Schuffler --help`                | *Bypassed*     | *Menu d'aide*                           |
|        `./Schuffler --option-inconnue test`        | *Bypassed*     | Option inconnue: --option-inconnue      |
| `./Schuffler -A -l` (valeur de longueur manquante) | *Bypassed*     | Longueur invalide                       |
|   `./Schuffler --special-set` (valeur manquante)   | *Bypassed*     | Jeu de caractères spéciaux manquant     |
|  `./Schuffler --exclude-chars` (valeur manquante)  | *Bypassed*     | Liste de caractères à exclure manquante |