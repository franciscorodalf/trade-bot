"""
Polymarket API client for BTC 5-minute prediction markets.

Handles market discovery, price reading, and order placement
via the Polymarket CLOB API and Gamma API.
"""

import json
import logging
import os
import time
from typing import Optional, Dict, List, Any

import aiohttp

logger = logging.getLogger(__name__)

_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")
with open(_config_path, "r") as f:
    config = json.load(f)

GAMMA_HOST = config["polymarket"]["gamma_host"]
CLOB_HOST = config["polymarket"]["host"]


class PolymarketClient:
    """
    Client for interacting with Polymarket's BTC 5-minute prediction markets.

    Supports two modes:
    - Read-only (no auth): Browse markets, read prices and order books
    - Trading (requires wallet): Place bets via py-clob-client

    For paper trading, only read-only mode is needed.
    """

    def __init__(self, paper_mode: bool = True) -> None:
        self.paper_mode = paper_mode
        self._clob_client = None
        self._cached_markets: Dict[str, Any] = {}
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 30  # Refresh market cache every 30s

    async def initialize(self) -> None:
        """Initialize the trading client (only needed for real trading)."""
        if not self.paper_mode:
            try:
                from py_clob_client.client import ClobClient

                private_key = config["polymarket"]["private_key"]
                if not private_key:
                    logger.error("No private key configured. Set POLYMARKET_PRIVATE_KEY.")
                    return

                self._clob_client = ClobClient(
                    CLOB_HOST,
                    key=private_key,
                    chain_id=config["polymarket"]["chain_id"],
                    signature_type=1,
                )
                creds = self._clob_client.create_or_derive_api_creds()
                self._clob_client.set_api_creds(creds)
                logger.info("Polymarket trading client initialized.")
            except ImportError:
                logger.error("py-clob-client not installed. Run: pip install py-clob-client")
            except Exception as e:
                logger.error(f"Failed to initialize Polymarket client: {e}")

    # ---- Market Discovery ----

    async def find_btc_5min_markets(self) -> List[Dict[str, Any]]:
        """
        Find active BTC 5-minute UP/DOWN prediction markets.

        Returns:
            List of market dicts with id, question, token IDs, and current prices.
        """
        now = time.time()
        if now - self._cache_timestamp < self._cache_ttl and self._cached_markets:
            return list(self._cached_markets.values())

        markets = []
        try:
            async with aiohttp.ClientSession() as session:
                # Search for BTC 5-minute markets
                params = {
                    "closed": "false",
                    "limit": 20,
                }
                url = f"{GAMMA_HOST}/markets"
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(f"Gamma API returned {resp.status}")
                        return markets

                    all_markets = await resp.json()

                    # Filter for BTC 5-minute prediction markets
                    for m in all_markets:
                        question = m.get("question", "").lower()
                        is_btc_5m = (
                            ("bitcoin" in question or "btc" in question)
                            and ("5" in question or "five" in question)
                            and ("above" in question or "up" in question
                                 or "higher" in question or "price" in question)
                        )
                        if is_btc_5m:
                            market_data = self._parse_market(m)
                            if market_data:
                                markets.append(market_data)

        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")

        # Update cache
        self._cached_markets = {m["id"]: m for m in markets}
        self._cache_timestamp = now

        logger.info(f"Found {len(markets)} active BTC 5-min markets")
        return markets

    async def get_market_price(self, token_id: str) -> Optional[float]:
        """
        Get current price for a specific outcome token.

        Args:
            token_id: The token ID for YES or NO outcome.

        Returns:
            Current price (0-1), or None on failure.
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{CLOB_HOST}/price"
                params = {"token_id": token_id, "side": "buy"}
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return float(data.get("price", 0))
        except Exception as e:
            logger.warning(f"Failed to get price for {token_id}: {e}")
        return None

    async def get_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Get order book for a specific outcome token."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{CLOB_HOST}/book"
                params = {"token_id": token_id}
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.warning(f"Failed to get orderbook for {token_id}: {e}")
        return None

    # ---- Trading ----

    async def place_bet(
        self,
        token_id: str,
        side: str,  # "UP" or "DOWN"
        amount: float,
        price: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Place a bet on a BTC 5-minute market.

        Args:
            token_id: Token ID for the YES outcome.
            side: "UP" (buy YES) or "DOWN" (buy NO).
            amount: Size in USDC.
            price: Limit price (0-1).

        Returns:
            Order response dict, or None on failure.
        """
        if self.paper_mode:
            return self._paper_bet(token_id, side, amount, price)

        if not self._clob_client:
            logger.error("Trading client not initialized.")
            return None

        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY

            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=amount / price,  # Convert USDC to shares
                side=BUY,
            )
            signed_order = self._clob_client.create_order(order_args)
            response = self._clob_client.post_order(signed_order, OrderType.FOK)

            logger.info(f"Order placed: {side} ${amount:.2f} @ {price:.2f}")
            return response

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None

    def _paper_bet(
        self, token_id: str, side: str, amount: float, price: float
    ) -> Dict[str, Any]:
        """Simulate a bet for paper trading."""
        return {
            "status": "PAPER",
            "token_id": token_id,
            "side": side,
            "amount": amount,
            "price": price,
            "shares": amount / price,
            "timestamp": time.time(),
        }

    # ---- Helpers ----

    def _parse_market(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse raw Gamma API market response into clean format."""
        try:
            tokens = raw.get("tokens", [])
            if not tokens or len(tokens) < 2:
                # Try clobTokenIds
                clob_ids = raw.get("clobTokenIds", [])
                if len(clob_ids) < 2:
                    return None
                tokens = [{"token_id": clob_ids[0]}, {"token_id": clob_ids[1]}]

            return {
                "id": raw.get("id", ""),
                "question": raw.get("question", ""),
                "condition_id": raw.get("conditionId", ""),
                "slug": raw.get("slug", ""),
                "yes_token_id": tokens[0].get("token_id", ""),
                "no_token_id": tokens[1].get("token_id", ""),
                "end_date": raw.get("endDate", ""),
                "active": raw.get("active", True),
            }
        except (IndexError, KeyError) as e:
            logger.debug(f"Failed to parse market: {e}")
            return None
