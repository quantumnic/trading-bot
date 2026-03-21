# 🤖 Bitcoin Paper Trading Bot

Live BTC paper trading bot mit echten Marktdaten von Binance.

## Strategie

**EMA Crossover + RSI + MACD + Bollinger Bands**

- EMA(9) kreuzt EMA(21) → Trendwechsel-Signal
- RSI(14) filtert Overbought/Oversold
- MACD bestätigt Momentum
- Bollinger Bands für Mean-Reversion-Signale
- Mindestens 4/7 Konfirmationspunkten für Trade-Einstieg

## Risk Management

| Parameter | Wert |
|-----------|------|
| Startkapital | $10'000 |
| Stop Loss | 2% |
| Take Profit | 4% (2:1 R/R) |
| Trailing Stop | 1.5% |
| Position Size | 95% des Kapitals |
| Trading Fee | 0.1% (Binance-like) |

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install pandas numpy requests websockets ta aiohttp
```

## Starten

```bash
PYTHONUNBUFFERED=1 python3 bot.py
```

## Status checken

```bash
python3 status.py
```

## Architektur

```
bot.py          → Hauptloop, WebSocket, Orchestrierung
strategy.py     → Trading-Strategien (modular, austauschbar)
paper_trader.py → Paper Trading Engine, P&L, Risk Management
config.py       → Alle Parameter an einem Ort
status.py       → Quick Status Check
```

## Features

- ✅ Live Binance WebSocket (1-min Candles)
- ✅ Paper Trading mit Fake-Geld
- ✅ State-Persistenz (überlebt Neustarts)
- ✅ Trailing Stop Loss
- ✅ Performance-Tracking (Win Rate, Drawdown, etc.)
- ✅ Automatische Reconnects bei Verbindungsverlust
