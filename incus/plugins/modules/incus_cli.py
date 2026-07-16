#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Module Ansible incus_cli
Execute Incus CLI commands with multiple modes: command, incus, template, shell
"""

from __future__ import absolute_import, division, print_function
__metaclass_type__ = type

DOCUMENTATION = r'''
---
module: incus_cli
short_description: Execute Incus CLI commands
version_added: "1.0.0"
description: Execute Incus CLI commands in a controlled and idempotent manner
author: Perreau
options:
  command:
    description: Simple command string to execute
    type: str
  incus:
    description: List of Incus commands to execute as separate steps
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
    description: Path to a Jinja2 template file that produces YAML in the incus format
    type: path
  variables:
    description: Variables to pass to the template
    type: dict
    default: {}
    no_log: false
  shell:
    description: Shell command string to execute
    type: str
  unsafe_shell:
    description: Must be set to true to use shell mode
    type: bool
    default: false
  executable:
    description: Shell executable to use
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
'''

EXAMPLES = r'''
- name: Start an instance
  community.incus.incus_cli:
    command: "incus start web01"

- name: Start and stop an instance
  community.incus.incus_cli:
    incus:
      - argv: ["start", "web01"]
      - argv: ["stop", "web01"]

- name: Use template mode
  community.incus.incus_cli:
    template: templates/instance.yml.j2
    variables:
      name: web01
      image: images:ubuntu/22.04

- name: Use shell mode
  community.incus.incus_cli:
    shell: "incus list --format json > list.json"
    unsafe_shell: true
'''

RETURN = r'''
changed:
    description: Whether any step resulted in a change
    type: bool
failed:
    description: Whether the module failed
    type: bool
mode:
    description: Which mode was used
    type: str
results:
    description: List of results for each executed step
    type: list
    elements: dict
'''

import time
import os
import json
import shlex
import re

from ansible.module_utils.basic import AnsibleModule


# Fonction de compatibilite pour remplacer to_text deprecie
def to_text(text, errors='surrogate_or_replace'):
    if not isinstance(text, bytes):
        return str(text)
    if errors == 'surrogate_or_replace':
        try:
            return text.decode('utf-8', 'surrogateescape')
        except (LookupError, TypeError):
            errors = 'replace'
    return text.decode('utf-8', errors)


# Constantes
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


def mask_sensitive_values_list(argv, sensitive_values):
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
    if module.params.get("variables") and not module.params.get("template"):
        return False, "'variables' can only be used with 'template' mode"
    if module.params.get("unsafe_shell") and not module.params.get("shell"):
        return False, "'unsafe_shell' can only be used with 'shell' mode"
    if module.params.get("shell") and not module.params.get("unsafe_shell"):
        return False, "'shell' mode requires 'unsafe_shell: true' for security reasons"
    
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
    
    command = module.params.get("command")
    if command:
        has_ops, found_ops = contains_shell_operators(command)
        if has_ops:
            return False, f"'command' mode does not support shell operators ({', '.join(found_ops)}). Use 'shell' mode with 'unsafe_shell: true' instead."
    
    return True, None


def execute_command_step(module, command_str, global_environment=None, chdir=None, sensitive_values=None):
    start_time = time.time()
    parsed, error = parse_command_string(command_str)
    if error:
        return StepResult(
            index=0, name="command", argv=parsed or [command_str],
            rc=1, stdout="", stderr=error, changed=False, skipped=False,
            duration_ms=int((time.time() - start_time) * 1000)
        )
    
    environment = global_environment or {}
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


def execute_incus_step(module, step, step_index, global_environment=None, chdir=None, global_creates=None, global_removes=None, check_mode=False):
    start_time = time.time()
    
    name = step.get("name", f"step_{step_index}")
    argv = step.get("argv", [])
    step_environment = step.get("environment", {})
    step_changed = step.get("changed", True)
    step_creates = step.get("creates")
    step_removes = step.get("removes")
    sensitive_values = step.get("sensitive_values", [])
    
    normalized_argv = normalize_argv(argv)
    skip_reason = None
    
    if global_creates and check_file_exists(global_creates):
        skip_reason = f"Global creates path '{global_creates}' exists"
    if global_removes and not check_file_exists(global_removes):
        skip_reason = f"Global removes path '{global_removes}' does not exist"
    
    if not skip_reason:
        if step_creates and check_file_exists(step_creates):
            skip_reason = f"Step creates path '{step_creates}' exists"
        if step_removes and not check_file_exists(step_removes):
            skip_reason = f"Step removes path '{step_removes}' does not exist"
    
    if not skip_reason and check_mode and step_changed:
        skip_reason = "check_mode: would execute"
    
    if skip_reason:
        return StepResult(
            index=step_index, name=name, argv=normalized_argv,
            rc=0, stdout="", stderr="", changed=False, skipped=True,
            duration_ms=0, skip_reason=skip_reason
        )
    
    merged_env = merge_environments(global_environment, step_environment)
    rc, stdout, stderr = module.run_command(normalized_argv, environ_update=merged_env, cwd=chdir)
    duration_ms = int((time.time() - start_time) * 1000)
    
    all_sensitive = sensitive_values
    stdout_masked = mask_sensitive_values(stdout, all_sensitive)
    stderr_masked = mask_sensitive_values(stderr, all_sensitive)
    argv_masked = mask_sensitive_values_list(normalized_argv, all_sensitive)
    
    if step.get("argv") and len(step["argv"]) > 0 and step["argv"][0] == INCUS_BINARY:
        module.warn(f"Duplicate 'incus' prefix found in step {step_index} argv[0], normalized to single instance")
    
    return StepResult(
        index=step_index, name=name, argv=argv_masked, rc=rc,
        stdout=to_text(stdout_masked, errors='surrogate_or_replace'),
        stderr=to_text(stderr_masked, errors='surrogate_or_replace'),
        changed=step_changed and (rc == 0), skipped=False, duration_ms=duration_ms
    )


def execute_shell_step(module, command_str, executable=None, global_environment=None, chdir=None, sensitive_values=None):
    start_time = time.time()
    environment = global_environment or {}
    
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


def main():
    module_args = ARGUMENT_SPEC.copy()
    module = AnsibleModule(
        argument_spec=module_args,
        mutually_exclusive=MUTUALLY_EXCLUSIVE,
        required_one_of=REQUIRED_ONE_OF,
        required_if=REQUIRED_IF,
        supports_check_mode=True,
    )
    
    valid, error = validate_module_args(module)
    if not valid:
        module.fail_json(msg=error, changed=False)
    
    results = []
    overall_changed = False
    overall_failed = False
    mode = None
    
    if module.params.get("command") is not None:
        mode = "command"
        result = execute_command_step(
            module, module.params["command"],
            global_environment=module.params.get("environment"),
            chdir=module.params.get("chdir"), sensitive_values=[]
        )
        results.append(result.to_dict())
        overall_changed = result.changed
        overall_failed = (result.rc != 0)
    
    elif module.params.get("incus") is not None:
        mode = "incus"
        for i, step in enumerate(module.params["incus"]):
            result = execute_incus_step(
                module, step, i,
                global_environment=module.params.get("environment"),
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
    
    elif module.params.get("template") is not None:
        mode = "template"
        module.fail_json(
            msg="Template mode requires the community.incus action plugin. "
                "Install: ansible-galaxy collection install community.incus",
            changed=False
        )
    
    elif module.params.get("shell") is not None:
        mode = "shell"
        result = execute_shell_step(
            module, module.params["shell"],
            executable=module.params.get("executable", "/bin/sh"),
            global_environment=module.params.get("environment"),
            chdir=module.params.get("chdir"), sensitive_values=[]
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
    main()
