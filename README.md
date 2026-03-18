<div align="center">

# Polymarket BTC Prediction Bot

**ML-powered bot that predicts Bitcoin price direction on [Polymarket](https://polymarket.com) 5-minute markets**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)](https://python.org)
[![XGBoost](https://img.shields.io/badge/Model-XGBoost-ff6600?logo=xgboost)](https://xgboost.readthedocs.io/)
[![Polymarket](https://img.shields.io/badge/Target-Polymarket-6366f1)](https://polymarket.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## What It Does

Every 5 minutes, [Polymarket](https://polymarket.com/event/btc-updown-5m-1773868500) opens a market: **"Will BTC be higher or lower in 5 minutes?"**

This bot:
1. **Collects** real-time data via Binance WebSocket (order book, trades, candles, funding rates)
2. **Computes** 40+ features (microstructure, momentum, volatility, sentiment)
3. **Predicts** BTC direction using a calibrated XGBoost model
4. **Detects edge** by comparing model probability vs market price
5. **Sizes bets** using fractional Kelly Criterion
6. **Places bets** on Polymarket (paper or real)

## Architecture

```
Binance WebSocket (real-time)        Alternative Data
├── 1m candles                        ├── Funding rates
├── L2 order book (100ms)             ├── Open interest
├── Trade tape                        ├── Liquidations
└── Best bid/ask                      └── Fear & Greed index
         │                                    │
         └──────────────┬─────────────────────┘
                        ▼
              Feature Engine (40+ features)
              ├── Order book imbalance
              ├── Trade flow (CVD, buy/sell ratio)
              ├── Momentum (RSI, MACD, BB)
              └── Volatility (ATR, realized vol)
                        │
                        ▼
              XGBoost + Isotonic Calibration
              (walk-forward validated)
                        │
                        ▼
              Edge Detection + Kelly Sizing
              (only bet when model > market)
                        │
                        ▼
              Polymarket CLOB API
              (py-clob-client on Polygon)
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train the model (fetches 30 days of 1m BTC data)
cd bot && python train_model.py

# 3. Run backtest to evaluate
python backtest.py

# 4. Start paper trading
cd .. && python run.py
```

Dashboard available at `http://localhost:8000`

## Project Structure

```
├── bot/
│   ├── data_collector.py    # Binance WebSocket streams (7 data sources)
│   ├── features.py          # 40+ feature computation engine
│   ├── train_model.py       # XGBoost training + walk-forward validation
│   ├── predict.py           # Calibrated probability predictions
│   ├── strategy.py          # Edge detection + risk management
│   ├── bet_sizing.py        # Fractional Kelly Criterion
│   ├── polymarket_client.py # Polymarket API wrapper
│   ├── paper_trading.py     # Main async trading loop
│   └── backtest.py          # Historical strategy simulation
├── api/
│   └── main.py              # FastAPI REST endpoints
├── web/
│   ├── index.html           # Dashboard UI
│   ├── styles.css           # Dark theme styles
│   └── dashboard.js         # Real-time data polling
├── config.json              # All configuration
├── run.py                   # Unified launcher
└── requirements.txt
```

## Key Technologies

| Component | Technology | Why |
|-----------|-----------|-----|
| ML Model | XGBoost | 84% accuracy vs 50% LSTM in crypto benchmarks |
| Validation | Walk-forward + purged gap | Prevents data leakage in time series |
| Calibration | Isotonic regression | Converts scores to true probabilities |
| Bet sizing | Fractional Kelly (0.25x) | Mathematically optimal with reduced variance |
| Data | Binance WebSocket | Real-time order book + trades, no API key needed |
| Target | Polymarket CLOB | On-chain settlement, ~$60M daily volume on BTC 5m |
| Metrics | Brier score, log loss, ECE | Proper probabilistic evaluation |

## Configuration

All parameters in `config.json`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `kelly_fraction` | 0.25 | Fraction of full Kelly (lower = safer) |
| `min_edge` | 0.03 | Minimum edge to place a bet (3%) |
| `min_bet` | $1.00 | Minimum bet size in USDC |
| `max_bet` | $25.00 | Maximum bet size |
| `prediction_interval` | 300s | Prediction cycle (5 minutes) |
| `cooldown_after_loss` | 600s | Pause after 3 consecutive losses |

## How It Works

### Edge Detection

The bot only bets when it finds an **edge** — when its calibrated probability differs significantly from the market price:

```
Model says: 62% chance BTC goes UP
Market price: 50¢ (implies 50%)
Edge = 62% - 50% = 12% → BET UP

Model says: 53% chance BTC goes UP
Market price: 52¢ (implies 52%)
Edge = 53% - 52% = 1% → SKIP (below 3% threshold)
```

### Kelly Criterion

Instead of flat betting, the bot sizes bets mathematically:

```
Full Kelly = (p × b - q) / b
Fractional Kelly = Full Kelly × 0.25

Where: p = win prob, q = 1-p, b = net odds
```

This ensures larger bets on high-confidence predictions and smaller bets on marginal edges.

## Roadmap

- [ ] Live Polymarket integration (real USDC bets)
- [ ] Order book features from historical data (Tardis.dev)
- [ ] Multi-timeframe model ensemble (1m + 5m + 15m)
- [ ] Reinforcement learning for dynamic threshold optimization
- [ ] Telegram/Discord alerts

## License

MIT — see [LICENSE](LICENSE) for details.
