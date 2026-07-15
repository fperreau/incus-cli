# -*- coding: utf-8 -*-
"""
Module utils pour incus_cli
Fonctions de normalisation, validation et utilitaires partagés
"""

from __future__ import absolute_import, division, print_function

__metaclass_type__ = type

import re
import shlex


# Constantes
INCUS_BINARY = "incus"

# Opérateurs shell interdits dans le mode command
SHELL_OPERATORS = ['|', '>', '>>', '<', '&&', '||', ';']

# Pattern pour détecter les substitutions de commande
COMMAND_SUBSTITUTION_PATTERN = re.compile(r'`[^`]+`|\$\([^)]*\)')


def normalize_argv(argv, binary=INCUS_BINARY):
    """
    Normalise une liste d'arguments en ajoutant le binaire incus en position 0.
    
    Args:
        argv: Liste d'arguments (ex: ["start", "web01"])
        binary: Nom du binaire à préfixer (par défaut: "incus")
    
    Returns:
        Liste normalisée avec le binaire en position 0
        Exemple: ["incus", "start", "web01"]
    
    Note:
        Si argv[0] est déjà le binary, on le conserve sans doublon.
        Ajoute un avertissement si un doublon est détecté.
    """
    if not argv:
        return argv
    
    # Vérifier si le binaire est déjà en première position
    if argv and argv[0] == binary:
        # Déjà présent, on retourne tel quel (normalisation silencieuse)
        return list(argv)
    
    # Ajouter le binaire en position 0
    return [binary] + list(argv)


def validate_argv(argv, allow_empty=False):
    """
    Valide une liste d'arguments.
    
    Args:
        argv: Liste d'arguments à valider
        allow_empty: Si True, accepte une liste vide
    
    Returns:
        Tuple (valid, error_message)
        valid: bool - True si valide
        error_message: str - Message d'erreur si invalide
    """
    if not isinstance(argv, list):
        return False, "argv must be a list"
    
    if not allow_empty and len(argv) == 0:
        return False, "argv cannot be empty"
    
    if len(argv) == 0:
        return True, None
    
    # Vérifier que tous les éléments sont des chaînes
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
        has_operators: bool - True si des opérateurs shell sont détectés
        found_operators: list - Liste des opérateurs trouvés
    """
    found = []
    
    # Vérifier les opérateurs simples
    for op in SHELL_OPERATORS:
        if op in command:
            found.append(op)
    
    # Vérifier les substitutions de commande
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
        parsed_argv: list - Liste des arguments analysés
        error: str - Message d'erreur si l'analyse échoue
    """
    try:
        # shlex.split conserve les guillemets et gère les espaces
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
            # Remplacer toutes les occurrences
            result = result.replace(value, mask)
    
    return result


def merge_environments(global_env, step_env):
    """
    Fusionne deux dictionnaires d'environnement.
    Les valeurs de step_env écrasent celles de global_env.
    
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
    Vérifie si un fichier existe (simulation pour check_mode).
    
    Args:
        path: Chemin du fichier à vérifier
    
    Returns:
        bool - True si le fichier existe
    """
    # Cette fonction sera remplacée par une implémentation réelle
    # ou sera mockée dans les tests
    try:
        import os
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
