.PHONY: help test test-unit validate pre-commit-setup pre-commit-run clean \
        network up down migrate cosign-keygen logs-defectdojo logs-falco

help: ## Show this help message
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# Stack Lifecycle
# ============================================================================

network: ## Create fawkes-net if it does not exist
	docker network create fawkes-net || true

up: network ## Start uFawkesSec stack (requires uFawkesRes running)
	docker compose up -d
	@echo ""
	@echo "DefectDojo: http://localhost:8080"
	@echo "Infisical:  http://localhost:8082"

down: ## Stop uFawkesSec stack
	docker compose down

migrate: ## Run DefectDojo database migration and create superuser
	@echo "Running DefectDojo database migration..."
	docker compose exec defectdojo python manage.py migrate
	@echo "Creating DefectDojo superuser..."
	docker compose exec defectdojo python manage.py createsuperuser --noinput
	@echo "✅ DefectDojo migration complete"
	@echo ""
	@echo "Required env vars (must be set before make migrate):"
	@echo "  DJANGO_SUPERUSER_USERNAME"
	@echo "  DJANGO_SUPERUSER_PASSWORD"
	@echo "  DJANGO_SUPERUSER_EMAIL"

cosign-keygen: ## Generate Cosign key pair (run once; store private key in Woodpecker secret)
	cosign generate-key-pair
	@echo ""
	@echo "Store cosign.key in Woodpecker secret 'cosign_private_key'"
	@echo "Commit cosign.pub to the repo"
	@rm -f cosign.key
	@echo "✅ cosign.key removed from disk (private key only in Woodpecker)"

logs-defectdojo: ## Tail DefectDojo logs
	docker compose logs -f defectdojo defectdojo-nginx

logs-falco: ## Tail Falco security events
	docker compose logs -f falco

# ============================================================================
# Test Commands
# ============================================================================

test: test-unit ## Run all tests
	@echo "All tests passed"

test-unit: ## Run unit tests
	pytest tests/unit/ -v --tb=short

test-coverage: ## Run tests with coverage report
	pytest tests/unit/ -v --tb=short --cov=tests/unit --cov-report=term-missing

# ============================================================================
# Validation Commands
# ============================================================================

validate: pre-commit-run ## Validate all files (alias for pre-commit-run)

# ============================================================================
# Pre-commit Commands
# ============================================================================

pre-commit-setup: ## Install pre-commit hooks
	@pip install pre-commit
	@pre-commit install
	@echo "✅ Pre-commit hooks installed"

pre-commit-run: ## Run all pre-commit hooks
	@pre-commit run --all-files

# ============================================================================
# Cleanup
# ============================================================================

clean: ## Clean up test artifacts
	rm -rf .pytest_cache __pycache__ tests/__pycache__ tests/unit/__pycache__
	rm -rf htmlcov .coverage coverage.xml
