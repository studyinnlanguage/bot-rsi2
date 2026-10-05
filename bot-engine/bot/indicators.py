"""
Technical Indicators Module
Calculates Exponential Moving Averages (EMA) for the strategy.
"""
import numpy as np
import pandas as pd


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA) for a given period.

    Args:
        series: Pandas Series of closing prices.
        period: EMA period (number of candles).

    Returns:
        Pandas Series containing EMA values.
    """
    if len(series) < period:
        return pd.Series([np.nan] * len(series), index=series.index)
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR) - volatility indicator.
    Used by IndicatorSet for chart display.
    """
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int = 200) -> pd.Series:
    """
    Calculate Simple Moving Average (SMA).
    Used as the long-term trend filter for the RSI-2 mean reversion strategy
    (Connors rule: only buy dips while price is above the 200-SMA).
    """
    return series.rolling(window=period, min_periods=period).mean()


def calculate_rsi(series: pd.Series, period: int = 2) -> pd.Series:
    """
    Calculate Wilder-smoothed RSI (default period = 2).

    The 2-period RSI is the core of Larry Connors' mean reversion strategy:
    - RSI(2) < 10  -> extremely oversold (buy zone, when above 200-SMA)
    - RSI(2) > 90  -> extremely overbought (short zone, when below 200-SMA)
    - RSI(2) > 65  -> recovery complete (exit long)
    - RSI(2) < 35  -> selloff complete (exit short)
    """
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    # Edge cases: pure-gain (RSI=100), pure-loss (RSI=0), perfectly flat (RSI=50)
    rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
    rsi = rsi.mask((gain == 0) & (loss > 0), 0.0)
    rsi = rsi.mask((gain == 0) & (loss == 0), 50.0)
    return rsi.clip(0, 100)


class IndicatorSet:
    """Container holding all indicators required by the strategy."""

    def __init__(self, ema_short=8, ema_mid1=13, ema_mid2=21, ema_long=55):
        self.ema_short = ema_short
        self.ema_mid1 = ema_mid1
        self.ema_mid2 = ema_mid2
        self.ema_long = ema_long

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all indicators on a DataFrame containing 'close' (and optionally 'high','low').

        Args:
            df: DataFrame with columns ['open','high','low','close','volume'] indexed by datetime.

        Returns:
            DataFrame with extra EMA columns appended.
        """
        df = df.copy()
        df["ema_8"] = calculate_ema(df["close"], self.ema_short)
        df["ema_13"] = calculate_ema(df["close"], self.ema_mid1)
        df["ema_21"] = calculate_ema(df["close"], self.ema_mid2)
        df["ema_55"] = calculate_ema(df["close"], self.ema_long)
        if {"high", "low"}.issubset(df.columns):
            df["atr"] = calculate_atr(df["high"], df["low"], df["close"])
        return df
