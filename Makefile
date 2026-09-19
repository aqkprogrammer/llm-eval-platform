.DEFAULT_GOAL := help
API_PORT ?= 8000

.PHONY: help install dev dev-api dev-web test lint format typecheck seed eval up down logs migrate build-web clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (uv) and frontend (npm) dependencies
	uv sync
	cd frontend && npm ci

dev: ## Run API (:8000) and Vite dev server (:5173) together
	@trap 'kill 0' INT TERM; \
	uv run evalctl serve --port $(API_PORT) --reload & \
	cd frontend && API_URL=http://localhost:$(API_PORT) npm run dev & \
	wait

dev-api: ## Run only the API with auto-reload
	uv run evalctl serve --port $(API_PORT) --reload

dev-web: ## Run only the Vite dev server
	cd frontend && API_URL=http://localhost:$(API_PORT) npm run dev

test: ## Run the backend test suite
	uv run pytest

lint: ## Lint backend (ruff) and frontend (eslint + tsc)
	uv run ruff check .
	uv run ruff format --check .
	cd frontend && npm run lint && npm run typecheck

format: ## Auto-format backend code
	uv run ruff check --fix .
	uv run ruff format .

seed: ## Load sample datasets/prompts/models, run demo experiments, simulate traffic
	uv run evalctl seed

eval: ## Run the example CI evaluation suite
	uv run evalctl run examples/eval-config.yaml --ephemeral --output eval-report.json

migrate: ## Apply Alembic migrations to DATABASE_URL
	uv run evalctl migrate

build-web: ## Build the dashboard into frontend/dist (served by the API locally)
	cd frontend && npm run build

up: ## Start the full stack with Docker Compose
	docker compose up -d --build

down: ## Stop the stack and remove volumes
	docker compose down -v

logs: ## Tail Docker Compose logs
	docker compose logs -f --tail=100

clean: ## Remove local caches and databases
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage evalplatform.db* frontend/dist
