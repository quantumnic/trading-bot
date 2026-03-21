#!/usr/bin/env python3
"""Quick status check — run anytime to see bot performance."""

import json
from datetime import datetime
from config import STATE_FILE, PERFORMANCE_FILE, INITIAL_BALANCE

def show_status():
    try:
        with open(PERFORMANCE_FILE) as f:
            perf = json.load(f)
    except FileNotFoundError:
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
                perf = {
                    "balance": state["balance"],
                    "total_trades": len(state.get("trades", [])),
                    "position": state.get("position"),
                    "trades": state.get("trades", []),
                }
        except FileNotFoundError:
            print("❌ No bot state found. Is the bot running?")
            return

    bal = perf.get("balance", INITIAL_BALANCE)
    ret = (bal - INITIAL_BALANCE) / INITIAL_BALANCE * 100
    trades = perf.get("total_trades", 0)

    print("═══ TRADING BOT STATUS ═══")
    print(f"Balance: ${bal:,.2f} (start: ${INITIAL_BALANCE:,.2f})")
    print(f"Return: {ret:+.2f}%")
    print(f"Trades: {trades}")

    if perf.get("win_rate") is not None:
        print(f"Win Rate: {perf['win_rate']:.1f}%")
        print(f"Total PnL: ${perf.get('total_pnl', 0):,.2f}")
        print(f"Max Drawdown: {perf.get('max_drawdown_pct', 0):.2f}%")

    if perf.get("position"):
        p = perf["position"]
        print(f"\n📊 Open Position:")
        print(f"  Entry: ${p['entry']:,.2f}")
        print(f"  Stop Loss: ${p['stop_loss']:,.2f}")
        print(f"  Take Profit: ${p['take_profit']:,.2f}")

    if perf.get("last_update"):
        print(f"\nLast update: {perf['last_update']}")

    # Show recent trades
    trades_data = perf.get("trades", [])
    if not trades_data:
        try:
            with open(STATE_FILE) as f:
                trades_data = json.load(f).get("trades", [])
        except:
            pass

    if trades_data:
        print(f"\n── Last 5 Trades ──")
        for t in trades_data[-5:]:
            emoji = "🟢" if t["pnl"] > 0 else "🔴"
            print(f"  {emoji} ${t['entry_price']:,.0f}→${t['exit_price']:,.0f} "
                  f"PnL: ${t['pnl']:,.2f} ({t['pnl_pct']:+.2f}%) [{t['reason']}]")


if __name__ == "__main__":
    show_status()
