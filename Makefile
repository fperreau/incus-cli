# Makefile for incus_cli module development and testing

.PHONY: all test unit-test integration-test clean

# Configuration
PYTHON := python3
ANSIBLE := ansible
ANSIBLE_PLAYBOOK := ansible-playbook
MODULE_PATH := library
PLAYBOOKS_PATH := playbooks
TESTS_PATH := tests
FAKE_INCUS := $(TESTS_PATH)/integration/fake_incus.py

# Test targets
all: test

test: unit-test integration-test

unit-test:
	@echo "Running unit tests..."
	$(PYTHON) -m pytest $(TESTS_PATH)/unit/ -v --tb=short

integration-test:
	@echo "Running integration tests..."
	# Set up fake incus
	@mkdir -p /tmp/incus_fake_logs
	@cp $(FAKE_INCUS) /usr/local/bin/fake_incus
	@chmod +x /usr/local/bin/fake_incus
	@export PATH="/usr/local/bin:$$PATH"
	@$(ANSIBLE_PLAYBOOK) -i inventories/lab/hosts.yml $(TESTS_PATH)/integration/test_bastion_deployment.yml

# Clean up
clean:
	@echo "Cleaning up..."
	@rm -f /usr/local/bin/fake_incus
	@rm -rf /tmp/incus_fake_logs
	@rm -f /tmp/the_bastion_*
	@rm -f /tmp/test_*

# Run specific playbook
run-bastion:
	@echo "Deploying The Bastion container..."
	@$(ANSIBLE_PLAYBOOK) -i inventories/lab/hosts.yml $(PLAYBOOKS_PATH)/deploy_the_bastion.yml

# Run with check mode
check-bastion:
	@echo "Running The Bastion deployment in check mode..."
	@$(ANSIBLE_PLAYBOOK) -i inventories/lab/hosts.yml --check $(PLAYBOOKS_PATH)/deploy_the_bastion.yml

# Syntax check
syntax-check:
	@echo "Checking playbook syntax..."
	@$(ANSIBLE_PLAYBOOK) -i inventories/lab/hosts.yml $(PLAYBOOKS_PATH)/deploy_the_bastion.yml --syntax-check

# List tasks
list-tasks:
	@echo "Listing tasks in playbook..."
	@$(ANSIBLE_PLAYBOOK) -i inventories/lab/hosts.yml $(PLAYBOOKS_PATH)/deploy_the_bastion.yml --list-tasks

# List hosts
list-hosts:
	@echo "Listing hosts..."
	@$(ANSIBLE_PLAYBOOK) -i inventories/lab/hosts.yml $(PLAYBOOKS_PATH)/deploy_the_bastion.yml --list-hosts

# Install dependencies
install-deps:
	@echo "Installing dependencies..."
	@pip install pytest pyyaml

# Run all tests with coverage
coverage:
	@echo "Running tests with coverage..."
	@pip install pytest-cov
	@$(PYTHON) -m pytest $(TESTS_PATH)/unit/ -v --cov=$(MODULE_PATH) --cov-report=term-missing

# Lint
lint:
	@echo "Running linters..."
	@pip install ansible-lint yamllint
	@ansible-lint $(PLAYBOOKS_PATH)/deploy_the_bastion.yml
	@yamllint $(PLAYBOOKS_PATH)/deploy_the_bastion.yml

# Help
help:
	@echo "Available targets:"
	@echo "  all              - Run all tests"
	@echo "  test             - Run all tests"
	@echo "  unit-test        - Run unit tests"
	@echo "  integration-test - Run integration tests"
	@echo "  run-bastion      - Deploy The Bastion container"
	@echo "  check-bastion    - Run deployment in check mode"
	@echo "  syntax-check     - Check playbook syntax"
	@echo "  list-tasks       - List playbook tasks"
	@echo "  list-hosts       - List playbook hosts"
	@echo "  install-deps     - Install Python dependencies"
	@echo "  coverage          - Run tests with coverage"
	@echo "  lint             - Run linters"
	@echo "  clean            - Clean up test files"
