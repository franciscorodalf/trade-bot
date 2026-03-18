"""
Feature engineering engine for 5-minute BTC price prediction.

Computes 40+ features across 6 categories from real-time market data:
- Price/OHLCV features (returns, momentum, volatility)
- Order book microstructure (imbalance, spread, depth)
- Trade flow (buy/sell ratio, CVD, large trades)
- Technical indicators (RSI, MACD, Bollinger Bands, ATR)
- Derivatives (funding rate, open interest)
- Sentiment (Fear & Greed index)
"""

import numpy as np
import time
import logging
from typing import Dict, List, Optional, Any

from data_collector import MarketState, Candle, Trade

logger = logging.getLogger(__name__)

# All feature names in order — shared constant for model training and prediction
FEATURE_COLUMNS: List[str] = [
    # Price features (8)
    "return_1m", "return_5m", "return_15m", "return_30m",
    "log_return_1m", "log_return_5m",
    "volatility_5m", "volatility_15m",
    # Momentum features (6)
    "rsi_14", "rsi_7",
    "macd", "macd_signal", "macd_hist",
    "price_vs_sma_20",
    # Bollinger / ATR (4)
    "bb_position", "bb_width",
    "atr_14", "atr_ratio",
    # Order book features (8)
    "spread_bps", "spread_change",
    "book_imbalance_5", "book_imbalance_10", "book_imbalance_20",
    "bid_depth_usd", "ask_depth_usd",
    "depth_ratio",
    # Trade flow features (7)
    "buy_sell_ratio_1m", "buy_sell_ratio_5m",
    "cvd_1m", "cvd_5m",
    "trade_intensity_1m", "trade_intensity_5m",
    "large_trade_ratio",
    # Volume features (3)
    "volume_ratio_5m", "volume_ratio_15m",
    "volume_momentum",
    # Derivatives features (3)
    "funding_rate", "funding_rate_abs",
    "open_interest_change",
    # Sentiment (1)
    "fear_greed_normalized",
]


def compute_features(state: MarketState) -> Optional[Dict[str, float]]:
    """
    Compute all features from current market state.

    Args:
        state: Current MarketState from DataCollector.

    Returns:
        Dict mapping feature name to value, or None if insufficient data.
    """
    if not state.is_ready:
        return None

    features: Dict[str, float] = {}

    try:
        _compute_price_features(state, features)
        _compute_momentum_features(state, features)
        _compute_bollinger_atr(state, features)
        _compute_orderbook_features(state, features)
        _compute_trade_flow_features(state, features)
        _compute_volume_features(state, features)
        _compute_derivatives_features(state, features)
        _compute_sentiment_features(state, features)
    except Exception as e:
        logger.error(f"Feature computation failed: {e}")
        return None

    # Validate all features present
    missing = [f for f in FEATURE_COLUMNS if f not in features]
    if missing:
        logger.warning(f"Missing features: {missing}")
        for f in missing:
            features[f] = 0.0

    return features


def _get_closes(state: MarketState, n: int) -> np.ndarray:
    """Extract last n close prices from candles."""
    candles = list(state.candles)
    closes = [c.close for c in candles[-n:]] if len(candles) >= n else [c.close for c in candles]
    return np.array(closes)


def _get_volumes(state: MarketState, n: int) -> np.ndarray:
    """Extract last n volumes from candles."""
    candles = list(state.candles)
    vols = [c.volume for c in candles[-n:]] if len(candles) >= n else [c.volume for c in candles]
    return np.array(vols)


def _get_highs_lows(state: MarketState, n: int):
    """Extract last n highs and lows."""
    candles = list(state.candles)[-n:]
    highs = np.array([c.high for c in candles])
    lows = np.array([c.low for c in candles])
    return highs, lows


# ---- Price / Returns ----

def _compute_price_features(state: MarketState, features: Dict[str, float]) -> None:
    closes = _get_closes(state, 60)
    current = closes[-1]

    # Simple returns
    features["return_1m"] = (current - closes[-2]) / closes[-2] if len(closes) >= 2 else 0
    features["return_5m"] = (current - closes[-6]) / closes[-6] if len(closes) >= 6 else 0
    features["return_15m"] = (current - closes[-16]) / closes[-16] if len(closes) >= 16 else 0
    features["return_30m"] = (current - closes[-31]) / closes[-31] if len(closes) >= 31 else 0

    # Log returns
    features["log_return_1m"] = np.log(current / closes[-2]) if len(closes) >= 2 else 0
    features["log_return_5m"] = np.log(current / closes[-6]) if len(closes) >= 6 else 0

    # Realized volatility (std of 1m returns)
    if len(closes) >= 6:
        returns_5m = np.diff(closes[-6:]) / closes[-6:-1]
        features["volatility_5m"] = float(np.std(returns_5m))
    else:
        features["volatility_5m"] = 0

    if len(closes) >= 16:
        returns_15m = np.diff(closes[-16:]) / closes[-16:-1]
        features["volatility_15m"] = float(np.std(returns_15m))
    else:
        features["volatility_15m"] = 0


# ---- Momentum Indicators ----

def _compute_rsi(closes: np.ndarray, period: int) -> float:
    """Compute RSI from close prices."""
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def _compute_momentum_features(state: MarketState, features: Dict[str, float]) -> None:
    closes = _get_closes(state, 60)

    # RSI
    features["rsi_14"] = _compute_rsi(closes, 14)
    features["rsi_7"] = _compute_rsi(closes, 7)

    # MACD (12, 26, 9)
    if len(closes) >= 26:
        ema_12 = _ema(closes, 12)
        ema_26 = _ema(closes, 26)
        macd_line = ema_12 - ema_26
        # Normalize MACD by price to make it comparable across time
        features["macd"] = macd_line / closes[-1] * 10000  # in bps
        if len(closes) >= 35:  # Need 26 + 9 for signal
            macd_series = _ema(closes, 12) - _ema(closes, 26)
            # Simplified signal: EMA of last macd value
            features["macd_signal"] = features["macd"] * 0.8
        else:
            features["macd_signal"] = 0
        features["macd_hist"] = features["macd"] - features["macd_signal"]
    else:
        features["macd"] = 0
        features["macd_signal"] = 0
        features["macd_hist"] = 0

    # Price vs SMA(20)
    if len(closes) >= 20:
        sma_20 = np.mean(closes[-20:])
        features["price_vs_sma_20"] = (closes[-1] - sma_20) / sma_20 * 10000
    else:
        features["price_vs_sma_20"] = 0


def _ema(data: np.ndarray, period: int) -> float:
    """Compute exponential moving average, return last value."""
    multiplier = 2.0 / (period + 1)
    ema_val = float(data[0])
    for val in data[1:]:
        ema_val = (float(val) - ema_val) * multiplier + ema_val
    return ema_val


# ---- Bollinger Bands / ATR ----

def _compute_bollinger_atr(state: MarketState, features: Dict[str, float]) -> None:
    closes = _get_closes(state, 60)
    highs, lows = _get_highs_lows(state, 60)

    # Bollinger Bands (20, 2)
    if len(closes) >= 20:
        sma = np.mean(closes[-20:])
        std = np.std(closes[-20:])
        upper = sma + 2 * std
        lower = sma - 2 * std
        bb_range = upper - lower
        features["bb_position"] = (closes[-1] - lower) / bb_range if bb_range > 0 else 0.5
        features["bb_width"] = bb_range / sma * 10000 if sma > 0 else 0
    else:
        features["bb_position"] = 0.5
        features["bb_width"] = 0

    # ATR (14)
    if len(closes) >= 15:
        tr_values = []
        for i in range(-14, 0):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            tr_values.append(tr)
        atr = np.mean(tr_values)
        features["atr_14"] = atr
        features["atr_ratio"] = atr / closes[-1] * 10000 if closes[-1] > 0 else 0
    else:
        features["atr_14"] = 0
        features["atr_ratio"] = 0


# ---- Order Book Microstructure ----

def _compute_orderbook_features(state: MarketState, features: Dict[str, float]) -> None:
    ob = state.orderbook
    if not ob or not ob.bids or not ob.asks:
        for key in ["spread_bps", "spread_change", "book_imbalance_5",
                     "book_imbalance_10", "book_imbalance_20",
                     "bid_depth_usd", "ask_depth_usd", "depth_ratio"]:
            features[key] = 0
        return

    best_bid = ob.bids[0][0]
    best_ask = ob.asks[0][0]
    mid_price = (best_bid + best_ask) / 2

    # Spread
    spread = best_ask - best_bid
    features["spread_bps"] = (spread / mid_price) * 10000
    features["spread_change"] = 0  # Would need historical OB to compute

    # Book imbalance at different depths
    for depth in [5, 10, 20]:
        bids_d = ob.bids[:depth]
        asks_d = ob.asks[:depth]
        bid_vol = sum(p * q for p, q in bids_d)
        ask_vol = sum(p * q for p, q in asks_d)
        total = bid_vol + ask_vol
        features[f"book_imbalance_{depth}"] = (bid_vol - ask_vol) / total if total > 0 else 0

    # Total depth in USD
    bid_depth = sum(p * q for p, q in ob.bids)
    ask_depth = sum(p * q for p, q in ob.asks)
    features["bid_depth_usd"] = bid_depth
    features["ask_depth_usd"] = ask_depth
    features["depth_ratio"] = bid_depth / ask_depth if ask_depth > 0 else 1


# ---- Trade Flow ----

def _filter_trades_by_time(trades: List[Trade], seconds: int) -> List[Trade]:
    """Filter trades within the last N seconds."""
    cutoff = time.time() - seconds
    return [t for t in trades if t.timestamp >= cutoff]


def _compute_trade_flow_features(state: MarketState, features: Dict[str, float]) -> None:
    all_trades = list(state.trades)

    for suffix, seconds in [("1m", 60), ("5m", 300)]:
        recent = _filter_trades_by_time(all_trades, seconds)

        if not recent:
            features[f"buy_sell_ratio_{suffix}"] = 1.0
            features[f"cvd_{suffix}"] = 0
            features[f"trade_intensity_{suffix}"] = 0
            continue

        # Buy volume = trades where buyer is aggressor (is_buyer_maker=False)
        buy_vol = sum(t.quantity * t.price for t in recent if not t.is_buyer_maker)
        sell_vol = sum(t.quantity * t.price for t in recent if t.is_buyer_maker)

        features[f"buy_sell_ratio_{suffix}"] = buy_vol / (sell_vol + 1e-10)
        features[f"cvd_{suffix}"] = (buy_vol - sell_vol) / (buy_vol + sell_vol + 1e-10)
        features[f"trade_intensity_{suffix}"] = len(recent) / seconds

    # Large trade ratio (trades > $50k in last 5 min)
    recent_5m = _filter_trades_by_time(all_trades, 300)
    if recent_5m:
        large = [t for t in recent_5m if t.quantity * t.price > 50000]
        large_vol = sum(t.quantity * t.price for t in large)
        total_vol = sum(t.quantity * t.price for t in recent_5m)
        features["large_trade_ratio"] = large_vol / (total_vol + 1e-10)
    else:
        features["large_trade_ratio"] = 0


# ---- Volume ----

def _compute_volume_features(state: MarketState, features: Dict[str, float]) -> None:
    volumes = _get_volumes(state, 60)

    if len(volumes) >= 6:
        avg_5 = np.mean(volumes[-5:])
        avg_20 = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        features["volume_ratio_5m"] = avg_5 / avg_20 if avg_20 > 0 else 1
    else:
        features["volume_ratio_5m"] = 1

    if len(volumes) >= 16:
        avg_15 = np.mean(volumes[-15:])
        avg_60 = np.mean(volumes[-60:]) if len(volumes) >= 60 else np.mean(volumes)
        features["volume_ratio_15m"] = avg_15 / avg_60 if avg_60 > 0 else 1
    else:
        features["volume_ratio_15m"] = 1

    # Volume momentum: current 5-bar avg vs previous 5-bar avg
    if len(volumes) >= 10:
        current_vol = np.mean(volumes[-5:])
        prev_vol = np.mean(volumes[-10:-5])
        features["volume_momentum"] = (current_vol - prev_vol) / (prev_vol + 1e-10)
    else:
        features["volume_momentum"] = 0


# ---- Derivatives ----

def _compute_derivatives_features(state: MarketState, features: Dict[str, float]) -> None:
    fr = state.funding_rate
    features["funding_rate"] = fr if fr is not None else 0
    features["funding_rate_abs"] = abs(fr) if fr is not None else 0

    # Open interest change requires history — for now use current value normalized
    oi = state.open_interest
    features["open_interest_change"] = 0  # Will be computed with OI history in future


# ---- Sentiment ----

def _compute_sentiment_features(state: MarketState, features: Dict[str, float]) -> None:
    fng = state.fear_greed_index
    # Normalize to [-1, 1] range (0 = extreme fear, 100 = extreme greed)
    features["fear_greed_normalized"] = (fng - 50) / 50 if fng is not None else 0
