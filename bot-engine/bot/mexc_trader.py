"""
MEXC Futures Trader Module
Handles all interactions with MEXC Futures (Contract) API.

Base URL: https://contract.mexc.com
Docs: https://mexcdevelop.github.io/apidocs/contract_v1_en/

Auth (private endpoints):
- Headers: ApiKey, Request-Time (ms), Signature, Content-Type
- Signature = HMAC-SHA256(secret, apiKey + requestTime + paramString)
  where paramString = raw query string (GET) or raw JSON body (POST).

Key differences vs Binance:
- Symbols use underscore format: "BTC_USDT" (bot config uses "BTCUSDT")
- Order volume is in CONTRACTS (base qty = vol * contractSize)
- side codes: 1=open long, 2=close short, 3=open short, 4=close long
- type codes: 1=limit, 5=market (2=POST_ONLY, 3=FOK, 4=IOC)
- Leverage is passed per-order (openType 1=isolated, 2=cross)
- MEXC has NO public futures testnet — demo mode is blocked with a clear
  message instead of silently sending orders to mainnet.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import requests

from .trader import Position

logger = logging.getLogger(__name__)

BASE_URL = "https://contract.mexc.com"

# MEXC kline interval codes
_INTERVAL_MAP = {
    "1m": "Min1", "3m": "Min5", "5m": "Min5", "15m": "Min15",
    "30m": "Min30", "1h": "Min60", "2h": "Min60", "4h": "Hour4",
    "8h": "Hour8", "1d": "Day1", "1w": "Week1",
}
_INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
    "8h": 28_800_000, "1d": 86_400_000, "1w": 604_800_000,
}


def _to_mexc_symbol(symbol: str) -> str:
    """BTCUSDT -> BTC_USDT (also handles USDC/ETH quoted pairs)."""
    s = symbol.upper().replace("_", "")
    for quote in ("USDT", "USDC", "ETH", "BTC"):
        if s.endswith(quote) and len(s) > len(quote):
            return s[: -len(quote)] + "_" + quote
    return s


@dataclass
class ContractInfo:
    symbol: str
    contract_size: float
    min_vol: float          # min volume in CONTRACTS
    vol_scale: float        # volume step in CONTRACTS
    price_scale: int        # price precision (decimals)
    max_leverage: int


class MEXCFuturesTrader:
    """MEXC futures trader with the same interface as BinanceFuturesTrader."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = (api_key or "").strip()
        self.api_secret = (api_secret or "").strip()
        self.testnet = testnet
        if testnet:
            logger.warning("MEXC has NO public futures testnet/demo environment. "
                           "Set Environment = Mainnet in settings to trade on MEXC.")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json",
                                     "User-Agent": "bot-engine/2.0"})
        self._contract_cache: dict = {}
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------
    def _sign(self, timestamp: str, param_string: str) -> str:
        msg = f"{self.api_key}{timestamp}{param_string}"
        return hmac.new(self.api_secret.encode(), msg.encode(),
                        hashlib.sha256).hexdigest()

    def _request(self, method: str, path: str, params: dict = None,
                 body: dict = None, signed: bool = False, timeout: int = 15):
        url = BASE_URL + path
        param_string = ""
        if method == "GET" and params:
            param_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{param_string}"
        body_string = ""
        headers = {}
        if signed:
            timestamp = str(int(time.time() * 1000))
            if method == "POST" and body is not None:
                body_string = json.dumps(body)
            headers = {
                "ApiKey": self.api_key,
                "Request-Time": timestamp,
                "Signature": self._sign(timestamp, body_string if method == "POST" else param_string),
                "Content-Type": "application/json",
            }
        resp = self.session.request(
            method, url, data=body_string if method == "POST" else None,
            headers=headers, timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # MEXC wraps responses: {"success": bool, "code": int, "data": ...}
        if isinstance(data, dict):
            if data.get("success") is False or (data.get("code") not in (0, None, 200)):
                raise RuntimeError(f"MEXC API error code={data.get('code')}: {data.get('message', data)}")
        return data

    def _retry_api_call(self, func, *args, max_retries: int = 3, **kwargs):
        last_err = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_err = e
                wait = min(2 ** attempt, 4)
                logger.warning("MEXC API call failed (attempt %d/%d): %s — retrying in %ss",
                               attempt + 1, max_retries, str(e)[:120], wait)
                time.sleep(wait)
        raise last_err

    # ------------------------------------------------------------------
    # Public market data
    # ------------------------------------------------------------------
    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> pd.DataFrame:
        """Fetch historical klines -> DataFrame indexed by datetime with
        columns open, high, low, close, volume."""
        sym = _to_mexc_symbol(symbol)
        mexc_interval = _INTERVAL_MAP.get(interval, "Min60")
        interval_ms = _INTERVAL_MS.get(interval, 3_600_000)
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - min(limit, 2000) * interval_ms

        def _fetch():
            return self._request(
                "GET", f"/api/v1/contract/kline/{sym}",
                params={"interval": mexc_interval, "start": start_ms, "end": end_ms},
            )

        resp = self._retry_api_call(_fetch)
        payload = resp.get("data", resp) if isinstance(resp, dict) else {}
        # data shape: {time: [...], open: [...], high: [...], low: [...], close: [...], vol: [...]}
        if not payload or not payload.get("time"):
            raise RuntimeError(f"MEXC klines empty for {symbol} ({interval})")
        df = pd.DataFrame({
            "open": [float(x) for x in payload["open"]],
            "high": [float(x) for x in payload["high"]],
            "low": [float(x) for x in payload["low"]],
            "close": [float(x) for x in payload["close"]],
            "volume": [float(x) for x in payload.get("vol", [0] * len(payload["time"]))],
        }, index=pd.to_datetime([int(t) for t in payload["time"]], unit="ms"))
        df = df[~df.index.duplicated(keep="last")].sort_index()
        if len(df) > limit:
            df = df.tail(limit)
        return df

    def get_mark_price(self, symbol: str) -> float:
        """Get current mark (fair) price for a symbol."""
        sym = _to_mexc_symbol(symbol)
        try:
            resp = self._retry_api_call(
                self._request, "GET", f"/api/v1/contract/market_price/{sym}")
            data = resp.get("data", resp) if isinstance(resp, dict) else {}
            price = float(data.get("fairPrice") or 0)
            if price > 0:
                return price
        except Exception as e:
            logger.warning("MEXC get_mark_price failed for %s: %s", symbol, e)
        # Fallback: last trade price
        try:
            resp = self._retry_api_call(
                self._request, "GET", f"/api/v1/contract/price/{sym}")
            data = resp.get("data", resp) if isinstance(resp, dict) else {}
            return float(data.get("price") or 0)
        except Exception as e:
            logger.warning("MEXC last-price fallback failed for %s: %s", symbol, e)
            return 0.0

    def get_contract_info(self, symbol: str) -> dict:
        """Fetch and cache contract metadata (contract size, scales, limits)."""
        sym = _to_mexc_symbol(symbol)
        with self._cache_lock:
            if sym in self._contract_cache:
                info: ContractInfo = self._contract_cache[sym]
                return {"step_size": info.vol_scale, "min_qty": info.min_vol,
                        "max_qty": info.min_vol * 1e9,
                        "tick_size": 10 ** (-info.price_scale) if info.price_scale >= 0 else 1,
                        "contract_size": info.contract_size,
                        "max_leverage": info.max_leverage}
        resp = self._retry_api_call(self._request, "GET", f"/api/v1/contract/detail/{sym}")
        d = resp.get("data", resp) if isinstance(resp, dict) else {}
        info = ContractInfo(
            symbol=sym,
            contract_size=float(d.get("contractSize", 0.0001)),
            min_vol=float(d.get("minVol", 1)),
            vol_scale=float(d.get("volScale", 1)),
            price_scale=int(d.get("priceScale", 2)),
            max_leverage=int(d.get("maxLever", 125)),
        )
        with self._cache_lock:
            self._contract_cache[sym] = info
        return {"step_size": info.vol_scale, "min_qty": info.min_vol,
                "max_qty": info.min_vol * 1e9,
                "tick_size": 10 ** (-info.price_scale) if info.price_scale >= 0 else 1,
                "contract_size": info.contract_size,
                "max_leverage": info.max_leverage}

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------
    def get_balance(self) -> float:
        """Get USDT balance available for trading."""
        try:
            resp = self._retry_api_call(self._request, "GET",
                                        "/api/v1/private/account/assets", signed=True)
            assets = resp.get("data", []) if isinstance(resp, dict) else []
            if isinstance(assets, dict):
                assets = assets.get("list", [assets])
            for item in assets:
                if isinstance(item, dict) and str(item.get("currency", "")).upper() == "USDT":
                    for key in ("availableBalance", "available", "equity", "balance"):
                        try:
                            v = float(item.get(key) or 0)
                            if v > 0:
                                return v
                        except (TypeError, ValueError):
                            continue
                    return 0.0
            return 0.0
        except Exception as e:
            logger.error("MEXC get_balance failed: %s", e)
            return 0.0

    def get_position(self, symbol: str) -> Position:
        """Get current position for a symbol (one-way mode)."""
        sym = _to_mexc_symbol(symbol)
        info = self.get_contract_info(symbol)
        csize = info.get("contract_size", 0.0001)
        try:
            resp = self._retry_api_call(self._request, "GET",
                                        "/api/v1/private/position/open_positions", signed=True)
            positions = resp.get("data", []) if isinstance(resp, dict) else []
            mark = self.get_mark_price(symbol)
            for p in positions:
                if not isinstance(p, dict):
                    continue
                if str(p.get("symbol", "")).upper() != sym.upper():
                    continue
                hold_amount = float(p.get("holdAmount") or 0)  # in contracts
                if hold_amount <= 0:
                    continue
                side_code = int(p.get("holdSide") or 0)
                side = "LONG" if side_code == 1 else "SHORT"
                size = hold_amount * csize  # base-asset qty
                entry = float(p.get("holdAvgPrice") or 0)
                mark_p = float(p.get("holdAvgFairPrice") or mark or 0)
                try:
                    upnl = float(p.get("unrealized") or 0)
                except (TypeError, ValueError):
                    upnl = 0.0
                try:
                    lev = int(float(p.get("leverage") or 1))
                except (TypeError, ValueError):
                    lev = 1
                return Position(symbol=symbol, side=side, size=size,
                                entry_price=entry, mark_price=mark_p or entry,
                                unrealized_pnl=upnl, leverage=lev)
        except Exception as e:
            logger.warning("MEXC get_position failed for %s: %s", symbol, e)
        return Position(symbol=symbol, side="NONE", size=0.0,
                        entry_price=0.0, mark_price=self.get_mark_price(symbol),
                        unrealized_pnl=0.0, leverage=1)

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------
    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """MEXC applies leverage per-order — nothing to pre-set globally.
        We validate against the symbol's max leverage and report back."""
        try:
            info = self.get_contract_info(symbol)
            max_lev = int(info.get("max_leverage", 125))
            lev = max(1, min(max_lev, int(leverage)))
            return {"success": True, "leverage": lev,
                    "note": "MEXC leverage is applied per order (isolated margin)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_symbol_filters(self, symbol: str) -> dict:
        """Return step_size / min_qty / tick_size for a symbol."""
        try:
            return self.get_contract_info(symbol)
        except Exception as e:
            logger.warning("MEXC get_symbol_filters failed for %s: %s", symbol, e)
            return {"step_size": 0.001, "min_qty": 0.001, "max_qty": 1e9,
                    "tick_size": 0.01, "contract_size": 0.0001}

    def _round_to_step(self, value: float, step: float) -> float:
        if step <= 0:
            step = 0.001
        # Floor to step (never exceed intended size)
        return max(step, round(int(value / step) * step, 12))

    def compute_quantity(self, notional_usdt: float, price: float,
                         leverage: int, qty_step: float = 0.001) -> float:
        """Compute base-asset quantity from desired USDT notional exposure."""
        if price <= 0:
            return 0.0
        raw_qty = notional_usdt / price
        return self._round_to_step(raw_qty, qty_step)

    def place_market_order(self, symbol: str, side: str, quantity: float,
                           reduce_only: bool = False,
                           position_side: str = None,
                           sl_price: float = None,
                           tp_price: float = None,
                           leverage: int = None) -> dict:
        """Place a MARKET order on MEXC futures.

        side: "BUY" (open long / close short) or "SELL" (open short / close long).
        quantity: BASE-asset qty (converted to contracts internally).
        sl_price/tp_price: attached trigger prices on OPEN orders only.
        """
        if self.testnet:
            return {"success": False,
                    "error": "MEXC has no demo/testnet. Set Environment = Mainnet to trade on MEXC."}
        if not self.api_key or not self.api_secret:
            return {"success": False, "error": "MEXC API keys missing"}

        side = side.upper()
        if side not in ("BUY", "SELL"):
            return {"success": False, "error": f"Invalid side: {side}"}
        if quantity <= 0:
            return {"success": False, "error": "Quantity must be > 0"}

        sym = _to_mexc_symbol(symbol)
        try:
            info = self.get_contract_info(symbol)
            csize = info.get("contract_size", 0.0001)
            vol_step = info.get("step_size", 1)
            min_vol = info.get("min_qty", 1)
            tick = info.get("tick_size", 0.01)
        except Exception as e:
            logger.warning("MEXC contract info unavailable for %s, using defaults: %s", symbol, e)
            csize, vol_step, min_vol, tick = 0.0001, 1, 1, 0.01

        vol = int(round(quantity / csize))
        # Floor vol to the contract step
        vol = int((vol // int(vol_step if vol_step >= 1 else 1)) * int(vol_step if vol_step >= 1 else 1))
        if vol < min_vol:
            return {"success": False,
                    "error": f"Volume {vol} contracts below min {min_vol} for {symbol} "
                             f"(qty {quantity} / contractSize {csize}). Increase amount."}

        # MEXC side codes:
        #   1 = open long, 2 = close short, 3 = open short, 4 = close long
        if reduce_only:
            mexc_side = 4 if side == "SELL" else 2   # close long (SELL) / close short (BUY)
            pos_side = position_side or ("LONG" if side == "SELL" else "SHORT")
        else:
            mexc_side = 1 if side == "BUY" else 3    # open long / open short
            pos_side = position_side or ("LONG" if side == "BUY" else "SHORT")

        try:
            lev = int(leverage or 10)
        except (TypeError, ValueError):
            lev = 10

        body = {
            "symbol": sym,
            "side": mexc_side,
            "type": 5,               # market
            "vol": vol,              # contracts
            "openType": 1,           # isolated
            "leverage": max(1, lev),
            "externalOid": f"bot{uuid.uuid4().hex[:20]}",
        }
        # SL/TP can only be attached to OPEN orders on MEXC
        if not reduce_only:
            if sl_price and sl_price > 0:
                body["stopLossPrice"] = str(self._round_price(sl_price, tick))
                body["stopLossType"] = 2    # market trigger order
            if tp_price and tp_price > 0:
                body["takeProfitPrice"] = str(self._round_price(tp_price, tick))
                body["takeProfitType"] = 2

        try:
            resp = self._retry_api_call(self._request, "POST",
                                        "/api/v1/private/order/submit",
                                        body=body, signed=True)
            oid = resp.get("data", "?") if isinstance(resp, dict) else "?"
            logger.info("MEXC order placed: side=%s %s vol=%s(posSide=%s) SL=%s TP=%s -> orderId=%s",
                        side, sym, vol, pos_side,
                        body.get("stopLossPrice"), body.get("takeProfitPrice"), oid)
            return {"success": True, "order": resp, "quantity": quantity,
                    "vol": vol, "sl_price": body.get("stopLossPrice"),
                    "tp_price": body.get("takeProfitPrice")}
        except Exception as e:
            logger.error("MEXC order failed: %s", e)
            return {"success": False, "error": str(e), "quantity": quantity}

    def _round_price(self, price: float, tick: float) -> float:
        if tick <= 0:
            tick = 0.01
        return round(round(price / tick) * tick, 12)

    def open_long(self, symbol: str, quantity: float,
                  sl_price: float = None, tp_price: float = None,
                  leverage: int = None) -> dict:
        return self.place_market_order(symbol, "BUY", quantity,
                                       reduce_only=False,
                                       position_side="LONG",
                                       sl_price=sl_price, tp_price=tp_price,
                                       leverage=leverage)

    def open_short(self, symbol: str, quantity: float,
                   sl_price: float = None, tp_price: float = None,
                   leverage: int = None) -> dict:
        return self.place_market_order(symbol, "SELL", quantity,
                                       reduce_only=False,
                                       position_side="SHORT",
                                       sl_price=sl_price, tp_price=tp_price,
                                       leverage=leverage)

    def close_position(self, symbol: str) -> dict:
        """Close the whole position using a reduceOnly market order."""
        pos = self.get_position(symbol)
        if pos.side == "NONE" or pos.size == 0:
            return {"success": True, "message": "No position to close"}
        close_side = "SELL" if pos.side == "LONG" else "BUY"
        return self.place_market_order(symbol, close_side, abs(pos.size),
                                       reduce_only=True,
                                       position_side=pos.side)

    def place_stop_loss(self, symbol: str, side: str, stop_price: float,
                        quantity: float) -> dict:
        """Place a backup stop-loss via a MARKET order is not possible as a
        resting order here — MEXC trigger orders use the plan-order endpoint.
        The bot's software watchdog is the primary SL; this is best-effort."""
        if self.testnet:
            return {"success": False, "error": "MEXC testnet not available"}
        sym = _to_mexc_symbol(symbol)
        try:
            info = self.get_contract_info(symbol)
            csize = info.get("contract_size", 0.0001)
            tick = info.get("tick_size", 0.01)
            vol = max(1, int(round(quantity / csize)))
            # trend: 1 = price falls to trigger (stop for LONG), 2 = price rises (stop for SHORT)
            trend = 1 if side.upper() == "SELL" else 2
            body = {
                "symbol": sym,
                "side": 4 if side.upper() == "SELL" else 2,   # close long / close short
                "vol": vol,
                "triggerPrice": str(self._round_price(stop_price, tick)),
                "triggerType": trend,
                "executeCycle": 1,       # trigger once
                "orderType": 5,          # market execution
                "trend": trend,
                "externalOid": f"botsl{uuid.uuid4().hex[:20]}",
            }
            resp = self._retry_api_call(self._request, "POST",
                                        "/api/v1/private/planorder/submit",
                                        body=body, signed=True)
            logger.info("MEXC plan (SL) order placed: %s %s @ %s", side, sym, stop_price)
            return {"success": True, "order": resp}
        except Exception as e:
            logger.warning("MEXC plan order (SL) failed: %s (software watchdog remains active)", e)
            return {"success": False, "error": str(e)}

    def place_take_profit(self, symbol: str, side: str, stop_price: float,
                          quantity: float) -> dict:
        """TP mirror of place_stop_loss (plan order)."""
        return self.place_stop_loss(symbol, side, stop_price, quantity)

    def cancel_open_orders(self, symbol: str) -> dict:
        """Cancel all resting/plan orders for a symbol (best-effort)."""
        if self.testnet:
            return {"success": False, "error": "MEXC testnet not available"}
        sym = _to_mexc_symbol(symbol)
        cancelled = 0
        # Cancel trigger/plan orders
        try:
            resp = self._retry_api_call(self._request, "POST",
                                        f"/api/v1/private/planorder/cancel_all/{sym}",
                                        body={}, signed=True)
            cancelled += 1
        except Exception as e:
            logger.debug("MEXC cancel plan orders notice: %s", e)
        # Cancel resting orders
        try:
            resp = self._retry_api_call(self._request, "POST",
                                        f"/api/v1/private/order/cancel_all/{sym}",
                                        body={}, signed=True)
            cancelled += 1
        except Exception as e:
            logger.debug("MEXC cancel orders notice: %s", e)
        return {"success": True, "cancelled": cancelled}

    def get_all_symbols(self) -> list:
        """Fetch all active USDT-quoted futures symbols from MEXC."""
        try:
            resp = self._retry_api_call(self._request, "GET", "/api/v1/contract/detail")
            data = resp.get("data", []) if isinstance(resp, dict) else []
            out = []
            for s in data:
                if not isinstance(s, dict):
                    continue
                sym = str(s.get("symbol", ""))
                quote = str(s.get("quoteCoin", s.get("quoteCoinName", ""))).upper()
                if quote == "USDT" and int(s.get("state", 0)) == 0:  # 0 = enabled
                    out.append(sym.replace("_", ""))
            return out
        except Exception as e:
            logger.error("MEXC get_all_symbols failed: %s", e)
            return []

    def test_connection(self) -> dict:
        """Verify API credentials + connectivity. Returns dict with status."""
        result = {"success": False, "exchange": "MEXC Futures", "details": []}
        # 1) public endpoint reachability
        try:
            self._retry_api_call(self._request, "GET", "/api/v1/contract/ping")
            result["details"].append("Public API: reachable")
        except Exception as e:
            result["details"].append(f"Public API FAILED: {str(e)[:120]}")
            return result
        # 2) private endpoint auth
        try:
            resp = self._retry_api_call(self._request, "GET",
                                        "/api/v1/private/account/assets", signed=True)
            assets = resp.get("data", []) if isinstance(resp, dict) else []
            usdt = "-"
            for item in (assets if isinstance(assets, list) else []):
                if isinstance(item, dict) and str(item.get("currency", "")).upper() == "USDT":
                    usdt = str(item.get("equity", item.get("availableBalance", "-")))
                    break
            result["details"].append(f"Auth OK — USDT equity: {usdt}")
            result["success"] = True
        except Exception as e:
            result["details"].append(f"Auth FAILED: {str(e)[:150]}")
        if self.testnet:
            result["details"].append("WARNING: MEXC has no demo environment — "
                                     "Environment is set to Demo, orders will be BLOCKED. "
                                     "Switch to Mainnet to trade.")
        return result
