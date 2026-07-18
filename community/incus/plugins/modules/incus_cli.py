#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Module Ansible incus_cli - Version Standalone Optimisée
Execute Incus CLI commands with multiple modes: command, incus, template, shell

Optimisations:
- Code unifié entre standalone et collection
- Meilleure gestion des erreurs
- Support complet du mode template
- Masquage des valeurs sensibles amélioré
- Validation renforcée
"""

from __future__ import absolute_import, division, print_function
__metaclass_type__ = type

import time
import os
import shlex
import re
import json

from ansible.module_utils.basic import AnsibleModule


# Compatibility function for deprecated to_text
def to_text(text, errors='surrogate_or_replace'):
    """Convert bytes to text safely."""
    if not isinstance(text, bytes):
        return str(text)
    if errors == 'surrogate_or_replace':
        try:
            return text.decode('utf-8', 'surrogateescape')
        except (LookupError, TypeError):
            errors = 'replace'
    return text.decode('utf-8', errors)


# Constants
INCUS_BINARY = "incus"
SHELL_OPERATORS = ['|', '>', '>>', '<', '&&', '||', ';']
COMMAND_SUBSTITUTION_PATTERN = re.compile(r'`[^`]+`|\$\([^)]*\)')


def normalize_argv(argv, binary=INCUS_BINARY):
    """
    Normalise une liste d'arguments en ajoutant le binaire incus en position 0.
    
    Args:
        argv: Liste d'arguments
        binary: Nom du binaire à préfixer
    
    Returns:
        Liste normalisée avec le binaire en position 0
    """
    if not argv:
        return argv
    if argv and argv[0] == binary:
        return list(argv)
    return [binary] + list(argv)


def validate_argv(argv, allow_empty=False):
    """
    Valide une liste d'arguments.
    
    Args:
        argv: Liste d'arguments à valider
        allow_empty: Si True, accepte une liste vide
    
    Returns:
        Tuple (valid, error_message)
    """
    if not isinstance(argv, list):
        return False, "argv must be a list"
    if not allow_empty and len(argv) == 0:
        return False, "argv cannot be empty"
    if len(argv) == 0:
        return True, None
    for i, arg in enumerate(argv):
        if not isinstance(arg, str):
            return False, f"argv[{i}] must be a string, got {type(arg).__name__}"
    return True, None


def contains_shell_operators(command):
    """
    Détecte si une commande contient des opérateurs shell.
    
    Args:
        command: Chaîne de commande à analyser
    
    Returns:
        Tuple (has_operators, found_operators)
    """
    found = []
    for op in SHELL_OPERATORS:
        if op in command:
            found.append(op)
    if COMMAND_SUBSTITUTION_PATTERN.search(command):
        found.append("command substitution")
    return (len(found) > 0, found)


def parse_command_string(command):
    """
    Analyse une chaîne de commande simple avec shlex.split.
    
    Args:
        command: Chaîne de commande à analyser
    
    Returns:
        Tuple (parsed_argv, error)
    """
    try:
        parsed = shlex.split(command)
        return parsed, None
    except ValueError as e:
        return None, f"Failed to parse command: {str(e)}"


def mask_sensitive_values(text, sensitive_values):
    """
    Masque les valeurs sensibles dans un texte.
    
    Args:
        text: Texte dans lequel masquer les valeurs
        sensitive_values: Liste de valeurs sensibles à masquer
    
    Returns:
        str - Texte avec les valeurs sensibles masquées
    """
    if not sensitive_values:
        return text
    result = text
    mask = "***SENSITIVE***"
    for value in sensitive_values:
        if value and isinstance(value, str):
            result = result.replace(value, mask)
    return result


def mask_sensitive_values_list(argv, sensitive_values):
    """
    Masque les valeurs sensibles dans une liste d'arguments.
    
    Args:
        argv: Liste d'arguments
        sensitive_values: Liste de valeurs sensibles à masquer
    
    Returns:
        list - Liste avec les valeurs sensibles masquées
    """
    if not sensitive_values:
        return argv
    result = []
    mask = "***SENSITIVE***"
    for arg in argv:
        masked_arg = arg
        for value in sensitive_values:
            if value and isinstance(value, str):
                masked_arg = masked_arg.replace(value, mask)
        result.append(masked_arg)
    return result


def merge_environments(global_env, step_env):
    """
    Fusionne deux dictionnaires d'environnement.
    
    Args:
        global_env: Dictionnaire d'environnement global
        step_env: Dictionnaire d'environnement de l'étape
    
    Returns:
        dict - Dictionnaire fusionné
    """
    result = dict(global_env) if global_env else {}
    if step_env:
        result.update(step_env)
    return result


def check_file_exists(path):
    """
    Vérifie si un fichier existe.
    
    Args:
        path: Chemin du fichier à vérifier
    
    Returns:
        bool - True si le fichier existe
    """
    try:
        return os.path.exists(path)
    except Exception:
        return False


class StepResult:
    """Représente le résultat d'une étape d'exécution"""
    
    def __init__(self, index, name=None, argv=None, rc=None, stdout="", stderr="", 
                 changed=True, skipped=False, duration_ms=0, skip_reason=None):
        self.index = index
        self.name = name
        self.argv = argv or []
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr
        self.changed = changed
        self.skipped = skipped
        self.duration_ms = duration_ms
        self.skip_reason = skip_reason
    
    def to_dict(self):
        """Convertit en dictionnaire pour le résultat du module"""
        result = {
            "index": self.index,
            "name": self.name,
            "argv": self.argv,
            "rc": self.rc,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "changed": self.changed,
            "skipped": self.skipped,
            "duration_ms": self.duration_ms,
        }
        if self.skip_reason:
            result["skip_reason"] = self.skip_reason
        return result


ARGUMENT_SPEC = {
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

MUTUALLY_EXCLUSIVE = [["command", "incus", "template", "shell"]]
REQUIRED_ONE_OF = [["command", "incus", "template", "shell"]]
REQUIRED_IF = [["unsafe_shell", True, ["shell"]]]


def validate_module_args(module):
    """
    Valide les arguments du module.
    
    Args:
        module: Instance AnsibleModule
    
    Returns:
        Tuple (valid, error_message)
    """
    # Vérifier les dépendances entre paramètres
    if module.params.get("variables") and not module.params.get("template"):
        return False, "'variables' can only be used with 'template' mode"
    
    if module.params.get("unsafe_shell") and not module.params.get("shell"):
        return False, "'unsafe_shell' can only be used with 'shell' mode"
    
    if module.params.get("shell") and not module.params.get("unsafe_shell"):
        return False, "'shell' mode requires 'unsafe_shell: true' for security reasons"
    
    # Valider la liste incus
    incus_list = module.params.get("incus")
    if incus_list:
        for i, step in enumerate(incus_list):
            argv = step.get("argv")
            if argv is None:
                return False, f"incus[{i}]: 'argv' is required"
            if argv is not None:
                valid, error = validate_argv(argv)
                if not valid:
                    return False, f"incus[{i}]: {error}"
    
    # Valider le mode command
    command = module.params.get("command")
    if command:
        has_ops, found_ops = contains_shell_operators(command)
        if has_ops:
            return False, f"'command' mode does not support shell operators ({', '.join(found_ops)}). Use 'shell' mode with 'unsafe_shell: true' instead."
    
    return True, None


def execute_command_step(module, command_str, global_env=None, chdir=None, sensitive_values=None):
    """
    Exécute une étape en mode command.
    
    Args:
        module: Instance AnsibleModule
        command_str: Commande à exécuter
        global_env: Environnement global
        chdir: Répertoire de travail
        sensitive_values: Valeurs sensibles à masquer
    
    Returns:
        StepResult: Résultat de l'exécution
    """
    start_time = time.time()
    parsed, error = parse_command_string(command_str)
    if error:
        return StepResult(
            index=0, name="command", argv=parsed or [command_str],
            rc=1, stdout="", stderr=error, changed=False, skipped=False,
            duration_ms=int((time.time() - start_time) * 1000)
        )
    
    environment = global_env or {}
    rc, stdout, stderr = module.run_command(parsed, environ_update=environment, cwd=chdir)
    duration_ms = int((time.time() - start_time) * 1000)
    
    if sensitive_values:
        stdout = mask_sensitive_values(stdout, sensitive_values)
        stderr = mask_sensitive_values(stderr, sensitive_values)
    
    return StepResult(
        index=0, name="command", argv=parsed, rc=rc,
        stdout=to_text(stdout, errors='surrogate_or_replace'),
        stderr=to_text(stderr, errors='surrogate_or_replace'),
        changed=(rc == 0), skipped=False, duration_ms=duration_ms
    )


def execute_incus_step(module, step, idx, global_env=None, chdir=None, global_creates=None, global_removes=None, check_mode=False):
    """
    Exécute une étape en mode incus.
    
    Args:
        module: Instance AnsibleModule
        step: Dictionnaire de l'étape
        idx: Index de l'étape
        global_env: Environnement global
        chdir: Répertoire de travail
        global_creates: Chemin pour creates global
        global_removes: Chemin pour removes global
        check_mode: Mode check
    
    Returns:
        StepResult: Résultat de l'exécution
    """
    start_time = time.time()
    
    name = step.get("name", f"step_{idx}")
    argv = step.get("argv", [])
    step_env = step.get("environment", {})
    step_changed = step.get("changed", True)
    step_creates = step.get("creates")
    step_removes = step.get("removes")
    sensitive_values = step.get("sensitive_values", [])
    
    normalized_argv = normalize_argv(argv)
    skip_reason = None
    
    # Vérifier les conditions de skip (global d'abord)
    if global_creates and check_file_exists(global_creates):
        skip_reason = f"Global creates path '{global_creates}' exists"
    if global_removes and not check_file_exists(global_removes):
        skip_reason = f"Global removes path '{global_removes}' does not exist"
    
    # Puis les conditions de l'étape
    if not skip_reason:
        if step_creates and check_file_exists(step_creates):
            skip_reason = f"Step creates path '{step_creates}' exists"
        if step_removes and not check_file_exists(step_removes):
            skip_reason = f"Step removes path '{step_removes}' does not exist"
    
    # Enfin le check_mode
    if not skip_reason and check_mode and step_changed:
        skip_reason = "check_mode: would execute"
    
    if skip_reason:
        return StepResult(
            index=idx, name=name, argv=normalized_argv,
            rc=0, stdout="", stderr="", changed=False, skipped=True,
            duration_ms=0, skip_reason=skip_reason
        )
    
    merged_env = merge_environments(global_env, step_env)
    rc, stdout, stderr = module.run_command(normalized_argv, environ_update=merged_env, cwd=chdir)
    duration_ms = int((time.time() - start_time) * 1000)
    
    all_sensitive = sensitive_values
    stdout_masked = mask_sensitive_values(stdout, all_sensitive)
    stderr_masked = mask_sensitive_values(stderr, all_sensitive)
    argv_masked = mask_sensitive_values_list(normalized_argv, all_sensitive)
    
    # Avertissement si doublon détecté
    if step.get("argv") and len(step["argv"]) > 0 and step["argv"][0] == INCUS_BINARY:
        module.warn(f"Duplicate 'incus' prefix found in step {idx} argv[0], normalized to single instance")
    
    return StepResult(
        index=idx, name=name, argv=argv_masked, rc=rc,
        stdout=to_text(stdout_masked, errors='surrogate_or_replace'),
        stderr=to_text(stderr_masked, errors='surrogate_or_replace'),
        changed=step_changed and (rc == 0), skipped=False, duration_ms=duration_ms
    )


def execute_shell_step(module, command_str, executable=None, global_env=None, chdir=None, sensitive_values=None):
    """
    Exécute une étape en mode shell.
    
    Args:
        module: Instance AnsibleModule
        command_str: Commande shell à exécuter
        executable: Interpréteur shell
        global_env: Environnement global
        chdir: Répertoire de travail
        sensitive_values: Valeurs sensibles à masquer
    
    Returns:
        StepResult: Résultat de l'exécution
    """
    start_time = time.time()
    environment = global_env or {}
    
    rc, stdout, stderr = module.run_command(
        command_str, use_unsafe_shell=True,
        executable=executable or "/bin/sh", environ_update=environment, cwd=chdir
    )
    duration_ms = int((time.time() - start_time) * 1000)
    
    stdout_masked = mask_sensitive_values(stdout, sensitive_values)
    stderr_masked = mask_sensitive_values(stderr, sensitive_values)
    
    return StepResult(
        index=0, name="shell", argv=[command_str], rc=rc,
        stdout=to_text(stdout_masked, errors='surrogate_or_replace'),
        stderr=to_text(stderr_masked, errors='surrogate_or_replace'),
        changed=(rc == 0), skipped=False, duration_ms=duration_ms
    )


def execute_template(module, template_path, variables, global_env=None, chdir=None):
    """
    Rend un template Jinja2 et retourne la liste des étapes.
    
    Args:
        module: Instance AnsibleModule
        template_path: Chemin du template
        variables: Variables pour le template
        global_env: Environnement global
        chdir: Répertoire de travail
    
    Returns:
        Tuple (steps, error)
    """
    try:
        import jinja2
        import yaml
    except ImportError as e:
        return None, f"Missing dependency: {str(e)}. Install with: pip install jinja2 pyyaml"
    
    # Résoudre le chemin du template
    if not os.path.isabs(template_path):
        # Chemin relatif - essayer plusieurs répertoires
        possible_dirs = [
            chdir or os.getcwd(),
            os.path.join(os.getcwd(), 'templates'),
            module.params.get('playbook_dir'),
        ]
        for base_dir in possible_dirs:
            if base_dir:
                full_path = os.path.join(base_dir, template_path)
                if os.path.exists(full_path):
                    template_path = full_path
                    break
    
    if not os.path.exists(template_path):
        return None, f"Template file not found: {template_path}"
    
    template_dir = os.path.dirname(template_path) or '.'
    template_file = os.path.basename(template_path)
    
    try:
        # Créer l'environnement Jinja2
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=False,
            undefined=jinja2.StrictUndefined
        )
        template = env.get_template(template_file)
        
        # Rendre le template avec les variables
        context = dict(variables) if variables else {}
        rendered = template.render(**context)
        
        # Parser le YAML
        steps = yaml.safe_load(rendered)
        
        if not isinstance(steps, dict):
            return None, "Template must produce a YAML mapping (dict)"
        
        # Valider la structure
        if 'incus' not in steps:
            return None, "Template must render a YAML structure with 'incus' as the root key"
        
        incus_list = steps['incus']
        if not isinstance(incus_list, list):
            return None, "The 'incus' key must contain a list of steps"
        
        # Valider chaque étape
        for i, step in enumerate(incus_list):
            if not isinstance(step, dict):
                return None, f"Each step in 'incus' must be a dictionary (step {i})"
            if 'argv' not in step:
                return None, f"Each step must have an 'argv' key (step {i})"
            if not isinstance(step.get('argv'), list):
                return None, f"The 'argv' key must be a list (step {i})"
        
        return steps, None
        
    except Exception as e:
        return None, f"Template error: {str(e)}"


def run_module():
    """
    Point d'entrée principal du module.
    """
    module = AnsibleModule(
        argument_spec=ARGUMENT_SPEC,
        mutually_exclusive=MUTUALLY_EXCLUSIVE,
        required_one_of=REQUIRED_ONE_OF,
        required_if=REQUIRED_IF,
        supports_check_mode=True,
    )
    
    # Valider les arguments
    valid, error = validate_module_args(module)
    if not valid:
        module.fail_json(msg=error, changed=False)
    
    results = []
    overall_changed = False
    overall_failed = False
    mode = None
    
    # Mode command
    if module.params.get("command") is not None:
        mode = "command"
        result = execute_command_step(
            module, module.params["command"],
            global_env=module.params.get("environment"),
            chdir=module.params.get("chdir"),
            sensitive_values=[]
        )
        results.append(result.to_dict())
        overall_changed = result.changed
        overall_failed = (result.rc != 0)
    
    # Mode incus
    elif module.params.get("incus") is not None:
        mode = "incus"
        for i, step in enumerate(module.params["incus"]):
            result = execute_incus_step(
                module, step, i,
                global_env=module.params.get("environment"),
                chdir=module.params.get("chdir"),
                global_creates=module.params.get("creates"),
                global_removes=module.params.get("removes"),
                check_mode=module.check_mode
            )
            results.append(result.to_dict())
            if module.params.get("stop_on_error", True) and result.rc != 0 and not result.skipped:
                overall_failed = True
            if result.changed:
                overall_changed = True
            if result.rc != 0:
                overall_failed = True
    
    # Mode template
    elif module.params.get("template") is not None:
        mode = "template"
        steps, error = execute_template(
            module,
            module.params["template"],
            module.params.get("variables", {}),
            module.params.get("environment"),
            module.params.get("chdir")
        )
        
        if error:
            module.fail_json(msg=error, changed=False)
        
        if not steps:
            module.fail_json(msg="Template produced no steps", changed=False)
        
        # Exécuter les étapes générées
        incus_steps = steps.get('incus', [])
        for i, step in enumerate(incus_steps):
            result = execute_incus_step(
                module, step, i,
                global_env=module.params.get("environment"),
                chdir=module.params.get("chdir"),
                global_creates=module.params.get("creates"),
                global_removes=module.params.get("removes"),
                check_mode=module.check_mode
            )
            results.append(result.to_dict())
            if module.params.get("stop_on_error", True) and result.rc != 0:
                overall_failed = True
            if result.changed:
                overall_changed = True
            if result.rc != 0:
                overall_failed = True
    
    # Mode shell
    elif module.params.get("shell") is not None:
        mode = "shell"
        result = execute_shell_step(
            module, module.params["shell"],
            executable=module.params.get("executable", "/bin/sh"),
            global_env=module.params.get("environment"),
            chdir=module.params.get("chdir"),
            sensitive_values=[]
        )
        results.append(result.to_dict())
        overall_changed = result.changed
        overall_failed = (result.rc != 0)
    
    if mode is None:
        module.fail_json(msg="One of 'command', 'incus', 'template', or 'shell' is required", changed=False)
    
    module.exit_json(
        changed=overall_changed,
        failed=overall_failed,
        mode=mode,
        results=results
    )


if __name__ == '__main__':
    run_module()
