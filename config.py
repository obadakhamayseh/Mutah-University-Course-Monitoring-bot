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
admin_env = os.getenv("ADMIN_TELEGRAM_ID", "933343496")
try:
    ADMIN_TELEGRAM_ID = int(admin_env) if admin_env else 933343496
except ValueError:
    ADMIN_TELEGRAM_ID = 933343496

# Subscription Limits (Maximum 6 monitored sections per user)
MAX_SUBSCRIPTIONS_PER_USER = int(os.getenv("MAX_SUBSCRIPTIONS_PER_USER", "6"))


