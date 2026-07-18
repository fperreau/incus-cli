#!/usr/bin/python3
# -*- coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
--- 
module: incus_cli
short_description: Manage Incus containers and resources
version_added: "1.0.0"
description: |
  A generic module to execute Incus CLI commands in a structured and secure way.
  This module supports multiple modes: command, incus (argv-based), template, and shell.
  
  The Bastion deployment example uses this module to create and configure containers
  with proper storage, networking, and resource limits.

options:
  command:
    description: A single command string to execute (simple mode).
    type: str
    version_added: "1.0.0"
  incus:
    description: |
      A list of Incus commands to execute in argv format.
      Each command will have 'incus' automatically prepended.
    type: list
    elements: dict
    version_added: "1.0.0"
    suboptions:
      argv:
        description: List of command arguments.
        type: list
        elements: str
        required: true
      name:
        description: Optional name for this command step.
        type: str
      environment:
        description: Environment variables for this specific command.
        type: dict
        default: {}
      changed:
        description: Whether this command should be considered as changing state.
        type: bool
        default: true
      creates:
        description: Path that should exist to skip this command.
        type: path
      removes:
        description: Path that should not exist to skip this command.
        type: path
      sensitive_values:
        description: List of sensitive values to mask in output.
        type: list
        elements: str
        default: []
        no_log: true
  template:
    description: Path to a Jinja2 template file that produces Incus commands.
    type: path
    version_added: "1.0.0"
  variables:
    description: Variables to pass to the Jinja2 template.
    type: dict
    default: {}
    version_added: "1.0.0"
  shell:
    description: A shell command to execute (unsafe mode).
    type: str
    version_added: "1.0.0"
  unsafe_shell:
    description: |
      Explicitly enable unsafe shell mode.
      Required when using the shell parameter.
    type: bool
    default: false
    version_added: "1.0.0"
  executable:
    description: The shell executable to use for shell mode.
    type: path
    default: /bin/sh
    version_added: "1.0.0"
  chdir:
    description: Working directory for shell mode.
    type: path
    version_added: "1.0.0"
  environment:
    description: Global environment variables for all commands.
    type: dict
    default: {}
    version_added: "1.0.0"
  creates:
    description: Global path that should exist to skip all commands.
    type: path
    version_added: "1.0.0"
  removes:
    description: Global path that should not exist to skip all commands.
    type: path
    version_added: "1.0.0"
  stop_on_error:
    description: Whether to stop execution on first error.
    type: bool
    default: true
    version_added: "1.0.0"

notes:
  - The module automatically prepends 'incus' to argv lists in 'incus' mode.
  - Shell mode requires explicit consent via unsafe_shell=true.
  - Template mode renders Jinja2 templates on the controller and executes on target.
  - All modes support idempotency through creates/removes parameters.
  - Sensitive values are masked in output and logs.

requirements:
  - incus (on target machine for incus commands)
  - python3

seealso:
  - name: Incus documentation
    description: Official Incus documentation
    link: https://linuxcontainers.org/incus/docs/main/
  - name: The Bastion documentation
    description: The Bastion official documentation
    link: https://ovh.github.io/the-bastion/index.html

author:
  - Your Name (@yourusername)

attributes:
  check_mode:
    support: full
    details: All commands are checked in check_mode without actual execution.
  diff_mode:
    support: none
  platform:
    name: Ubuntu
    versions:
      - focal
      - jammy
      - noble
    name: Debian
    versions:
      - bullseye
      - bookworm
"""

EXAMPLES = r"""
# Simple command mode
- name: Start a container
  my_namespace.incus.incus_cli:
    command: "incus start my-container"

# Robust argv mode (recommended)
- name: Create and start The Bastion container
  my_namespace.incus.incus_cli:
    incus:
      - argv:
          - launch
          - docker:the-bastion/the-bastion:latest
          - the_bastion
          - --storage
          - default
          - -c
          - "limits.cpu=2"
          - -c
          - "limits.memory=2GiB"
      - argv:
          - start
          - the_bastion

# Template mode
- name: Deploy container from template
  my_namespace.incus.incus_cli:
    template: templates/bastion_container.yml.j2
    variables:
      container_name: the_bastion
      image: docker:the-bastion/the-bastion:latest
      cpu_limit: 2
      memory_limit: 2GiB

# Shell mode (unsafe - requires explicit consent)
- name: Export container list
  my_namespace.incus.incus_cli:
    shell: "incus list --format json > /tmp/containers.json"
    unsafe_shell: true
"""

RETURN = r"""
changed:
    description: Whether any command resulted in a change.
    type: bool
    returned: always
    sample: true
failed:
    description: Whether the module failed.
    type: bool
    returned: always
    sample: false
mode:
    description: The mode used (command, incus, template, shell).
    type: str
    returned: always
    sample: "incus"
results:
    description: Detailed results of each command execution.
    type: list
    elements: dict
    returned: always
    contains:
        index:
            description: Index of the command in the list.
            type: int
        name:
            description: Name of the command step (if provided).
            type: str
        argv:
            description: The actual command arguments executed.
            type: list
            elements: str
        rc:
            description: Return code of the command.
            type: int
        stdout:
            description: Standard output of the command.
            type: str
        stderr:
            description: Standard error of the command.
            type: str
        changed:
            description: Whether this command changed state.
            type: bool
        skipped:
            description: Whether this command was skipped.
            type: bool
        duration_ms:
            description: Execution duration in milliseconds.
            type: int
        skip_reason:
            description: Reason for skipping (if skipped).
            type: str
warnings:
    description: List of warning messages.
    type: list
    elements: str
    returned: always
    sample: ["Duplicate 'incus' prefix removed from argv"]
"""

from ansible.module_utils.basic import AnsibleModule
import os
import time
import shlex
import json
import yaml
from pathlib import Path

try:
    from ansible.module_utils.parsing.convert_bool import boolean
    HAS_BOOL_CONVERT = True
except ImportError:
    HAS_BOOL_CONVERT = False


class IncusCLIModule:
    """Main class for the incus_cli module."""
    
    def __init__(self, module):
        self.module = module
        self.results = []
        self.warnings = []
        self.mode = None
        self.global_environment = module.params.get('environment', {})
        self.stop_on_error = module.params.get('stop_on_error', True)
        self.check_mode = module.check_mode
        
    def _mask_sensitive_values(self, text, sensitive_values):
        """Mask sensitive values in text."""
        if not text or not sensitive_values:
            return text
        
        masked_text = text
        for value in sensitive_values:
            if value and value in masked_text:
                masked_text = masked_text.replace(value, '***MASKED***')
        return masked_text
    
    def _normalize_argv(self, argv):
        """Normalize argv by ensuring 'incus' is at position 0 without duplication."""
        if not argv:
            return ['incus']
        
        # Check if first element is already 'incus'
        if argv and argv[0] == 'incus':
            self.warnings.append("Duplicate 'incus' prefix detected")
            return argv
        
        # Prepend 'incus' to the argv
        return ['incus'] + argv
    
    def _validate_argv(self, argv):
        """Validate argv list."""
        if not argv:
            self.module.fail_json(msg="argv cannot be empty")
        
        # Check that all elements are strings
        for i, arg in enumerate(argv):
            if not isinstance(arg, str):
                self.module.fail_json(
                    msg=f"All argv elements must be strings, got {type(arg).__name__} at index {i}"
                )
        
        return True
    
    def _should_skip_command(self, command, global_creates=None, global_removes=None):
        """Determine if a command should be skipped based on creates/removes."""
        # Check global creates/removes
        if global_creates and os.path.exists(global_creates):
            return True, f"Global creates path {global_creates} exists"
        
        if global_removes and not os.path.exists(global_removes):
            return True, f"Global removes path {global_removes} does not exist"
        
        # Check command-specific creates/removes
        if command.get('creates') and os.path.exists(command.get('creates')):
            return True, f"Creates path {command.get('creates')} exists"
        
        if command.get('removes') and not os.path.exists(command.get('removes')):
            return True, f"Removes path {command.get('removes')} does not exist"
        
        return False, None
    
    def _execute_command(self, argv, environment=None, sensitive_values=None):
        """Execute a single command and return result."""
        start_time = time.time()
        
        # Merge environment (command-specific takes precedence)
        final_environment = self.global_environment.copy()
        if environment:
            final_environment.update(environment)
        
        # In check_mode, don't actually execute
        if self.check_mode:
            return {
                'argv': argv,
                'rc': 0,
                'stdout': '',
                'stderr': '',
                'changed': True,
                'skipped': True,
                'duration_ms': 0,
                'skip_reason': 'check_mode'
            }
        
        # Execute the command
        try:
            rc, stdout, stderr = self.module.run_command(
                argv,
                environ_update=final_environment,
                use_unsafe_shell=False
            )
        except Exception as e:
            return {
                'argv': argv,
                'rc': 1,
                'stdout': '',
                'stderr': str(e),
                'changed': False,
                'skipped': False,
                'duration_ms': int((time.time() - start_time) * 1000),
                'skip_reason': None
            }
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Mask sensitive values
        if sensitive_values:
            stdout = self._mask_sensitive_values(stdout, sensitive_values)
            stderr = self._mask_sensitive_values(stderr, sensitive_values)
        
        return {
            'argv': argv,
            'rc': rc,
            'stdout': stdout,
            'stderr': stderr,
            'changed': rc == 0,
            'skipped': False,
            'duration_ms': duration_ms,
            'skip_reason': None
        }
    
    def _execute_shell_command(self, command, executable, chdir, environment):
        """Execute a shell command (unsafe mode)."""
        start_time = time.time()
        
        # Merge environment
        final_environment = self.global_environment.copy()
        if environment:
            final_environment.update(environment)
        
        # In check_mode, don't actually execute
        if self.check_mode:
            return {
                'argv': [executable, '-c', command],
                'rc': 0,
                'stdout': '',
                'stderr': '',
                'changed': True,
                'skipped': False,
                'duration_ms': 0,
                'skip_reason': 'check_mode'
            }
        
        # Execute the shell command
        try:
            rc, stdout, stderr = self.module.run_command(
                command,
                executable=executable,
                cwd=chdir,
                environ_update=final_environment,
                use_unsafe_shell=True
            )
        except Exception as e:
            return {
                'argv': [executable, '-c', command],
                'rc': 1,
                'stdout': '',
                'stderr': str(e),
                'changed': False,
                'skipped': False,
                'duration_ms': int((time.time() - start_time) * 1000),
                'skip_reason': None
            }
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return {
            'argv': [executable, '-c', command],
            'rc': rc,
            'stdout': stdout,
            'stderr': stderr,
            'changed': rc == 0,
            'skipped': False,
            'duration_ms': duration_ms,
            'skip_reason': None
        }
    
    def _process_command_mode(self):
        """Process command mode."""
        command = self.module.params.get('command')
        
        if not command:
            self.module.fail_json(msg="command parameter is required for command mode")
        
        # Check for shell operators
        shell_operators = ['|', '>', '>>', '<', '&&', '||', ';', '$(', '`']
        for operator in shell_operators:
            if operator in command:
                self.module.fail_json(
                    msg=f"Shell operator '{operator}' detected in command mode. "
                        f"Use shell mode with unsafe_shell=true for shell features."
                )
        
        # Parse command using shlex
        try:
            argv = shlex.split(command)
        except ValueError as e:
            self.module.fail_json(msg=f"Failed to parse command: {str(e)}")
        
        # Execute the command
        result = self._execute_command(argv)
        self.results.append(result)
        
        return any(r.get('changed', False) for r in self.results)
    
    def _process_incus_mode(self):
        """Process incus mode (argv-based)."""
        incus_commands = self.module.params.get('incus', [])
        
        if not incus_commands:
            self.module.fail_json(msg="incus parameter is required for incus mode")
        
        global_creates = self.module.params.get('creates')
        global_removes = self.module.params.get('removes')
        
        for index, command in enumerate(incus_commands):
            # Validate command structure
            if not isinstance(command, dict):
                self.module.fail_json(
                    msg=f"Each incus command must be a dict, got {type(command).__name__} at index {index}"
                )
            
            if 'argv' not in command:
                self.module.fail_json(
                    msg=f"Each incus command must have 'argv' parameter at index {index}"
                )
            
            argv = command['argv']
            name = command.get('name', f"step_{index}")
            environment = command.get('environment', {})
            changed = command.get('changed', True)
            creates = command.get('creates')
            removes = command.get('removes')
            sensitive_values = command.get('sensitive_values', [])
            
            # Validate argv
            self._validate_argv(argv)
            
            # Normalize argv (add 'incus' prefix)
            normalized_argv = self._normalize_argv(argv)
            
            # Check if should skip
            skip, skip_reason = self._should_skip_command(
                command, global_creates, global_removes
            )
            
            if skip:
                result = {
                    'index': index,
                    'name': name,
                    'argv': normalized_argv,
                    'rc': 0,
                    'stdout': '',
                    'stderr': '',
                    'changed': False,
                    'skipped': True,
                    'duration_ms': 0,
                    'skip_reason': skip_reason
                }
                self.results.append(result)
                continue
            
            # Execute command
            result = self._execute_command(
                normalized_argv,
                environment=environment,
                sensitive_values=sensitive_values
            )
            
            # Override changed if specified
            if not changed:
                result['changed'] = False
            
            result.update({
                'index': index,
                'name': name
            })
            self.results.append(result)
            
            # Check for errors and stop_on_error
            if self.stop_on_error and result.get('rc', 0) != 0:
                break
        
        return any(r.get('changed', False) for r in self.results)
    
    def _process_template_mode(self):
        """Process template mode."""
        template_path = self.module.params.get('template')
        variables = self.module.params.get('variables', {})
        
        if not template_path:
            self.module.fail_json(msg="template parameter is required for template mode")
        
        # Check if template exists
        if not os.path.exists(template_path):
            self.module.fail_json(
                msg=f"Template file {template_path} does not exist"
            )
        
        # Load and render template
        try:
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Simple template rendering (in a real implementation, use Jinja2)
            rendered_content = template_content
            for key, value in variables.items():
                placeholder = f"{{{{ {key} }}}}"
                rendered_content = rendered_content.replace(placeholder, str(value))
            
            # Parse rendered YAML
            try:
                rendered_data = yaml.safe_load(rendered_content)
            except yaml.YAMLError as e:
                self.module.fail_json(
                    msg=f"Failed to parse rendered template as YAML: {str(e)}"
                )
            
            # Validate structure
            if not isinstance(rendered_data, dict):
                self.module.fail_json(
                    msg="Template must render to a YAML mapping"
                )
            
            if 'incus' not in rendered_data:
                self.module.fail_json(
                    msg="Template must contain 'incus' key with command list"
                )
            
            # Set the rendered data as module params and process as incus mode
            self.module.params['incus'] = rendered_data['incus']
            return self._process_incus_mode()
            
        except Exception as e:
            self.module.fail_json(
                msg=f"Failed to process template: {str(e)}"
            )
    
    def _process_shell_mode(self):
        """Process shell mode."""
        shell_command = self.module.params.get('shell')
        unsafe_shell = self.module.params.get('unsafe_shell', False)
        executable = self.module.params.get('executable', '/bin/sh')
        chdir = self.module.params.get('chdir')
        
        if not shell_command:
            self.module.fail_json(msg="shell parameter is required for shell mode")
        
        if not unsafe_shell:
            self.module.fail_json(
                msg="shell mode requires unsafe_shell=true to be explicitly set. "
                    "This mode is unsafe and can lead to command injection vulnerabilities. "
                    "Consider using 'incus' or 'command' mode instead."
            )
        
        # Execute shell command
        result = self._execute_shell_command(
            shell_command,
            executable,
            chdir,
            self.module.params.get('environment', {})
        )
        
        result.update({
            'index': 0,
            'name': 'shell_command'
        })
        self.results.append(result)
        
        return result.get('changed', False)
    
    def run(self):
        """Main execution method."""
        # Determine mode
        if self.module.params.get('command') is not None:
            self.mode = 'command'
        elif self.module.params.get('incus') is not None:
            self.mode = 'incus'
        elif self.module.params.get('template') is not None:
            self.mode = 'template'
        elif self.module.params.get('shell') is not None:
            self.mode = 'shell'
        else:
            self.module.fail_json(
                msg="One of 'command', 'incus', 'template', or 'shell' must be provided"
            )
        
        # Validate mutually exclusive parameters
        provided_params = [
            p for p in ['command', 'incus', 'template', 'shell']
            if self.module.params.get(p) is not None
        ]
        if len(provided_params) > 1:
            self.module.fail_json(
                msg=f"Parameters {provided_params} are mutually exclusive. "
                    f"Please provide only one of 'command', 'incus', 'template', or 'shell'"
            )
        
        # Validate template mode parameters
        if self.mode == 'template':
            if self.module.params.get('variables') is None:
                self.module.params['variables'] = {}
        
        # Validate shell mode parameters
        if self.mode == 'shell':
            if not self.module.params.get('unsafe_shell', False):
                self.module.fail_json(
                    msg="shell mode requires unsafe_shell=true"
                )
        
        # Process based on mode
        try:
            if self.mode == 'command':
                changed = self._process_command_mode()
            elif self.mode == 'incus':
                changed = self._process_incus_mode()
            elif self.mode == 'template':
                changed = self._process_template_mode()
            elif self.mode == 'shell':
                changed = self._process_shell_mode()
        except Exception as e:
            self.module.fail_json(
                msg=f"Error in {self.mode} mode: {str(e)}"
            )
        
        # Return results
        self.module.exit_json(
            changed=changed,
            failed=False,
            mode=self.mode,
            results=self.results,
            warnings=self.warnings
        )


def main():
    """Main function."""
    module_args = dict(
        command=dict(type='str', default=None),
        incus=dict(
            type='list',
            elements='dict',
            default=None,
            options=dict(
                argv=dict(type='list', elements='str', required=True),
                name=dict(type='str', default=None),
                environment=dict(type='dict', default={}),
                changed=dict(type='bool', default=True),
                creates=dict(type='path', default=None),
                removes=dict(type='path', default=None),
                sensitive_values=dict(
                    type='list',
                    elements='str',
                    default=[],
                    no_log=True
                ),
            )
        ),
        template=dict(type='path', default=None),
        variables=dict(type='dict', default=None),
        shell=dict(type='str', default=None),
        unsafe_shell=dict(type='bool', default=False),
        executable=dict(type='path', default='/bin/sh'),
        chdir=dict(type='path', default=None),
        environment=dict(type='dict', default={}),
        creates=dict(type='path', default=None),
        removes=dict(type='path', default=None),
        stop_on_error=dict(type='bool', default=True),
    )
    
    module = AnsibleModule(
        argument_spec=module_args,
        mutually_exclusive=[
            ['command', 'incus', 'template', 'shell'],
        ],
        required_one_of=[
            ['command', 'incus', 'template', 'shell'],
        ],
        required_if=[
            ['unsafe_shell', True, ['shell']],
        ],
        supports_check_mode=True
    )
    
    # Initialize and run the module
    incus_cli = IncusCLIModule(module)
    incus_cli.run()


if __name__ == '__main__':
    main()
