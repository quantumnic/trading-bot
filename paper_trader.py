"""Paper trading engine — tracks positions, P&L, risk management."""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional
from config import *
from notify import notify_trade


@dataclass
class Position:
    entry_price: float
    quantity: float  # BTC amount
    entry_time: float
    side: str  # "LONG"
    stop_loss: float
    take_profit: float
    highest_price: float = 0.0  # For trailing stop


@dataclass
class Trade:
    entry_price: float
    exit_price: float
    quantity: float
    side: str
    entry_time: float
    exit_time: float
    pnl: float
    pnl_pct: float
    reason: str
    fees: float


class PaperTrader:
    def __init__(self):
        self.balance = INITIAL_BALANCE
        self.position: Optional[Position] = None
        self.trades: list[Trade] = []
        self.peak_balance = INITIAL_BALANCE
        self.max_drawdown = 0.0
        self._load_state()

    def _load_state(self):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                self.balance = state["balance"]
                self.peak_balance = state.get("peak_balance", INITIAL_BALANCE)
                self.max_drawdown = state.get("max_drawdown", 0.0)
                if state.get("position"):
                    self.position = Position(**state["position"])
                self.trades = [Trade(**t) for t in state.get("trades", [])]
                print(f"📂 Loaded state: ${self.balance:.2f} balance, "
                      f"{len(self.trades)} trades")
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"🆕 Fresh start: ${self.balance:.2f}")

    def save_state(self):
        state = {
            "balance": self.balance,
            "peak_balance": self.peak_balance,
            "max_drawdown": self.max_drawdown,
            "position": asdict(self.position) if self.position else None,
            "trades": [asdict(t) for t in self.trades],
        }
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def open_position(self, price: float, signal_reason: str) -> Optional[str]:
        if self.position:
            return None  # Already in position

        # Calculate position size
        trade_amount = self.balance * POSITION_SIZE_PCT
        fee = trade_amount * TRADING_FEE
        net_amount = trade_amount - fee
        quantity = net_amount / price

        stop_loss = price * (1 - STOP_LOSS_PCT)
        take_profit = price * (1 + TAKE_PROFIT_PCT)

        self.position = Position(
            entry_price=price,
            quantity=quantity,
            entry_time=time.time(),
            side="LONG",
            stop_loss=stop_loss,
            take_profit=take_profit,
            highest_price=price,
        )
        self.balance -= trade_amount
        self.save_state()

        msg = (f"🟢 LONG @ ${price:,.2f} | "
               f"Qty: {quantity:.6f} BTC | "
               f"SL: ${stop_loss:,.2f} | TP: ${take_profit:,.2f} | "
               f"Fee: ${fee:.2f} | {signal_reason}")
        self._log(msg)
        notify_trade(msg)
        return msg

    def check_exit(self, price: float) -> Optional[str]:
        if not self.position:
            return None

        pos = self.position
        reason = None

        # Update trailing stop
        if price > pos.highest_price:
            pos.highest_price = price
            new_stop = price * (1 - TRAILING_STOP_PCT)
            if new_stop > pos.stop_loss:
                pos.stop_loss = new_stop

        # Check stop loss
        if price <= pos.stop_loss:
            reason = f"Stop Loss (${pos.stop_loss:,.2f})"
        # Check take profit
        elif price >= pos.take_profit:
            reason = f"Take Profit (${pos.take_profit:,.2f})"

        if reason:
            return self.close_position(price, reason)
        return None

    def close_position(self, price: float, reason: str) -> str:
        if not self.position:
            return "No position to close"

        pos = self.position
        gross_value = pos.quantity * price
        fee = gross_value * TRADING_FEE
        net_value = gross_value - fee

        entry_cost = pos.quantity * pos.entry_price
        pnl = net_value - entry_cost
        pnl_pct = (pnl / entry_cost) * 100

        trade = Trade(
            entry_price=pos.entry_price,
            exit_price=price,
            quantity=pos.quantity,
            side=pos.side,
            entry_time=pos.entry_time,
            exit_time=time.time(),
            pnl=pnl,
            pnl_pct=pnl_pct,
            reason=reason,
            fees=fee + (entry_cost * TRADING_FEE),
        )
        self.trades.append(trade)
        self.balance += net_value

        # Track drawdown
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        dd = (self.peak_balance - self.balance) / self.peak_balance
        self.max_drawdown = max(self.max_drawdown, dd)

        self.position = None
        self.save_state()

        emoji = "🟢" if pnl > 0 else "🔴"
        msg = (f"{emoji} CLOSE @ ${price:,.2f} | "
               f"PnL: ${pnl:,.2f} ({pnl_pct:+.2f}%) | "
               f"Balance: ${self.balance:,.2f} | {reason}")
        self._log(msg)
        notify_trade(msg)
        return msg

    def get_stats(self) -> dict:
        if not self.trades:
            return {
                "total_trades": 0,
                "balance": self.balance,
                "total_return_pct": 0,
                "position": self._pos_summary(),
            }

        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        total_pnl = sum(t.pnl for t in self.trades)
        total_fees = sum(t.fees for t in self.trades)
        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0

        return {
            "total_trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self.trades) * 100,
            "total_pnl": total_pnl,
            "total_fees": total_fees,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss else float('inf'),
            "balance": self.balance,
            "total_return_pct": (self.balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100,
            "max_drawdown_pct": self.max_drawdown * 100,
            "position": self._pos_summary(),
        }

    def _pos_summary(self) -> Optional[dict]:
        if not self.position:
            return None
        return {
            "entry": self.position.entry_price,
            "stop_loss": self.position.stop_loss,
            "take_profit": self.position.take_profit,
            "quantity": self.position.quantity,
        }

    def _log(self, msg: str):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

    def get_performance_report(self) -> str:
        s = self.get_stats()
        lines = [
            "═══ PERFORMANCE REPORT ═══",
            f"Balance: ${s['balance']:,.2f} (started: ${INITIAL_BALANCE:,.2f})",
            f"Return: {s.get('total_return_pct', 0):+.2f}%",
            f"Trades: {s['total_trades']}",
        ]
        if s['total_trades'] > 0:
            lines += [
                f"Win Rate: {s['win_rate']:.1f}% ({s['wins']}W / {s['losses']}L)",
                f"Total PnL: ${s['total_pnl']:,.2f}",
                f"Total Fees: ${s['total_fees']:,.2f}",
                f"Avg Win: ${s['avg_win']:,.2f} | Avg Loss: ${s['avg_loss']:,.2f}",
                f"Profit Factor: {s['profit_factor']:.2f}",
                f"Max Drawdown: {s['max_drawdown_pct']:.2f}%",
            ]
        if s['position']:
            p = s['position']
            lines.append(f"Open: LONG @ ${p['entry']:,.2f} "
                         f"(SL: ${p['stop_loss']:,.2f}, TP: ${p['take_profit']:,.2f})")
        return "\n".join(lines)
