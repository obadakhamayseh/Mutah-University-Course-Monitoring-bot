#!/usr/bin/env python3
"""
Main launcher for the Mutah University Course Monitoring Telegram Bot.
"""
import sys
import asyncio
from bot.main import main

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nExiting gracefully...")
