# ============================================
# AI Trading Bot — Makefile
# Common commands for development & deployment
# ============================================

.PHONY: help install train run run-all run-bot run-api run-web docker-up docker-down docker-logs clean test backtest retrain

# Default
help: ## Show this help message
	@echo ""
	@echo "  AI Trading Bot — Available Commands"
	@echo "  ======================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ---- Setup ----
install: ## Install Python dependencies
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	@mkdir -p database logs bot/models
	@echo "\n✅ Setup complete. Run 'make train' to train the ML model."

# ---- ML Model ----
train: ## Train the AI model on historical data
	. venv/bin/activate && python3 bot/train_model.py

retrain: ## Retrain model with fresh market data
	. venv/bin/activate && python3 bot/retrain_model.py

# ---- Run (Local) ----
run: ## Start ALL services in one terminal (Bot + API + Web)
	. venv/bin/activate && python3 run.py

run-bot: ## Start the trading bot only
	. venv/bin/activate && python3 bot/paper_trading.py

run-api: ## Start the FastAPI server
	. venv/bin/activate && uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

run-web: ## Start the web dashboard (port 5500)
	cd web && python3 -m http.server 5500

# ---- Docker ----
docker-up: ## Start all services with Docker Compose
	@test -f .env || cp .env.example .env
	docker compose up --build -d
	@echo "\n🚀 Dashboard: http://localhost:5500"
	@echo "📡 API:       http://localhost:8000"

docker-down: ## Stop all Docker services
	docker compose down

docker-logs: ## View logs from all services
	docker compose logs -f

# ---- Testing ----
backtest: ## Run backtesting on historical data
	. venv/bin/activate && python3 bot/backtest.py

test: ## Run unit tests
	. venv/bin/activate && python3 -m pytest tests/ -v

# ---- Maintenance ----
clean: ## Remove generated files (models, db, logs)
	rm -rf database/*.db logs/*.log bot/models/*.pkl
	rm -f backtest_trades.csv bot_status.json
	@echo "🧹 Cleaned generated files."
