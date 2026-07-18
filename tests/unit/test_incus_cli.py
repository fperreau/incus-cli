#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for the incus_cli module.
These tests verify the functionality of the module without requiring
a real Incus installation.
"""

import unittest
import os
import sys
import tempfile
import yaml
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path

# Add the library directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'library'))

# Import the module (we'll mock Ansible components)
import incus_cli


class TestIncusCLIModule(unittest.TestCase):
    """Test cases for the IncusCLIModule class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_module = MagicMock()
        self.mock_module.params = {}
        self.mock_module.check_mode = False
        self.mock_module.fail_json = MagicMock(side_effect=Exception("fail_json called"))
        self.mock_module.exit_json = MagicMock()
        self.mock_module.run_command = MagicMock(return_value=(0, "", ""))
        
        # Create instance
        self.module = incus_cli.IncusCLIModule(self.mock_module)
    
    def test_normalize_argv_adds_incus(self):
        """Test that normalize_argv adds 'incus' prefix."""
        argv = ['start', 'my-container']
        normalized = self.module._normalize_argv(argv)
        self.assertEqual(normalized, ['incus', 'start', 'my-container'])
    
    def test_normalize_argv_no_duplicate(self):
        """Test that normalize_argv doesn't duplicate 'incus'."""
        argv = ['incus', 'start', 'my-container']
        normalized = self.module._normalize_argv(argv)
        self.assertEqual(normalized, ['incus', 'start', 'my-container'])
        self.assertIn("Duplicate 'incus' prefix detected", self.module.warnings)
    
    def test_normalize_argv_empty(self):
        """Test that normalize_argv handles empty list."""
        argv = []
        normalized = self.module._normalize_argv(argv)
        self.assertEqual(normalized, ['incus'])
    
    def test_validate_argv_valid(self):
        """Test that validate_argv accepts valid argv."""
        argv = ['start', 'my-container']
        result = self.module._validate_argv(argv)
        self.assertTrue(result)
    
    def test_validate_argv_empty(self):
        """Test that validate_argv rejects empty argv."""
        argv = []
        with self.assertRaises(Exception):
            self.module._validate_argv(argv)
    
    def test_validate_argv_non_string(self):
        """Test that validate_argv rejects non-string elements."""
        argv = ['start', 123]
        with self.assertRaises(Exception):
            self.module._validate_argv(argv)
    
    def test_mask_sensitive_values(self):
        """Test that sensitive values are masked."""
        text = "password=secret123 and token=abc123"
        sensitive = ['secret123', 'abc123']
        masked = self.module._mask_sensitive_values(text, sensitive)
        self.assertNotIn('secret123', masked)
        self.assertNotIn('abc123', masked)
        self.assertIn('***MASKED***', masked)
    
    def test_mask_sensitive_values_none(self):
        """Test that mask_sensitive_values handles None inputs."""
        text = None
        sensitive = ['secret']
        masked = self.module._mask_sensitive_values(text, sensitive)
        self.assertIsNone(masked)
    
    def test_should_skip_command_global_creates(self):
        """Test should_skip_command with global creates."""
        # Mock os.path.exists to return True
        with patch('os.path.exists', return_value=True):
            skip, reason = self.module._should_skip_command(
                {}, global_creates='/tmp/test'
            )
            self.assertTrue(skip)
            self.assertIn('/tmp/test', reason)
    
    def test_should_skip_command_command_creates(self):
        """Test should_skip_command with command-specific creates."""
        with patch('os.path.exists', return_value=True):
            command = {'creates': '/tmp/test'}
            skip, reason = self.module._should_skip_command(command)
            self.assertTrue(skip)
            self.assertIn('/tmp/test', reason)
    
    def test_should_skip_command_global_removes(self):
        """Test should_skip_command with global removes."""
        with patch('os.path.exists', return_value=False):
            skip, reason = self.module._should_skip_command(
                {}, global_removes='/tmp/test'
            )
            self.assertTrue(skip)
            self.assertIn('/tmp/test', reason)
    
    def test_execute_command_success(self):
        """Test execute_command with successful execution."""
        self.mock_module.run_command.return_value = (0, "success", "")
        
        result = self.module._execute_command(['incus', 'list'])
        
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['stdout'], "success")
        self.assertTrue(result['changed'])
        self.assertEqual(result['argv'], ['incus', 'list'])
    
    def test_execute_command_failure(self):
        """Test execute_command with failed execution."""
        self.mock_module.run_command.return_value = (1, "", "error occurred")
        
        result = self.module._execute_command(['incus', 'start', 'nonexistent'])
        
        self.assertEqual(result['rc'], 1)
        self.assertEqual(result['stderr'], "error occurred")
        self.assertFalse(result['changed'])
    
    def test_execute_command_check_mode(self):
        """Test execute_command in check_mode."""
        self.module.check_mode = True
        
        result = self.module._execute_command(['incus', 'start', 'container'])
        
        self.assertTrue(result['skipped'])
        self.assertEqual(result['skip_reason'], 'check_mode')
        self.assertEqual(result['changed'], True)
        
        # Verify run_command was not called
        self.mock_module.run_command.assert_not_called()
    
    def test_execute_command_with_sensitive_values(self):
        """Test execute_command masks sensitive values."""
        self.mock_module.run_command.return_value = (0, "password=secret", "")
        
        result = self.module._execute_command(
            ['incus', 'exec', 'container'],
            sensitive_values=['secret']
        )
        
        self.assertNotIn('secret', result['stdout'])
        self.assertIn('***MASKED***', result['stdout'])
    
    def test_process_command_mode_success(self):
        """Test process_command_mode with valid command."""
        self.mock_module.params['command'] = "incus list"
        
        changed = self.module._process_command_mode()
        
        self.assertTrue(changed)
        self.assertEqual(len(self.module.results), 1)
        self.assertEqual(self.module.results[0]['argv'], ['incus', 'list'])
    
    def test_process_command_mode_with_shell_operator(self):
        """Test process_command_mode rejects shell operators."""
        self.mock_module.params['command'] = "incus list | grep running"
        
        with self.assertRaises(Exception):
            self.module._process_command_mode()
    
    def test_process_command_mode_invalid_command(self):
        """Test process_command_mode with invalid command syntax."""
        self.mock_module.params['command'] = "incus list \"unclosed quote"
        
        with self.assertRaises(Exception):
            self.module._process_command_mode()
    
    def test_process_incus_mode_success(self):
        """Test process_incus_mode with multiple commands."""
        self.mock_module.params['incus'] = [
            {'argv': ['start', 'container1']},
            {'argv': ['stop', 'container2']}
        ]
        
        changed = self.module._process_incus_mode()
        
        self.assertTrue(changed)
        self.assertEqual(len(self.module.results), 2)
        # First command should have 'incus' prepended
        self.assertEqual(self.module.results[0]['argv'], ['incus', 'start', 'container1'])
        self.assertEqual(self.module.results[1]['argv'], ['incus', 'stop', 'container2'])
    
    def test_process_incus_mode_with_duplicate_incus(self):
        """Test process_incus_mode handles duplicate incus prefix."""
        self.mock_module.params['incus'] = [
            {'argv': ['incus', 'start', 'container1']}
        ]
        
        changed = self.module._process_incus_mode()
        
        self.assertTrue(changed)
        self.assertEqual(self.module.results[0]['argv'], ['incus', 'start', 'container1'])
        self.assertIn("Duplicate 'incus' prefix detected", self.module.warnings)
    
    def test_process_incus_mode_with_creates(self):
        """Test process_incus_mode skips commands when creates path exists."""
        with patch('os.path.exists', return_value=True):
            self.mock_module.params['incus'] = [
                {'argv': ['start', 'container1'], 'creates': '/tmp/test'}
            ]
            
            changed = self.module._process_incus_mode()
            
            self.assertFalse(changed)
            self.assertTrue(self.module.results[0]['skipped'])
            self.assertIn('/tmp/test', self.module.results[0]['skip_reason'])
    
    def test_process_incus_mode_stop_on_error(self):
        """Test process_incus_mode stops on error when configured."""
        # First command succeeds, second fails
        self.mock_module.run_command.side_effect = [
            (0, "", ""),
            (1, "", "error")
        ]
        
        self.mock_module.params['incus'] = [
            {'argv': ['start', 'container1']},
            {'argv': ['stop', 'container2']}
        ]
        self.mock_module.params['stop_on_error'] = True
        
        changed = self.module._process_incus_mode()
        
        # Should only execute first command due to stop_on_error
        self.assertEqual(len(self.module.results), 2)
        self.assertEqual(self.module.results[0]['rc'], 0)
        self.assertEqual(self.module.results[1]['rc'], 1)
    
    def test_process_incus_mode_continue_on_error(self):
        """Test process_incus_mode continues on error when configured."""
        # Mock run_command to return different results for each call
        call_count = [0]
        def mock_run_command(argv, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return (1, "", "error")
            else:
                return (0, "", "")
        
        self.mock_module.run_command = mock_run_command
        
        self.mock_module.params['incus'] = [
            {'argv': ['start', 'container1']},
            {'argv': ['stop', 'container2']}
        ]
        self.mock_module.params['stop_on_error'] = False
        
        # Recreate the module with the new run_command
        self.module = incus_cli.IncusCLIModule(self.mock_module)
        
        changed = self.module._process_incus_mode()
        
        # Should execute both commands
        self.assertEqual(len(self.module.results), 2)
        self.assertEqual(self.module.results[0]['rc'], 1)
        self.assertEqual(self.module.results[1]['rc'], 0)
    
    def test_process_template_mode_success(self):
        """Test process_template_mode with valid template."""
        # Create a temporary template file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml.j2', delete=False) as f:
            f.write("""---
incus:
  - argv:
      - start
      - "{{ container_name }}"
""")
            template_path = f.name
        
        try:
            self.mock_module.params['template'] = template_path
            self.mock_module.params['variables'] = {'container_name': 'test-container'}
            
            changed = self.module._process_template_mode()
            
            self.assertTrue(changed)
            self.assertEqual(len(self.module.results), 1)
            self.assertEqual(
                self.module.results[0]['argv'],
                ['incus', 'start', 'test-container']
            )
        finally:
            os.unlink(template_path)
    
    def test_process_template_mode_missing_file(self):
        """Test process_template_mode with missing template file."""
        self.mock_module.params['template'] = '/nonexistent/template.yml.j2'
        
        with self.assertRaises(Exception):
            self.module._process_template_mode()
    
    def test_process_template_mode_invalid_yaml(self):
        """Test process_template_mode with invalid YAML template."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml.j2', delete=False) as f:
            f.write("invalid: yaml: content:")
            template_path = f.name
        
        try:
            self.mock_module.params['template'] = template_path
            self.mock_module.params['variables'] = {}
            
            with self.assertRaises(Exception):
                self.module._process_template_mode()
        finally:
            os.unlink(template_path)
    
    def test_process_template_mode_missing_incus_key(self):
        """Test process_template_mode with template missing incus key."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml.j2', delete=False) as f:
            f.write("""---
commands:
  - argv:
      - start
      - container
""")
            template_path = f.name
        
        try:
            self.mock_module.params['template'] = template_path
            self.mock_module.params['variables'] = {}
            
            with self.assertRaises(Exception):
                self.module._process_template_mode()
        finally:
            os.unlink(template_path)
    
    def test_process_shell_mode_without_consent(self):
        """Test process_shell_mode fails without unsafe_shell=true."""
        self.mock_module.params['shell'] = "incus list"
        self.mock_module.params['unsafe_shell'] = False
        
        with self.assertRaises(Exception):
            self.module._process_shell_mode()
    
    def test_process_shell_mode_with_consent(self):
        """Test process_shell_mode with unsafe_shell=true."""
        self.mock_module.params['shell'] = "incus list --format json > /tmp/output.json"
        self.mock_module.params['unsafe_shell'] = True
        self.mock_module.params['executable'] = '/bin/sh'
        self.mock_module.params['chdir'] = '/tmp'
        
        changed = self.module._process_shell_mode()
        
        self.assertTrue(changed)
        self.assertEqual(len(self.module.results), 1)
        # Verify run_command was called with use_unsafe_shell=True
        call_args = self.mock_module.run_command.call_args
        self.assertTrue(call_args[1].get('use_unsafe_shell', False))
    
    def test_mode_detection(self):
        """Test that the module correctly detects the mode."""
        # Test command mode
        self.mock_module.params['command'] = "incus list"
        self.module.run()
        self.assertEqual(self.module.mode, 'command')
        
        # Test incus mode
        self.mock_module.params = {'incus': [{'argv': ['list']}]}
        self.module = incus_cli.IncusCLIModule(self.mock_module)
        self.module.run()
        self.assertEqual(self.module.mode, 'incus')
        
        # Test template mode
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml.j2', delete=False) as f:
            f.write("---\nincus:\n  - argv:\n      - list\n")
            template_path = f.name
        
        try:
            self.mock_module.params = {'template': template_path, 'variables': {}}
            self.module = incus_cli.IncusCLIModule(self.mock_module)
            self.module.run()
            self.assertEqual(self.module.mode, 'template')
        finally:
            os.unlink(template_path)
        
        # Test shell mode
        self.mock_module.params = {'shell': 'incus list', 'unsafe_shell': True}
        self.module = incus_cli.IncusCLIModule(self.mock_module)
        self.module.run()
        self.assertEqual(self.module.mode, 'shell')
    
    def test_mutually_exclusive_parameters(self):
        """Test that mutually exclusive parameters are enforced."""
        self.mock_module.params = {
            'command': 'incus list',
            'incus': [{'argv': ['list']}]
        }
        
        with self.assertRaises(Exception):
            self.module.run()
    
    def test_required_one_of_parameters(self):
        """Test that at least one mode parameter is required."""
        self.mock_module.params = {}
        
        with self.assertRaises(Exception):
            self.module.run()


class TestTheBastionDeployment(unittest.TestCase):
    """Test cases specific to The Bastion deployment scenario."""
    
    def setUp(self):
        """Set up test fixtures for The Bastion deployment."""
        self.mock_module = MagicMock()
        self.mock_module.params = {}
        self.mock_module.check_mode = False
        self.mock_module.fail_json = MagicMock(side_effect=Exception("fail_json called"))
        self.mock_module.exit_json = MagicMock()
        self.mock_module.run_command = MagicMock(return_value=(0, "", ""))
        
        self.module = incus_cli.IncusCLIModule(self.mock_module)
    
    def test_bastion_container_creation(self):
        """Test The Bastion container creation command."""
        bastion_commands = [
            {
                'argv': [
                    'launch',
                    'docker:the-bastion/the-bastion:latest',
                    'the_bastion',
                    '--storage',
                    'default',
                    '-c',
                    'limits.cpu=2',
                    '-c',
                    'limits.memory=2GiB'
                ],
                'name': 'Launch The Bastion container'
            }
        ]
        
        self.mock_module.params['incus'] = bastion_commands
        
        changed = self.module._process_incus_mode()
        
        self.assertTrue(changed)
        self.assertEqual(len(self.module.results), 1)
        
        # Verify the command was normalized correctly
        result = self.module.results[0]
        self.assertEqual(result['name'], 'Launch The Bastion container')
        self.assertEqual(result['argv'][0], 'incus')
        self.assertEqual(result['argv'][1], 'launch')
        self.assertIn('docker:the-bastion/the-bastion:latest', result['argv'])
        self.assertIn('the_bastion', result['argv'])
    
    def test_bastion_volume_attachment(self):
        """Test volume attachment for The Bastion."""
        volume_commands = [
            {
                'argv': [
                    'storage',
                    'volume',
                    'attach',
                    'default',
                    'bastion_data',
                    'the_bastion',
                    '/var/lib/bastion'
                ],
                'name': 'Attach data volume'
            }
        ]
        
        self.mock_module.params['incus'] = volume_commands
        
        changed = self.module._process_incus_mode()
        
        self.assertTrue(changed)
        result = self.module.results[0]
        self.assertEqual(result['name'], 'Attach data volume')
        self.assertIn('storage', result['argv'])
        self.assertIn('volume', result['argv'])
        self.assertIn('attach', result['argv'])
    
    def test_bastion_network_configuration(self):
        """Test network configuration for The Bastion."""
        network_commands = [
            {
                'argv': [
                    'network',
                    'create',
                    'bastion_net',
                    '--type',
                    'bridge',
                    'ipv4.address=192.168.1.100/24',
                    'ipv4.gateway=192.168.1.1'
                ],
                'name': 'Create bastion network'
            }
        ]
        
        self.mock_module.params['incus'] = network_commands
        
        changed = self.module._process_incus_mode()
        
        self.assertTrue(changed)
        result = self.module.results[0]
        self.assertEqual(result['name'], 'Create bastion network')
        self.assertIn('network', result['argv'])
        self.assertIn('create', result['argv'])
        self.assertIn('bastion_net', result['argv'])
    
    def test_bastion_resource_limits(self):
        """Test resource limit configuration for The Bastion."""
        limit_commands = [
            {
                'argv': [
                    'config',
                    'set',
                    'the_bastion',
                    'limits.cpu=2'
                ],
                'name': 'Set CPU limit'
            },
            {
                'argv': [
                    'config',
                    'set',
                    'the_bastion',
                    'limits.memory=2GiB'
                ],
                'name': 'Set memory limit'
            },
            {
                'argv': [
                    'config',
                    'set',
                    'the_bastion',
                    'limits.disk=10GiB'
                ],
                'name': 'Set disk limit'
            }
        ]
        
        self.mock_module.params['incus'] = limit_commands
        
        changed = self.module._process_incus_mode()
        
        self.assertTrue(changed)
        self.assertEqual(len(self.module.results), 3)
        
        # Verify all limit commands were processed
        for result in self.module.results:
            self.assertIn('config', result['argv'])
            self.assertIn('set', result['argv'])
            self.assertIn('the_bastion', result['argv'])
    
    def test_bastion_ssh_configuration(self):
        """Test SSH configuration for The Bastion."""
        ssh_commands = [
            {
                'argv': [
                    'config',
                    'device',
                    'add',
                    'the_bastion',
                    'ssh',
                    'proxy',
                    'listen=tcp:0.0.0.0:2222',
                    'connect=tcp:127.0.0.1:22'
                ],
                'name': 'Configure SSH proxy'
            }
        ]
        
        self.mock_module.params['incus'] = ssh_commands
        
        changed = self.module._process_incus_mode()
        
        self.assertTrue(changed)
        result = self.module.results[0]
        self.assertEqual(result['name'], 'Configure SSH proxy')
        self.assertIn('config', result['argv'])
        self.assertIn('device', result['argv'])
        self.assertIn('add', result['argv'])


class TestIdempotency(unittest.TestCase):
    """Test cases for idempotency features."""
    
    def setUp(self):
        """Set up test fixtures for idempotency tests."""
        self.mock_module = MagicMock()
        self.mock_module.params = {}
        self.mock_module.check_mode = False
        self.mock_module.fail_json = MagicMock(side_effect=Exception("fail_json called"))
        self.mock_module.exit_json = MagicMock()
        self.mock_module.run_command = MagicMock(return_value=(0, "", ""))
        
        self.module = incus_cli.IncusCLIModule(self.mock_module)
    
    def test_creates_skips_when_exists(self):
        """Test that commands are skipped when creates path exists."""
        with patch('os.path.exists', return_value=True):
            self.mock_module.params['incus'] = [
                {
                    'argv': ['start', 'container'],
                    'creates': '/tmp/container_started'
                }
            ]
            
            changed = self.module._process_incus_mode()
            
            self.assertFalse(changed)
            self.assertTrue(self.module.results[0]['skipped'])
            # Verify run_command was not called
            self.mock_module.run_command.assert_not_called()
    
    def test_removes_skips_when_not_exists(self):
        """Test that commands are skipped when removes path doesn't exist."""
        with patch('os.path.exists', return_value=False):
            self.mock_module.params['incus'] = [
                {
                    'argv': ['stop', 'container'],
                    'removes': '/tmp/container_stopped'
                }
            ]
            
            changed = self.module._process_incus_mode()
            
            self.assertFalse(changed)
            self.assertTrue(self.module.results[0]['skipped'])
    
    def test_check_mode_no_execution(self):
        """Test that check_mode doesn't execute commands."""
        self.module.check_mode = True
        
        self.mock_module.params['incus'] = [
            {'argv': ['start', 'container']}
        ]
        
        changed = self.module._process_incus_mode()
        
        self.assertTrue(changed)
        self.assertTrue(self.module.results[0]['skipped'])
        self.assertEqual(self.module.results[0]['skip_reason'], 'check_mode')
        # Verify run_command was not called
        self.mock_module.run_command.assert_not_called()
    
    def test_changed_false_no_change(self):
        """Test that commands with changed=false don't report changes."""
        self.mock_module.params['incus'] = [
            {
                'argv': ['list'],
                'changed': False
            }
        ]
        
        changed = self.module._process_incus_mode()
        
        self.assertFalse(changed)
        self.assertFalse(self.module.results[0]['changed'])


if __name__ == '__main__':
    unittest.main()
