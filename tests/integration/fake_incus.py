#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Faux binaire Incus pour les tests d'intégration

Ce script simule le comportement du binaire `incus` réel pour permettre
des tests sans nécessiter une installation réelle d'Incus.

Usage:
    1. Placer ce script dans le PATH avant le vrai binaire incus
    2. Le script registre toutes les commandes exécutées
    3. Il peut simuler différents comportements selon les arguments
"""

import sys
import json
import os
import time
import argparse
from datetime import datetime


# Fichier pour stocker les appels
LOG_FILE = os.environ.get('FAKE_INCUS_LOG', '/tmp/fake_incus_calls.jsonl')


def log_call(args, stdout=None, stderr=None, rc=0):
    """Enregistre un appel dans le fichier de log"""
    call_record = {
        'timestamp': datetime.utcnow().isoformat(),
        'argv': args,
        'stdout': stdout or '',
        'stderr': stderr or '',
        'rc': rc
    }
    
    # Écrire en JSON Lines
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(call_record) + '\n')


def clear_log():
    """Efface le fichier de log"""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)


def get_command(args):
    """Récupère la commande principale (sans les options)"""
    if not args:
        return None
    
    # Ignorer les options globales
    for arg in args:
        if not arg.startswith('-'):
            return arg
    return None


def simulate_start(args):
    """Simule 'incus start'"""
    # Trouver le nom de l'instance
    instance_name = None
    for arg in args[1:]:  # Skip 'start'
        if not arg.startswith('-') and ':' in arg:
            instance_name = arg
            break
        elif not arg.startswith('-'):
            instance_name = arg
            break
    
    if not instance_name:
        instance_name = "unknown"
    
    stdout = f"Starting instance: {instance_name}"
    return stdout, None, 0


def simulate_stop(args):
    """Simule 'incus stop'"""
    # Trouver le nom de l'instance
    instance_name = None
    for arg in args[1:]:  # Skip 'stop'
        if not arg.startswith('-') and ':' in arg:
            instance_name = arg
            break
        elif not arg.startswith('-'):
            instance_name = arg
            break
    
    if not instance_name:
        instance_name = "unknown"
    
    stdout = f"Stopping instance: {instance_name}"
    return stdout, None, 0


def simulate_list(args):
    """Simule 'incus list'"""
    # Générer une liste fictive d'instances
    instances = [
        {
            "name": "web01",
            "status": "Running",
            "type": "container",
            "remote": "prod"
        },
        {
            "name": "db01", 
            "status": "Running",
            "type": "container",
            "remote": "prod"
        }
    ]
    
    # Vérifier le format
    format_arg = None
    for i, arg in enumerate(args[1:]):
        if arg == '--format' and i + 1 < len(args):
            format_arg = args[i + 2]
    
    if format_arg == 'json':
        stdout = json.dumps(instances, indent=2)
    else:
        # Format table
        stdout = "NAME\t\tSTATE\t\tTYPE\t\tREMOTE\n"
        stdout += "web01\t\tRunning\t\tcontainer\t\tprod\n"
        stdout += "db01\t\tRunning\t\tcontainer\t\tprod\n"
    
    return stdout, None, 0


def simulate_info(args):
    """Simule 'incus info'"""
    # Trouver le nom de l'instance
    instance_name = args[1] if len(args) > 1 else "web01"
    
    info = {
        "name": instance_name,
        "status": "Running",
        "type": "container",
        "architecture": "x86_64",
        "config": {
            "image.description": "Ubuntu 22.04"
        }
    }
    
    stdout = json.dumps(info, indent=2)
    return stdout, None, 0


def simulate_error(args):
    """Simule une erreur"""
    # Trouver la commande
    command = get_command(args)
    
    if command == 'delete':
        instance_name = args[1] if len(args) > 1 else "unknown"
        stderr = f"Error: Instance {instance_name} not found"
        return None, stderr, 1
    
    return None, "Error: Unknown command or invalid arguments", 1


def main():
    """Point d'entrée principal"""
    args = sys.argv[1:]  # Le premier arg est le nom du script (fake_incus)
    
    # Si le premier argument n'est pas 'incus', c'est qu'on nous appelle directement
    # On ajoute 'incus' au début
    if args and args[0] != 'incus':
        args = ['incus'] + args
    
    # Log l'appel
    log_call(args)
    
    # Simuler selon la commande
    if not args:
        print("Usage: incus <command> [options]")
        print("Commands: start, stop, list, info, delete")
        sys.exit(1)
    
    # Trouver la commande
    command = get_command(args)
    
    # Dispatcher
    if command == 'start':
        stdout, stderr, rc = simulate_start(args)
    elif command == 'stop':
        stdout, stderr, rc = simulate_stop(args)
    elif command == 'list':
        stdout, stderr, rc = simulate_list(args)
    elif command == 'info':
        stdout, stderr, rc = simulate_info(args)
    elif command == 'version':
        stdout = "Incus 6.0 (fake)"
        stderr = None
        rc = 0
    elif command == 'help':
        stdout = "Usage: incus <command> [options]\n\nCommands:\n  start, stop, list, info, version"
        stderr = None
        rc = 0
    else:
        stdout, stderr, rc = simulate_error(args)
    
    # Afficher le résultat
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    
    sys.exit(rc)


if __name__ == '__main__':
    main()
