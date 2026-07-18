# -*- coding: utf-8 -*-
"""
Tests unitaires pour le mode shell du module incus_cli
Incrément 5: Mode shell
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Ajouter les chemins pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from library.incus_cli import (
    validate_module_args,
    execute_shell_step,
    mask_sensitive_values,
)


class MockAnsibleModule:
    """Mock pour AnsibleModule"""
    
    def __init__(self, params=None, check_mode=False):
        self.params = params or {}
        self.check_mode = check_mode
        self.run_command_calls = []
    
    def run_command(self, cmd, **kwargs):
        """Mock de run_command"""
        self.run_command_calls.append({
            "cmd": cmd,
            "kwargs": kwargs
        })
        # Retourner un résultat par défaut
        return 0, "output", ""


class TestShellModeValidation:
    """Tests pour la validation du mode shell"""

    def test_shell_without_unsafe_shell_rejected(self):
        """Doit rejeter shell sans unsafe_shell=true"""
        module = MockAnsibleModule(params={
            "shell": "incus list --format json > file.txt"
        })
        valid, error = validate_module_args(module)
        assert not valid
        assert "'shell' mode requires 'unsafe_shell: true'" in error

    def test_shell_with_unsafe_shell_accepted(self):
        """Doit accepter shell avec unsafe_shell=true"""
        module = MockAnsibleModule(params={
            "shell": "incus list --format json > file.txt",
            "unsafe_shell": True
        })
        valid, error = validate_module_args(module)
        assert valid
        assert error is None

    def test_unsafe_shell_without_shell_rejected(self):
        """Doit rejeter unsafe_shell sans shell"""
        module = MockAnsibleModule(params={
            "unsafe_shell": True,
            "command": "incus start web01"
        })
        valid, error = validate_module_args(module)
        assert not valid
        assert "'unsafe_shell' can only be used with 'shell' mode" in error

    def test_shell_with_redirection_accepted(self):
        """Doit accepter shell avec redirection"""
        module = MockAnsibleModule(params={
            "shell": "incus list --format json > /tmp/list.json",
            "unsafe_shell": True
        })
        valid, error = validate_module_args(module)
        assert valid
        assert error is None

    def test_shell_with_pipe_accepted(self):
        """Doit accepter shell avec pipe"""
        module = MockAnsibleModule(params={
            "shell": "incus list | grep web01",
            "unsafe_shell": True
        })
        valid, error = validate_module_args(module)
        assert valid
        assert error is None


class TestExecuteShellStep:
    """Tests pour l'exécution du mode shell"""

    def test_uses_unsafe_shell(self):
        """Doit utiliser use_unsafe_shell=True"""
        module = MockAnsibleModule()
        
        result = execute_shell_step(
            module,
            "incus list",
            executable="/bin/sh"
        )
        
        # Vérifier que run_command a été appelé avec use_unsafe_shell=True
        assert len(module.run_command_calls) > 0
        assert module.run_command_calls[0]["kwargs"].get("use_unsafe_shell") == True

    def test_respects_executable(self):
        """Doit respecter le paramètre executable"""
        module = MockAnsibleModule()
        
        execute_shell_step(
            module,
            "incus list",
            executable="/bin/bash"
        )
        
        assert module.run_command_calls[0]["kwargs"].get("executable") == "/bin/bash"

    def test_respects_chdir(self):
        """Doit respecter le paramètre chdir"""
        module = MockAnsibleModule()
        
        execute_shell_step(
            module,
            "incus list",
            chdir="/tmp"
        )
        
        assert module.run_command_calls[0]["kwargs"].get("cwd") == "/tmp"

    def test_respects_environment(self):
        """Doit respecter le paramètre environment"""
        module = MockAnsibleModule()
        
        execute_shell_step(
            module,
            "incus list",
            global_environment={"VAR1": "value1", "VAR2": "value2"}
        )
        
        env = module.run_command_calls[0]["kwargs"].get("environ_update")
        assert env["VAR1"] == "value1"
        assert env["VAR2"] == "value2"

    def test_masks_sensitive_values(self):
        """Doit masquer les valeurs sensibles"""
        module = MockAnsibleModule()
        module.run_command = Mock(return_value=(0, "Password: secret123", "Error: secret123"))
        
        result = execute_shell_step(
            module,
            "incus start web01 --password secret123",
            sensitive_values=["secret123"]
        )
        
        assert "secret123" not in result.stdout
        assert "secret123" not in result.stderr
        assert "***SENSITIVE***" in result.stdout
        assert "***SENSITIVE***" in result.stderr


class TestMaskSensitiveValues:
    """Tests pour le masquage des valeurs sensibles"""

    def test_mask_multiple_occurrences(self):
        """Doit masquer toutes les occurrences"""
        text = "secret123 and secret123 and secret123"
        result = mask_sensitive_values(text, ["secret123"])
        assert text.count("secret123") == 3
        assert result.count("***SENSITIVE***") == 3
        assert "secret123" not in result

    def test_mask_preserves_structure(self):
        """Doit préserver la structure du texte"""
        text = "Password: secret123, Token: tok456"
        result = mask_sensitive_values(text, ["secret123", "tok456"])
        # La structure (positions des : et ,) doit être préservée
        assert result.startswith("Password: ")
        assert ", Token: " in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
