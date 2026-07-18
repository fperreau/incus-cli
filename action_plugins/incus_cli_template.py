# -*- coding: utf-8 -*-
"""
Action Plugin pour le mode template du module incus_cli

Ce plugin permet de :
1. Lire et rendre un template Jinja2 sur le contrôleur Ansible
2. Parser le YAML résultant
3. Valider la structure
4. Transmettre la structure normalisée au module
"""

from __future__ import absolute_import, division, print_function

__metaclass_type__ = type

import os
import json
import yaml

try:
    from ansible.plugins.action import ActionBase
    from ansible.errors import AnsibleError
    from ansible.utils.display import Display
    HAS_ANSIBLE = True
except ImportError:
    HAS_ANSIBLE = False

try:
    from ansible.template import Templar
    HAS_TEMPLAR = True
except ImportError:
    HAS_TEMPLAR = False

from jinja2 import Environment, FileSystemLoader, StrictUndefined


display = Display()


class ActionModule(ActionBase):
    """
    Action plugin pour le mode template du module incus_cli
    """
    
    TRANSFERS_FILES = False
    
    def __init__(self, *args, **kwargs):
        super(ActionModule, self).__init__(*args, **kwargs)
        self._supports_check_mode = True
        self._supports_async = False
    
    def run(self, tmp=None, task_vars=None):
        """
        Exécute l'action plugin.
        
        Args:
            tmp: Répertoire temporaire
            task_vars: Variables de la tâche
        
        Returns:
            Résultat à passer au module
        """
        # Vérifier que template et variables sont présents
        if not task_vars:
            task_vars = {}
        
        # Récupérer les paramètres
        template_path = self._task.params.get('template')
        variables = self._task.params.get('variables', {})
        
        if not template_path:
            raise AnsibleError("template parameter is required for template mode")
        
        # Trouver le fichier de template
        # Le template peut être relatif au répertoire du playbook
        # ou absolu
        template_dir = self._find_template_directory(task_vars)
        
        if not template_dir:
            raise AnsibleError(f"Could not find template directory for template: {template_path}")
        
        # Résoudre le chemin du template
        if os.path.isabs(template_path):
            template_abs_path = template_path
        else:
            template_abs_path = os.path.join(template_dir, template_path)
        
        if not os.path.exists(template_abs_path):
            raise AnsibleError(f"Template file not found: {template_abs_path}")
        
        # Lire le contenu du template
        with open(template_abs_path, 'r') as f:
            template_content = f.read()
        
        # Rendre le template avec Jinja2
        rendered_content = self._render_template(template_content, variables, task_vars, template_abs_path)
        
        # Parser le YAML
        try:
            parsed_yaml = yaml.safe_load(rendered_content)
        except yaml.YAMLError as e:
            raise AnsibleError(f"Failed to parse rendered template as YAML: {str(e)}")
        
        if parsed_yaml is None:
            parsed_yaml = {}
        
        if not isinstance(parsed_yaml, dict):
            raise AnsibleError(f"Template must render to a YAML mapping (dict), got {type(parsed_yaml).__name__}")
        
        # Valider la structure
        self._validate_template_structure(parsed_yaml)
        
        # Normaliser la structure pour le mode incus
        normalized_params = self._normalize_to_incus_mode(parsed_yaml)
        
        # Ajouter les paramètres supplémentaires
        for key in ['chdir', 'environment', 'creates', 'removes', 'stop_on_error']:
            if key in self._task.params:
                normalized_params[key] = self._task.params[key]
        
        # Exécuter le module avec les paramètres normalisés
        result = self._execute_module(
            module_name='incus_cli',
            module_args=normalized_params,
            task_vars=task_vars,
            tmp=tmp
        )
        
        return result
    
    def _find_template_directory(self, task_vars):
        """
        Trouve le répertoire contenant les templates.
        
        Args:
            task_vars: Variables de la tâche
        
        Returns:
            Chemin du répertoire des templates, ou None
        """
        # Essayer plusieurs chemins possibles
        possible_dirs = [
            # Répertoire du playbook
            task_vars.get('playbook_dir'),
            # Répertoire du rôle
            task_vars.get('role_path'),
            # Répertoire courant
            os.getcwd(),
            # Répertoire des templates
            os.path.join(os.getcwd(), 'templates'),
        ]
        
        for path in possible_dirs:
            if path and os.path.isdir(path):
                return path
        
        return None
    
    def _render_template(self, template_content, variables, task_vars, template_path):
        """
        Rend un template Jinja2.
        
        Args:
            template_content: Contenu du template
            variables: Variables fournies par l'utilisateur
            task_vars: Variables de la tâche Ansible
            template_path: Chemin du template (pour les erreurs)
        
        Returns:
            str: Contenu rendu
        
        Raises:
            AnsibleError: Si une variable est indéfinie
        """
        # Créer un environnement Jinja2 avec StrictUndefined
        # pour échouer sur les variables indéfinies
        
        # Obtenir le répertoire du template
        template_dir = os.path.dirname(template_path)
        
        # Créer l'environnement
        env = Environment(
            loader=FileSystemLoader(template_dir or os.getcwd()),
            undefined=StrictUndefined,
            autoescape=False
        )
        
        # Créer le contexte de rendu
        # Les variables fournies écrasent les variables du contexte
        context = dict(task_vars)
        context.update(variables)
        
        # Créer le template
        template = env.from_string(template_content)
        
        try:
            rendered = template.render(**context)
            return rendered
        except Exception as e:
            # Jinja2 lève des exceptions pour les variables indéfinies
            raise AnsibleError(
                f"Failed to render template '{template_path}': {str(e)}. "
                f"Undefined variable detected. Please ensure all variables are defined."
            )
    
    def _validate_template_structure(self, parsed_yaml):
        """
        Valide que la structure YAML rendue est valide pour le mode incus.
        
        Args:
            parsed_yaml: Structure YAML parsée
        
        Raises:
            AnsibleError: Si la structure est invalide
        """
        # La structure doit avoir une clé 'incus' qui est une liste
        if 'incus' not in parsed_yaml:
            raise AnsibleError(
                "Template must render a YAML structure with 'incus' as the root key. "
                "Expected format: {incus: [{argv: [command, arg1, ...]}, ...]}"
            )
        
        incus_list = parsed_yaml['incus']
        
        if not isinstance(incus_list, list):
            raise AnsibleError(
                "The 'incus' key must contain a list of steps. "
                f"Got {type(incus_list).__name__} instead."
            )
        
        # Valider chaque étape
        for i, step in enumerate(incus_list):
            if not isinstance(step, dict):
                raise AnsibleError(
                    f"Each step in 'incus' must be a dictionary (step {i}). "
                    f"Got {type(step).__name__} instead."
                )
            
            # Vérifier que argv existe
            if 'argv' not in step:
                raise AnsibleError(
                    f"Each step must have an 'argv' key (step {i})."
                )
            
            argv = step.get('argv')
            if not isinstance(argv, list):
                raise AnsibleError(
                    f"The 'argv' key must be a list (step {i}). "
                    f"Got {type(argv).__name__} instead."
                )
            
            # Vérifier que tous les éléments de argv sont des chaînes
            for j, arg in enumerate(argv):
                if not isinstance(arg, str):
                    raise AnsibleError(
                        f"All elements in argv must be strings (step {i}, argv[{j}]). "
                        f"Got {type(arg).__name__} instead."
                    )
            
            # Vérifier les autres clés autorisées
            allowed_keys = ['name', 'argv', 'environment', 'changed', 'creates', 'removes', 'sensitive_values']
            for key in step.keys():
                if key not in allowed_keys:
                    raise AnsibleError(
                        f"Unexpected key '{key}' in step {i}. "
                        f"Allowed keys: {', '.join(allowed_keys)}"
                    )
        
        # Vérifier qu'il n'y a pas de clés inattendues à la racine
        allowed_root_keys = ['incus']
        for key in parsed_yaml.keys():
            if key not in allowed_root_keys:
                raise AnsibleError(
                    f"Unexpected root key '{key}'. "
                    f"Only 'incus' is allowed at the root level."
                )
    
    def _normalize_to_incus_mode(self, parsed_yaml):
        """
        Normalise la structure pour le mode incus.
        
        Args:
            parsed_yaml: Structure YAML parsée
        
        Returns:
            dict: Paramètres normalisés pour le module incus_cli
        """
        # Simplement retourner la structure avec la clé incus
        # Le module gérera la normalisation des argv
        return parsed_yaml


# Pour permettre l'utilisation comme plugin standalone
# (nécessaire pour que Ansible le trouve)


def main():
    """Point d'entrée pour l'utilisation comme script"""
    # Ce n'est pas normalement appelé directement
    pass


if __name__ == '__main__':
    main()
