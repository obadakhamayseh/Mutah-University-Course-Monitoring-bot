import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Database Configuration
# Default is async SQLite; can be overridden with async PostgreSQL:
# e.g.: postgresql+asyncpg://user:password@localhost:5432/mutah_db
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'mutah_bot.db'}")

# University Portal Configuration
PORTAL_URL = os.getenv("PORTAL_URL", "https://subp.mutah.edu.jo/")
PORTAL_TIMEOUT_SECONDS = int(os.getenv("PORTAL_TIMEOUT_SECONDS", "25"))
SESSION_CACHE_TTL_SECONDS = int(os.getenv("SESSION_CACHE_TTL_SECONDS", "300"))  # 5 minutes

# Monitoring Worker Configuration
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "2.0"))

# Logging & Admin
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", None)
if ADMIN_TELEGRAM_ID:
    try:
        ADMIN_TELEGRAM_ID = int(ADMIN_TELEGRAM_ID)
    except ValueError:
        ADMIN_TELEGRAM_ID = None
