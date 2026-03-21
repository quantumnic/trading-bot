"""Trade notifications via openclaw system event."""

import subprocess
import os


def notify_trade(msg: str):
    """Send trade notification via openclaw system event → triggers main session."""
    try:
        subprocess.Popen(
            ["openclaw", "system", "event",
             "--text", f"🤖 TRADE ALERT: {msg}",
             "--mode", "now"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"⚠️ Notification failed: {e}")
