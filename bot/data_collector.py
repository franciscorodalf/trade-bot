"""
Real-time data collector using Binance WebSocket streams.

Collects 1-minute candles, Level 2 order book, trade tape,
funding rates, open interest, and liquidations — all without
API keys (public endpoints only).
"""

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import aiohttp
import websockets

logger = logging.getLogger(__name__)

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

WS_BASE = config["binance"]["ws_base"]
REST_BASE = config["binance"]["rest_base"]
SYMBOL = config["binance"]["symbol"].lower()
CANDLE_BUFFER = config["features"]["candle_buffer_size"]
TRADE_BUFFER = config["features"]["trade_buffer_size"]
OB_DEPTH = config["features"]["orderbook_depth"]
FUNDING_POLL = config["features"]["funding_poll_seconds"]
FNG_POLL = config["features"]["fear_greed_poll_seconds"]


@dataclass
class Candle:
    """Single OHLCV candle."""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool


@dataclass
class Trade:
    """Single trade from the tape."""
    timestamp: float
    price: float
    quantity: float
    is_buyer_maker: bool  # True = seller aggressor (sell), False = buyer aggressor (buy)


@dataclass
class OrderBookSnapshot:
    """Level 2 order book snapshot."""
    timestamp: float
    bids: List[List[float]] = field(default_factory=list)  # [[price, qty], ...]
    asks: List[List[float]] = field(default_factory=list)


@dataclass
class MarketState:
    """Complete market state at any point in time."""
    candles: deque = field(default_factory=lambda: deque(maxlen=CANDLE_BUFFER))
    orderbook: Optional[OrderBookSnapshot] = None
    trades: deque = field(default_factory=lambda: deque(maxlen=TRADE_BUFFER))
    funding_rate: Optional[float] = None
    open_interest: Optional[float] = None
    fear_greed_index: Optional[int] = None
    last_liquidation: Optional[Dict[str, Any]] = None
    last_update: float = 0.0
    is_ready: bool = False

    def check_ready(self) -> bool:
        """Check if we have enough data to make predictions."""
        has_candles = len(self.candles) >= 60  # At least 60 minutes
        has_orderbook = self.orderbook is not None
        has_trades = len(self.trades) >= 100
        self.is_ready = has_candles and has_orderbook and has_trades
        return self.is_ready


class DataCollector:
    """
    Async data collector that maintains real-time market state
    via Binance WebSocket streams and REST polling.

    All data sources are free and require no API keys.
    """

    def __init__(self) -> None:
        self.state = MarketState()
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """Start all data collection streams concurrently."""
        self._running = True
        logger.info("Starting data collector...")

        self._tasks = [
            asyncio.create_task(self._stream_candles()),
            asyncio.create_task(self._stream_orderbook()),
            asyncio.create_task(self._stream_trades()),
            asyncio.create_task(self._stream_liquidations()),
            asyncio.create_task(self._poll_funding_rate()),
            asyncio.create_task(self._poll_open_interest()),
            asyncio.create_task(self._poll_fear_greed()),
        ]

        logger.info(f"Data collector started — 7 streams active for {SYMBOL.upper()}")

    async def stop(self) -> None:
        """Stop all data collection streams."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Data collector stopped.")

    def get_state(self) -> MarketState:
        """Return current market state snapshot."""
        return self.state

    # ---- WebSocket Streams ----

    async def _ws_connect(self, stream: str):
        """Connect to a Binance WebSocket stream with auto-reconnect."""
        url = f"{WS_BASE}/{stream}"
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    logger.info(f"Connected to {stream}")
                    async for msg in ws:
                        if not self._running:
                            break
                        yield json.loads(msg)
            except (websockets.ConnectionClosed, ConnectionError) as e:
                logger.warning(f"WS {stream} disconnected: {e}. Reconnecting in 3s...")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"WS {stream} error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _stream_candles(self) -> None:
        """Stream 1-minute klines."""
        async for data in self._ws_connect(f"{SYMBOL}@kline_1m"):
            k = data["k"]
            candle = Candle(
                timestamp=k["t"] / 1000,
                open=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                is_closed=k["x"],
            )

            # Update or append candle
            if self.state.candles and not candle.is_closed:
                # Update current (incomplete) candle
                if (self.state.candles[-1].timestamp == candle.timestamp):
                    self.state.candles[-1] = candle
                else:
                    self.state.candles.append(candle)
            elif candle.is_closed:
                self.state.candles.append(candle)

            self.state.last_update = time.time()
            self.state.check_ready()

    async def _stream_orderbook(self) -> None:
        """Stream top-N order book levels updated every 100ms."""
        async for data in self._ws_connect(f"{SYMBOL}@depth{OB_DEPTH}@100ms"):
            self.state.orderbook = OrderBookSnapshot(
                timestamp=time.time(),
                bids=[[float(p), float(q)] for p, q in data["bids"]],
                asks=[[float(p), float(q)] for p, q in data["asks"]],
            )

    async def _stream_trades(self) -> None:
        """Stream aggregated trades."""
        async for data in self._ws_connect(f"{SYMBOL}@aggTrade"):
            trade = Trade(
                timestamp=data["T"] / 1000,
                price=float(data["p"]),
                quantity=float(data["q"]),
                is_buyer_maker=data["m"],
            )
            self.state.trades.append(trade)

    async def _stream_liquidations(self) -> None:
        """Stream forced liquidation orders."""
        async for data in self._ws_connect(f"{SYMBOL}@forceOrder"):
            order = data.get("o", {})
            self.state.last_liquidation = {
                "side": order.get("S", ""),
                "price": float(order.get("p", 0)),
                "quantity": float(order.get("q", 0)),
                "timestamp": time.time(),
            }
            logger.debug(
                f"Liquidation: {order.get('S')} "
                f"{order.get('q')} @ {order.get('p')}"
            )

    # ---- REST Polling ----

    async def _poll_funding_rate(self) -> None:
        """Poll Binance futures funding rate every minute."""
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{REST_BASE}/fapi/v1/premiumIndex"
                    params = {"symbol": SYMBOL.upper()}
                    async with session.get(url, params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self.state.funding_rate = float(
                                data.get("lastFundingRate", 0)
                            )
            except Exception as e:
                logger.warning(f"Funding rate poll failed: {e}")
            await asyncio.sleep(FUNDING_POLL)

    async def _poll_open_interest(self) -> None:
        """Poll Binance futures open interest every minute."""
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{REST_BASE}/fapi/v1/openInterest"
                    params = {"symbol": SYMBOL.upper()}
                    async with session.get(url, params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self.state.open_interest = float(
                                data.get("openInterest", 0)
                            )
            except Exception as e:
                logger.warning(f"Open interest poll failed: {e}")
            await asyncio.sleep(FUNDING_POLL)

    async def _poll_fear_greed(self) -> None:
        """Poll Alternative.me Fear & Greed Index every 15 minutes."""
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://api.alternative.me/fng/?limit=1&format=json"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            value = data.get("data", [{}])[0].get("value")
                            if value is not None:
                                self.state.fear_greed_index = int(value)
            except Exception as e:
                logger.warning(f"Fear & Greed poll failed: {e}")
            await asyncio.sleep(FNG_POLL)


async def _test_collector():
    """Quick test: collect data for 30 seconds and print state."""
    logging.basicConfig(level=logging.INFO)
    collector = DataCollector()
    await collector.start()

    for i in range(6):
        await asyncio.sleep(5)
        state = collector.get_state()
        print(
            f"[{i*5}s] Candles: {len(state.candles)} | "
            f"Trades: {len(state.trades)} | "
            f"OB: {'YES' if state.orderbook else 'NO'} | "
            f"Funding: {state.funding_rate} | "
            f"FnG: {state.fear_greed_index} | "
            f"Ready: {state.is_ready}"
        )

    await collector.stop()


if __name__ == "__main__":
    asyncio.run(_test_collector())
