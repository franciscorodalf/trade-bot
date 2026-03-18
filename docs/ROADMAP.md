# Roadmap

## Phase 1: Core Bot (current)
- [x] Real-time data collection (Binance WebSocket)
- [x] 40+ feature engine (order book, trade flow, momentum)
- [x] XGBoost model with walk-forward validation
- [x] Isotonic probability calibration
- [x] Fractional Kelly bet sizing
- [x] Paper trading loop
- [x] Backtesting engine
- [x] Web dashboard

## Phase 2: Live Trading
- [ ] Polymarket CLOB integration (real USDC bets)
- [ ] Wallet management and USDC deposit flow
- [ ] Real-time market price from Polymarket WebSocket
- [ ] Fee-aware bet sizing (3% taker fee on 5-min markets)

## Phase 3: Model Improvements
- [ ] Historical order book data (Tardis.dev) for training
- [ ] Multi-timeframe ensemble (1m + 5m + 15m)
- [ ] LightGBM/CatBoost model comparison
- [ ] Feature importance drift detection
- [ ] Auto-retraining pipeline

## Phase 4: Advanced
- [ ] Reinforcement learning for dynamic thresholds
- [ ] Market making on Polymarket (provide liquidity)
- [ ] Telegram/Discord alerts
- [ ] Multi-asset support (ETH, SOL prediction markets)
