# INCUS-CLI Ansible Module

A generic Ansible module for managing Incus containers and resources. This module provides a structured and secure way to execute Incus CLI commands with support for multiple modes: command, incus (argv-based), template, and shell.

## Features

- **Multiple Modes**: Support for command, incus (argv-based), template, and shell modes
- **Idempotency**: Built-in support for idempotent operations through creates/removes parameters
- **Security**: Automatic masking of sensitive values and safe command execution
- **Flexibility**: Template mode allows for complex deployments using Jinja2 templates
- **Error Handling**: Configurable error handling with stop_on_error option
- **Check Mode**: Full support for Ansible check mode

## Installation

### Prerequisites

- Python 3.6+
- Ansible 2.9+
- Incus (on target machines for actual Incus operations)

### Install the Module

1. Clone this repository:
   ```bash
   git clone https://github.com/fperreau/incus-cli.git
   cd incus-cli
   ```

2. Add the module to your Ansible library path:
   - Copy the `library/incus_cli.py` file to your Ansible library directory
   - Or configure Ansible to use this directory by setting `library` in your `ansible.cfg`:
     ```ini
     [defaults]
     library = ./library
     ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Module Modes

#### 1. Command Mode (Simple)

Execute a single Incus command:

```yaml
- name: List all containers
  my_namespace.incus.incus_cli:
    command: "incus list"

- name: Start a container
  my_namespace.incus.incus_cli:
    command: "incus start my-container"
```

**Limitations**: This mode does not support shell operators (|, >, &&, etc.). Use shell mode for those.

#### 2. Incus Mode (Recommended)

Execute multiple Incus commands using argv format. This is the most robust and secure mode:

```yaml
- name: Create and start a container
  my_namespace.incus.incus_cli:
    incus:
      - argv:
          - launch
          - ubuntu:22.04
          - my-container
          - --storage
          - default
        name: Launch container
      
      - argv:
          - start
          - my-container
        name: Start container
        changed: true
      
      - argv:
          - list
          - --format
          - json
        name: List containers
        changed: false
```

**Features**:
- Automatic `incus` prefix added to each command
- Support for multiple commands in sequence
- Individual command options (environment, creates, removes, etc.)
- Sensitive value masking

#### 3. Template Mode

Use Jinja2 templates to generate Incus commands dynamically:

```yaml
- name: Deploy container from template
  my_namespace.incus.incus_cli:
    template: templates/container.yml.j2
    variables:
      container_name: my-container
      image: ubuntu:22.04
      cpu_limit: 2
      memory_limit: 2GiB
```

Template file (`templates/container.yml.j2`):
```yaml
incus:
  - argv:
      - launch
      - "{{ image }}"
      - "{{ container_name }}"
      - -c
      - "limits.cpu={{ cpu_limit }}"
      - -c
      - "limits.memory={{ memory_limit }}"
    name: Launch container
  
  - argv:
      - start
      - "{{ container_name }}"
    name: Start container
```

#### 4. Shell Mode (Unsafe)

Execute shell commands directly. **This mode is unsafe and can lead to command injection vulnerabilities.**

```yaml
- name: Export container list to file
  my_namespace.incus.incus_cli:
    shell: "incus list --format json > /tmp/containers.json"
    unsafe_shell: true
    executable: /bin/bash
```

**Warning**: Shell mode requires explicit consent via `unsafe_shell: true`. Use with caution.

### The Bastion Deployment Example

This project includes a complete example for deploying [The Bastion](https://ovh.github.io/the-bastion/index.html) using the incus_cli module:

```yaml
- name: Deploy The Bastion container
  hosts: localhost
  connection: local
  tasks:
    - name: Deploy The Bastion
      my_namespace.incus.incus_cli:
        template: templates/bastion_container.yml.j2
        variables:
          container_name: the_bastion
          container_image: docker:the-bastion/the-bastion:latest
          storage_pool: default
          data_volume: bastion_data
          logs_volume: bastion_logs
          backup_volume: bastion_backup
          network_name: bastion_net
          cpu_limit: 2
          memory_limit: 2GiB
          disk_limit: 10GiB
          bastion_ssh_port: 2222
```

See `playbooks/deploy_the_bastion.yml` for the complete deployment playbook.

### Idempotency

The module supports idempotent operations through several mechanisms:

1. **creates parameter**: Skip command if file exists
   ```yaml
   - argv:
       - start
       - my-container
     creates: /tmp/my-container-started
   ```

2. **removes parameter**: Skip command if file doesn't exist
   ```yaml
   - argv:
       - stop
       - my-container
     removes: /tmp/my-container-stopped
   ```

3. **changed parameter**: Control whether command reports changes
   ```yaml
   - argv:
       - list
       - --format
       - json
     changed: false
   ```

4. **Check Mode**: Full support for Ansible's check mode
   ```bash
   ansible-playbook playbook.yml --check
   ```

### Error Handling

Control error handling behavior:

```yaml
- name: Multiple commands with error handling
  my_namespace.incus.incus_cli:
    incus:
      - argv:
          - start
          - container1
      - argv:
          - start
          - container2
    stop_on_error: true  # Stop on first error (default)
    # stop_on_error: false  # Continue on errors
```

### Sensitive Value Masking

Mask sensitive values in output and logs:

```yaml
- name: Execute command with sensitive data
  my_namespace.incus.incus_cli:
    incus:
      - argv:
          - exec
          - my-container
          - --
          - bash
          - -c
          - "echo password=secret123"
        sensitive_values:
          - "secret123"
```

## Testing

### Unit Tests

Run unit tests to verify module functionality:

```bash
# Install test dependencies
pip install pytest pyyaml

# Run unit tests
make unit-test
# or
python -m pytest tests/unit/ -v
```

### Integration Tests

Run integration tests to verify the complete workflow:

```bash
# Set up fake Incus for testing
make integration-test

# Or manually:
cp tests/integration/fake_incus.py /usr/local/bin/fake_incus
chmod +x /usr/local/bin/fake_incus
ansible-playbook -i inventories/lab/hosts.yml tests/integration/test_bastion_deployment.yml
```

### Test with Real Incus

To test with a real Incus installation:

```bash
# Run the deployment playbook
ansible-playbook -i inventories/lab/hosts.yml playbooks/deploy_the_bastion.yml

# Run in check mode first
ansible-playbook -i inventories/lab/hosts.yml --check playbooks/deploy_the_bastion.yml
```

## Project Structure

```
incus-cli/
├── library/
│   └── incus_cli.py          # Main module implementation
├── playbooks/
│   ├── deploy_the_bastion.yml # The Bastion deployment example
│   └── test_deployment.yml    # Test playbook with fake Incus
├── templates/
│   └── bastion_container.yml.j2 # Jinja2 template for Bastion
├── tests/
│   ├── unit/
│   │   └── test_incus_cli.py  # Unit tests
│   └── integration/
│       ├── test_bastion_deployment.yml # Integration tests
│       └── fake_incus.py       # Fake Incus for testing
├── inventories/
│   └── lab/
│       └── hosts.yml          # Test inventory
├── Makefile                  # Build and test commands
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## The Bastion Configuration

When deploying The Bastion, the following configuration is applied:

### Container Configuration
- **Name**: `the_bastion`
- **Image**: `docker:the-bastion/the-bastion:latest`
- **Storage**: Separate volumes for data, logs, and backups
- **Network**: Dedicated bridge network with static IP
- **Resource Limits**: CPU, memory, and disk limits

### Storage Volumes
- **Data Volume**: `/var/lib/bastion` - 5GiB
- **Logs Volume**: `/var/log/bastion` - 2GiB
- **Backup Volume**: `/var/backups/bastion` - 3GiB

### Network Configuration
- **Network Type**: Bridge
- **IP Address**: 192.168.1.100/24
- **Gateway**: 192.168.1.1
- **SSH Port**: 2222 (proxy to container's port 22)

### Resource Limits
- **CPU**: 2 cores
- **Memory**: 2GiB
- **Disk**: 10GiB

## Security Considerations

1. **Shell Mode**: Always use `unsafe_shell: true` explicitly. This mode can lead to command injection vulnerabilities.

2. **Sensitive Data**: Use the `sensitive_values` parameter to mask passwords, tokens, and other sensitive information.

3. **Idempotency**: Design your playbooks to be idempotent using creates/removes parameters.

4. **Check Mode**: Always test your playbooks with `--check` before running them in production.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.

## References

- [Incus Documentation](https://linuxcontainers.org/incus/docs/main/)
- [The Bastion Documentation](https://ovh.github.io/the-bastion/index.html)
- [Ansible Documentation](https://docs.ansible.com/)

## Support

For issues and questions, please open an issue on the GitHub repository.
