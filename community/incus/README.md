# Collection incus - Module **incus_cli**

> **Note**: Ce projet implémente un module Ansible `incus_cli` comme module standalone dans le repertoire `library/`.

## Presentation

Module Ansible generique pour executer des commandes **Incus CLI** de maniere controlee, securisee et idempotente.

## Preambule

Ce module est developpe suivant une approche **TDD** (Test Driven Development) et respecte les specifications du prompt fourni.

## Modes d'utilisation

### 1. Mode rapide `command`

Execute une commande simple sans traitement special.

**Exemple:**
```yaml
- name: Demarrer une instance
  incus_cli:
    command: "incus start {{ instance_name }}"
```

**Caracteristiques:**
- La commande doit etre complete (pas de prefixe `incus` automatique)
- Interdit les operateurs shell (|, >, >>, <, &&, ||, ;)
- Analyse avec `shlex.split` (respect des guillemets)

### 2. Mode robuste `incus`

Execute plusieurs commandes de maniere structuree.

**Exemple:**
```yaml
- name: Demarrer puis arreter une instance
  incus_cli:
    incus:
      - name: Demarrer web01
        argv:
          - start
          - "{{ name }}"
          - --project
          - production
      - name: Arreter web01
        argv:
          - stop
          - "{{ name }}"
```

**Caracteristiques:**
- Prefixe automatique `incus` en position 0
- Normalisation : pas de doublon si `incus` est deja present
- Support de `changed`, `creates`, `removes`, `environment`, `sensitive_values`

### 3. Mode `template`

Execute des commandes generees a partir d'un template Jinja2.

**Exemple:**
```yaml
- name: Executer un scenario depuis un template
  incus_cli:
    template: templates/instance.yml.j2
    variables:
      name: web01
      state: started
      remote: prod
      project: production
```

**Template (instance.yml.j2):**
```yaml
incus:
  - argv:
      - "{{ 'start' if state == 'started' else 'stop' }}"
      - "{{ remote }}:{{ name }}"
      - --project
      - "{{ project }}"
```

### 4. Mode `shell`

Execute des commandes necessitant les fonctionnalites du shell.

**Exemple:**
```yaml
- name: Exporter la liste des instances
  incus_cli:
    shell: "incus list --format json > list.json"
    unsafe_shell: true
```

**Avertissement:** Ce mode utilise explicitement un shell et peut etre vulnerables aux injections. **Consentement explicite requis** avec `unsafe_shell: true`.

## Configuration Ansible

Pour utiliser ce module comme module local :

```ini
# ansible.cfg
[defaults]
library = ./library
action_plugins = ./action_plugins
```

## Structure du projet

```
incus-cli/
├── ansible.cfg                    # Configuration Ansible
├── library/
│   └── incus_cli.py              # Module principal
├── module_utils/
│   └── incus_cli.py              # Fonctions utilitaires
├── action_plugins/
│   └── incus_cli_template.py     # Action plugin pour le mode template
├── templates/
│   └── instance.yml.j2           # Template d'exemple
├── playbooks/
│   └── test_incus_cli.yml
├── tests/
│   ├── unit/
│   │   ├── module_utils/
│   │   │   └── test_incus_cli.py
│   │   └── modules/
│   │       ├── test_incus_cli.py
│   │       └── test_incus_cli_shell.py
│   └── integration/
│       ├── fake_incus.py
│       └── targets/
└── molecule/
    └── default/
        ├── molecule.yml
        ├── create.yml
        ├── prepare.yml
        ├── converge.yml
        ├── verify.yml
        └── destroy.yml
```

## Tests

### Tests unitaires

```bash
cd /home/perreau/incus-cli
.venv/bin/python -m pytest tests/unit/ -v
```

### Tests Molecule

```bash
cd /home/perreau/incus-cli
molecule test
```

## Resultat

Le module retourne une structure stable :

```json
{
  "changed": true,
  "failed": false,
  "mode": "incus",
  "results": [
    {
      "index": 0,
      "name": "Demarrer web01",
      "argv": ["incus", "start", "web01"],
      "rc": 0,
      "stdout": "...",
      "stderr": "",
      "changed": true,
      "skipped": false,
      "duration_ms": 120
    }
  ],
  "warnings": []
}
```
