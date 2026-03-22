"""Trading Bot Configuration"""

# Paper Trading Settings
INITIAL_BALANCE = 10_000.0  # USD starting balance
TRADING_FEE = 0.001  # 0.1% per trade (Binance-like)

# Strategy Settings
SYMBOL = "BTCUSDT"
TIMEFRAME = "5m"  # 5-minute candles, less noise

# EMA Crossover Strategy
EMA_FAST = 12
EMA_SLOW = 26
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Risk Management
POSITION_SIZE_PCT = 0.95  # Use 95% of balance per trade
STOP_LOSS_PCT = 0.02  # 2% stop loss
TAKE_PROFIT_PCT = 0.04  # 4% take profit (2:1 R/R)
TRAILING_STOP_PCT = 0.015  # 1.5% trailing stop
MIN_SIGNAL_SCORE = 5  # Minimum confirmation points (out of 7) for entry
MIN_HOLD_CANDLES = 20  # Hold position at least N candles (~100min on 5m) before signal-exit

# Bot Settings
LOG_FILE = "trades.log"
STATE_FILE = "bot_state.json"
PERFORMANCE_FILE = "performance.json"
CANDLE_HISTORY = 100  # Keep last N candles

# Binance Public API (no auth needed for market data)
BINANCE_WS = "wss://stream.binance.com:9443/ws"
BINANCE_REST = "https://api.binance.com/api/v3"
