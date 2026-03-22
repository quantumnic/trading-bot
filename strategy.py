"""Trading strategies — modular so we can swap/optimize."""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradeSignal:
    signal: Signal
    confidence: float  # 0-1
    reason: str


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.inf)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(series: pd.Series, period=20, std_dev=2):
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower


def adx(df: pd.DataFrame, period=14) -> pd.Series:
    """Average Directional Index — measures trend strength."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1))
    adx_val = dx.ewm(span=period, adjust=False).mean()
    return adx_val


class EMAcrossRSI:
    """EMA crossover + RSI filter + MACD confirmation."""

    def __init__(self, fast=9, slow=21, rsi_period=14,
                 rsi_ob=70, rsi_os=30):
        self.fast = fast
        self.slow = slow
        self.rsi_period = rsi_period
        self.rsi_ob = rsi_ob
        self.rsi_os = rsi_os

    def evaluate(self, df: pd.DataFrame) -> TradeSignal:
        if len(df) < max(self.slow, 50) + 10:
            return TradeSignal(Signal.HOLD, 0, "Not enough data")

        close = df["close"]

        # Trend filter: EMA50 determines macro trend
        ema_trend = ema(close, 50)
        cur_trend = ema_trend.iloc[-1]
        cur_price_val = close.iloc[-1]
        is_uptrend = cur_price_val > cur_trend
        is_downtrend = cur_price_val < cur_trend

        # ADX: only trade when there IS a trend (ADX > 25)
        adx_val = adx(df)
        cur_adx = adx_val.iloc[-1]
        has_trend = cur_adx > 25

        # Indicators
        ema_fast = ema(close, self.fast)
        ema_slow = ema(close, self.slow)
        rsi_val = rsi(close, self.rsi_period)
        macd_line, signal_line, macd_hist = macd(close)
        bb_upper, bb_middle, bb_lower = bollinger_bands(close)

        # Current values
        cur_fast = ema_fast.iloc[-1]
        cur_slow = ema_slow.iloc[-1]
        prev_fast = ema_fast.iloc[-2]
        prev_slow = ema_slow.iloc[-2]
        cur_rsi = rsi_val.iloc[-1]
        cur_macd = macd_hist.iloc[-1]
        prev_macd = macd_hist.iloc[-2]
        cur_price = close.iloc[-1]
        cur_bb_lower = bb_lower.iloc[-1]
        cur_bb_upper = bb_upper.iloc[-1]

        # Crossover detection
        bullish_cross = prev_fast <= prev_slow and cur_fast > cur_slow
        bearish_cross = prev_fast >= prev_slow and cur_fast < cur_slow

        # Trend strength
        trend_strength = abs(cur_fast - cur_slow) / cur_slow

        # === BUY CONDITIONS ===
        buy_signals = 0
        reasons = []

        if bullish_cross:
            buy_signals += 2
            reasons.append("EMA bullish cross")
        elif cur_fast > cur_slow:
            buy_signals += 1
            reasons.append("EMA bullish")

        if cur_rsi < self.rsi_os:
            buy_signals += 2
            reasons.append(f"RSI oversold ({cur_rsi:.0f})")
        elif cur_rsi < 45:
            buy_signals += 1
            reasons.append(f"RSI low ({cur_rsi:.0f})")

        if cur_macd > 0 and prev_macd <= 0:
            buy_signals += 2
            reasons.append("MACD bullish cross")
        elif cur_macd > prev_macd:
            buy_signals += 1
            reasons.append("MACD rising")

        if cur_price <= cur_bb_lower * 1.01:
            buy_signals += 1
            reasons.append("Near BB lower")

        # === SELL CONDITIONS ===
        sell_signals = 0
        sell_reasons = []

        if bearish_cross:
            sell_signals += 2
            sell_reasons.append("EMA bearish cross")
        elif cur_fast < cur_slow:
            sell_signals += 1
            sell_reasons.append("EMA bearish")

        if cur_rsi > self.rsi_ob:
            sell_signals += 2
            sell_reasons.append(f"RSI overbought ({cur_rsi:.0f})")
        elif cur_rsi > 55:
            sell_signals += 1
            sell_reasons.append(f"RSI high ({cur_rsi:.0f})")

        if cur_macd < 0 and prev_macd >= 0:
            sell_signals += 2
            sell_reasons.append("MACD bearish cross")
        elif cur_macd < prev_macd:
            sell_signals += 1
            sell_reasons.append("MACD falling")

        if cur_price >= cur_bb_upper * 0.99:
            sell_signals += 1
            sell_reasons.append("Near BB upper")

        # Decision — require strong confluence + trend alignment
        from config import MIN_SIGNAL_SCORE

        # Only trade with trend + ADX confirmation
        if buy_signals >= MIN_SIGNAL_SCORE and buy_signals > sell_signals + 1 and is_uptrend and has_trend:
            confidence = min(buy_signals / 7, 1.0)
            return TradeSignal(Signal.BUY, confidence,
                               " + ".join(reasons) + f" [Uptrend ✅ ADX:{cur_adx:.0f}]")
        elif sell_signals >= MIN_SIGNAL_SCORE and sell_signals > buy_signals + 1:
            confidence = min(sell_signals / 7, 1.0)
            return TradeSignal(Signal.SELL, confidence,
                               " + ".join(sell_reasons) +
                               (" [Downtrend ⚠️]" if is_downtrend else ""))
        elif is_downtrend and buy_signals >= MIN_SIGNAL_SCORE:
            return TradeSignal(Signal.HOLD, 0,
                               f"Buy blocked: downtrend (price < EMA50)")
        elif not has_trend and buy_signals >= MIN_SIGNAL_SCORE:
            return TradeSignal(Signal.HOLD, 0,
                               f"Buy blocked: no trend (ADX={cur_adx:.0f} < 25)")

        return TradeSignal(Signal.HOLD, 0,
                           f"No clear signal (buy={buy_signals}, sell={sell_signals})")
