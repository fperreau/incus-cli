# Makefile pour le projet incus_cli
# Gère le build, les tests et le déploiement

.PHONY: all help test lint clean build install deploy

# Variables configurables
COLLECTION_NAME ?= community.incus
COLLECTION_VERSION ?= 1.0.0
ANSIBLE_GALAXY_CLI ?= ansible-galaxy
PYTHON ?= python3
PIP ?= pip

# Répertoires
COLLECTION_DIR ?= community/incus
LIBRARY_DIR ?= library
MODULE_UTILS_DIR ?= module_utils
ACTION_PLUGINS_DIR ?= action_plugins
TESTS_DIR ?= tests
PLAYBOOKS_DIR ?= playbooks

# Fichiers
MODULE_FILE ?= $(LIBRARY_DIR)/incus_cli.py
COLLECTION_MODULE_FILE ?= $(COLLECTION_DIR)/plugins/modules/incus_cli.py
COLLECTION_MODULE_UTILS_FILE ?= $(COLLECTION_DIR)/plugins/module_utils/incus_cli.py
COLLECTION_ACTION_PLUGIN_FILE ?= $(COLLECTION_DIR)/plugins/action/incus_cli_template.py

help: ## Affiche cette aide
	@echo "Cibles disponibles:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

all: test lint ## Exécute tous les tests et la vérification

# ============================================================================
# BUILD
# ============================================================================

build: build-collection ## Construit la collection Ansible

build-collection: ## Construit le package de la collection
	@echo "[INFO] Construction de la collection $(COLLECTION_NAME)..."
	cd $(COLLECTION_DIR) && $(ANSIBLE_GALAXY_CLI) collection build
	@echo "[SUCCESS] Collection construite: $(COLLECTION_DIR)/$(COLLECTION_NAME)-$(COLLECTION_VERSION).tar.gz"

# ============================================================================
# INSTALLATION
# ============================================================================

install: install-collection install-requirements ## Installe la collection et les dépendances

install-requirements: ## Installe les dépendances Python
	@echo "[INFO] Installation des dépendances Python..."
	$(PIP) install -r requirements.txt
	@echo "[SUCCESS] Dépendances installées"

install-collection: ## Installe la collection localement
	@echo "[INFO] Installation de la collection $(COLLECTION_NAME)..."
	cd $(COLLECTION_DIR) && $(ANSIBLE_GALAXY_CLI) collection install . --force
	@echo "[SUCCESS] Collection installée"

# ============================================================================
# SYNCHRONISATION
# ============================================================================

sync: sync-module sync-module-utils sync-action-plugins ## Synchronise les fichiers entre standalone et collection

sync-module: ## Synchronise le module principal
	@echo "[INFO] Synchronisation du module principal..."
	cp $(MODULE_FILE) $(COLLECTION_MODULE_FILE)
	@echo "[SUCCESS] Module synchronisé"

sync-module-utils: ## Synchronise les module_utils
	@echo "[INFO] Synchronisation des module_utils..."
	cp $(MODULE_UTILS_DIR)/incus_cli.py $(COLLECTION_MODULE_UTILS_FILE)
	@echo "[SUCCESS] Module utils synchronisé"

sync-action-plugins: ## Synchronise les action plugins
	@echo "[INFO] Synchronisation des action plugins..."
	cp $(ACTION_PLUGINS_DIR)/incus_cli_template.py $(COLLECTION_ACTION_PLUGIN_FILE)
	@echo "[SUCCESS] Action plugin synchronisé"

# ============================================================================
# TESTS
# ============================================================================

test: test-unit test-integration ## Exécute tous les tests

test-unit: ## Exécute les tests unitaires
	@echo "[INFO] Exécution des tests unitaires..."
	$(PYTHON) -m pytest $(TESTS_DIR)/unit/ -v --tb=short
	@echo "[SUCCESS] Tests unitaires terminés"

test-integration: ## Exécute les tests d'intégration
	@echo "[INFO] Exécution des tests d'intégration..."
	$(PYTHON) -m pytest $(TESTS_DIR)/integration/ -v --tb=short
	@echo "[SUCCESS] Tests d'intégration terminés"

# ============================================================================
# LINTING
# ============================================================================

lint: lint-yaml lint-python ## Exécute le linting

lint-yaml: ## Vérifie la syntaxe YAML
	@echo "[INFO] Vérification de la syntaxe YAML..."
	$(PYTHON) -c "import yaml; yaml.safe_load(open('$(MODULE_FILE)'))" 2>/dev/null || echo "[WARN] Fichier non YAML: $(MODULE_FILE)"
	for file in $$(find $(PLAYBOOKS_DIR) -name "*.yml" -o -name "*.yaml"); do \
		$(PYTHON) -c "import yaml; yaml.safe_load(open('$$file'))" && echo "[OK] $$file" || echo "[ERROR] $$file" ; \
	done
	@echo "[SUCCESS] Vérification YAML terminée"

lint-python: ## Vérifie la syntaxe Python
	@echo "[INFO] Vérification de la syntaxe Python..."
	$(PYTHON) -m py_compile $(MODULE_FILE)
	$(PYTHON) -m py_compile $(COLLECTION_MODULE_FILE)
	$(PYTHON) -m py_compile $(COLLECTION_MODULE_UTILS_FILE)
	for file in $$(find $(TESTS_DIR) -name "*.py"); do \
		$(PYTHON) -m py_compile $$file && echo "[OK] $$file" || echo "[ERROR] $$file" ; \
	done
	@echo "[SUCCESS] Vérification Python terminée"

# ============================================================================
# NETTOYAGE
# ============================================================================

clean: clean-build clean-test ## Nettoie les fichiers temporaires

clean-build: ## Nettoie les fichiers de build
	@echo "[INFO] Nettoyage des fichiers de build..."
	rm -f $(COLLECTION_DIR)/*.tar.gz
	@echo "[SUCCESS] Fichiers de build nettoyés"

clean-test: ## Nettoie les fichiers de test
	@echo "[INFO] Nettoyage des fichiers de test..."
	rm -rf .pytest_cache
	rm -rf __pycache__
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	@echo "[SUCCESS] Fichiers de test nettoyés"

# ============================================================================
# DÉPLOIEMENT
# ============================================================================

deploy: build install ## Déploie la collection (build + install)

# ============================================================================
# PLAYBOOKS
# ============================================================================

run-test-playbook: ## Exécute le playbook de test
	@echo "[INFO] Exécution du playbook de test..."
	ANSIBLE_CONFIG=ansible.cfg ansible-playbook $(PLAYBOOKS_DIR)/test_incus_cli.yml -v

run-bastion-playbook: ## Exécute le playbook de déploiement de The Bastion
	@echo "[INFO] Exécution du playbook The Bastion..."
	ANSIBLE_CONFIG=ansible.cfg ansible-playbook $(PLAYBOOKS_DIR)/deploy_the_bastion.yml -v

# ============================================================================
# UTILITAIRES
# ============================================================================

check-syntax: ## Vérifie la syntaxe de tous les fichiers
	@echo "[INFO] Vérification de la syntaxe..."
	make lint-yaml
	make lint-python
	@echo "[SUCCESS] Vérification de la syntaxe terminée"

show-version: ## Affiche la version
	@echo "Version: $(COLLECTION_VERSION)"
