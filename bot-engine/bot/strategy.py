"""
Trading Strategy Module
EMA Crossover Strategy based on 4 EMAs (8, 13, 21, 55).

Rules (STRICT MODE):
- BUY  (LONG)  : EMA 55 crosses BELOW all other EMAs (8, 13, 21) -> 55 is the LOWEST line.
- SELL (SHORT) : EMA 55 crosses ABOVE all other EMAs (8, 13, 21) -> 55 is the HIGHEST line.
- HOLD         : otherwise

Cross Detection:
- `just_crossed` is True ONLY on the candle where the signal FIRST appears.
- If bot starts and line is ALREADY crossed, just_crossed = False (no trade).
- Bot must wait for a FRESH cross to enter a trade.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd

from .indicators import IndicatorSet, calculate_rsi, calculate_sma

logger = logging.getLogger(__name__)


class Signal(str, Enum):
    BUY = "BUY"      # Go LONG
    SELL = "SELL"    # Go SHORT
    HOLD = "HOLD"    # No action


@dataclass
class StrategyResult:
    signal: Signal
    ema_8: float
    ema_13: float
    ema_21: float
    ema_55: float
    last_close: float
    reason: str
    just_crossed: bool = False   # True only on the FRESH candle where cross first happens
    # Strategy-specific exit advice (used by RSI-2 mean reversion mode).
    # Engine watchdog closes LONG when exit_long=True, SHORT when exit_short=True.
    exit_long: bool = False
    exit_short: bool = False
    # Extra indicator context (optional, for UI/logs)
    rsi_2: float = None
    sma_200: float = None


class EMAQuadStrategy:
    """Quad-EMA crossover strategy with cross-detection."""

    def __init__(self, ema_short=8, ema_mid1=13, ema_mid2=21, ema_long=55):
        self.indicators = IndicatorSet(ema_short, ema_mid1, ema_mid2, ema_long)
        self.ema_short = ema_short
        self.ema_mid1 = ema_mid1
        self.ema_mid2 = ema_mid2
        self.ema_long = ema_long
        # Track previous candle's signal to detect fresh crosses
        self._prev_signal: Signal = Signal.HOLD
        # Track the LAST signal we acted on (for reset_cross_state logic)
        self._last_acted_signal: Signal = Signal.HOLD
        # After reset_cross_state is called, we require the signal to go to
        # HOLD (or opposite) and THEN come back to a fresh BUY/SELL before
        # just_crossed becomes True again. This prevents the bot from
        # immediately re-entering after a position closes when the EMA55
        # is still in the same position.
        self._require_hold_before_cross: bool = False

    def analyze(self, df: pd.DataFrame) -> Optional[StrategyResult]:
        """Analyze the latest candle and return a signal."""
        if df is None or len(df) < self.ema_long + 5:
            logger.warning("Insufficient data for strategy (need >= %d rows, got %d)",
                           self.ema_long + 5, len(df) if df is not None else 0)
            return None

        enriched = self.indicators.compute(df)
        last = enriched.iloc[-1]

        e8, e13, e21, e55 = last["ema_8"], last["ema_13"], last["ema_21"], last["ema_55"]
        last_close = last["close"]

        if pd.isna(e55) or pd.isna(e8) or pd.isna(e13) or pd.isna(e21):
            logger.warning("EMA values contain NaN - need more historical data")
            return None

        # Determine current signal
        if e55 < e8 and e55 < e13 and e55 < e21:
            signal = Signal.BUY
            reason = "EMA55 is the BOTTOM line (below EMA8, EMA13, EMA21) -> LONG signal"
        elif e55 > e8 and e55 > e13 and e55 > e21:
            signal = Signal.SELL
            reason = "EMA55 is the TOP line (above EMA8, EMA13, EMA21) -> SHORT signal"
        else:
            signal = Signal.HOLD
            reason = "EMA55 is in a mixed position -> no action"

        # Detect FRESH cross: signal changed from HOLD or opposite signal to this signal
        just_crossed = False

        # CRITICAL FIX: If reset_cross_state() was called (e.g., after a
        # position closed), we REQUIRE the signal to first go to HOLD
        # (EMA55 leaves extreme position) and THEN come back to a fresh
        # BUY/SELL before allowing just_crossed = True. This prevents
        # the bot from immediately re-entering a trade when the position
        # closes but EMA55 is still in the same position.
        #
        # Example: Bot opens LONG because EMA55 is at bottom. User manually
        # closes position. Bot calls reset_cross_state(). On next tick,
        # EMA55 is STILL at bottom → signal=BUY → prev_signal was reset to
        # HOLD → just_crossed would be True → bot opens another LONG!
        # This is WRONG. We need to wait for EMA55 to leave the bottom
        # (signal goes to HOLD) and then come back (signal goes to BUY
        # again) before allowing a fresh entry.
        if self._require_hold_before_cross:
            # We're in "waiting for HOLD" mode.
            if signal == Signal.HOLD:
                # EMA55 has left its extreme position - clear the flag
                # Now we're ready to detect a fresh cross on the next tick
                self._require_hold_before_cross = False
                # Don't set just_crossed here - HOLD is not a tradeable signal
            else:
                # Signal is still BUY/SELL (same as before reset) — NOT a fresh cross
                # Keep waiting for HOLD
                pass
        else:
            # Normal mode: detect fresh cross when signal changes from
            # HOLD (or opposite) to BUY/SELL
            if signal in (Signal.BUY, Signal.SELL):
                if self._prev_signal != signal:
                    just_crossed = True

        # Update previous signal state
        self._prev_signal = signal

        return StrategyResult(
            signal=signal,
            ema_8=float(e8),
            ema_13=float(e13),
            ema_21=float(e21),
            ema_55=float(e55),
            last_close=float(last_close),
            reason=reason,
            just_crossed=just_crossed,
        )

    def latest_indicators(self, df: pd.DataFrame) -> dict:
        """Return latest indicator values as a dict (for UI display)."""
        if df is None or len(df) < self.ema_long + 5:
            return {}
        enriched = self.indicators.compute(df)
        last = enriched.iloc[-1]
        return {
            "ema_8": float(last["ema_8"]) if not pd.isna(last["ema_8"]) else None,
            "ema_13": float(last["ema_13"]) if not pd.isna(last["ema_13"]) else None,
            "ema_21": float(last["ema_21"]) if not pd.isna(last["ema_21"]) else None,
            "ema_55": float(last["ema_55"]) if not pd.isna(last["ema_55"]) else None,
            "close": float(last["close"]),
            "timestamp": str(last.name) if last.name is not None else None,
        }

    def reset_cross_state(self):
        """Reset the previous-signal tracker. Called when bot starts or
        after a trade closes, so the next cross must be FRESH.

        CRITICAL FIX: After this is called, the strategy will NOT fire
        just_crossed=True until the signal first goes to HOLD (EMA55 leaves
        its extreme position) and then comes back to BUY/SELL. This prevents
        the bot from immediately re-entering a trade after a manual close
        when EMA55 is still in the same position.
        """
        self._prev_signal = Signal.HOLD
        self._require_hold_before_cross = True
        logger.info("Strategy cross state reset - waiting for EMA55 to leave "
                    "extreme position and come back (fresh cross required)")

    def reset_for_reversal(self):
        """Reset prev_signal to HOLD WITHOUT requiring HOLD-before-cross.

        Used after an EMA55-REVERSAL TP fires. The signal has just flipped
        to the OPPOSITE side (e.g., BUY → SELL), which IS a fresh cross.
        We want the bot to immediately open the opposite position on the
        next tick — NOT wait for EMA55 to go to HOLD/mixed first.

        Example flow:
          1. Bot is LONG (entry_signal=BUY). EMA55 was at BOTTOM.
          2. EMA55 flips to TOP. Signal becomes SELL.
          3. EMA-reversal TP fires → close LONG.
          4. Call reset_for_reversal() → _prev_signal = HOLD.
          5. Next tick: _prev_signal=HOLD, signal=SELL → just_crossed=True.
          6. Bot opens SHORT. ✅ (Immediate reversal, no waiting.)
        """
        self._prev_signal = Signal.HOLD
        # Do NOT set _require_hold_before_cross — let the natural cross
        # detection fire just_crossed=True on the next tick.
        self._require_hold_before_cross = False
        logger.info("Strategy reset for REVERSAL - opposite signal will "
                    "trigger fresh entry on next tick (no HOLD required)")


class RSI2MeanReversionStrategy:
    """Larry Connors-style RSI(2) mean reversion strategy with 200-SMA filter.

    This is the most heavily backtested high-win-rate retail strategy family
    (documented 65-85% win rates on equities and adapted here for crypto
    perpetual futures).

    Two entry modes:
      CLASSIC : RSI(2) crosses below `buy_below` (default 10) -> extreme dip
      CUM     : cumulative RSI (RSI[i] + RSI[i-1]) < `cum_rsi` (default 35)
                -- Connors' original "cumulative RSI" upgrade. Deeper dips,
                fewer + better trades. Verified stronger on BTC/ETH/AVAX.

    Rules (LONG):
      - FILTER : close > SMA(200)  -> only buy dips inside a long-term uptrend
      - ENTRY  : CLASSIC RSI dip or CUM sum-dip (see above)
      - EXIT   : close recovers above EMA(5) (bounce confirmed — fast exit)
                 OR RSI(2) >= `exit_long_above` (default 65)
                 OR hard SL hit (always price-based, always active)

    Rules (SHORT — mirror, disabled when longs_only=True):
      - FILTER : close < SMA(200)  -> only short rips inside a downtrend
      - ENTRY  : CLASSIC RSI spike or CUM sum-spike (mirror thresholds)
      - EXIT   : close falls below EMA(5) OR RSI(2) <= `exit_short_below` (35)

    Backtest evidence (corrected engine, 4h, 10x lev, SL 5%, 2023-2026):
      BTC CUM35: PF 1.21 maker fees / 1.27 MEXC-class fees, WR ~67-69%,
      ETH CUM35: PF 1.20 maker / 1.24 low-fee, WR ~70%.
      6-year split: ETH consistent both halves; BTC edge is regime-dependent
      (flat 2020-23, strong 2023-26). ALTCOIN mode (classic RSI<10, SL 5%)
      best on ADA/AVAX/SOL. LINK/TRX/XRP/BNB/memes lose with ANY config.
      Lower TFs (5m/15m/1h) lose: 4h is the only recommended timeframe.
      Fees decide everything: use limit/post-only entries or a low-fee
      exchange (MEXC 0.00/0.01) — at 0.05% taker the edge disappears.

    Fresh-trigger detection: a signal fires ONLY on the candle where the
    entry condition first becomes true. After a trade closes,
    `reset_cross_state()` blocks re-entry until RSI returns to the
    neutral band (30-70), preventing immediate re-entries in the same zone.
    """

    def __init__(self, rsi_len: int = 2, sma_len: int = 200,
                 buy_below: float = 10.0, sell_above: float = 90.0,
                 exit_long_above: float = 65.0, exit_short_below: float = 35.0,
                 exit_ema_span: int = 5,
                 ema_short: int = 8, ema_mid1: int = 13,
                 ema_mid2: int = 21, ema_long: int = 55,
                 cum_rsi: float = None, longs_only: bool = False):
        self.rsi_len = int(rsi_len)
        self.sma_len = int(sma_len)
        self.buy_below = float(buy_below)
        self.sell_above = float(sell_above)
        self.exit_long_above = float(exit_long_above)
        self.exit_short_below = float(exit_short_below)
        self.exit_ema_span = int(exit_ema_span)
        # PRO mode: Connors cumulative-RSI entry (sum of last two RSI bars).
        # None -> classic single-bar entry (buy_below / sell_above).
        # 35.0 -> LONG when RSI[i]+RSI[i-1] < 35 while close > SMA(200);
        #         SHORT mirror: sum > 165 while close < SMA(200).
        self.cum_rsi = float(cum_rsi) if cum_rsi else None
        # SAFE mode: long side only (crypto upside drift, higher win rate).
        self.longs_only = bool(longs_only)
        # IndicatorSet kept ONLY for UI chart EMA overlays (display parity
        # with the EMA mode). Trading decisions use RSI(2) + SMA filter.
        self.indicators = IndicatorSet(ema_short, ema_mid1, ema_mid2, ema_long)
        self.ema_long = ema_long
        # State
        self._prev_rsi: float = None       # previous candle's RSI value
        self._prev2_rsi: float = None      # two candles ago RSI (cum mode)
        self._require_neutral: bool = False  # block re-entry until RSI is neutral again
        self._last_block_reason: str = ""

    # ------------------------------------------------------------------
    def analyze(self, df: pd.DataFrame) -> Optional[StrategyResult]:
        """Analyze the latest candle and return a signal (+ exit advice)."""
        min_rows = self.sma_len + 10
        if df is None or len(df) < min_rows:
            logger.warning("Insufficient data for RSI2 strategy (need >= %d rows, got %d)",
                           min_rows, len(df) if df is not None else 0)
            return None

        enriched = self.indicators.compute(df)
        close = enriched["close"]
        rsi_series = calculate_rsi(close, self.rsi_len)
        sma_series = calculate_sma(close, self.sma_len)
        exit_ema_series = close.ewm(span=self.exit_ema_span, adjust=False).mean()

        last = enriched.iloc[-1]
        rsi = rsi_series.iloc[-1]
        sma = sma_series.iloc[-1]
        exit_ema = exit_ema_series.iloc[-1]
        last_close = float(last["close"])

        if pd.isna(rsi) or pd.isna(sma) or pd.isna(exit_ema):
            logger.warning("RSI/SMA values contain NaN - need more historical data")
            return None

        e8 = float(last["ema_8"]) if not pd.isna(last["ema_8"]) else 0.0
        e13 = float(last["ema_13"]) if not pd.isna(last["ema_13"]) else 0.0
        e21 = float(last["ema_21"]) if not pd.isna(last["ema_21"]) else 0.0
        e55 = float(last["ema_55"]) if not pd.isna(last["ema_55"]) else 0.0
        rsi = float(rsi)
        sma = float(sma)
        exit_ema = float(exit_ema)

        # ---------- EXIT ADVICE (checked by engine watchdog on open positions)
        # Combined exit: fast EMA bounce OR full RSI recovery — whichever
        # fires first closes the mean reversion trade.
        exit_long = (rsi >= self.exit_long_above) or (last_close > exit_ema)
        exit_short = (rsi <= self.exit_short_below) or (last_close < exit_ema)

        # ---------- ENTRY LOGIC ----------
        prev_rsi = self._prev_rsi
        if self.cum_rsi:
            # Cumulative mode needs 2-bar RSI history (prev + prev2)
            if prev_rsi is None or self._prev2_rsi is None:
                prev_rsi = None  # not enough history yet -> no fresh trigger
        if self.cum_rsi and prev_rsi is not None:
            cum = rsi + prev_rsi
            long_zone = (last_close > sma) and (cum < self.cum_rsi)
            short_zone = (last_close < sma) and (cum > (200.0 - self.cum_rsi)) \
                and not self.longs_only
            prev_cum = prev_rsi + self._prev2_rsi
            fresh_long = prev_cum >= self.cum_rsi
            fresh_short = prev_cum <= (200.0 - self.cum_rsi)
        elif not self.cum_rsi:
            long_zone = (last_close > sma) and (rsi < self.buy_below)
            short_zone = (last_close < sma) and (rsi > self.sell_above) \
                and not self.longs_only
            fresh_long = (prev_rsi is None) or (prev_rsi >= self.buy_below)
            fresh_short = (prev_rsi is None) or (prev_rsi <= self.sell_above)
        else:
            # cum mode warming up (waiting for 2-bar history)
            long_zone = short_zone = False
            fresh_long = fresh_short = False

        signal = Signal.HOLD
        just_crossed = False
        mode_tag = f"CUM{self.cum_rsi:.0f}" if self.cum_rsi else \
            f"RSI<{self.buy_below:.0f}"
        reason = (f"RSI{self.rsi_len}={rsi:.1f} [{mode_tag}] | "
                  f"SMA{self.sma_len}={sma:.2f} | "
                  f"close={'ABOVE' if last_close > sma else 'BELOW'} SMA -> no trigger")

        if long_zone:
            if self._require_neutral:
                # Wait for RSI to come back to neutral band before allowing
                # another fresh long trigger (anti-immediate-reentry guard).
                reason = (f"RSI{self.rsi_len}={rsi:.1f} still in entry zone - "
                          f"waiting for neutral reset (30-70)")
                if 30.0 <= rsi <= 70.0:
                    self._require_neutral = False
            elif fresh_long:
                signal = Signal.BUY
                just_crossed = True
                if self.cum_rsi:
                    reason = (f"CUM RSI{self.rsi_len} dipped to {rsi + prev_rsi:.1f} "
                              f"(< {self.cum_rsi:.0f}) while price ABOVE SMA{self.sma_len} "
                              f"({sma:.2f}) -> oversold BUY "
                              f"(exit: close>EMA{self.exit_ema_span} or RSI>={self.exit_long_above:.0f})")
                else:
                    reason = (f"RSI{self.rsi_len} dipped to {rsi:.1f} (< {self.buy_below}) "
                              f"while price ABOVE SMA{self.sma_len} ({sma:.2f}) -> oversold BUY "
                              f"(exit: close>EMA{self.exit_ema_span} or RSI>={self.exit_long_above:.0f})")
            else:
                reason = (f"RSI{self.rsi_len}={rsi:.1f} still in entry zone "
                          f"(not a fresh dip) -> waiting")
        elif short_zone:
            if self._require_neutral:
                reason = (f"RSI{self.rsi_len}={rsi:.1f} still in entry zone - "
                          f"waiting for neutral reset (30-70)")
                if 30.0 <= rsi <= 70.0:
                    self._require_neutral = False
            elif fresh_short:
                signal = Signal.SELL
                just_crossed = True
                if self.cum_rsi:
                    reason = (f"CUM RSI{self.rsi_len} spiked to {rsi + prev_rsi:.1f} "
                              f"(> {200.0 - self.cum_rsi:.0f}) while price BELOW SMA{self.sma_len} "
                              f"({sma:.2f}) -> overbought SELL")
                else:
                    reason = (f"RSI{self.rsi_len} spiked to {rsi:.1f} (> {self.sell_above}) "
                              f"while price BELOW SMA{self.sma_len} ({sma:.2f}) -> overbought SELL")
            else:
                reason = (f"RSI{self.rsi_len}={rsi:.1f} still above "
                          f"(not a fresh spike) -> waiting")
        else:
            # No entry zone active - clear waiting flags naturally
            if self._require_neutral and (30.0 <= rsi <= 70.0):
                self._require_neutral = False

        # Update state
        self._prev2_rsi = self._prev_rsi
        self._prev_rsi = rsi

        return StrategyResult(
            signal=signal,
            ema_8=e8, ema_13=e13, ema_21=e21, ema_55=e55,
            last_close=last_close,
            reason=reason,
            just_crossed=just_crossed,
            exit_long=exit_long,
            exit_short=exit_short,
            rsi_2=rsi,
            sma_200=sma,
        )

    # ------------------------------------------------------------------
    def latest_indicators(self, df: pd.DataFrame) -> dict:
        """Return latest indicator values as a dict (for UI display)."""
        min_rows = self.sma_len + 10
        if df is None or len(df) < min_rows:
            return {}
        enriched = self.indicators.compute(df)
        last = enriched.iloc[-1]
        rsi = calculate_rsi(enriched["close"], self.rsi_len).iloc[-1]
        sma = calculate_sma(enriched["close"], self.sma_len).iloc[-1]
        return {
            "ema_8": float(last["ema_8"]) if not pd.isna(last["ema_8"]) else None,
            "ema_13": float(last["ema_13"]) if not pd.isna(last["ema_13"]) else None,
            "ema_21": float(last["ema_21"]) if not pd.isna(last["ema_21"]) else None,
            "ema_55": float(last["ema_55"]) if not pd.isna(last["ema_55"]) else None,
            "close": float(last["close"]),
            "rsi_2": float(rsi) if not pd.isna(rsi) else None,
            "sma_200": float(sma) if not pd.isna(sma) else None,
            "timestamp": str(last.name) if last.name is not None else None,
        }

    # ------------------------------------------------------------------
    def reset_cross_state(self):
        """Called when bot starts or after a trade closes.
        Requires RSI to return to the neutral band (30-70) before the next
        fresh entry is allowed — prevents immediate re-entry in the same
        oversold/overbought zone."""
        self._prev_rsi = None
        self._prev2_rsi = None
        self._require_neutral = True
        logger.info("RSI2 strategy state reset - waiting for RSI to return "
                    "to neutral band before next fresh entry")

    def reset_for_reversal(self):
        """Clear state so the next trigger (either side) can fire immediately."""
        self._prev_rsi = None
        self._prev2_rsi = None
        self._require_neutral = False
        logger.info("RSI2 strategy reset for reversal - next trigger may fire immediately")
