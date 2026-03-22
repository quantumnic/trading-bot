#!/usr/bin/env python3
"""Generate performance chart from bot state."""

import json
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone, timedelta
from config import STATE_FILE, INITIAL_BALANCE

ZH = timezone(timedelta(hours=1))


def generate_chart(output_path="performance.png"):
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        trades = state.get("trades", [])
        balance = state.get("balance", INITIAL_BALANCE)
        position = state.get("position")
    except FileNotFoundError:
        trades = []
        balance = INITIAL_BALANCE
        position = None

    # Build equity curve
    times = [datetime.fromtimestamp(trades[0]["entry_time"], tz=ZH) if trades else datetime.now(tz=ZH)]
    equity = [INITIAL_BALANCE]

    running_balance = INITIAL_BALANCE
    for t in trades:
        # Entry point
        entry_time = datetime.fromtimestamp(t["entry_time"], tz=ZH)
        times.append(entry_time)
        equity.append(running_balance)

        # Exit point
        exit_time = datetime.fromtimestamp(t["exit_time"], tz=ZH)
        running_balance += t["pnl"]
        times.append(exit_time)
        equity.append(running_balance)

    # Add current state
    now = datetime.now(tz=ZH)
    times.append(now)
    equity.append(balance)

    # Calculate stats
    total_return = (balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] <= 0)
    win_rate = (wins / len(trades) * 100) if trades else 0

    # Create chart
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#16213e')

    # Equity line
    color = '#00ff88' if total_return >= 0 else '#ff4444'
    ax.plot(times, equity, color=color, linewidth=2, zorder=3)
    ax.fill_between(times, INITIAL_BALANCE, equity, alpha=0.15, color=color, zorder=2)

    # Start line
    ax.axhline(y=INITIAL_BALANCE, color='#ffffff', linewidth=0.8, linestyle='--', alpha=0.4, zorder=1)

    # Trade markers
    for t in trades:
        exit_time = datetime.fromtimestamp(t["exit_time"], tz=ZH)
        exit_equity = sum(tr["pnl"] for tr in trades if tr["exit_time"] <= t["exit_time"]) + INITIAL_BALANCE
        if t["pnl"] > 0:
            ax.scatter(exit_time, exit_equity, color='#00ff88', s=50, zorder=4, marker='^')
        else:
            ax.scatter(exit_time, exit_equity, color='#ff4444', s=50, zorder=4, marker='v')

    # Labels
    ax.set_title(f'BTC Paper Trading Bot — Return: {total_return:+.2f}%',
                 color='white', fontsize=14, fontweight='bold', pad=15)

    status_text = (f'Balance: ${balance:,.2f}  |  '
                   f'Trades: {len(trades)}  |  '
                   f'Win Rate: {win_rate:.0f}% ({wins}W/{losses}L)')
    if position:
        status_text += f'  |  📊 Open: LONG @ ${position["entry_price"]:,.0f}'

    ax.set_xlabel(status_text.replace('$', r'\$'), color='#aaaaaa', fontsize=10, labelpad=10)
    ax.set_ylabel(r'Balance (\$)', color='#aaaaaa', fontsize=11)

    # Formatting
    ax.tick_params(colors='#888888')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#333333')
    ax.spines['left'].set_color('#333333')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
    fig.autofmt_xdate(rotation=30)
    ax.grid(True, alpha=0.15, color='#ffffff')

    # Timestamp
    fig.text(0.99, 0.01, f'Updated: {now.strftime("%d.%m.%Y %H:%M")}',
             ha='right', va='bottom', color='#555555', fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"✅ Chart saved: {output_path}")
    return output_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "performance.png"
    generate_chart(out)
