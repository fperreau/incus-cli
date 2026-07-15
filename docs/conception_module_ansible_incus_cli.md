# Conception d’un module Ansible générique `incus_cli`

Les deux formes proposées sont cohérentes pour construire un **orchestrateur générique Incus**, à condition de distinguer clairement le rendu Jinja, l’exécution des commandes, la sécurité et l’idempotence.

## Recommandation synthétique

- conserver un mode `command`, mais préférer une liste structurée de commandes et d’arguments à une chaîne shell ;
- conserver un mode `template`, dans lequel le fichier produit la même structure de commandes ;
- rendre `command` et `template` mutuellement exclusifs ;
- placer les variables dans un dictionnaire `vars` explicite ;
- exécuter chaque commande sans shell par défaut ;
- proposer éventuellement un mode `shell` séparé et explicitement dangereux ;
- prévoir `creates`, `removes`, `changed_when`, `failed_when` ou une phase de vérification pour maîtriser l’idempotence.

## 1. Forme `command`

Une chaîne multilignes peut fonctionner :

```yaml
- name: Exécuter plusieurs commandes Incus
  my_namespace.incus.incus_cli:
    command: |
      incus start {{ name }}
      incus storage volume attach {{ storage }} {{ volume }} {{ name }}
  vars:
    name: web01
    storage: default
    volume: data01
```

Cependant, cette forme ressemble à un script shell. Elle pose des difficultés avec les espaces, guillemets, retours à la ligne, commentaires, tubes, redirections et valeurs non fiables.

Une structure `commands` est plus robuste :

```yaml
- name: Exécuter plusieurs commandes Incus
  my_namespace.incus.incus_cli:
    commands:
      - argv:
          - incus
          - start
          - "{{ remote }}:{{ name }}"
          - --project
          - "{{ project }}"

      - argv:
          - incus
          - storage
          - volume
          - attach
          - "{{ remote }}:{{ storage }}"
          - "{{ volume }}"
          - "{{ name }}"
          - data
          - /srv/data
  vars:
    remote: prod
    project: production
    name: web01
    storage: default
    volume: data01
```

Chaque élément de `argv` devient un argument distinct. Le module peut appeler `run_command(argv)` sans passer par `/bin/sh`.

## 2. Forme `template`

La syntaxe YAML devrait séparer le chemin du fichier et les variables :

```yaml
- name: Exécuter un scénario Incus depuis un modèle
  my_namespace.incus.incus_cli:
    template: templates/incus_instance.yml.j2
    variables:
      name: web01
      state: started
      remote: prod
      project: production
```

Le modèle peut produire la même structure que le mode `commands` :

```yaml
commands:
  - argv:
      - incus
      - "{{ 'start' if state == 'started' else 'stop' }}"
      - "{{ remote }}:{{ name }}"
      - --project
      - "{{ project }}"
```

Le module charge le modèle, effectue le rendu, parse le YAML généré, valide sa structure puis exécute les commandes. Il ne devrait pas exécuter directement le texte rendu comme un script shell.

## 3. Contrat recommandé du module

```yaml
- name: Appliquer un scénario Incus
  my_namespace.incus.incus_cli:
    template: templates/instance.yml.j2
    variables:
      remote: prod
      project: production
      name: web01
      state: started

    environment:
      INCUS_CONF: /etc/incus/client

    stop_on_error: true
    check_mode_policy: validate
```

`command`, `commands` et `template` devraient être mutuellement exclusifs. `variables` contient les données fournies au modèle, tandis que `environment` contient uniquement les variables d’environnement du processus.

## 4. Schéma interne possible

```python
argument_spec = {
    "command": {"type": "str"},
    "commands": {
        "type": "list",
        "elements": "dict",
        "options": {
            "argv": {"type": "list", "elements": "str", "required": True},
            "changed_when": {"type": "str"},
            "failed_when": {"type": "str"},
            "creates": {"type": "path"},
            "removes": {"type": "path"},
        },
    },
    "template": {"type": "path"},
    "variables": {"type": "dict", "default": {}},
    "environment": {"type": "dict", "default": {}},
    "stop_on_error": {"type": "bool", "default": True},
}

mutually_exclusive = [
    ["command", "commands", "template"],
]

required_one_of = [
    ["command", "commands", "template"],
]
```

Dans une collection réelle, le rendu d’un fichier Jinja situé sur le contrôleur est souvent plus naturel dans un **action plugin**. Le module exécuté sur l’hôte cible reçoit alors une structure déjà rendue et validée.

## 5. Sécurité

La forme shell ne doit pas être le comportement par défaut. Cette commande est risquée si `name` contient une valeur non fiable :

```yaml
command: |
  incus start {{ name }}
```

Avec `argv`, la valeur entière reste un seul argument :

```yaml
commands:
  - argv:
      - incus
      - start
      - "{{ name }}"
```

Si les tubes, redirections ou opérateurs `&&` sont indispensables, prévoir une propriété explicite :

```yaml
- shell: |
    incus list --format csv | gzip > /tmp/incus.csv.gz
  unsafe_shell: true
```

Ce mode doit être documenté comme non structuré, sensible à l’injection et plus difficile à rendre idempotent.

## 6. Idempotence

Un wrapper CLI générique ne sait pas automatiquement si une commande modifie l’état. `incus start web01` peut être inutile si l’instance est déjà démarrée ; une commande de consultation ne doit jamais produire `changed: true`.

Une première approche consiste à définir le comportement de chaque étape :

```yaml
commands:
  - argv: [incus, start, "prod:web01"]
    changed_when: "'already running' not in stderr"

  - argv: [incus, list, "prod:", --format, json]
    changed_when: false
```

Une approche plus fiable ajoute une vérification :

```yaml
commands:
  - name: Démarrer web01 si nécessaire
    check:
      argv: [incus, list, "prod:web01", --format, json]
      json_query: "[0].status == 'Running'"
    apply:
      argv: [incus, start, "prod:web01"]
```

Le module exécute `check`, compare l’état observé à l’état attendu et n’exécute `apply` que si nécessaire. Cette forme fournit une base déclarative sans devoir modéliser toute la CLI Incus.

## 7. Résultat retourné

Le module devrait retourner le détail de chaque étape :

```yaml
changed: true
results:
  - index: 0
    argv: [incus, start, "prod:web01"]
    rc: 0
    stdout: ""
    stderr: ""
    changed: true
    duration_ms: 182
```

Les jetons, certificats, mots de passe et variables marquées secrètes doivent être masqués avec `no_log` ou une liste de paramètres sensibles.

## Conclusion

Les deux entrées génériques sont pertinentes, mais elles devraient converger vers un **format intermédiaire commun**, idéalement une liste de commandes `argv`.

Le flux recommandé est :

```text
command/commands ou template
          ↓
rendu des variables Jinja
          ↓
parsing et validation
          ↓
liste structurée de commandes argv
          ↓
vérification éventuelle de l’état
          ↓
exécution sans shell
          ↓
résultat détaillé et changed maîtrisé
```

Cette architecture couvre presque toute la CLI Incus sans déclarer chacune de ses options dans `argument_spec`, tout en conservant une meilleure sécurité et une meilleure maintenabilité qu’un bloc shell libre.
