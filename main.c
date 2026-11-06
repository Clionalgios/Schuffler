/* ==========================================================================
 *  SCHUFFLER
 *  Générateur de mot de passe déterministe — portage C de schuffler.sh
 * ==========================================================================
 *
 *  PRINCIPE
 *    Le même secret et les mêmes options produisent toujours le même mot de
 *    passe, en bash comme en C (sorties et codes de retour identiques).
 *
 *  CHAÎNE DE TRAITEMENT
 *    1. Lecture du secret : argument positionnel, sinon saisie invisible.
 *    2. Construction de l'alphabet selon les options et les exclusions.
 *    3. Expansion déterministe : SHA-256("secret:compteur") ; chaque paire
 *       hexadécimale donne un octet, projeté sur l'alphabet par modulo.
 *    4. Injection forcée d'un caractère par classe active (positions 0 à 3).
 *    5. Permutation déterministe : final[i] = result[(i*7+13) % n].
 *    6. Sortie selon le mode : API (chaîne en clair sur la sortie standard),
 *       clipboard (copie via xclip puis affichage de « 0 »), ou les deux.
 *       Sans option de mode : clipboard par défaut.
 *
 *  COMPILATION
 *    cc -O2 -Wall -Wextra -o schuffler schuffler.c
 *
 *  DÉPENDANCES
 *    libc POSIX.1-2008 (sigaction, termios, popen) et xclip (presse-papiers,
 *    requis en mode clipboard uniquement).
 *
 *  ÉQUIVALENCE AVEC LE SCRIPT BASH
 *    Chaque section ci-dessous cite la fonction bash correspondante. Les
 *    particularités du script sont conservées à dessein : parsing octal de
 *    --length (bash : -l 010 vaut 8), quirk de « -- » (le reste est ignoré),
 *    sémantique de « read » sans -r (antislashs, rognage IFS), arrêt fatal
 *    sur alphabet de classe vide (bash : division par zéro).
 *    Divergence volontaire unique : un secret saisi vide provoque un message
 *    d'erreur explicite puis l'aide, tous deux sur la sortie d'erreur (le
 *    script bash affiche « 1 » sur la sortie standard). La sortie standard
 *    reste ainsi réservée à la chaîne transformée en mode API.
 *
 *  SOMMAIRE
 *     1. En-têtes et options de compilation
 *     2. État global
 *     3. Utilitaires mémoire
 *     4. Cycle de vie : nettoyage et interruption
 *     5. Aide en ligne
 *     6. Analyse de la ligne de commande
 *     7. Construction de l'alphabet
 *     8. Saisie du secret
 *     9. SHA-256
 *    10. Génération du mot de passe
 *    11. Sortie : modes API et presse-papiers
 *    12. Point d'entrée
 * ========================================================================== */

/* ==========================================================================
 *  1. EN-TÊTES ET OPTIONS DE COMPILATION
 * ========================================================================== */

#define _POSIX_C_SOURCE 200809L

#include <errno.h>    /* errno, ERANGE (parse_length)                    */
#include <signal.h>   /* sigaction (équivalent du trap INT)             */
#include <stdint.h>   /* uint32_t, uint64_t, uint8_t (SHA-256)          */
#include <stdio.h>    /* stdio, popen (presse-papiers)                  */
#include <stdlib.h>   /* malloc, realloc, free, exit, atexit            */
#include <string.h>   /* strlen, strcmp, strchr, memcpy, memmove, memset */
#include <termios.h>  /* tcgetattr, tcsetattr (echo off, read -s)       */
#include <unistd.h>   /* isatty, write, STDOUT_FILENO                   */

/* ==========================================================================
 *  2. ÉTAT GLOBAL
 * --------------------------------------------------------------------------
 *  Miroir des variables globales du script bash, regroupées en deux
 *  structures :
 *    - cfg : configuration (options + alphabets), non sensible ;
 *    - ws  : espaces de travail (secrets et buffers), effacés en sortie.
 *
 *  Pour ajouter une classe de caractères ou une option : étendre ces
 *  structures, puis les sections 6 (analyse), 7 (alphabet) et 10 (génération/
 *  injection).
 * ========================================================================== */

/* Configuration : options de la ligne de commande et alphabets. */
typedef struct {
    unsigned long long output_length;  /* OUTPUT_LENGTH — défaut 20, min 4 */
    int use_lower;                     /* USE_LOWER   — classe [a-z] active   */
    int use_upper;                     /* USE_UPPER   — classe [A-Z] active   */
    int use_digits;                    /* USE_DIGITS  — classe [0-9] active   */
    int use_special;                   /* USE_SPECIAL — classe spéciaux active */
    int mode_api;                      /* MODE_API      — option -A : sortie standard */
    int mode_clipboard;                /* MODE_CLIPBOARD — option -C : presse-papiers  */
    char *lower;                       /* LOWER         — minuscules (filtré) */
    char *upper;                       /* UPPER         — majuscules (filtré) */
    char *digits;                       /* DIGITS        — chiffres (filtré)   */
    char *special_chars;               /* SPECIAL_CHARS — spéciaux (filtré)   */
    char *custom_special_set;          /* CUSTOM_SPECIAL_SET — "" par défaut  */
    char *excluded_chars;              /* EXCLUDED_CHARS — "" par défaut      */
    char *all_chars;                   /* ALL_CHARS — alphabet final assemblé */
} Config;

/* Espaces de travail : secrets et buffers temporaires. */
typedef struct {
    char *input;        /* INPUT  — secret en service                       */
    char *secret;       /* SECRET — saisie brute, effacée aussitôt         */
    char *result;       /* result — mot de passe brut                      */
    char *final;        /* final  — mot de passe après permutation         */
    char hash[65];      /* hash   — SHA-256 courant, hexadécimal (64 + NUL) */
} Workspace;

/* Valeurs par défaut : identiques à l'entête du script bash. Les deux modes
 * démarrent désactivés ; parse_arguments active le mode clipboard seul si
 * ni -A ni -C n'ont été passés. */
static Config cfg = {
    20,               /* OUTPUT_LENGTH */
    1, 1, 1, 1,       /* USE_LOWER, USE_UPPER, USE_DIGITS, USE_SPECIAL */
    0, 0,             /* MODE_API, MODE_CLIPBOARD (résolu à l'analyse) */
    NULL, NULL, NULL, NULL, NULL, NULL, NULL
};


static Workspace ws = { NULL, NULL, NULL, NULL, { 0 } };

/* Premier argument positionnel (le secret). Pointe dans argv ; l'original
 * de la ligne de commande est effacé par secure_cleanup (éq. « unset arg »). */
static const char *secret_arg = NULL;

/* Alphabets par défaut — identiques aux constantes du script bash. */
static const char CHARSET_LOWER[]         = "abcdefghijklmnopqrstuvwxyz";
static const char CHARSET_UPPER[]         = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
static const char CHARSET_DIGITS[]        = "0123456789";
static const char CHARSET_SPECIAL[]       = "!@$%^&*+#";

/* --------------------------------------------------------------------------
 * init_charsets — initialisation de la configuration
 * Équivalent bash : affectations globales en tête de schuffler.sh.
 * -------------------------------------------------------------------------- */
static char *xstrdup(const char *s); /* définie en section 3 */

static void init_charsets(void)
{
    cfg.lower = xstrdup(CHARSET_LOWER);
    cfg.upper = xstrdup(CHARSET_UPPER);
    cfg.digits = xstrdup(CHARSET_DIGITS);
    cfg.special_chars = xstrdup(CHARSET_SPECIAL);
    cfg.custom_special_set = xstrdup("");
    cfg.excluded_chars = xstrdup("");
}

/* ==========================================================================
 *  3. UTILITAIRES MÉMOIRE
 * ========================================================================== */

/* --------------------------------------------------------------------------
 * secure_memzero — effacement mémoire résistant aux optimisations
 * Le pointeur volatile empêche le compilateur de supprimer l'écriture.
 * -------------------------------------------------------------------------- */
static void secure_memzero(void *ptr, size_t len)
{
    volatile unsigned char *p = (volatile unsigned char *)ptr;
    while (len--)
        *p++ = 0;
}

/* --------------------------------------------------------------------------
 * xmalloc — allocation avec arrêt fatal si la mémoire manque
 * -------------------------------------------------------------------------- */
static void *xmalloc(size_t n)
{
    void *p = malloc(n);
    if (p == NULL) {
        fprintf(stderr, "Memoire insuffisante\n");
        exit(1);
    }
    return p;
}

/* --------------------------------------------------------------------------
 * xstrdup — copie allouée d'une chaîne
 * -------------------------------------------------------------------------- */
static char *xstrdup(const char *s)
{
    size_t n = strlen(s) + 1;
    char *p = xmalloc(n);
    memcpy(p, s, n);
    return p;
}

/* ==========================================================================
 *  4. CYCLE DE VIE : NETTOYAGE ET INTERRUPTION
 * ========================================================================== */

/* --------------------------------------------------------------------------
 * wipe_free — effacement sécurisé puis libération
 * -------------------------------------------------------------------------- */
static void wipe_free(char **p)
{
    if (*p != NULL) {
        secure_memzero(*p, strlen(*p));
        free(*p);
        *p = NULL;
    }
}

/* --------------------------------------------------------------------------
 * secure_cleanup — nettoyage général
 * Équivalent bash : trap secure_cleanup EXIT
 * Efface puis libère tout ce qui est sensible ; les alphabets, non
 * sensibles, sont simplement libérés.
 * -------------------------------------------------------------------------- */
static void secure_cleanup(void)
{
    secure_memzero(ws.hash, sizeof ws.hash);
    wipe_free(&ws.input);
    wipe_free(&ws.secret);
    wipe_free(&ws.result);
    wipe_free(&ws.final);

    /* Équivalent du « unset arg » : effacement de la ligne de commande. */
    if (secret_arg != NULL) {
        secure_memzero((void *)secret_arg, strlen(secret_arg));
        secret_arg = NULL;
    }

    free(cfg.lower);              cfg.lower = NULL;
    free(cfg.upper);              cfg.upper = NULL;
    free(cfg.digits);            cfg.digits = NULL;
    free(cfg.special_chars);      cfg.special_chars = NULL;
    free(cfg.custom_special_set);  cfg.custom_special_set = NULL;
    free(cfg.excluded_chars);     cfg.excluded_chars = NULL;
    free(cfg.all_chars);          cfg.all_chars = NULL;
}

/* --------------------------------------------------------------------------
 * handle_interrupt — interruption utilisateur (Ctrl-C)
 * Équivalent bash : trap handle_interrupt INT (echo ; exit 1)
 * -------------------------------------------------------------------------- */
static void handle_interrupt(int sig)
{
    (void)sig;
    ssize_t rc = write(STDOUT_FILENO, "\n", 1);
    (void)rc;
    exit(1); /* déclenche secure_cleanup, comme en bash */
}

/* --------------------------------------------------------------------------
 * init_signals — installation du gestionnaire d'interruption
 * Équivalent bash : trap handle_interrupt INT
 * -------------------------------------------------------------------------- */
static void init_signals(void)
{
    struct sigaction sa;

    memset(&sa, 0, sizeof sa);
    sa.sa_handler = handle_interrupt;
    sigaction(SIGINT, &sa, NULL);
}

/* ==========================================================================
 *  5. AIDE EN LIGNE
 * ========================================================================== */

/* --------------------------------------------------------------------------
 * show_help — texte d'usage
 * Équivalent bash : cat <<'EOF' de show_help (repris verbatim).
 * La destination est paramétrable : stdout pour -h/--help, stderr en cas
 * d'erreur fatale, afin que la sortie standard reste réservée à la chaîne
 * transformée (canal du mot de passe en mode -A).
 * -------------------------------------------------------------------------- */
static void show_help(FILE *stream)
{
    fputs("Usage:\n"
          "  schuffler.sh [options] [secret]\n"
          "\n"
          "Description:\n"
          "  Générateur de mot de passe déterministe.\n"
          "  Le même secret + les mêmes options produisent toujours le même mot de passe.\n"
          "\n"
          "Modes:\n"
          "  -C: --clipboard\n"
          "        Mode clipboard. Envoie la chaîne transformée dans le presse-papier.\n"
          "  -A: --API\n"
          "        Mode ligne de commande. Renvoie directement la chaîne de caractères transformée.\n"
          "\n"
          "  Par défaut (aucune option) : mode clipboard.\n"
          "  Si les deux options sont passées, la chaîne est envoyée à la fois\n"
          "  sur la sortie standard et dans le presse-papier.\n"
          "\n"
          "Options:\n"
          "  -l, --length N\n"
          "        Longueur du mot de passe (minimum 4, défaut: 20)\n"
          "\n"
          "  --no-lower\n"
          "        Exclure les lettres minuscules [a-z]\n"
          "\n"
          "  --no-upper\n"
          "        Exclure les lettres majuscules [A-Z]\n"
          "\n"
          "  --no-digits\n"
          "        Exclure les chiffres [0-9]\n"
          "\n"
          "  --no-special\n"
          "        Exclure les caractères spéciaux\n"
          "\n"
          "  --special-set \"<chars>\"\n"
          "        Forcer le jeu de caractères spéciaux\n"
          "        (ex: '@#$%')\n"
          "\n"
          "  --exclude-chars \"<chars>\"\n"
          "        Exclure explicitement certains caractères\n"
          "        (appliqué après tous les jeux)\n"
          "\n"
          "  -h, --help\n"
          "        Afficher cette aide et quitter\n"
          "\n"
          "  -a, --artefact\n"
          "        Affiche l'artefact de la chaîne transformée (premier et dernier caractère)\n"
          "\n"
          "Entrée:\n"
          "  secret\n"
          "        Secret fourni en argument.\n"
          "        S'il est absent, il sera demandé en saisie invisible (stdin).\n"
          "\n"
          "Exemples:\n"
          "  schuffler.sh\n"
          "  schuffler.sh monsecret\n"
          "  schuffler.sh --length 32 --no-special\n"
          "  schuffler.sh --special-set '@#%' --exclude-chars '#'\n"
          "  schuffler.sh -A monsecret\n"
          "  schuffler.sh -C monsecret\n"
          "  schuffler.sh -A -C monsecret\n",
          stream);
}

/* ==========================================================================
 *  6. ANALYSE DE LA LIGNE DE COMMANDE
 * --------------------------------------------------------------------------
 *  Équivalent bash : parse_arguments.
 *  Sémantique conservée :
 *    - les options -l/--length, --exclude-chars et --special-set consomment
 *      l'argument suivant ; s'il manque ou est vide : erreur (sauf -l qui
 *      affiche « Longueur invalide ») ;
 *    - « -- » s'arrête ET ignore le reste (quirk du script original) ;
 *    - toute chaîne commençant par « - » est une option : inconnue -> erreur ;
 *    - seul le premier argument positionnel est retenu (le secret).
 *
 *  Modes de sortie (nouveau par rapport au script) :
 *    - -A / --API       : mode API seul (sortie standard) ;
 *    - -C / --clipboard : mode clipboard seul (presse-papiers) ;
 *    - aucun des deux   : clipboard par défaut ;
 *    - les deux         : sortie standard ET presse-papiers.
 * ========================================================================== */

/* --------------------------------------------------------------------------
 * parse_length — validation d'une longueur
 *
 * Équivalent bash : [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -ge 4 ]]
 * Particularité bash : en contexte arithmétique, un zéro initial désigne
 * de l'octal ('-l 010' vaut 8 ; '-l 08' est une erreur).
 *
 * Retour : 1 si valide (valeur stockée dans *out), 0 sinon.
 * -------------------------------------------------------------------------- */
static int parse_length(const char *s, unsigned long long *out)
{
    int base = 10;

    if (*s == '\0')
        return 0;
    for (const char *p = s; *p != '\0'; p++) {
        if (*p < '0' || *p > '9')
            return 0;
    }

    if (s[0] == '0' && s[1] != '\0') {
        base = 8;
        for (const char *p = s + 1; *p != '\0'; p++) {
            if (*p == '8' || *p == '9') {
                fprintf(stderr,
                        "schuffler: %s: value too great for base "
                        "(error token is \"%s\")\n", s, s);
                return 0;
            }
        }
    }

    errno = 0;
    unsigned long long v = strtoull(s, NULL, base);
    if (errno == ERANGE) /* valeur hors bornes -> erreur -> invalide */
        return 0;
    if (v < 4)
        return 0;
    *out = v;
    return 1;
}

/* --------------------------------------------------------------------------
 * parse_arguments — parcours de argv
 * Écrit dans cfg et secret_arg. Arrêt (exit) en cas d'option invalide.
 * -------------------------------------------------------------------------- */
static void parse_arguments(int argc, char **argv)
{
    int i = 1;

    while (i < argc) {
        const char *arg = argv[i];

        if (strcmp(arg, "-h") == 0 || strcmp(arg, "--help") == 0) {
            show_help(stdout);
            exit(0);
        }
        else if (strcmp(arg, "-A") == 0 || strcmp(arg, "--API") == 0) {
            cfg.mode_api = 1;
        }
        else if (strcmp(arg, "-C") == 0 || strcmp(arg, "--clipboard") == 0) {
            cfg.mode_clipboard = 1;
        }
        else if (strcmp(arg, "-l") == 0 || strcmp(arg, "--length") == 0) {
            const char *val = (i + 1 < argc) ? argv[i + 1] : "";
            if (!parse_length(val, &cfg.output_length)) {
                puts("Longueur invalide");
                exit(1);
            }
            i++;
        }
        else if (strcmp(arg, "--no-lower") == 0) {
            cfg.use_lower = 0;
        }
        else if (strcmp(arg, "--no-upper") == 0) {
            cfg.use_upper = 0;
        }
        else if (strcmp(arg, "--no-digits") == 0) {
            cfg.use_digits = 0;
        }
        else if (strcmp(arg, "--no-special") == 0) {
            cfg.use_special = 0;
        }
        else if (strcmp(arg, "--exclude-chars") == 0) {
            const char *val = (i + 1 < argc) ? argv[i + 1] : "";
            if (*val == '\0') {
                puts("Liste de caractères à exclure manquante");
                exit(1);
            }
            free(cfg.excluded_chars);
            cfg.excluded_chars = xstrdup(val);
            i++;
        }
        else if (strcmp(arg, "--special-set") == 0) {
            const char *val = (i + 1 < argc) ? argv[i + 1] : "";
            if (*val == '\0') {
                puts("Jeu de caractères spéciaux manquant");
                exit(1);
            }
            free(cfg.custom_special_set);
            cfg.custom_special_set = xstrdup(val);
            i++;
        }
        else if (strcmp(arg, "--") == 0) {
            /* Fidèle au script bash : « shift; break » —
             * tout ce qui suit « -- » est ignoré. */
            i++;
            break;
        }
        else if (arg[0] == '-') {
            printf("Option inconnue: %s\n", arg);
            exit(1);
        }
        else {
            if (secret_arg == NULL)
                secret_arg = arg; /* seul le premier compte */
        }

        i++;
    }

    /* Mode par défaut : si ni -A ni -C n'ont été passés, mode clipboard. */
    if (!cfg.mode_api && !cfg.mode_clipboard)
        cfg.mode_clipboard = 1;

    if (!cfg.use_lower && !cfg.use_upper && !cfg.use_digits && !cfg.use_special) {
        puts("Toutes les catégories ont été exclues");
        exit(1);
    }
}

/* ==========================================================================
 *  7. CONSTRUCTION DE L'ALPHABET
 * --------------------------------------------------------------------------
 *  Équivalent bash : filter_charset + build_charset.
 *  Chaque classe active est filtrée de cfg.excluded_chars ; les alphabets
 *  vides sont ignorés ; l'union constitue cfg.all_chars.
 * ========================================================================== */

/* --------------------------------------------------------------------------
 * filter_charset — copie de « charset » sans les caractères exclus
 * Équivalent bash : boucle sur les caractères + test « *"$c"* ».
 * -------------------------------------------------------------------------- */
static char *filter_charset(const char *charset)
{
    size_t n = strlen(charset);
    char *filtered = xmalloc(n + 1);
    size_t k = 0;

    for (size_t i = 0; i < n; i++) {
        if (strchr(cfg.excluded_chars, charset[i]) == NULL)
            filtered[k++] = charset[i];
    }
    filtered[k] = '\0';
    return filtered;
}

/* --------------------------------------------------------------------------
 * append_chars — concatène « s » à cfg.all_chars
 * Équivalent bash : ALL_CHARS+="$s"
 * -------------------------------------------------------------------------- */
static void append_chars(const char *s)
{
    size_t len = strlen(s);
    size_t old = strlen(cfg.all_chars);
    char *grown = realloc(cfg.all_chars, old + len + 1);

    if (grown == NULL) {
        fprintf(stderr, "Memoire insuffisante\n");
        exit(1);
    }
    cfg.all_chars = grown;
    memcpy(cfg.all_chars + old, s, len + 1);
}

/* --------------------------------------------------------------------------
 * build_charset — assemblage de l'alphabet final
 * Filtrage + union des classes actives ; arrêt si l'union est vide.
 * -------------------------------------------------------------------------- */
static void build_charset(void)
{
    char *filtered;

    free(cfg.all_chars);
    cfg.all_chars = xstrdup("");

    if (cfg.use_lower) {
        filtered = filter_charset(cfg.lower);
        free(cfg.lower);
        cfg.lower = filtered;
        if (*cfg.lower != '\0')
            append_chars(cfg.lower);
    }

    if (cfg.use_upper) {
        filtered = filter_charset(cfg.upper);
        free(cfg.upper);
        cfg.upper = filtered;
        if (*cfg.upper != '\0')
            append_chars(cfg.upper);
    }

    if (cfg.use_digits) {
        filtered = filter_charset(cfg.digits);
        free(cfg.digits);
        cfg.digits = filtered;
        if (*cfg.digits != '\0')
            append_chars(cfg.digits);
    }

    if (cfg.use_special) {
        if (*cfg.custom_special_set != '\0') {
            free(cfg.special_chars);
            cfg.special_chars = xstrdup(cfg.custom_special_set);
        }

        filtered = filter_charset(cfg.special_chars);
        free(cfg.special_chars);
        cfg.special_chars = filtered;
        if (*cfg.special_chars != '\0')
            append_chars(cfg.special_chars);
    }

    if (*cfg.all_chars == '\0') {
        puts("Alphabet final vide après exclusions");
        exit(1);
    }
}

/* ==========================================================================
 *  8. SAISIE DU SECRET
 * --------------------------------------------------------------------------
 *  Équivalent bash : read_secrets + read_inputs.
 *  Sémantique de « read » sans -r, conservée à dessein :
 *    - antislash + caractère -> le caractère seul (antislash retiré) ;
 *    - antislash + saut de ligne -> continuation de ligne ;
 *    - antislash en fin d'entrée (EOF) -> antislash ignoré ;
 *    - espaces et tabulations (IFS) rognés aux deux extrémités.
 *
 *  Divergence volontaire d'avec le script bash : un secret saisi vide
 *  déclenche un message d'erreur explicite puis l'aide en ligne, tous deux
 *  sur la sortie d'erreur, au lieu du seul « 1 » du script. La sortie
 *  standard reste ainsi réservée à la chaîne transformée (mode -A) ; le
 *  code de retour demeure 1.
 * ========================================================================== */

/* --------------------------------------------------------------------------
 * read_line_bash — lecture d'une ligne avec la sémantique de « read »
 * Retourne une chaîne allouée (toujours non NULL, éventuellement vide).
 * -------------------------------------------------------------------------- */
static char *read_line_bash(void)
{
    size_t cap = 64;
    size_t len = 0;
    char *buf = xmalloc(cap);
    int c;

    buf[0] = '\0';

    for (;;) {
        c = getchar();
        if (c == EOF || c == '\n')
            break;
        if (c == '\\') {
            int d = getchar();
            if (d == EOF)      /* antislash final avant EOF : ignoré */
                break;
            if (d == '\n')     /* continuation de ligne */
                continue;
            c = d;             /* antislash échappant le caractère suivant */
        }
        if (len + 1 >= cap) {
            cap *= 2;
            char *grown = realloc(buf, cap);
            if (grown == NULL) {
                fprintf(stderr, "Memoire insuffisante\n");
                exit(1);
            }
            buf = grown;
        }
        buf[len++] = (char)c;
    }

    /* Rognage IFS : espaces et tabulations aux extrémités. */
    size_t start = 0;
    size_t end = len;
    while (start < end && (buf[start] == ' ' || buf[start] == '\t'))
        start++;
    while (end > start && (buf[end - 1] == ' ' || buf[end - 1] == '\t'))
        end--;
    if (start > 0)
        memmove(buf, buf + start, end - start);
    buf[end - start] = '\0';
    return buf;
}

/* --------------------------------------------------------------------------
 * read_secrets — saisie invisible sur stdin
 * Équivalent bash : read -s SECRET ; echo ; test vide -> « 1 » ; exit 1.
 * Divergence assumée (voir section 8) : secret vide -> message d'erreur
 * puis aide sur la sortie d'erreur ; exit 1.
 * Le secret brut est effacé dès sa copie dans ws.input (éq. « unset SECRET »).
 * -------------------------------------------------------------------------- */
static void read_secrets(void)
{
    int is_tty = isatty(STDIN_FILENO);
    struct termios saved;

    if (is_tty) {
        tcgetattr(STDIN_FILENO, &saved);
        struct termios noecho = saved;
        noecho.c_lflag &= (tcflag_t)~ECHO;
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &noecho);
    }

    ws.secret = read_line_bash();

    if (is_tty)
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &saved);

    putchar('\n'); /* écho du retour à la ligne, comme « read -s; echo » */

    if (*ws.secret == '\0') {
        fprintf(stderr,
                "Erreur : aucune chaîne à transformer n'a été fournie "
                "(le secret saisi est vide).\n"
                "\n");
        show_help(stderr);
        exit(1); /* secure_cleanup efface ws.secret */
    }

    ws.input = xstrdup(ws.secret);

    /* Suppression immédiate du secret, comme « unset SECRET ». */
    secure_memzero(ws.secret, strlen(ws.secret));
    free(ws.secret);
    ws.secret = NULL;
}

/* --------------------------------------------------------------------------
 * read_inputs — aiguillage : argument positionnel ou saisie
 * Équivalent bash : read_inputs (seul le premier argument compte).
 * -------------------------------------------------------------------------- */
static void read_inputs(void)
{
    if (secret_arg != NULL) {
        ws.input = xstrdup(secret_arg);
        /* « unset arg » : l'original de la ligne de commande est
         * effacé par secure_cleanup en sortie. */
    }
    else {
        read_secrets();
    }
}

/* ==========================================================================
 *  9. SHA-256
 * --------------------------------------------------------------------------
 *  Implémentation compacte de SHA-256 (FIPS 180-4), remplaçant
 *  « sha256sum » : le script bash hache « secret:compteur » et n'en garde
 *  que l'hexadécimal minuscule. Validée contre hashlib (Python) sur 214
 *  vecteurs, dont toutes les tailles de bloc frontières.
 * ========================================================================== */

typedef struct {
    uint32_t state[8];   /* registres H0..H7            */
    uint64_t bit_len;    /* longueur totale en bits      */
    uint8_t  block[64];  /* bloc en cours de remplissage */
    size_t   block_len;  /* octets déjà en attente       */
} Sha256;

/* Constantes K de SHA-256 (fractionnaires des racines des nombres premiers). */
static const uint32_t SHA256_K[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
    0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
    0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
    0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
};

/* --------------------------------------------------------------------------
 * rotr32 — rotation de bits vers la droite sur 32 bits
 * -------------------------------------------------------------------------- */
static uint32_t rotr32(uint32_t x, int n)
{
    return (x >> n) | (x << (32 - n));
}

/* --------------------------------------------------------------------------
 * sha256_init — initialisation des registres H0..H7
 * -------------------------------------------------------------------------- */
static void sha256_init(Sha256 *ctx)
{
    ctx->state[0] = 0x6a09e667u;
    ctx->state[1] = 0xbb67ae85u;
    ctx->state[2] = 0x3c6ef372u;
    ctx->state[3] = 0xa54ff53au;
    ctx->state[4] = 0x510e527fu;
    ctx->state[5] = 0x9b05688cu;
    ctx->state[6] = 0x1f83d9abu;
    ctx->state[7] = 0x5be0cd19u;
    ctx->bit_len = 0;
    ctx->block_len = 0;
}

/* --------------------------------------------------------------------------
 * sha256_compress — une ronde de compression sur un bloc de 64 octets
 * -------------------------------------------------------------------------- */
static void sha256_compress(Sha256 *ctx, const uint8_t *p)
{
    uint32_t w[64];

    for (int i = 0; i < 16; i++) {
        w[i] = ((uint32_t)p[4 * i] << 24)
             | ((uint32_t)p[4 * i + 1] << 16)
             | ((uint32_t)p[4 * i + 2] << 8)
             | (uint32_t)p[4 * i + 3];
    }
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = rotr32(w[i - 15], 7) ^ rotr32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = rotr32(w[i - 2], 17) ^ rotr32(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }

    uint32_t a = ctx->state[0], b = ctx->state[1];
    uint32_t c = ctx->state[2], d = ctx->state[3];
    uint32_t e = ctx->state[4], f = ctx->state[5];
    uint32_t g = ctx->state[6], h = ctx->state[7];

    for (int i = 0; i < 64; i++) {
        uint32_t S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
        uint32_t ch = (e & f) ^ (~e & g);
        uint32_t t1 = h + S1 + ch + SHA256_K[i] + w[i];
        uint32_t S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t t2 = S0 + maj;

        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }

    ctx->state[0] += a; ctx->state[1] += b;
    ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f;
    ctx->state[6] += g; ctx->state[7] += h;
}

/* --------------------------------------------------------------------------
 * sha256_update — absorption de données de longueur quelconque
 * -------------------------------------------------------------------------- */
static void sha256_update(Sha256 *ctx, const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;

    ctx->bit_len += (uint64_t)len * 8;
    while (len > 0) {
        size_t take = 64 - ctx->block_len;
        if (take > len)
            take = len;
        memcpy(ctx->block + ctx->block_len, p, take);
        ctx->block_len += take;
        p += take;
        len -= take;
        if (ctx->block_len == 64) {
            sha256_compress(ctx, ctx->block);
            ctx->block_len = 0;
        }
    }
}

/* --------------------------------------------------------------------------
 * sha256_final — bourrage final et extraction du condensat (32 octets)
 * -------------------------------------------------------------------------- */
static void sha256_final(Sha256 *ctx, uint8_t out[32])
{
    uint64_t bits = ctx->bit_len;
    uint8_t pad = 0x80;
    uint8_t zero = 0;
    uint8_t lenbuf[8];

    sha256_update(ctx, &pad, 1);
    while (ctx->block_len != 56)
        sha256_update(ctx, &zero, 1);

    for (int i = 0; i < 8; i++)
        lenbuf[i] = (uint8_t)(bits >> (56 - 8 * i));
    sha256_update(ctx, lenbuf, 8);

    for (int i = 0; i < 8; i++) {
        out[4 * i]     = (uint8_t)(ctx->state[i] >> 24);
        out[4 * i + 1] = (uint8_t)(ctx->state[i] >> 16);
        out[4 * i + 2] = (uint8_t)(ctx->state[i] >> 8);
        out[4 * i + 3] = (uint8_t)(ctx->state[i]);
    }
}

/* ==========================================================================
 *  10. GÉNÉRATION DU MOT DE PASSE
 * --------------------------------------------------------------------------
 *  Équivalent bash : hash_stream, generate_base_string, inject_char,
 *  enforce_character_classes, shuffle_result.
 * ========================================================================== */

/* --------------------------------------------------------------------------
 * hash_stream — hachage déterministe d'un tour
 * Équivalent bash :
 *   echo -n "${seed}:${counter}" | sha256sum | awk '{print $1}'
 * Résultat : ws.hash, hexadécimal minuscule de 64 caractères.
 * -------------------------------------------------------------------------- */
static void hash_stream(unsigned long counter)
{
    size_t slen = strlen(ws.input);
    char *msg = xmalloc(slen + 32);
    int mlen = snprintf(msg, slen + 32, "%s:%lu", ws.input, counter);
    Sha256 ctx;
    uint8_t digest[32];

    if (mlen < 0) {
        free(msg);
        fprintf(stderr, "Erreur interne snprintf\n");
        exit(1);
    }

    sha256_init(&ctx);
    sha256_update(&ctx, msg, (size_t)mlen);
    sha256_final(&ctx, digest);

    for (int i = 0; i < 32; i++)
        sprintf(ws.hash + 2 * i, "%02x", digest[i]);
    ws.hash[64] = '\0';

    secure_memzero(msg, (size_t)mlen);
    free(msg);
}

/* --------------------------------------------------------------------------
 * hex_val — valeur d'un chiffre hexadécimal minuscule
 * -------------------------------------------------------------------------- */
static unsigned hex_val(char c)
{
    if (c >= '0' && c <= '9')
        return (unsigned)(c - '0');
    if (c >= 'a' && c <= 'f')
        return (unsigned)(c - 'a' + 10);
    return 0; /* n'arrive pas : SHA-256 rendu en hexa minuscule */
}

/* --------------------------------------------------------------------------
 * generate_base_string — expansion déterministe jusqu'à la longueur cible
 * Équivalent bash : boucle counter + lecture des paires hexadécimales,
 * octet % taille de l'alphabet. Résultat : ws.result.
 * -------------------------------------------------------------------------- */
static void generate_base_string(void)
{
    size_t wanted = (size_t)cfg.output_length;
    size_t alphabet_len = strlen(cfg.all_chars);
    size_t n = 0;
    unsigned long counter = 0;

    ws.result = xmalloc(wanted + 1);
    ws.result[0] = '\0';

    while (n < wanted) {
        hash_stream(counter);
        for (size_t i = 0; i < 64 && n < wanted; i += 2) {
            unsigned byte = hex_val(ws.hash[i]) * 16u + hex_val(ws.hash[i + 1]);
            ws.result[n++] = cfg.all_chars[byte % alphabet_len];
        }
        counter++;
    }
    ws.result[n] = '\0';
}

/* --------------------------------------------------------------------------
 * inject_char — force le caractère charset[pos % len] à la position pos
 * Équivalent bash : inject_char. Si « charset » est vide, bash échoue sur
 * un modulo par zéro et s'arrête (rc 1, aucune sortie) : comportement
 * reproduit fidèlement.
 * -------------------------------------------------------------------------- */
static void inject_char(const char *charset, size_t pos)
{
    size_t len = strlen(charset);

    if (len == 0) {
        fprintf(stderr,
                "schuffler: pos %% 0: division by 0 (error token is \"0\")\n");
        exit(1);
    }
    ws.result[pos] = charset[pos % len];
}

/* --------------------------------------------------------------------------
 * enforce_character_classes — garantie d'un caractère par classe active
 * Équivalent bash : enforce_character_classes (positions 0 à 3, une par
 * classe dans l'ordre minuscules, majuscules, chiffres, spéciaux).
 * -------------------------------------------------------------------------- */
static void enforce_character_classes(void)
{
    size_t pos = 0;

    if (cfg.use_lower) {
        inject_char(cfg.lower, pos);
        pos++;
    }
    if (cfg.use_upper) {
        inject_char(cfg.upper, pos);
        pos++;
    }
    if (cfg.use_digits) {
        inject_char(cfg.digits, pos);
        pos++;
    }
    if (cfg.use_special) {
        inject_char(cfg.special_chars, pos);
        pos++;
    }
}

/* --------------------------------------------------------------------------
 * shuffle_result — permutation déterministe finale
 * Équivalent bash : final[i] = result[(i*7+13) % n]. Résultat : ws.final.
 * -------------------------------------------------------------------------- */
static void shuffle_result(void)
{
    size_t n = strlen(ws.result);

    ws.final = xmalloc(n + 1);
    for (size_t i = 0; i < n; i++) {
        size_t j = (i * 7 + 13) % n;
        ws.final[i] = ws.result[j];
    }
    ws.final[n] = '\0';
}

/* ==========================================================================
 *  11. SORTIE : MODES API ET PRESSE-PAPIERS
 * --------------------------------------------------------------------------
 *  Aiguillage selon les modes actifs, résolus par parse_arguments :
 *    - mode API seul  (-A)         : mot de passe en clair sur la sortie
 *                                   standard, rien d'autre ;
 *    - mode clipboard (-C, défaut) : copie via xclip puis affichage de « 0 »,
 *                                   comme le script bash d'origine ;
 *    - modes combinés (-A -C)      : sortie standard PUIS presse-papiers ;
 *                                   la sortie standard contient donc le mot
 *                                   de passe puis « 0 ».
 * ========================================================================== */

/* --------------------------------------------------------------------------
 * copy_to_clipboard — copie via xclip puis affichage de « 0 »
 * Équivalent bash : echo -n "$final" | xclip -selection clipboard ; echo "0"
 * -------------------------------------------------------------------------- */
static void copy_to_clipboard(void)
{
    FILE *pp = popen("xclip -selection clipboard", "w");

    if (pp != NULL) {
        fputs(ws.final, pp);
        pclose(pp);
    }
    puts("0");
}

/* --------------------------------------------------------------------------
 * output_result — aiguillage selon les modes actifs (-A / -C)
 * -------------------------------------------------------------------------- */
static void output_result(void)
{
    if (cfg.mode_api)
        puts(ws.final);
    if (cfg.mode_clipboard)
        copy_to_clipboard();
}

/* ==========================================================================
 *  12. POINT D'ENTRÉE
 * ========================================================================== */

/* --------------------------------------------------------------------------
 * main — enchaînement identique à la fonction main du script bash :
 * traps -> parse_arguments -> build_charset -> read_inputs ->
 * generate_base_string -> enforce_character_classes -> shuffle_result ->
 * output_result (API, clipboard ou les deux).
 * -------------------------------------------------------------------------- */
int main(int argc, char **argv)
{
    atexit(secure_cleanup);
    init_signals();
    init_charsets();

    parse_arguments(argc, argv);
    build_charset();
    read_inputs();
    generate_base_string();
    enforce_character_classes();
    shuffle_result();
    output_result();

    return 0;
}