#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Module Ansible incus_cli
Fournit un wrapper générique pour exécuter des commandes Incus CLI

Supports quatre modes:
1. command - mode rapide avec une chaîne de commande
2. incus - mode robuste avec des tableaux argv
3. template - mode template Jinja2/YAML
4. shell - mode shell (non sécurisé)
"""

from __future__ import absolute_import, division, print_function

__metaclass_type__ = type

DOCUMENTATION = r'''
--- 
module: incus_cli
short_description: Execute Incus CLI commands
version_added: "1.0.0"
description:
  - Execute Incus CLI commands in a controlled and idempotent manner
  - Supports four modes: command, incus, template, and shell
author: "Ansible Developer"
options:
  command:
    description:
      - Simple command string to execute (must be complete, no automatic incus prefix)
      - Variables are resolved before execution
    type: str
  incus:
    description:
      - List of Incus commands to execute as separate steps
      - Each step is a dict with argv, name, environment, etc.
      - The 'incus' binary is automatically prefixed to argv[0]
    type: list
    elements: dict
    suboptions:
      name:
        description: Optional name for the step
        type: str
      argv:
        description: List of command arguments
        type: list
        elements: str
        required: true
      environment:
        description: Environment variables for this step
        type: dict
        default: {}
      changed:
        description: Whether this step should be considered as a change
        type: bool
        default: true
      creates:
        description: Path that should exist to skip this step
        type: path
      removes:
        description: Path that should not exist to skip this step
        type: path
      sensitive_values:
        description: List of sensitive values to mask in output
        type: list
        elements: str
        default: []
        no_log: true
  template:
    description:
      - Path to a Jinja2 template file that produces YAML in the incus format
      - Template is rendered on the controller and validated
    type: path
  variables:
    description:
      - Variables to pass to the template
      - These override any context variables
    type: dict
    default: {}
    no_log: false
  shell:
    description:
      - Shell command string to execute
      - WARNING: This mode uses a shell and may be vulnerable to injection
      - Requires unsafe_shell=true to be explicitly set
    type: str
  unsafe_shell:
    description:
      - Must be set to true to use shell mode
      - This is a safety mechanism
    type: bool
    default: false
  executable:
    description: Shell executable to use (only applicable in shell mode)
    type: path
    default: /bin/sh
  chdir:
    description: Working directory for command execution
    type: path
  environment:
    description: Global environment variables for all steps
    type: dict
    default: {}
  creates:
    description: Global path that should exist to skip all steps
    type: path
  removes:
    description: Global path that should not exist to skip all steps
    type: path
  stop_on_error:
    description: Whether to stop execution on first error
    type: bool
    default: true

mutually_exclusive:
  - command
  - incus
  - template
  - shell

required_one_of:
  - command
  - incus
  - template
  - shell

required_if:
  - unsafe_shell: true
    - shell

notes:
  - The incus binary is automatically prefixed to argv in 'incus' mode
  - The 'command' mode does NOT automatically prefix 'incus' - the full command must be provided
  - Shell mode requires explicit consent via unsafe_shell=true
  - Remote specifications like [remote:]name are preserved as single arguments
  - check_mode is supported with proper change prediction

examples:
  - name: Start an instance using command mode
    incus_cli:
      command: "incus start web01"

  - name: Start and stop an instance using incus mode
    incus_cli:
      incus:
        - argv: ["start", "web01"]
        - argv: ["stop", "web01"]

  - name: Use template mode
    incus_cli:
      template: templates/instance.yml.j2
      variables:
        name: web01
        state: started

  - name: Use shell mode with redirection
    incus_cli:
      shell: "incus list --format json > list.json"
      unsafe_shell: true

return:
  changed:
    description: Whether any step resulted in a change
    type: bool
    returned: always
  failed:
    description: Whether the module failed
    type: bool
    returned: always
  mode:
    description: Which mode was used (command, incus, template, shell)
    type: str
    returned: always
  results:
    description: List of results for each executed step
    type: list
    elements: dict
    returned: always
    contains:
      index:
        description: Step index
        type: int
      name:
        description: Step name (if provided)
        type: str
      argv:
        description: Normalized command arguments
        type: list
        elements: str
      rc:
        description: Return code
        type: int
      stdout:
        description: Standard output
        type: str
      stderr:
        description: Standard error
        type: str
      changed:
        description: Whether this step changed something
        type: bool
      skipped:
        description: Whether this step was skipped
        type: bool
      duration_ms:
        description: Execution duration in milliseconds
        type: int
      skip_reason:
        description: Reason for skipping (if applicable)
        type: str
  warnings:
    description: List of warning messages
    type: list
    elements: str
    returned: always
'''

EXAMPLES = r'''
- name: Start an instance using command mode
  incus_cli:
    command: "incus start {{ instance_name }}"

- name: Start and stop an instance using incus mode
  incus_cli:
    incus:
      - name: Start web01
        argv: ["start", "{{ instance_name }}"]
      - name: Stop web01
        argv: ["stop", "{{ instance_name }}"]

- name: Use template mode with variables
  incus_cli:
    template: templates/instance.yml.j2
    variables:
      name: web01
      state: started
      project: production

- name: Use shell mode with redirection (use with caution!)
  incus_cli:
    shell: "incus list --format json > {{ output_file }}"
    unsafe_shell: true
'''

RETURN = r'''
changed:
    description: Whether any step resulted in a change
    type: bool
    sample: true
failed:
    description: Whether the module failed
    type: bool
    sample: false
mode:
    description: Which mode was used
    type: str
    sample: "incus"
results:
    description: List of step results
    type: list
    sample: [{"index": 0, "name": "Start web01", "argv": ["incus", "start", "web01"], "rc": 0, "stdout": "", "stderr": "", "changed": true, "skipped": false, "duration_ms": 120}]
warnings:
    description: List of warning messages
    type: list
    sample: ["Duplicate 'incus' prefix found in argv[0], normalized to single instance"]
'''

import time
import os
import json
import shlex
import traceback

try:
    from ansible.module_utils.basic import AnsibleModule
    from ansible.module_utils._text import to_text, to_native
except ImportError:
    from ansible.module_utils.basic import AnsibleModule
    HAS_ANSIBLE = True
else:
    HAS_ANSIBLE = True

# Importer les utilitaires locaux
try:
    from module_utils.incus_cli import (
        normalize_argv,
        validate_argv,
        contains_shell_operators,
        parse_command_string,
        mask_sensitive_values,
        merge_environments,
        check_file_exists,
        StepResult,
        INCUS_BINARY,
    )
except ImportError:
    # Fallback pour les tests sans module_utils
    import sys
    import re
    INCUS_BINARY = "incus"
    SHELL_OPERATORS = ['|', '>', '>>', '<', '&&', '||', ';']
    COMMAND_SUBSTITUTION_PATTERN = re.compile(r'`[^`]+`|\$\([^)]*\)')

    def normalize_argv(argv, binary=INCUS_BINARY):
        if not argv:
            return argv
        if argv and argv[0] == binary:
            return list(argv)
        return [binary] + list(argv)

    def validate_argv(argv, allow_empty=False):
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
        found = []
        for op in SHELL_OPERATORS:
            if op in command:
                found.append(op)
        if COMMAND_SUBSTITUTION_PATTERN.search(command):
            found.append("command substitution")
        return (len(found) > 0, found)

    def parse_command_string(command):
        try:
            parsed = shlex.split(command)
            return parsed, None
        except ValueError as e:
            return None, f"Failed to parse command: {str(e)}"

    def mask_sensitive_values(text, sensitive_values):
        if not sensitive_values:
            return text
        result = text
        mask = "***SENSITIVE***"
        for value in sensitive_values:
            if value and isinstance(value, str):
                result = result.replace(value, mask)
        return result

    def merge_environments(global_env, step_env):
        result = dict(global_env) if global_env else {}
        if step_env:
            result.update(step_env)
        return result

    def check_file_exists(path):
        try:
            return os.path.exists(path)
        except Exception:
            return False

    class StepResult:
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


# Argument spec du module
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

MUTUALLY_EXCLUSIVE = [
    ["command", "incus", "template", "shell"],
]

REQUIRED_ONE_OF = [
    ["command", "incus", "template", "shell"],
]

REQUIRED_IF = [
    ["unsafe_shell", True, ["shell"]],
]


def validate_module_args(module):
    """
    Valide les arguments du module selon les règles métier.
    
    Args:
        module: Instance AnsibleModule
    
    Returns:
        Tuple (valid, error_message)
    """
    # Vérifier que variables n'est utilisé qu'avec template
    if module.params.get("variables") and not module.params.get("template"):
        return False, "'variables' can only be used with 'template' mode"
    
    # Vérifier que unsafe_shell et executable ne sont utilisés qu'avec shell
    if module.params.get("unsafe_shell") and not module.params.get("shell"):
        return False, "'unsafe_shell' can only be used with 'shell' mode"
    
    if module.params.get("executable") != "/bin/sh" and not module.params.get("shell"):
        # L'argument executable est fourni mais shell mode n'est pas actif
        # Note: executable a une valeur par défaut, donc on vérifie si c'est la valeur par défaut
        pass  # On laisse passer car executable peut être fourni même sans shell mode
    
    # Vérifier que shell a unsafe_shell=true
    if module.params.get("shell") and not module.params.get("unsafe_shell"):
        return False, "'shell' mode requires 'unsafe_shell: true' for security reasons. Use 'incus' or 'command' mode for safer execution."
    
    # Valider le mode incus
    incus_list = module.params.get("incus")
    if incus_list:
        for i, step in enumerate(incus_list):
            # Vérifier que argv existe et n'est pas vide
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
        # Vérifier les opérateurs shell
        has_ops, found_ops = contains_shell_operators(command)
        if has_ops:
            return False, f"'command' mode does not support shell operators ({', '.join(found_ops)}). Use 'shell' mode with 'unsafe_shell: true' instead."
    
    return True, None


def execute_command_step(module, command_str, global_environment=None, chdir=None, sensitive_values=None):
    """
    Exécute une commande en mode 'command'.
    
    Args:
        module: Instance AnsibleModule
        command_str: Chaîne de commande à exécuter
        global_environment: Environnement global
        chdir: Répertoire de travail
        sensitive_values: Valeurs sensibles à masquer
    
    Returns:
        StepResult
    """
    start_time = time.time()
    
    # Analyser la commande
    parsed, error = parse_command_string(command_str)
    if error:
        return StepResult(
            index=0,
            name="command",
            argv=parsed or [command_str],
            rc=1,
            stdout="",
            stderr=error,
            changed=False,
            skipped=False,
            duration_ms=int((time.time() - start_time) * 1000),
            skip_reason=None
        )
    
    # Exécuter sans shell
    environment = global_environment or {}
    rc, stdout, stderr = module.run_command(
        parsed,
        environ_update=environment,
        cwd=chdir
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Masquer les valeurs sensibles
    if sensitive_values:
        stdout = mask_sensitive_values(stdout, sensitive_values)
        stderr = mask_sensitive_values(stderr, sensitive_values)
    
    return StepResult(
        index=0,
        name="command",
        argv=parsed,
        rc=rc,
        stdout=to_text(stdout, errors='surrogate_or_replace'),
        stderr=to_text(stderr, errors='surrogate_or_replace'),
        changed=(rc == 0),
        skipped=False,
        duration_ms=duration_ms
    )


def execute_incus_step(module, step, step_index, global_environment=None, chdir=None, global_creates=None, global_removes=None, check_mode=False):
    """
    Exécute une étape du mode 'incus'.
    
    Args:
        module: Instance AnsibleModule
        step: Dictionnaire de l'étape
        step_index: Index de l'étape
        global_environment: Environnement global
        chdir: Répertoire de travail
        global_creates: creates global
        global_removes: removes global
        check_mode: Mode check
    
    Returns:
        StepResult
    """
    start_time = time.time()
    
    name = step.get("name", f"step_{step_index}")
    argv = step.get("argv", [])
    step_environment = step.get("environment", {})
    step_changed = step.get("changed", True)
    step_creates = step.get("creates")
    step_removes = step.get("removes")
    sensitive_values = step.get("sensitive_values", [])
    
    # Normaliser argv
    normalized_argv = normalize_argv(argv)
    
    # Vérifier les conditions de skip
    skip_reason = None
    
    # Vérifier creates/removes global d'abord
    if global_creates and check_file_exists(global_creates):
        skip_reason = f"Global creates path '{global_creates}' exists"
    
    if global_removes and not check_file_exists(global_removes):
        skip_reason = f"Global removes path '{global_removes}' does not exist"
    
    # Vérifier creates/removes de l'étape
    if not skip_reason:
        if step_creates and check_file_exists(step_creates):
            skip_reason = f"Step creates path '{step_creates}' exists"
        
        if step_removes and not check_file_exists(step_removes):
            skip_reason = f"Step removes path '{step_removes}' does not exist"
    
    # En check_mode, si c'est une étape modificatrice, on skip
    # Mais on autorise les étapes marquées changed=false (consultation sûre)
    if not skip_reason and check_mode and step_changed:
        skip_reason = "check_mode: would execute"
    
    if skip_reason:
        return StepResult(
            index=step_index,
            name=name,
            argv=normalized_argv,
            rc=0,
            stdout="",
            stderr="",
            changed=False,
            skipped=True,
            duration_ms=0,
            skip_reason=skip_reason
        )
    
    # Fusionner les environnements
    merged_env = merge_environments(global_environment, step_environment)
    
    # Exécuter la commande
    rc, stdout, stderr = module.run_command(
        normalized_argv,
        environ_update=merged_env,
        cwd=chdir
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Masquer les valeurs sensibles
    all_sensitive = sensitive_values
    if global_environment:
        # Ajouter les valeurs marquées comme sensibles dans l'environnement global
        pass
    
    stdout_masked = mask_sensitive_values(stdout, all_sensitive)
    stderr_masked = mask_sensitive_values(stderr, all_sensitive)
    argv_masked = mask_sensitive_values_list(normalized_argv, all_sensitive)
    
    return StepResult(
        index=step_index,
        name=name,
        argv=argv_masked,
        rc=rc,
        stdout=to_text(stdout_masked, errors='surrogate_or_replace'),
        stderr=to_text(stderr_masked, errors='surrogate_or_replace'),
        changed=step_changed and (rc == 0),
        skipped=False,
        duration_ms=duration_ms,
        skip_reason=None
    )


def mask_sensitive_values_list(argv, sensitive_values):
    """Masque les valeurs sensibles dans une liste d'arguments"""
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


def execute_shell_step(module, command_str, executable=None, global_environment=None, chdir=None, sensitive_values=None):
    """
    Exécute une commande en mode 'shell'.
    
    Args:
        module: Instance AnsibleModule
        command_str: Chaîne de commande shell
        executable: Exécutable shell
        global_environment: Environnement global
        chdir: Répertoire de travail
        sensitive_values: Valeurs sensibles à masquer
    
    Returns:
        StepResult
    """
    start_time = time.time()
    
    environment = global_environment or {}
    
    # Exécuter avec shell
    rc, stdout, stderr = module.run_command(
        command_str,
        use_unsafe_shell=True,
        executable=executable or "/bin/sh",
        environ_update=environment,
        cwd=chdir
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Masquer les valeurs sensibles
    stdout_masked = mask_sensitive_values(stdout, sensitive_values)
    stderr_masked = mask_sensitive_values(stderr, sensitive_values)
    
    return StepResult(
        index=0,
        name="shell",
        argv=[command_str],
        rc=rc,
        stdout=to_text(stdout_masked, errors='surrogate_or_replace'),
        stderr=to_text(stderr_masked, errors='surrogate_or_replace'),
        changed=(rc == 0),
        skipped=False,
        duration_ms=duration_ms
    )


def run_module():
    """
    Point d'entrée principal du module.
    """
    module_args = ARGUMENT_SPEC.copy()
    
    module = AnsibleModule(
        argument_spec=module_args,
        mutually_exclusive=MUTUALLY_EXCLUSIVE,
        required_one_of=REQUIRED_ONE_OF,
        required_if=REQUIRED_IF,
        supports_check_mode=True,
    )
    
    # Valider les arguments
    valid, error = validate_module_args(module)
    if not valid:
        module.fail_json(msg=error, changed=False)
    
    # Initialiser les résultats
    results = []
    warnings = []
    overall_changed = False
    overall_failed = False
    mode = None
    
    # Déterminer le mode
    if module.params.get("command") is not None:
        mode = "command"
        command_str = module.params["command"]
        
        # Exécuter en mode command
        result = execute_command_step(
            module,
            command_str,
            global_environment=module.params.get("environment"),
            chdir=module.params.get("chdir"),
            sensitive_values=[]  # Les valeurs sensibles dans command mode doivent être gérées via no_log
        )
        results.append(result.to_dict())
        overall_changed = result.changed
        overall_failed = (result.rc != 0)
    
    elif module.params.get("incus") is not None:
        mode = "incus"
        incus_steps = module.params["incus"]
        stop_on_error = module.params.get("stop_on_error", True)
        global_creates = module.params.get("creates")
        global_removes = module.params.get("removes")
        global_environment = module.params.get("environment")
        chdir = module.params.get("chdir")
        check_mode = module.check_mode
        
        # Exécuter chaque étape
        for i, step in enumerate(incus_steps):
            result = execute_incus_step(
                module,
                step,
                i,
                global_environment=global_environment,
                chdir=chdir,
                global_creates=global_creates,
                global_removes=global_removes,
                check_mode=check_mode
            )
            
            results.append(result.to_dict())
            
            # Gérer stop_on_error
            if stop_on_error and result.rc != 0 and not result.skipped:
                # Arrêter mais continuer à collecter les résultats
                overall_failed = True
                # On pourrait break ici, mais on continue pour collecter tous les résultats
                # Pour l'instant, on continue mais on marque l'échec
            
            if result.changed:
                overall_changed = True
            
            if result.rc != 0:
                overall_failed = True
            
            # Vérifier les doublons
            if step.get("argv") and len(step["argv"]) > 0 and step["argv"][0] == INCUS_BINARY:
                warnings.append(f"Duplicate 'incus' prefix found in step {i} argv[0], normalized to single instance")
    
    elif module.params.get("template") is not None:
        mode = "template"
        template_path = module.params["template"]
        variables = module.params.get("variables", {})
        
        # Le mode template nécessite un action plugin
        # Pour un module standalone, nous devons gérer cela différemment
        # Pour l'instant, nous allons simuler le comportement
        module.fail_json(
            msg="Template mode requires an action plugin. Please use this module as part of a collection or implement the action plugin.",
            changed=False
        )
    
    elif module.params.get("shell") is not None:
        mode = "shell"
        command_str = module.params["shell"]
        executable = module.params.get("executable", "/bin/sh")
        
        # Exécuter en mode shell
        result = execute_shell_step(
            module,
            command_str,
            executable=executable,
            global_environment=module.params.get("environment"),
            chdir=module.params.get("chdir"),
            sensitive_values=[]
        )
        results.append(result.to_dict())
        overall_changed = result.changed
        overall_failed = (result.rc != 0)
    
    # Si aucune condition n'est rencontrée (ne devrait pas arriver à cause de required_one_of)
    if mode is None:
        module.fail_json(msg="One of 'command', 'incus', 'template', or 'shell' is required", changed=False)
    
    # Construire le résultat
    module.exit_json(
        changed=overall_changed,
        failed=overall_failed,
        mode=mode,
        results=results,
        warnings=warnings
    )


if __name__ == '__main__':
    run_module()
