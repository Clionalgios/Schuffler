# Tests

Les tests sont les épreuves de validation du programme et de ses options, quels que soient le langage employé. Chaque version du programme doit en définitive se comporter de la même façon, afin de garder la meilleure portabilité du programme.

Chaque catégorie ci-dessous reprend un aspect du fonctionnement déclaré du programme. Les cellules marquées *À définir* sont laissées vides : elles doivent être complétées à partir de la transformation produite par Schuffler, afin de vérifier que les valeurs obtenues demeurent bien celles qui sont consignées.

## Conventions

Les tableaux suivent les conventions ci-dessous, alignées sur le cadre de test scripté (`schuffler_tests.py`) :

- Sortie standard : réservée à la chaîne transformée (mode `-A`), au « 0 » du mode clipboard seul, à l'artefact (option `-a` en mode clipboard seul) et à l'aide demandée explicitement (`-h`/`--help`). Aucun message d'erreur n'y figure jamais.

- Sortie d'erreur : porte tous les messages d'erreur, ainsi que l'aide affichée à la suite d'une erreur (divergence de flux documentée du portage C : le script bash affichait ces messages sur la sortie standard).

- Code : code de retour du processus ; 0 en cas de succès, 1 en cas d'erreur.

- Clipboard : contenu du presse-papiers à l'issue de l'exécution ; *Rien* signifie que le presse-papiers n'est pas touché, *Vide* qu'il demeure vide (le cadre de test le vide avant chaque exécution).

- Entrée scanf : *Entrée* indique que le secret est attendu en saisie invisible sur l'entrée standard ; *Bypassed* que l'entrée standard n'est pas consommée, le secret étant passé en argument.

## Catégorie 1 — Sans-mode (mode par défaut)

Comportement attendu : en l'absence de toute option de mode, le programme se ferme en demandant qu'un mode soit indiqué. Le refus a lieu avant toute lecture : l'entrée standard n'est pas consommée et le secret n'est jamais demandé.

| Commande                                         | Entrée `scanf` | Sortie standard | Sortie d'erreur                                                     | Code | Clipboard |
| ------------------------------------------------ | -------------- | --------------- | ------------------------------------------------------------------- | ---- | --------- |
| `./Schuffler`                                    | *Bypassed*     | *Vide*          | `Erreur : aucun mode de fonctionnement indiqué`, puis *menu d'aide* | 1    | *Rien*    |
| `./Schuffler monsecret`                          | *Bypassed*     | *Vide*          | `Erreur : aucun mode de fonctionnement indiqué`, puis *menu d'aide* | 1    | *Rien*    |
| `./Schuffler --length 32 --no-special monsecret` | *Bypassed*     | *Vide*          | `Erreur : aucun mode de fonctionnement indiqué`, puis *menu d'aide* | 1    | *Rien*    |
| `./Schuffler -l 4 test`                          | *Bypassed*     | *Vide*          | `Erreur : aucun mode de fonctionnement indiqué`, puis *menu d'aide* | 1    | *Rien*    |
## Catégorie 2 — Mode API

Comportement attendu : l'option `-A` renvoie directement la chaîne transformée sur la sortie standard, sans action sur le presse-papier. Le secret doit être passé en argument : la saisie invisible n'y est pas proposée et l'entrée standard n'est pas consommée. Une chaîne transformable vide passée en argument compte pour une absence de chaîne : la demande est rejetée de la même façon, sous un message propre au secret passé vide.

| Commande                                      | Entrée `scanf` | Sortie standard                                      | Sortie d'erreur                                                        | Code |
| --------------------------------------------- | -------------- | ---------------------------------------------------- | ---------------------------------------------------------------------- | ---- |
| `./Schuffler -A`                              | *Bypassed*     | *Vide*                                               | `Erreur : pas de clé transformable passée`, puis *menu d'aide*         | 1    |
| `./Schuffler -A test`                         | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                               | *Rien*                                                                 | 0    |
| `./Schuffler -A test1`                        | *Bypassed*     | `1awABg92YU%JrQ33R*FB`                               | *Rien*                                                                 | 0    |
| `./Schuffler -A -l 50 test`                   | *Bypassed*     | `b5UdvYAHNFWd!IIOrPnh%Zql3Me2lMeGjlBVDlM4FafTWKN%o6` | *Rien*                                                                 | 0    |
| `./Schuffler -A -l 4 test`                    | *Bypassed*     | `Ba%2`                                               | *Rien*                                                                 | 0    |
| `./Schuffler --API test` (option longue)      | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                               | *Rien*                                                                 | 0    |
| `./Schuffler -A ""` (secret vide en argument) | *Bypassed*     | *Vide*                                               | `Erreur : clé transformable passée non-utilisable`, puis *menu d'aide* | 1    |

## Catégorie 3 — Mode Clipboard

Comportement attendu : l'option `-C` envoie la chaîne transformée dans le presse-papier, sans sortie de la chaîne sur la sortie standard (seul le « 0 » y est affiché). Une chaîne transformable vide passée en argument compte pour une absence de chaîne : la saisie invisible est proposée, comme pour un appel sans secret.

| Commande                                       | Entrée     | Sortie standard | Sortie d'erreur                                            | Code | Clipboard              |
| ---------------------------------------------- | ---------- | --------------- | ---------------------------------------------------------- | ---- | ---------------------- |
| `./Schuffler -C test`                          | *Bypassed* | `0`             | *Rien*                                                     | 0    | `bafTBVD2lM%ZqIIOAHN6` |
| `./Schuffler -C monsecret`                     | *Bypassed* | `0`             | *Rien*                                                     | 0    | `Ya+mBqP2Lm%aGUN^i1@s` |
| `./Schuffler -C` (saisie vide à l'invite)      | *Entrée*   | *Vide*          | `Erreur : aucune chaîne à transformer`, puis *menu d'aide* | 1    | *Vide*                 |
| `./Schuffler -C ""` (chaîne vide en argument)  | *Entrée*   | `0`             | *Rien*                                                     | 0    | `bafTBVD2lM%ZqIIOAHN6` |
| `./Schuffler --clipboard test` (option longue) | *Bypassed* | `0`             | *Rien*                                                     | 0    | `bafTBVD2lM%ZqIIOAHN6` |
| `./Schuffler -C -l 4 test`                     | *Bypassed* | `0`             | *Rien*                                                     | 0    | `Ba%2`                 |

## Catégorie 4 — Mode combiné (`-A` et `-C`)

Comportement attendu : lorsque les deux options sont passées simultanément, la chaîne transformée est envoyée à la fois sur la sortie standard et dans le presse-papier ; le « 0 » du mode clipboard seul n'y est pas ajouté.

| Commande                                 | Entrée `scanf` | Sortie standard                                      | Sortie d'erreur | Code | Clipboard                                            |
| ---------------------------------------- | -------------- | ---------------------------------------------------- | --------------- | ---- | ---------------------------------------------------- |
| `./Schuffler -A -C test`                 | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                               | *Rien*          | 0    | `bafTBVD2lM%ZqIIOAHN6`                               |
| `./Schuffler -A -C -l 50 monsecret`      | *Bypassed*     | `Y$2Wtwi1@YPClUN^jCkO%aGaKjA2LmY@fmBqPt#vga+m%uNaSs` | *Rien*          | 0    | `Y$2Wtwi1@YPClUN^jCkO%aGaKjA2LmY@fmBqPt#vga+m%uNaSs` |
| `./Schuffler -C -A test` (ordre inversé) | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                               | *Rien*          | 0    | `bafTBVD2lM%ZqIIOAHN6`                               |

## Catégorie 5 — Déterminisme

Comportement attendu : le même secret combiné aux mêmes options produit toujours le même mot de passe, quelle que soit l'exécution.

| Commande                                                             | Entrée `scanf` | Sortie standard                                                                                                    | Sortie d'erreur | Code | Clipboard                                  |
| -------------------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------ | --------------- | ---- | ------------------------------------------ |
| `./Schuffler -A test` (1re exécution)                                | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                                                                                             | *Rien*          | 0    | *Rien*                                     |
| `./Schuffler -A test` (2e exécution)                                 | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                                                                                             | *Rien*          | 0    | *Rien*                                     |
| `./Schuffler -A -l 32 test` (2 exécutions successives)               | *Bypassed*     | Première exécution : `b5U2lMeGAHNFBVDlMIIOrafTWK%Zql36`<br>Deuxième exécution : `b5U2lMeGAHNFBVDlMIIOrafTWK%Zql36` | *Rien*          | 0    | *Rien*                                     |
| `./Schuffler -C test` (2 exécutions successives)                     | *Bypassed*     | `0` aux deux exécutions                                                                                            | *Rien*          | 0    | `bafTBVD2lM%ZqIIOAHN6` aux deux exécutions |
| `./Schuffler -A --special-set '@#%' test` (2 exécutions successives) | *Bypassed*     | `nalTBVD2x4@#COO0ST5f` aux deux exécutions                                                                         | *Rien*          | 0    | *Rien*                                     |

## Catégorie 6 — Longueur du mot de passe

Comportement attendu : la longueur par défaut est de 20 caractères ; la longueur minimale acceptée est de 4 caractères. Aucune notation de numération suggérée par l'écriture de la valeur n'est interprétée : un zéro initial est retiré et la valeur est lue comme expression décimale (`-l 010` vaut 10, `-l 08` vaut 8) ; une valeur contenant une lettre — notation hexadécimale (`0x10`) ou binaire (`0b1010`) — refuse la commande.

| Commande                                                    | Entrée `scanf` | Sortie standard                                                                                        | Sortie d'erreur                                                                           | Code |
| ----------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- | ---- |
| `./Schuffler -A test` (longueur par défaut : 20)            | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                                                                                 | *Rien*                                                                                    | 0    |
| `./Schuffler -A -l 20 test`                                 | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                                                                                 | *Rien*                                                                                    | 0    |
| `./Schuffler -A --length 20 test` (option longue)           | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                                                                                 | *Rien*                                                                                    | 0    |
| `./Schuffler -A -l 4 test`                                  | *Bypassed*     | `Ba%2`                                                                                                 | *Rien*                                                                                    | 0    |
| `./Schuffler -A -l 3 test` (sous le minimum)                | *Bypassed*     | *Vide*                                                                                                 | `Longueur invalide`                                                                       | 1    |
| `./Schuffler -A -l 0 test` (valeur nulle)                   | *Bypassed*     | *Vide*                                                                                                 | `Longueur invalide`                                                                       | 1    |
| `./Schuffler -A -l test` (valeur non numérique)             | *Bypassed*     | *Vide*                                                                                                 | `Longueur invalide`                                                                       | 1    |
| `./Schuffler -A -l 010 test` (zéro initial : lu en décimal, vaut 10) | *Bypassed*     | `%afIBVA2l6`                                                                                          | *Rien*                                                                                    | 0    |
| `./Schuffler -A -l 08 test` (zéro initial : lu en décimal, vaut 8)  | *Bypassed*     | `AI%2Baf6`                                                                                            | *Rien*                                                                                    | 0    |
| `./Schuffler -A -l 0x10 test` (hexadécimal : lettres → refus)       | *Bypassed*     | *Vide*                                                                                                 | `Longueur invalide`                                                                       | 1    |
| `./Schuffler -A -l 0b1010 test` (binaire : lettres → refus)         | *Bypassed*     | *Vide*                                                                                                 | `Longueur invalide`                                                                       | 1    |
| `./Schuffler -A -l 100 test`                                | *Bypassed*     | `b5UdvYAFOD*5OIIOrPnhVSdeKOu2lMeGjl!6n$StCafTWKN%ozVdxYwXAHNFWd!N6HLms^%Zql3MeT5!HEuCBVDlM4FTl*ef+tX6` | *Rien*                                                                                    | 0    |
  
## Catégorie 7 — Jeux de caractères (exclusions)

Comportement attendu : chaque option d'exclusion retire une classe de caractères de la transformation ; `--exclude-chars` est appliquée après tous les jeux. Une classe active mais vidée par les exclusions interrompt le programme (particularité du script d'origine reproduite à dessein), de même qu'un alphabet final vide.  

| Commande                                                                                                              | Entrée `scanf` | Sortie standard                                      | Sortie d'erreur                                          | Code |
| --------------------------------------------------------------------------------------------------------------------- | -------------- | ---------------------------------------------------- | -------------------------------------------------------- | ---- |
| `./Schuffler -A --no-lower test`                                                                                      | *Bypassed*     | `IA5A1C3$S0JNXPPCO^1U`                               | *Rien*                                                   | 0    |
| `./Schuffler -A --no-upper test`                                                                                      | *Bypassed*     | `ia5a1c3$s0jnxppco^1u`                               | *Rien*                                                   | 0    |
| `./Schuffler -A --no-digits test`                                                                                     | *Bypassed*     | `vapTBVD$FhwkKSS#^@ir`                               | *Rien*                                                   | 0    |
| `./Schuffler -A --no-special test`                                                                                    | *Bypassed*     | `taoTBVD2DduhIRR61Zeo`                               | *Rien*                                                   | 0    |
| `./Schuffler -A --no-lower --no-upper test`                                                                           | *Bypassed*     | `!007@9!214@36!!@@45!`                               | *Rien*                                                   | 0    |
| `./Schuffler -A --no-lower --no-upper --no-digits test`                                                               | *Bypassed*     | `#!^!^$$$!#!^&**$&^!$`                               | *Rien*                                                   | 0    |
| `./Schuffler -A --no-lower --no-upper --no-digits --no-special test` (jeu vide)                                       | *Bypassed*     | *Vide*                                               | `Toutes les catégories ont été exclues`                  | 1    |
| `./Schuffler -A --exclude-chars 'aeiou' -l 50 test`                                                                   | *Bypassed*     | `p!ZrF3UW7U1xcSS3wZrB%^FA#1y2A6sQmFB0IvR^KbnY@PXmsd` | *Rien*                                                   | 0    |
| `./Schuffler -A --exclude-chars 'abcdefghijklmnopqrstuvwxyz' test` (classe des minuscules vidée mais active)          | *Bypassed*     | *Vide*                                               | `schuffler: pos % 0: division by 0 (error token is "0")` | 1    |
| `./Schuffler -A --no-lower --no-upper --no-digits --special-set '@#' --exclude-chars '@#' test` (alphabet final vide) | *Bypassed*     | *Vide*                                               | `Alphabet final vide après exclusions`                   | 1    |

## Catégorie 8 — Jeu de caractères spéciaux personnalisé

Comportement attendu : `--special-set` force le jeu de caractères spéciaux ; il peut être combiné à `--exclude-chars`, laquelle s'applique en dernier. Le jeu personnalisé est sans effet si la classe des spéciaux est désactivée (`--no-special`).

| Commande                                                                                    | Entrée `scanf` | Sortie standard                                      | Sortie d'erreur                       | Code |
| ------------------------------------------------------------------------------------------- | -------------- | ---------------------------------------------------- | ------------------------------------- | ---- |
| `./Schuffler -A --special-set '@#%' test`                                                   | *Bypassed*     | `nalTBVD2x4@#COO0ST5f`                               | *Rien*                                | 0    |
| `./Schuffler -A --special-set '@#$%' --exclude-chars '#' test`                              | *Bypassed*     | `nalTBVD2x4@$COO0ST5f`                               | *Rien*                                | 0    |
| `./Schuffler -A --special-set '@#%' -l 50 test`                                             | *Bypassed*     | `n5UpBYST5RWvdOO0rVnz@#CxcYw2x4qMjDBVDrM@FalT8KTmof` | *Rien*                                | 0    |
| `./Schuffler -A --special-set '@#%' --no-special test` (jeu sans effet : classe désactivée) | *Bypassed*     | *À définir*                                          | *Rien*                                | 0    |
| `./Schuffler -A --special-set '@@@' test` (caractères répétés)                              | *Bypassed*     | *À définir*                                          | *Rien*                                | 0    |
| `./Schuffler -A --special-set '' test` (jeu spécial vide)                                   | *Bypassed*     | *Vide*                                               | `Jeu de caractères spéciaux manquant` | 1    |

## Catégorie 9 — Artefact

Comportement attendu : l'option `-a` affiche l'artefact de la chaîne transformée (premier et dernier caractère) : en complément de la chaîne en clair sur la sortie standard en mode API, à la place du « 0 » en mode clipboard seul. Le presse-papier reçoit toujours la chaîne complète.

| Commande                                                          | Entrée `scanf` | Sortie standard                                | Sortie d'erreur                                                     | Code | Clipboard              |
| ----------------------------------------------------------------- | -------------- | ---------------------------------------------- | ------------------------------------------------------------------- | ---- | ---------------------- |
| `./Schuffler -A -a test`                                          | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6` puis `b6` (deux lignes) | *Rien*                                                              | 0    | *Rien*                 |
| `./Schuffler -a test`                                             | *Bypassed*     | *Vide*                                         | `Erreur : aucun mode de fonctionnement indiqué`, puis *menu d'aide* | 1    | *Vide*                 |
| `./Schuffler -A -a -l 4 test`                                     | *Bypassed*     | `Ba%2` puis `B2` (deux lignes)                 | *Rien*                                                              | 0    | *Rien*                 |
| `./Schuffler test -a -C`                                          | *Bypassed*     | `b6`                                           | *Rien*                                                              | 0    | `bafTBVD2lM%ZqIIOAHN6` |
| `./Schuffler -C -a test` (ordre canonique de la ligne précédente) | *Bypassed*     | `b6`                                           | *Rien*                                                              | 0    | `bafTBVD2lM%ZqIIOAHN6` |
| `./Schuffler -A -C -a test` (modes combinés)                      | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6` puis `b6` (deux lignes) | *Rien*                                                              | 0    | `bafTBVD2lM%ZqIIOAHN6` |
## Catégorie 10 — Aide et erreurs d'appel

Comportement attendu : `-h` affiche l'aide sur la sortie standard et quitte (code 0) ; une option inconnue doit être signalée sans produire de transformation. L'aide prime sur le reste de la ligne : l'analyse s'arrête à sa rencontre.

| Commande                                                         | Entrée `scanf` | Sortie standard | Sortie d'erreur                           | Code |
| ---------------------------------------------------------------- | -------------- | --------------- | ----------------------------------------- | ---- |
| `./Schuffler -h`                                                 | *Bypassed*     | *Menu d'aide*   | *Rien*                                    | 0    |
| `./Schuffler --help`                                             | *Bypassed*     | *Menu d'aide*   | *Rien*                                    | 0    |
| `./Schuffler -A -h` (l'aide prime sur le mode)                   | *Bypassed*     | *Menu d'aide*   | *Rien*                                    | 0    |
| `./Schuffler -h --option-inconnue` (l'analyse s'arrête à l'aide) | *Bypassed*     | *Menu d'aide*   | *Rien*                                    | 0    |
| `./Schuffler --option-inconnue test`                             | *Bypassed*     | *Vide*          | `Option inconnue: --option-inconnue`      | 1    |
| `./Schuffler -A -l` (valeur de longueur manquante)               | *Bypassed*     | *Vide*          | `Longueur invalide`                       | 1    |
| `./Schuffler --special-set` (valeur manquante)                   | *Bypassed*     | *Vide*          | `Jeu de caractères spéciaux manquant`     | 1    |
| `./Schuffler --exclude-chars` (valeur manquante)                 | *Bypassed*     | *Vide*          | `Liste de caractères à exclure manquante` | 1    |

## Catégorie 11 — Saisie invisible du secret

Comportement attendu : en mode clipboard sans secret en argument, le secret est demandé en saisie invisible sur l'entrée standard. La sémantique du « read » du script d'origine est conservée à dessein : un antislash échappe le caractère suivant, un antislash en fin de ligne poursuit la saisie à la ligne suivante, et les espaces et tabulations extrêmes sont rognés. Un secret saisi vide rejette l'appel.

| Commande         | Saisie à l'invite                                                    | Sortie standard | Sortie d'erreur                                            | Code | Clipboard                                    |
| ---------------- | -------------------------------------------------------------------- | --------------- | ---------------------------------------------------------- | ---- | -------------------------------------------- |
| `./Schuffler -C` | `test`                                                               | `0`             | *Rien*                                                     | 0    | `bafTBVD2lM%ZqIIOAHN6`                       |
| `./Schuffler -C` | `te\st` (l'antislash échappe le caractère suivant)                   | `0`             | *Rien*                                                     | 0    | `bafTBVD2lM%ZqIIOAHN6` (équivalent à `test`) |
| `./Schuffler -C` | `te\` puis *Entrée*, puis `st` (continuation de ligne)               | `0`             | *Rien*                                                     | 0    | `bafTBVD2lM%ZqIIOAHN6` (équivalent à `test`) |
| `./Schuffler -C` | `␣␣test␣␣␉` (espaces et tabulations rognés ; ␣ espace, ␉ tabulation) | `0`             | *Rien*                                                     | 0    | `bafTBVD2lM%ZqIIOAHN6` (équivalent à `test`) |
| `./Schuffler -C` | *(saisie vide)*                                                      | *Vide*          | `Erreur : aucune chaîne à transformer`, puis *menu d'aide* | 1    | *Vide*                                       |

## Catégorie 12 — Sémantique de l'analyse

Comportement attendu : le parcours de la ligne de commande conserve les particularités du script d'origine : seul le premier argument positionnel sert de secret, toute chaîne commençant par un tiret est traitée comme une option, « -- » interrompt l'analyse et le reste de la ligne est ignoré, et la dernière valeur passée à une option à valeur l'emporte.

| Commande                                                                                | Entrée `scanf` | Sortie standard                                     | Sortie d'erreur                                                | Code |
| --------------------------------------------------------------------------------------- | -------------- | --------------------------------------------------- | -------------------------------------------------------------- | ---- |
| `./Schuffler -A -- test` (le secret suivant « -- » est ignoré)                          | *Bypassed*     | *Vide*                                              | `Erreur : pas de clé transformable passée`, puis *menu d'aide* | 1    |
| `./Schuffler -A test monsecret` (seul le premier argument compte)                       | *Bypassed*     | `bafTBVD2lM%ZqIIOAHN6`                              | *Rien*                                                         | 0    |
| `./Schuffler -A -test` (un secret ne peut commencer par un tiret)                       | *Bypassed*     | *Vide*                                              | `Option inconnue: -test`                                       | 1    |
| `./Schuffler -A --exclude-chars a --exclude-chars e test` (la dernière liste l'emporte) | *Bypassed*     | *À définir* (équivalent à `--exclude-chars e test`) | *Rien*                                                         | 0    |

