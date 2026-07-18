#!/usr/bin/env python3
"""
Fake Incus CLI for testing purposes.
This script simulates the Incus CLI behavior without requiring
a real Incus installation.
"""

import sys
import json
import os
import time
from datetime import datetime


def log_command(args):
    """Log the command to a file for verification."""
    log_dir = os.environ.get('INCUS_FAKE_LOG_DIR', '/tmp/incus_fake_logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'commands.jsonl')
    
    command_record = {
        'timestamp': datetime.now().isoformat(),
        'argv': args,
        'pid': os.getpid()
    }
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(command_record) + '\n')


def handle_list(args):
    """Handle 'incus list' command."""
    # Extract filters and options
    containers = []
    format_type = 'table'
    
    i = 1  # Skip 'list'
    while i < len(args):
        arg = args[i]
        if arg == '--format':
            i += 1
            if i < len(args):
                format_type = args[i]
        elif arg == '--all-projects':
            pass
        elif arg == '--project':
            i += 1
            if i < len(args):
                pass  # Filter by project
        elif not arg.startswith('--'):
            # This is a container name filter
            containers.append({
                'name': arg,
                'status': 'Running',
                'type': 'container',
                'ipv4': '192.168.1.100',
                'ipv6': '',
                'state': 'RUNNING'
            })
        i += 1
    
    if format_type == 'json':
        print(json.dumps(containers))
    elif format_type == 'csv':
        if containers:
            print('NAME,STATUS,TYPE,IPV4,IPV6,STATE')
            for c in containers:
                print(f"{c['name']},{c['status']},{c['type']},{c['ipv4']},{c['ipv6']},{c['state']}")
        else:
            print('NAME,STATUS,TYPE,IPV4,IPV6,STATE')
    else:
        if containers:
            print("+--------+---------+----------+--------------+------+-------+")
            print("| NAME   |  STATE  |   TYPE    |   IPV4       | IPV6 | SNAPS |")
            print("+--------+---------+----------+--------------+------+-------+")
            for c in containers:
                print(f"| {c['name']:6} | RUNNING | container | {c['ipv4']:12} |      | 0     |")
            print("+--------+---------+----------+--------------+------+-------+")
        else:
            print("No containers found")


def handle_info(args):
    """Handle 'incus info' command."""
    if len(args) > 1 and args[1] != '--help':
        # Info about a specific container
        container_name = args[1]
        print(f"Name: {container_name}")
        print("Status: RUNNING")
        print("Type: container")
        print("Architecture: x86_64")
        print("PID: 12345")
        print("IPv4: 192.168.1.100")
        print("IPv6: -")
    else:
        # Server info
        print("API extensions:")
        print("API status: active")
        print("API version: 1.0")
        print("Auth: trusted")
        print("Public: false")
        print("Auth methods: tls")
        print("Environment:")
        print("  addresses: []")
        print("  architectures:")
        print("  - x86_64")
        print("  - i686")
        print("  certificate: |")
        print("    certificate=...")
        print("  certificate_fingerprint: abc123...")
        print("  driver: incus")
        print("  driver_version: 1.0.0")
        print("  firewall: xtables")
        print("  kernel: Linux")
        print("  kernel_architecture: x86_64")
        print("  kernel_version: 5.15.0")
        print("  lxc_features:")
        print("  - cgroup2")
        print("  - devpts_fd")
        print("  os_name: Ubuntu")
        print("  os_version: 22.04")
        print("  project: default")
        print("  server: incus")
        print("  server_clustered: false")
        print("  server_name: test-server")
        print("  server_pid: 1234")
        print("  server_version: 1.0.0")
        print("  storage: dir")
        print("  storage_version: 1")


def handle_version(args):
    """Handle 'incus version' command."""
    print("Client version: 1.0.0")
    print("Server version: 1.0.0")
    print("API version: 1.0")


def handle_storage(args):
    """Handle storage-related commands."""
    if len(args) < 2:
        print("Error: Missing storage command")
        sys.exit(1)
    
    subcommand = args[1]
    
    if subcommand == 'list':
        print("+---------+--------+------------------+---------+---------+")
        print("| NAME    | DRIVER |       SOURCE      |  USED BY |  STATE  |")
        print("+---------+--------+------------------+---------+---------+")
        print("| default | dir    | /var/lib/incus   | 2       | CREATED |")
        print("+---------+--------+------------------+---------+---------+")
    
    elif subcommand == 'volume':
        if len(args) < 4:
            print("Error: Missing volume subcommand")
            sys.exit(1)
        
        volume_subcommand = args[2]
        
        if volume_subcommand == 'list':
            pool = args[3] if len(args) > 3 else 'default'
            print("+--------+-------------+--------+------------------+---------+")
            print("| TYPE   |     NAME     |  USED BY |      PATH       |  STATE  |")
            print("+--------+-------------+--------+------------------+---------+")
            print("| filesystem | test_data | 0      | /var/lib/incus   | CREATED |")
            print("| filesystem | test_logs | 0      | /var/lib/incus   | CREATED |")
            print("+--------+-------------+--------+------------------+---------+")
        
        elif volume_subcommand == 'create':
            if len(args) < 5:
                print("Error: Missing volume name")
                sys.exit(1)
            pool = args[3]
            volume_name = args[4]
            print(f"Volume {volume_name} created in pool {pool}")
        
        elif volume_subcommand == 'attach':
            if len(args) < 6:
                print("Error: Missing arguments for volume attach")
                sys.exit(1)
            pool = args[3]
            volume_name = args[4]
            container = args[5]
            path = args[6] if len(args) > 6 else '/'
            print(f"Volume {volume_name} attached to {container} at {path}")
    
    elif subcommand == 'create':
        if len(args) < 3:
            print("Error: Missing pool name")
            sys.exit(1)
        pool_name = args[2]
        pool_type = args[3] if len(args) > 3 else 'dir'
        print(f"Storage pool {pool_name} created with driver {pool_type}")


def handle_network(args):
    """Handle network-related commands."""
    if len(args) < 2:
        print("Error: Missing network command")
        sys.exit(1)
    
    subcommand = args[1]
    
    if subcommand == 'list':
        print("+---------+----------+---------+-------------------+---------+")
        print("| NAME    |   TYPE   |  USED BY |       IPV4        |  STATE  |")
        print("+---------+----------+---------+-------------------+---------+")
        print("| default | bridge   | 2       | 192.168.1.1/24    | CREATED |")
        print("+---------+----------+---------+-------------------+---------+")
    
    elif subcommand == 'create':
        if len(args) < 3:
            print("Error: Missing network name")
            sys.exit(1)
        network_name = args[2]
        print(f"Network {network_name} created")


def handle_launch(args):
    """Handle 'incus launch' command."""
    if len(args) < 3:
        print("Error: Missing image or container name")
        sys.exit(1)
    
    image = args[1]
    container_name = args[2]
    
    # Extract options
    options = {}
    i = 3
    while i < len(args):
        arg = args[i]
        if arg.startswith('--'):
            if '=' in arg:
                key, value = arg[2:].split('=', 1)
                options[key] = value
            else:
                options[arg[2:]] = True
        elif arg.startswith('-') and len(arg) == 2:
            # Short options
            key = arg[1:]
            if i + 1 < len(args) and not args[i + 1].startswith('-'):
                options[key] = args[i + 1]
                i += 1
            else:
                options[key] = True
        i += 1
    
    print(f"Container {container_name} launched from {image}")
    print(f"Options: {options}")


def handle_start(args):
    """Handle 'incus start' command."""
    if len(args) < 2:
        print("Error: Missing container name")
        sys.exit(1)
    
    for container in args[1:]:
        print(f"Container {container} started")


def handle_stop(args):
    """Handle 'incus stop' command."""
    if len(args) < 2:
        print("Error: Missing container name")
        sys.exit(1)
    
    for container in args[1:]:
        print(f"Container {container} stopped")


def handle_config(args):
    """Handle 'incus config' command."""
    if len(args) < 3:
        print("Error: Missing config subcommand")
        sys.exit(1)
    
    subcommand = args[1]
    
    if subcommand == 'set':
        if len(args) < 4:
            print("Error: Missing container name or key=value")
            sys.exit(1)
        container = args[2]
        for setting in args[3:]:
            print(f"Config set for {container}: {setting}")
    
    elif subcommand == 'device':
        if len(args) < 4:
            print("Error: Missing device subcommand")
            sys.exit(1)
        
        device_subcommand = args[2]
        
        if device_subcommand == 'add':
            if len(args) < 5:
                print("Error: Missing container or device name")
                sys.exit(1)
            container = args[3]
            device_name = args[4]
            device_type = args[5] if len(args) > 5 else 'nic'
            print(f"Device {device_name} ({device_type}) added to {container}")
            for option in args[6:]:
                print(f"  Option: {option}")


def handle_exec(args):
    """Handle 'incus exec' command."""
    if len(args) < 3:
        print("Error: Missing container name or command")
        sys.exit(1)
    
    container = args[1]
    # Find the -- separator
    try:
        separator_index = args.index('--')
        command = args[separator_index + 1:]
    except ValueError:
        command = args[2:]
    
    print(f"Executed in {container}: {' '.join(command)}")


def handle_wait(args):
    """Handle 'incus wait' command."""
    if len(args) < 2:
        print("Error: Missing container name")
        sys.exit(1)
    
    container = args[1]
    condition = 'running'
    timeout = '30'
    
    i = 2
    while i < len(args):
        arg = args[i]
        if arg == '--condition' and i + 1 < len(args):
            condition = args[i + 1]
            i += 1
        elif arg == '--timeout' and i + 1 < len(args):
            timeout = args[i + 1]
            i += 1
        i += 1
    
    print(f"Waiting for {container} to be {condition} (timeout: {timeout}s)")
    time.sleep(0.1)  # Simulate waiting
    print(f"Container {container} is {condition}")


def handle_help(args):
    """Handle help command."""
    print("Usage: incus <command> [options]")
    print("")
    print("Commands:")
    print("  list, info, version, launch, start, stop, config, exec, wait")
    print("  storage, network, image")
    print("")
    print("For more information, run: incus <command> --help")


def main():
    """Main function to handle Incus commands."""
    # Log the command
    log_command(sys.argv)
    
    args = sys.argv[1:]
    
    if not args:
        handle_help(sys.argv)
        return
    
    command = args[0]
    
    # Handle different commands
    command_handlers = {
        'list': handle_list,
        'info': handle_info,
        'version': handle_version,
        'storage': handle_storage,
        'network': handle_network,
        'launch': handle_launch,
        'start': handle_start,
        'stop': handle_stop,
        'config': handle_config,
        'exec': handle_exec,
        'wait': handle_wait,
        '--help': handle_help,
        '-h': handle_help,
        'help': handle_help,
    }
    
    if command in command_handlers:
        command_handlers[command](args)
    else:
        print(f"Error: Unknown command '{command}'")
        print("Try 'incus --help' for more information")
        sys.exit(1)


if __name__ == '__main__':
    main()
