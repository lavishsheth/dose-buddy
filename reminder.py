"""Run this next to app.py: python reminder.py
Checks the saved schedule every 20 seconds and alerts when a dose is due.
Desktop notification works offline. Telegram is optional and needs internet."""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

import core

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def notify(title, message):
    print(f"[{datetime.now():%H:%M}] {title}: {message}", flush=True)
    try:
        from plyer import notification
        notification.notify(title=title, message=message, timeout=30)
    except Exception:
        pass  # plyer not installed or no desktop session: console print still happens
    if TOKEN and CHAT_ID:
        try:
            data = urllib.parse.urlencode(
                {"chat_id": CHAT_ID, "text": f"{title}\n{message}"}).encode()
            urllib.request.urlopen(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage", data, timeout=10)
        except Exception as e:
            print("Telegram failed:", e, flush=True)


def main():
    sent = set()
    print("Dose Buddy reminder running. Press Ctrl+C to stop.", flush=True)
    while True:
        schedule = core.load_schedule()
        if schedule:
            now = datetime.now()
            hhmm = now.strftime("%H:%M")
            for t, name, dose, notes in core.doses_for_day(
                    schedule["medicines"], schedule["start"], now.date()):
                key = (now.date(), name, t)
                if t == hhmm and key not in sent:
                    sent.add(key)
                    extra = f" ({notes})" if notes else ""
                    notify(f"Time for {schedule['person']}'s medicine",
                           f"{name} {dose}{extra}")
        time.sleep(20)


if __name__ == "__main__":
    main()
