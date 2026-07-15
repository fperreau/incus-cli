# -*- coding: utf-8 -*-
"""
Tests unitaires pour les utilitaires du module incus_cli
Incrément 1: Normalisation argv
"""

import pytest
import sys
import os

# Ajouter les chemins pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from module_utils.incus_cli import (
    normalize_argv,
    validate_argv,
    contains_shell_operators,
    parse_command_string,
    mask_sensitive_values,
    merge_environments,
    INCUS_BINARY,
)


class TestNormalizeArgv:
    """Tests pour la fonction normalize_argv"""

    def test_add_incus_prefix(self):
        """Doit ajouter 'incus' en position 0"""
        result = normalize_argv(["start", "web01"])
        assert result == ["incus", "start", "web01"]

    def test_no_duplicate_incus(self):
        """Ne doit pas doubler le prefixe incus"""
        result = normalize_argv(["incus", "start", "web01"])
        assert result == ["incus", "start", "web01"]

    def test_empty_list_returns_empty(self):
        """Doit retourner une liste vide si l'entree est vide"""
        result = normalize_argv([])
        assert result == []

    def test_preserve_spaces_in_argument(self):
        """Doit conserver un argument contenant des espaces"""
        result = normalize_argv(["start", "instance with spaces"])
        assert "instance with spaces" in result
        assert len(result) == 3

    def test_preserve_remote_colon(self):
        """Doit conserver [remote:]ressource sans transformation"""
        result = normalize_argv(["start", "prod:web01"])
        assert "prod:web01" in result
        assert len(result) == 3

    def test_custom_binary(self):
        """Doit permettre de specifier un binaire personnalise"""
        result = normalize_argv(["start", "web01"], binary="custom_incus")
        assert result == ["custom_incus", "start", "web01"]


class TestValidateArgv:
    """Tests pour la validation des argv"""

    def test_empty_argv_rejected(self):
        """Doit rejeter argv vide"""
        valid, error = validate_argv([])
        assert not valid
        assert "cannot be empty" in error

    def test_empty_argv_allowed(self):
        """Doit accepter argv vide si allow_empty=True"""
        valid, error = validate_argv([], allow_empty=True)
        assert valid
        assert error is None

    def test_all_strings_valid(self):
        """Tous les elements doivent etre des chaines"""
        valid, error = validate_argv(["start", "web01", "--project", "production"])
        assert valid
        assert error is None

    def test_reject_non_string(self):
        """Doit rejeter les elements non-string"""
        valid, error = validate_argv(["start", 123, "web01"])
        assert not valid
        assert "must be a string" in error

    def test_reject_non_list(self):
        """Doit rejeter si argv n'est pas une liste"""
        valid, error = validate_argv("not a list")
        assert not valid
        assert "must be a list" in error


class TestContainsShellOperators:
    """Tests pour la detection des operateurs shell"""

    def test_no_operators(self):
        """Ne doit pas detecter d'operateurs dans une commande simple"""
        has_ops, found = contains_shell_operators("incus start web01")
        assert not has_ops
        assert len(found) == 0

    def test_pipe_operator(self):
        """Doit detecter l'operateur pipe"""
        has_ops, found = contains_shell_operators("incus list | grep web01")
        assert has_ops
        assert "|" in found

    def test_redirect_operator(self):
        """Doit detecter les operateurs de redirection"""
        for op in [">", ">>", "<"]:
            has_ops, found = contains_shell_operators(f"incus list {op} file.txt")
            assert has_ops
            assert op in found

    def test_logical_operators(self):
        """Doit detecter les operateurs logiques"""
        for op in ["&&", "||"]:
            has_ops, found = contains_shell_operators(f"incus start web01 {op} incus stop web01")
            assert has_ops
            assert op in found

    def test_semicolon_operator(self):
        """Doit detecter le point-virgule"""
        has_ops, found = contains_shell_operators("incus start web01; incus stop web01")
        assert has_ops
        assert ";" in found

    def test_command_substitution(self):
        """Doit detecter les substitutions de commande"""
        for cmd in ["`date`", "$(date)"]:
            has_ops, found = contains_shell_operators(f"incus start {cmd}")
            assert has_ops
            assert "command substitution" in found


class TestParseCommandString:
    """Tests pour l'analyse des chaines de commande"""

    def test_simple_command(self):
        """Doit analyser une commande simple"""
        parsed, error = parse_command_string("incus start web01")
        assert error is None
        assert parsed == ["incus", "start", "web01"]

    def test_quoted_argument(self):
        """Doit gerer les arguments entre guillemets"""
        parsed, error = parse_command_string('incus start "my instance"')
        assert error is None
        assert parsed == ["incus", "start", "my instance"]

    def test_single_quotes(self):
        """Doit gerer les guillemets simples"""
        parsed, error = parse_command_string("incus start 'my instance'")
        assert error is None
        assert parsed == ["incus", "start", "my instance"]

    def test_preserve_remote_colon(self):
        """Doit preserver le format remote:resource"""
        parsed, error = parse_command_string("incus start prod:web01")
        assert error is None
        assert parsed == ["incus", "start", "prod:web01"]


class TestMaskSensitiveValues:
    """Tests pour le masquage des valeurs sensibles"""

    def test_mask_single_value(self):
        """Doit masquer une valeur sensible"""
        text = "incus start web01 --password secret123"
        result = mask_sensitive_values(text, ["secret123"])
        assert "secret123" not in result
        assert "***SENSITIVE***" in result

    def test_mask_multiple_values(self):
        """Doit masquer plusieurs valeurs sensibles"""
        text = "incus start web01 --password pass1 --token tok2"
        result = mask_sensitive_values(text, ["pass1", "tok2"])
        assert "pass1" not in result
        assert "tok2" not in result
        assert result.count("***SENSITIVE***") == 2

    def test_no_sensitive_values(self):
        """Doit retourner le texte inchange si aucune valeur sensible"""
        text = "incus start web01"
        result = mask_sensitive_values(text, [])
        assert result == text

    def test_empty_string(self):
        """Doit gerer les chaines vides"""
        result = mask_sensitive_values("", ["secret"])
        assert result == ""


class TestMergeEnvironments:
    """Tests pour la fusion d'environnements"""

    def test_merge_empty(self):
        """Doit gerer les dictionnaires vides"""
        result = merge_environments({}, {})
        assert result == {}

    def test_merge_global_only(self):
        """Doit retourner global_env si step_env est vide"""
        global_env = {"VAR1": "value1"}
        result = merge_environments(global_env, {})
        assert result == {"VAR1": "value1"}

    def test_merge_step_overrides_global(self):
        """Les valeurs de step_env doivent ecraser global_env"""
        global_env = {"VAR1": "value1", "VAR2": "value2"}
        step_env = {"VAR1": "new_value1", "VAR3": "value3"}
        result = merge_environments(global_env, step_env)
        assert result["VAR1"] == "new_value1"
        assert result["VAR2"] == "value2"
        assert result["VAR3"] == "value3"

    def test_merge_none_global(self):
        """Doit gerer global_env=None"""
        result = merge_environments(None, {"VAR1": "value1"})
        assert result == {"VAR1": "value1"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
