.PHONY: install dev test lint typecheck format run docker-build docker-up docker-down clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

dev: ## Install with dev dependencies
	uv sync --extra dev

test: ## Run tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=leo_risk --cov-report=term-missing

lint: ## Run linter
	uv run ruff check src/ tests/

typecheck: ## Run type checker
	uv run mypy src/

format: ## Format code
	uv run ruff format src/ tests/

format-check: ## Check formatting without changes
	uv run ruff format --check src/ tests/

run: ## Run development server
	uv run uvicorn leo_risk.interface.http.app:app --reload

docker-build: ## Build Docker image
	docker compose build

docker-up: ## Start services
	docker compose up -d

docker-down: ## Stop services
	docker compose down

clean: ## Remove build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
