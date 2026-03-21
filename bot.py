#!/usr/bin/env python3
"""
Bitcoin Paper Trading Bot
Live price feed from Binance, paper trading with risk management.
Runs continuously, saves state, recoverable on restart.
"""

import asyncio
import json
import time
import signal
import sys
import pandas as pd
import websockets
import requests
from datetime import datetime

from config import *
MIN_HOLD_CANDLES = getattr(__import__('config'), 'MIN_HOLD_CANDLES', 10)
from strategy import EMAcrossRSI, Signal
from paper_trader import PaperTrader


class TradingBot:
    def __init__(self):
        self.trader = PaperTrader()
        self.strategy = EMAcrossRSI(
            fast=EMA_FAST, slow=EMA_SLOW,
            rsi_period=RSI_PERIOD, rsi_ob=RSI_OVERBOUGHT, rsi_os=RSI_OVERSOLD
        )
        self.candles: list[dict] = []
        self.current_candle: dict = {}
        self.last_report = time.time()
        self.running = True
        self.tick_count = 0
        self.candles_in_position = 0  # Track how long in position

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, *args):
        print("\n🛑 Shutting down gracefully...")
        self.running = False

    def _fetch_historical(self):
        """Fetch historical klines to bootstrap indicators."""
        print(f"📊 Fetching {CANDLE_HISTORY} historical candles...")
        url = f"{BINANCE_REST}/klines"
        params = {
            "symbol": SYMBOL,
            "interval": TIMEFRAME,
            "limit": CANDLE_HISTORY,
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            for k in data[:-1]:  # Skip last (incomplete) candle
                self.candles.append({
                    "time": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                })
            print(f"✅ Loaded {len(self.candles)} candles, "
                  f"latest close: ${self.candles[-1]['close']:,.2f}")
        except Exception as e:
            print(f"⚠️ Failed to fetch history: {e}")

    def _process_ws_message(self, data: dict):
        """Process kline websocket message."""
        k = data.get("k", {})
        if not k:
            return

        candle = {
            "time": k["t"],
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
        }
        is_closed = k["x"]
        price = candle["close"]

        self.tick_count += 1

        # Check exits on every tick
        exit_msg = self.trader.check_exit(price)
        if exit_msg:
            print(exit_msg)

        if is_closed:
            # New completed candle
            self.candles.append(candle)
            if len(self.candles) > CANDLE_HISTORY:
                self.candles = self.candles[-CANDLE_HISTORY:]

            # Track candles while in position
            if self.trader.position:
                self.candles_in_position += 1

            # Run strategy
            df = pd.DataFrame(self.candles)
            signal_result = self.strategy.evaluate(df)

            if signal_result.signal == Signal.BUY and not self.trader.position:
                msg = self.trader.open_position(price, signal_result.reason)
                if msg:
                    self.candles_in_position = 0
                    print(msg)
            elif (signal_result.signal == Signal.SELL and self.trader.position
                  and self.candles_in_position >= MIN_HOLD_CANDLES):
                msg = self.trader.close_position(price, signal_result.reason)
                if msg:
                    self.candles_in_position = 0
                    print(msg)

        # Periodic report (every 30 min)
        if time.time() - self.last_report > 1800:
            self._print_status(price)
            self.last_report = time.time()
            self.trader.save_state()
            self._save_performance()

    def _print_status(self, price: float):
        ts = datetime.now().strftime("%H:%M:%S")
        stats = self.trader.get_stats()
        pos_str = ""
        if self.trader.position:
            unrealized = (price - self.trader.position.entry_price) * self.trader.position.quantity
            pos_str = f" | Pos: ${unrealized:+,.2f}"
        print(f"\n⏱ [{ts}] BTC: ${price:,.2f} | "
              f"Bal: ${stats['balance']:,.2f} | "
              f"Trades: {stats['total_trades']} | "
              f"Return: {stats.get('total_return_pct', 0):+.2f}%{pos_str}\n")

    def _save_performance(self):
        stats = self.trader.get_stats()
        stats["last_update"] = datetime.now().isoformat()
        stats["uptime_hours"] = (time.time() - self.start_time) / 3600
        with open(PERFORMANCE_FILE, "w") as f:
            json.dump(stats, f, indent=2, default=str)

    async def run(self):
        self.start_time = time.time()
        self._fetch_historical()

        stream = f"{SYMBOL.lower()}@kline_{TIMEFRAME}"
        ws_url = f"{BINANCE_WS}/{stream}"

        print(f"\n🚀 Bot started | Strategy: EMA({EMA_FAST}/{EMA_SLOW}) + RSI + MACD")
        print(f"💰 Balance: ${self.trader.balance:,.2f}")
        print(f"📡 Connecting to {ws_url}...")

        reconnect_delay = 1
        while self.running:
            try:
                async with websockets.connect(ws_url, ping_interval=20) as ws:
                    print("✅ WebSocket connected")
                    reconnect_delay = 1

                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(msg)
                            self._process_ws_message(data)
                        except asyncio.TimeoutError:
                            # Send pong to keep alive
                            continue
                        except websockets.ConnectionClosed:
                            print("🔌 WebSocket disconnected")
                            break

            except Exception as e:
                if not self.running:
                    break
                print(f"⚠️ Connection error: {e}. Retrying in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)

        # Final report
        print("\n" + self.trader.get_performance_report())
        self.trader.save_state()
        self._save_performance()
        print("👋 Bot stopped.")


if __name__ == "__main__":
    bot = TradingBot()
    asyncio.run(bot.run())
