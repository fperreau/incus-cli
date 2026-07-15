# Prompt — Développement TDD d’une collection Ansible `incus_cli`

## Rôle

Tu es un développeur senior Python, Ansible et DevOps, spécialisé dans la conception de collections Ansible, les modules idempotents, les action plugins, Jinja2, Molecule, `ansible-test`, `pytest` et les interfaces CLI sécurisées.

Tu dois concevoir, coder, documenter et tester une collection Ansible fournissant un module générique `incus_cli`. Le développement doit suivre une démarche **Test Driven Development** : écrire ou présenter les tests avant l’implémentation correspondante, exécuter les tests, puis compléter le code jusqu’à leur réussite.

Ne te limite pas à des extraits illustratifs. Produis une arborescence de projet complète et des fichiers directement exploitables. Lorsque l’environnement ne permet pas d’exécuter un test, indique précisément la commande à lancer, le résultat attendu et la raison de la limitation, sans prétendre que le test a réussi.

---

## Objectif fonctionnel

Créer une collection Ansible nommée par défaut :

```text
namespace : my_namespace
collection: incus
FQCN      : my_namespace.incus.incus_cli
```

Prévoir une méthode simple pour modifier le namespace et le nom de collection.

Le composant doit prendre en charge quatre modes d’utilisation mutuellement exclusifs :

1. mode rapide `command` ;
2. mode robuste `incus`, basé sur des tableaux `argv` auxquels le binaire `incus` est automatiquement préfixé ;
3. mode `template`, à partir d’un fichier YAML/Jinja2 et d’un dictionnaire de variables ;
4. mode `shell`, explicitement non sécurisé et réservé aux fonctionnalités du shell.

Corriger partout la faute de frappe `inclus_cli` en `incus_cli`.

---

# Interfaces attendues

## 1. Mode rapide `command`

Exemple utilisateur :

```yaml
- name: Démarrer une instance avec le mode rapide
  my_namespace.incus.incus_cli:
    command: "incus start {{ name }}"
  vars:
    name: web01
```

### Comportement attendu

- `command` accepte une chaîne ou, si cela reste clair et testable, une chaîne multiligne contenant plusieurs commandes simples ;
- les variables Ansible sont résolues avant l’appel du module ;
- une commande simple est analysée avec une méthode équivalente à `shlex.split` ;
- l’exécution se fait sans shell ;
- refuser dans ce mode les opérateurs nécessitant un shell, notamment `|`, `>`, `>>`, `<`, `&&`, `||`, `;`, les substitutions de commande et les expansions shell ;
- inviter l’utilisateur à employer le mode `shell` lorsqu’un opérateur shell est détecté ;
- aucun préfixe `incus` automatique n’est ajouté dans ce mode : la commande fournie doit être complète.

---

## 2. Mode robuste `incus`

Exemple utilisateur :

```yaml
- name: Démarrer puis arrêter une instance
  my_namespace.incus.incus_cli:
    incus:
      - argv:
          - start
          - "{{ name }}"
      - argv:
          - stop
          - "{{ name }}"
  vars:
    name: web01
```

### Normalisation obligatoire

Pour chaque élément, le module ajoute automatiquement `incus` en position zéro :

```text
entrée : ["start", "web01"]
sortie : ["incus", "start", "web01"]
```

Ne pas ajouter une seconde fois le binaire si l’utilisateur fournit accidentellement `incus` en première position. Choisir l’une des deux stratégies suivantes, la documenter et la tester :

- normaliser silencieusement en supprimant le doublon ; ou
- refuser l’entrée avec un message explicite.

La stratégie recommandée est de normaliser sans doublon, tout en ajoutant un avertissement dans le résultat.

### Structure d’une étape

Chaque entrée de `incus` doit accepter au minimum :

```yaml
- name: Nom facultatif de l’étape
  argv:
    - start
    - prod:web01
    - --project
    - production
  environment: {}
  changed: true
  creates: null
  removes: null
  sensitive_values: []
```

Prévoir une conception extensible permettant ensuite d’ajouter une vérification déclarative :

```yaml
- name: Démarrer seulement si nécessaire
  check:
    argv:
      - list
      - prod:web01
      - --format
      - json
    json_path: "[0].status"
    equals: Running
  apply:
    argv:
      - start
      - prod:web01
```

La première version peut implémenter `check/apply` ou réserver proprement cette évolution. Si elle n’est pas implémentée, ne pas accepter silencieusement ces clés : retourner une erreur de validation claire.

---

## 3. Mode `template`

Exemple utilisateur :

```yaml
- name: Exécuter un scénario Incus depuis un modèle
  my_namespace.incus.incus_cli:
    template: templates/instance.yml.j2
    variables:
      name: web01
      state: started
      remote: prod
      project: production
```

Le template doit produire un document YAML structuré utilisant le même format interne que le mode `incus` :

```yaml
incus:
  - argv:
      - "{{ 'start' if state == 'started' else 'stop' }}"
      - "{{ remote }}:{{ name }}"
      - --project
      - "{{ project }}"
```

### Architecture obligatoire

Utiliser un **action plugin** pour le mode `template` :

1. le fichier Jinja2 est recherché et lu sur le contrôleur Ansible ;
2. les variables de `variables`, complétées par le contexte Ansible autorisé, sont rendues sur le contrôleur ;
3. le résultat YAML est parsé avec un chargeur sûr ;
4. la structure obtenue est validée ;
5. elle est transmise au module sous la forme normalisée `incus` ;
6. le module exécuté sur la cible ne doit pas ouvrir directement un template situé sur le contrôleur.

Définir une règle de précédence explicite pour les variables. Recommandation : les clés du dictionnaire `variables` écrasent les variables homonymes du contexte disponible pour le template.

Le rendu doit échouer sur une variable indéfinie, avec un message donnant le nom du template et la variable concernée.

---

## 4. Mode `shell`

Exemple utilisateur :

```yaml
- name: Exporter la liste des instances
  my_namespace.incus.incus_cli:
    shell: "incus list host: --format json > list.json"
    unsafe_shell: true
```

### Comportement attendu

- `shell` utilise explicitement un shell ;
- `unsafe_shell: true` est obligatoire, sinon le module échoue avec un message clair ;
- documenter le risque d’injection et recommander `incus/argv` par défaut ;
- permettre de définir le shell exécutable, avec une valeur par défaut raisonnable telle que `/bin/sh` ;
- prendre en charge `chdir`, `environment`, `creates` et `removes` ;
- masquer les valeurs sensibles dans les journaux et le résultat ;
- ne jamais construire implicitement une commande shell depuis le mode robuste.

---

# Schéma commun du module

Définir un `argument_spec` proche de celui-ci, en l’améliorant si nécessaire :

```python
argument_spec = {
    "command": {"type": "str"},
    "incus": {
        "type": "list",
        "elements": "dict",
        "options": {
            "name": {"type": "str"},
            "argv": {
                "type": "list",
                "elements": "str",
            },
            "environment": {"type": "dict", "default": {}},
            "changed": {"type": "bool", "default": True},
            "creates": {"type": "path"},
            "removes": {"type": "path"},
            "sensitive_values": {
                "type": "list",
                "elements": "str",
                "default": [],
                "no_log": True,
            },
        },
    },
    "template": {"type": "path"},
    "variables": {"type": "dict", "default": {}, "no_log": False},
    "shell": {"type": "str"},
    "unsafe_shell": {"type": "bool", "default": False},
    "executable": {"type": "path", "default": "/bin/sh"},
    "chdir": {"type": "path"},
    "environment": {"type": "dict", "default": {}},
    "creates": {"type": "path"},
    "removes": {"type": "path"},
    "stop_on_error": {"type": "bool", "default": True},
}
```

Appliquer les contraintes suivantes :

```python
mutually_exclusive = [
    ["command", "incus", "template", "shell"],
]

required_one_of = [
    ["command", "incus", "template", "shell"],
]

required_if = [
    ["unsafe_shell", True, ["shell"]],
]
```

Compléter ces règles par une validation métier, notamment :

- `variables` n’est valide qu’avec `template` ;
- `unsafe_shell` et `executable` n’ont de sens qu’avec `shell` ;
- chaque étape `incus` possède `argv` ou une structure `check/apply` prise en charge ;
- `argv` ne doit pas être vide ;
- tous les éléments d’`argv` doivent être des chaînes après transformation Ansible ;
- les arguments contenant des espaces restent un seul élément ;
- `stop_on_error: false` poursuit l’exécution et agrège les erreurs ;
- `stop_on_error: true` s’arrête à la première erreur.

---

# Sécurité et exécution

## Exécution sans shell

Dans les modes `command` et `incus`, utiliser une liste d’arguments et une API telle que :

```python
rc, stdout, stderr = module.run_command(argv, environ_update=environment)
```

Ne jamais utiliser `shell=True` ou `use_unsafe_shell=True` pour ces modes.

## Exécution shell

Le mode `shell` est le seul à pouvoir utiliser :

```python
module.run_command(
    shell_command,
    use_unsafe_shell=True,
    executable=executable,
    environ_update=environment,
)
```

Adapter l’appel à l’API Ansible réellement disponible et couvrir ce comportement par des tests unitaires avec mocks.

## Secrets

- prendre en charge `no_log` pour les données sensibles ;
- masquer les valeurs présentes dans `sensitive_values` dans `argv`, `stdout`, `stderr`, les erreurs et le résultat retourné ;
- ne jamais afficher intégralement un token, un mot de passe ou une clé privée ;
- tester le masquage des secrets.

---

# Idempotence et `check_mode`

Un wrapper CLI générique ne peut pas déduire automatiquement tous les changements. Implémenter les règles suivantes :

1. une étape de consultation peut déclarer `changed: false` ;
2. une étape d’action utilise `changed: true` par défaut ;
3. `creates` empêche l’exécution si le chemin existe ;
4. `removes` empêche l’exécution si le chemin n’existe pas ;
5. en `check_mode`, ne pas exécuter les commandes ayant un potentiel de modification ;
6. en `check_mode`, retourner la commande normalisée et le changement prévisionnel ;
7. si une étape est explicitement `changed: false`, autoriser son exécution en `check_mode` seulement si elle est considérée comme une consultation sûre, ou documenter une politique plus conservatrice ;
8. retourner une justification dans `skip_reason` lorsqu’une commande est ignorée.

Si `check/apply` est implémenté, la vérification doit être exécutable en `check_mode`, tandis que `apply` ne l’est pas.

---

# Résultat du module

Retourner une structure stable et documentée :

```yaml
changed: true
failed: false
mode: incus
results:
  - index: 0
    name: Démarrer web01
    argv:
      - incus
      - start
      - web01
    rc: 0
    stdout: ""
    stderr: ""
    changed: true
    skipped: false
    duration_ms: 120
warnings: []
```

En cas de plusieurs erreurs avec `stop_on_error: false`, retourner tous les résultats et terminer la tâche en échec après l’exécution complète.

---

# Arborescence attendue

Créer au minimum :

```text
ansible_collections/my_namespace/incus/
├── galaxy.yml
├── README.md
├── CHANGELOG.md
├── meta/
│   └── runtime.yml
├── plugins/
│   ├── action/
│   │   └── incus_cli.py
│   ├── module_utils/
│   │   └── incus_cli.py
│   └── modules/
│       └── incus_cli.py
├── tests/
│   ├── unit/
│   │   ├── plugins/
│   │   │   ├── action/
│   │   │   │   └── test_incus_cli.py
│   │   │   ├── module_utils/
│   │   │   │   └── test_incus_cli.py
│   │   │   └── modules/
│   │   │       └── test_incus_cli.py
│   └── integration/
│       └── targets/
│           └── incus_cli/
│               ├── aliases
│               └── tasks/
│                   └── main.yml
└── extensions/
    └── molecule/
        └── default/
            ├── molecule.yml
            ├── create.yml
            ├── prepare.yml
            ├── converge.yml
            ├── verify.yml
            └── destroy.yml
```

Si les conventions de la version retenue de Molecule recommandent un emplacement différent, utiliser la convention actuelle, expliquer le choix et conserver une arborescence cohérente.

---

# Stratégie TDD obligatoire

Procéder par incréments. Pour chaque incrément :

1. écrire le test en échec ;
2. présenter ou exécuter le test et constater l’échec attendu ;
3. écrire le minimum de code nécessaire ;
4. exécuter le test jusqu’à sa réussite ;
5. refactoriser sans casser les tests ;
6. mettre à jour la documentation si l’interface change.

## Incrément 1 — Normalisation `argv`

Tests à écrire en premier :

- ajoute `incus` en `argv[0]` ;
- ne double pas un préfixe `incus` existant ;
- refuse une liste vide ;
- conserve un argument contenant des espaces comme un seul argument ;
- conserve `[remote:]ressource` sans transformation.

## Incrément 2 — Mode robuste

Tests :

- exécute plusieurs étapes dans l’ordre ;
- agrège les résultats ;
- s’arrête à la première erreur lorsque `stop_on_error` vaut `true` ;
- poursuit lorsque `stop_on_error` vaut `false` ;
- fusionne l’environnement global et l’environnement de l’étape, celui de l’étape étant prioritaire.

## Incrément 3 — Mode rapide

Tests :

- analyse correctement une commande simple ;
- respecte les guillemets ;
- refuse les opérateurs shell ;
- ne préfixe pas automatiquement `incus` ;
- retourne un message recommandant le mode `shell` en cas de redirection ou de tube.

## Incrément 4 — Action plugin et templates

Tests :

- localise le template sur le contrôleur ;
- applique les variables ;
- échoue sur une variable indéfinie ;
- parse le YAML rendu en mode sûr ;
- refuse une racine non conforme ;
- transmet au module une structure `incus` normalisée ;
- interdit les clés YAML inattendues ;
- teste la précédence des variables.

## Incrément 5 — Mode shell

Tests :

- refuse `shell` sans `unsafe_shell: true` ;
- utilise le shell uniquement dans ce mode ;
- respecte `executable` et `chdir` ;
- gère une redirection ;
- masque les secrets dans les résultats.

## Incrément 6 — Idempotence et check mode

Tests :

- `changed: false` retourne `changed: false` ;
- `creates` et `removes` sautent correctement l’étape ;
- `check_mode` ne lance pas une commande modificatrice ;
- `check_mode` renvoie les commandes qui auraient été exécutées ;
- le résultat global `changed` correspond au OU logique des étapes modifiées.

## Incrément 7 — Molecule

Créer un scénario Molecule couvrant les quatre modes. Les tests ne doivent pas dépendre d’un véritable serveur Incus externe.

Préparer sur l’hôte de test un faux exécutable `incus` contrôlable, placé en tête du `PATH`. Ce faux binaire doit :

- enregistrer tous les arguments reçus sous forme JSON Lines ;
- simuler des sorties et codes retour selon les arguments ;
- permettre de vérifier que `incus` est bien ajouté en `argv[0]` au niveau du processus ;
- simuler succès, échec, start, stop et list ;
- ne jamais nécessiter de privilèges Incus réels.

Le scénario Molecule doit tester :

- `command` avec une commande simple ;
- `incus` avec `start` puis `stop` ;
- `template` avec `state: started` ;
- `shell` avec redirection dans un fichier temporaire ;
- le refus de `shell` sans consentement explicite ;
- `stop_on_error` dans les deux modes ;
- `check_mode` ;
- une seconde convergence démontrant le comportement idempotent des cas qui le permettent ;
- la conformité des arguments enregistrés par le faux binaire.

Utiliser `ansible.builtin.assert` dans `verify.yml` et compléter, lorsque pertinent, avec Testinfra ou `pytest` sans rendre les tests inutilement dépendants d’outils externes.

---

# Qualité et outillage

Fournir les fichiers de configuration nécessaires et des commandes reproductibles pour :

```bash
ansible-test sanity --docker
ansible-test units --docker
ansible-test integration incus_cli --docker
molecule test
```

Ajouter selon les besoins :

- `pytest` ;
- `pytest-cov` ;
- `ruff` ;
- `black` ;
- `yamllint` ;
- `ansible-lint`.

Ne pas appliquer un outil sans fournir sa configuration minimale. Éviter les dépendances non indispensables.

Respecter :

- les conventions de documentation des modules Ansible (`DOCUMENTATION`, `EXAMPLES`, `RETURN`) ;
- les FQCN dans les playbooks ;
- la compatibilité Python explicitement annoncée ;
- la compatibilité `ansible-core` explicitement annoncée ;
- les erreurs explicites et actionnables ;
- les fonctions courtes et testables ;
- la séparation entre rendu, validation, normalisation et exécution.

---

# Documentation attendue

Le `README.md` doit contenir :

1. les prérequis ;
2. l’installation de la collection ;
3. la description des quatre modes ;
4. un exemple complet pour chaque mode ;
5. les risques du mode shell ;
6. le comportement de `check_mode` ;
7. les règles d’idempotence ;
8. le format des résultats ;
9. la procédure de tests unitaires, intégration et Molecule ;
10. les limites connues.

Documenter clairement que :

- `[remote:]` reste une partie d’un argument Incus et n’est pas analysé ni repositionné par le module ;
- `--project`, `--profile` et les autres options restent des éléments séparés dans `argv` ;
- le module n’essaie pas de reproduire toute la grammaire CLI d’Incus ;
- le mode robuste garantit seulement une construction sûre du processus et l’ajout du binaire `incus` ;
- le mode shell est volontairement séparé.

---

# Critères d’acceptation

Le travail est accepté si :

- les quatre modes sont implémentés et documentés ;
- `command`, `incus`, `template` et `shell` sont mutuellement exclusifs ;
- le mode `incus` ajoute exactement une fois le binaire en `argv[0]` ;
- les modes `command` et `incus` n’utilisent jamais de shell ;
- le mode `template` est rendu sur le contrôleur via un action plugin ;
- le YAML rendu est chargé et validé de manière sûre ;
- le mode `shell` exige un consentement explicite ;
- les secrets sont masqués ;
- `check_mode`, `creates`, `removes`, `changed` et `stop_on_error` sont testés ;
- les tests unitaires couvrent les fonctions de normalisation et de validation ;
- les tests Molecule couvrent les quatre modes avec un faux binaire Incus ;
- le code réussit les contrôles `ansible-test sanity` pertinents ;
- les résultats de tests sont montrés sans être inventés ;
- la documentation permet à un autre développeur de reprendre le projet sans information supplémentaire.

---

# Format de la réponse attendue

Répondre dans cet ordre :

1. résumé de l’architecture et décisions techniques ;
2. matrice des exigences et tests associés ;
3. arborescence finale ;
4. tests écrits avant l’implémentation, incrément par incrément ;
5. code complet de chaque fichier ;
6. scénario Molecule complet ;
7. commandes d’installation et de test ;
8. résultats réels des tests exécutés ;
9. couverture obtenue ;
10. limites, risques et améliorations futures.

Ne remplace aucun fichier par `...`, « code omis » ou pseudo-code lorsque le fichier est nécessaire au fonctionnement du projet. Les extraits de sortie de tests doivent provenir d’une exécution réelle ou être explicitement marqués comme résultats attendus non exécutés.
