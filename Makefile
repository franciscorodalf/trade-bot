# ============================================
# Polymarket BTC Prediction Bot — Makefile
# ============================================

.PHONY: help install train backtest run api test lint clean docker-up docker-down

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

train: ## Train XGBoost model (fetches 30 days of 1m data)
	cd bot && python train_model.py

backtest: ## Run walk-forward backtest
	cd bot && python backtest.py

run: ## Start bot + API + dashboard
	python run.py

run-train: ## Train model, then start everything
	python run.py --train

api: ## Start API server only
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Run all tests
	pytest tests/ -v

lint: ## Check code with flake8
	flake8 bot/ api/ --max-line-length=120 --ignore=E501,W503

clean: ## Remove generated files
	rm -rf database/ logs/ bot/models/*.pkl __pycache__ .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

docker-up: ## Build and start with Docker Compose
	docker compose up --build -d

docker-down: ## Stop Docker containers
	docker compose down
