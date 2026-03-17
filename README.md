<div align="center">

# AI Quantitative Trading Bot

### Autonomous Cryptocurrency Trading System Powered by Machine Learning

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![Binance](https://img.shields.io/badge/Binance_Futures-F0B90B?style=for-the-badge&logo=binance&logoColor=black)](https://www.binance.com)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-66_passed-00d68f?style=for-the-badge&logo=pytest&logoColor=white)](#testing)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

<br/>

An end-to-end automated trading pipeline that combines **technical analysis** with a **Random Forest ML model** to scan 12+ cryptocurrency pairs simultaneously, identify high-probability trading opportunities, and execute simulated trades with dynamic ATR-based risk management — all visualized through a real-time web dashboard.

<br/>

[Features](#-features) · [Architecture](#-architecture) · [Tech Stack](#-tech-stack) · [Getting Started](#-getting-started) · [API Reference](#-api-reference) · [Documentation](#-documentation) · [Roadmap](#-roadmap)

</div>

<br/>

---

## Highlights

<table>
<tr>
<td width="50%">

### Real-Time AI Market Scanner
The bot continuously scans **12 cryptocurrency pairs** (BTC, ETH, SOL, BNB, ADA, XRP, DOGE, PEPE, SHIB, LTC, AVAX, LINK) every 60 seconds, ranking opportunities by ML confidence score.

</td>
<td width="50%">

### Dynamic Risk Management
Position sizing and stop-losses are calculated dynamically using **ATR (Average True Range)**, adapting to market volatility in real-time. Never risks more than 2% per trade.

</td>
</tr>
<tr>
<td width="50%">

### Universal ML Model
A single **Random Forest Classifier** trained on combined data from all symbols learns general crypto market patterns — making it adaptable to new assets without retraining.

</td>
<td width="50%">

### Live Web Dashboard
Interactive command center with **TradingView charts**, portfolio tracking, trade history, and system logs — all updating in real-time via polling.

</td>
</tr>
</table>

---

## Features

- **Multi-Symbol Scanner** — Monitors 12+ pairs simultaneously, ranking by prediction confidence
- **ML-Powered Signals** — Random Forest model trained on 25 technical features (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, lag features)
- **ATR-Based Stop Loss / Take Profit** — Dynamic exits that adapt to market volatility (1.5× ATR for SL, 2.5× ATR for TP)
- **Volatility Filter** — Automatically skips low-volatility markets to avoid noise and fee erosion
- **Paper Trading Engine** — Realistic simulation with commission (0.05%) and slippage (0.03%) modeling
- **Portfolio Management** — Configurable max open positions (default: 3) with per-trade risk limits
- **RESTful API** — FastAPI backend serving real-time data for scanner, charts, trades, and statistics
- **Interactive Dashboard** — Dark-themed SPA with candlestick charts, trade tables, and live system logs
- **Pause/Resume Control** — Toggle bot execution from the dashboard without stopping the process
- **Backtesting Engine** — Validate strategies on historical data with equity curve and Sharpe Ratio metrics
- **Auto-Retraining** — Script for scheduled model updates with fresh market data

---

## Architecture

The system follows a **modular, decoupled architecture** where each component operates independently but coordinates through a central SQLite database:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SYSTEM ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐      ┌──────────────────┐      ┌────────────┐  │
│   │  Binance API  │─────▶│   Bot Engine      │─────▶│  SQLite DB │  │
│   │  (CCXT)       │ OHLCV│                  │Trades│            │  │
│   └──────────────┘      │  ┌────────────┐  │      └─────┬──────┘  │
│                         │  │ ML Model   │  │            │         │
│                         │  │ (RF)       │  │            │         │
│                         │  └────────────┘  │            │         │
│                         │  ┌────────────┐  │            │         │
│                         │  │ Strategy   │  │      ┌─────▼──────┐  │
│                         │  │ (ATR/SL/TP)│  │      │  FastAPI    │  │
│                         │  └────────────┘  │      │  Backend    │  │
│                         └──────────────────┘      └─────┬──────┘  │
│                                                         │ REST    │
│                                                   ┌─────▼──────┐  │
│                                                   │    Web      │  │
│                                                   │  Dashboard  │  │
│                                                   └────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Binance → Raw OHLCV → Feature Engineering (25 indicators) → ML Prediction
    → Signal (BUY/SELL/HOLD) + Confidence Score
        → Strategy Validation (volatility filter, position limits)
            → Trade Execution (paper) → Database → API → Dashboard
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **ML Engine** | scikit-learn | Random Forest Classifier for market prediction |
| **Data Pipeline** | pandas, numpy | Feature engineering & data manipulation |
| **Technical Analysis** | ta (Technical Analysis Library) | 25+ indicator calculations |
| **Exchange Connectivity** | CCXT | Binance Futures market data via REST |
| **Backend API** | FastAPI + Uvicorn | Async REST API serving real-time data |
| **Database** | SQLite | Lightweight persistence for trades, signals, balances |
| **Frontend** | HTML5, CSS3, Vanilla JS | Zero-dependency responsive dashboard |
| **Charts** | TradingView Lightweight Charts | Professional candlestick visualization |
| **Model Persistence** | joblib | Efficient ML model serialization |
| **Containerization** | Docker + Compose | One-command deployment of all services |
| **Web Server** | Nginx (Docker) | Static file serving for dashboard |

---

## Getting Started

### Quick Start with Docker (Recommended)

The fastest way to run the entire system with a single command:

```bash
# Clone the repository
git clone https://github.com/tu-usuario/trade-bot.git
cd trade-bot

# Copy environment template
cp .env.example .env

# Train the ML model first
make install && make train

# Launch everything
make docker-up
```

> **Dashboard**: http://localhost:5500 · **API**: http://localhost:8000

### Manual Installation

If you prefer running without Docker:

```bash
# Clone & setup
git clone https://github.com/tu-usuario/trade-bot.git
cd trade-bot
make install

# Train the AI model (~1-2 min)
make train

# Launch all services in a single terminal
make run
```

> This starts **Bot + API + Web** in one process. Press `Ctrl+C` to stop all.

You can also start services individually (3 separate terminals):

```bash
make run-bot    # Terminal 1 — Trading Engine
make run-api    # Terminal 2 — API Server
make run-web    # Terminal 3 — Web Dashboard
```

Open your browser at **http://localhost:5500** to access the dashboard.

### Available Commands

```bash
make help       # Show all commands
make install    # Setup virtual environment & dependencies
make train      # Train ML model on historical data
make retrain    # Retrain with fresh market data
make run        # Start ALL services (single terminal)
make run-bot    # Start trading bot only
make run-api    # Start FastAPI server only
make run-web    # Start web dashboard only
make docker-up  # Launch all services (Docker)
make docker-down # Stop all services
make backtest   # Run backtesting engine
make test       # Run unit tests (pytest)
make clean      # Remove generated files
```

### Configuration

All parameters are configurable via `config.json`:

```json
{
  "initial_capital": 80.0,
  "risk_per_trade": 0.02,
  "buy_threshold": 0.55,
  "sell_threshold": 0.40,
  "max_open_positions": 3,
  "timeframe": "1h",
  "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "..."]
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `initial_capital` | `80.0` | Starting balance for paper trading (USDT) |
| `risk_per_trade` | `0.02` | Maximum risk per trade (2% of balance) |
| `buy_threshold` | `0.55` | Minimum ML probability to trigger a BUY signal |
| `sell_threshold` | `0.40` | ML probability below which triggers a SELL signal |
| `max_open_positions` | `3` | Maximum concurrent open trades |
| `timeframe` | `"1h"` | Candlestick timeframe for analysis |
| `volatility_threshold` | `0.002` | Minimum volatility to consider trading |
| `commission_rate` | `0.0005` | Simulated trading fee (0.05%) |
| `slippage` | `0.0003` | Simulated price slippage (0.03%) |

---

## API Reference

The FastAPI backend exposes the following endpoints on `http://localhost:8000`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/scanner` | Latest ML signal for each symbol (sorted by confidence) |
| `GET` | `/balance` | Current balance and equity |
| `GET` | `/trades?limit=50` | Recent trade history |
| `GET` | `/statistics` | Win rate, total PnL, and trade count |
| `GET` | `/live-signal` | Most recent ML prediction |
| `GET` | `/chart-data?symbol=BTC/USDT` | OHLCV candlestick data |
| `GET` | `/logs?lines=20` | Latest system log entries |
| `POST` | `/control` | Pause/resume bot execution |

### Example Response — Scanner

```json
[
  {
    "symbol": "BTC/USDT",
    "signal_type": "BUY",
    "probability": 0.73,
    "close_price": 67542.50,
    "timestamp": "2026-03-17 14:30:00"
  }
]
```

---

## Project Structure

```
trade-bot/
├── api/
│   └── main.py              # FastAPI REST API server
├── bot/
│   ├── backtest.py           # Historical backtesting engine
│   ├── models/               # Trained ML model storage (.pkl)
│   ├── paper_trading.py      # Main trading loop
│   ├── predict.py            # Real-time prediction engine
│   ├── retrain_model.py      # Model retraining script
│   ├── strategy.py           # ATR-based risk management
│   ├── train_model.py        # ML training pipeline
│   └── utils.py              # Data fetching & indicators
├── database/                 # SQLite database
├── docs/
│   ├── ARCHITECTURE.md       # System architecture details
│   ├── ROADMAP.md            # Development roadmap
│   └── STRATEGY.md           # Trading strategy & AI docs
├── logs/                     # Application logs
├── tests/
│   ├── conftest.py           # Shared fixtures & mock data
│   ├── test_strategy.py      # Strategy & risk management tests
│   ├── test_utils.py         # Indicator calculation tests
│   ├── test_api.py           # FastAPI endpoint tests
│   └── test_model.py         # ML pipeline & prediction tests
├── web/
│   ├── dashboard.js          # Frontend logic & chart rendering
│   ├── index.html            # Dashboard HTML
│   └── styles.css            # Dark theme styling
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
├── config.json               # Central configuration
├── docker-compose.yml        # Multi-service orchestration
├── Dockerfile                # Container build instructions
├── Makefile                  # Development & deploy commands
├── pyproject.toml            # Modern Python project metadata
├── requirements.txt          # Python dependencies
├── run.py                    # Single-command launcher (all services)
└── README.md
```

---

## ML Model Details

### Training Pipeline

```
Data Collection (5,000 candles × 12 symbols)
    ↓
Feature Engineering (25 technical indicators)
    ↓
Label Generation (binary: next candle up/down)
    ↓
Train/Test Split (80/20)
    ↓
Random Forest Training (100 trees, max_depth=10)
    ↓
Model Evaluation (accuracy, confusion matrix)
    ↓
Serialization (joblib → model.pkl)
```

### Feature Set (25 inputs)

| Category | Features |
|----------|----------|
| **Trend** | SMA(20), SMA(50), EMA(12), MACD |
| **Momentum** | RSI(14) |
| **Volatility** | Bollinger Band Width, ATR(14), Return Std Dev |
| **Lag Features** | t-1, t-2, t-3 of all main indicators |

### Decision Logic

```
IF probability > 0.55 AND volatility > threshold AND open_positions < max
    → OPEN LONG (BUY)

IF probability < 0.40 OR price <= stop_loss OR price >= take_profit
    → CLOSE POSITION (SELL)

OTHERWISE → HOLD
```

---

## Testing

The project includes a comprehensive test suite using **pytest**:

```bash
make test
```

| Test Module | Coverage |
|-------------|----------|
| `test_strategy.py` | SL/TP calculation, exit detection, signal logic, position lifecycle |
| `test_utils.py` | Indicator calculation, feature validation, edge cases, data integrity |
| `test_api.py` | All REST endpoints, response formats, database queries, control actions |
| `test_model.py` | Feature consistency (train/predict parity), ML pipeline, threshold logic |

Tests use synthetic market data and in-memory databases — no network calls or API keys required.

---

## Documentation

For deep dives into specific areas:

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design, data flow, and component communication |
| [Strategy & AI](docs/STRATEGY.md) | ML model details, indicators, and risk management logic |
| [Roadmap](docs/ROADMAP.md) | Development phases and planned features |

---

## Roadmap

- [x] **Phase 1** — Core engine: ML model, paper trading, multi-symbol scanner, API & dashboard
- [x] **Phase 1.5** — DevOps: Docker + Compose, Makefile, `.env` configuration, professional dashboard redesign
- [ ] **Phase 2** — Performance: Async data fetching (`ccxt.async_support`), WebSocket streaming
- [ ] **Phase 3** — Advanced AI: Sentiment analysis, LSTM experiments, enhanced backtesting
- [ ] **Phase 4** — Production: Telegram/Discord alerts, live trading mode, CI/CD pipeline

---

## Disclaimer

> **This software is intended for educational and research purposes only.** Cryptocurrency trading involves significant risk of capital loss. Past model performance does not guarantee future results. Use at your own risk. This is a paper trading system — no real funds are at risk.

---

<div align="center">

**Built with discipline, data, and a lot of coffee.**

[![Python](https://img.shields.io/badge/Made_with-Python-3776AB?style=flat-square&logo=python&logoColor=white)](#)
[![ML](https://img.shields.io/badge/Powered_by-Machine_Learning-F7931E?style=flat-square&logo=scikit-learn&logoColor=white)](#)

</div>
