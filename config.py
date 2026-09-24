import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Database Configuration
# Default to Supabase PostgreSQL (IPv4 Pooler endpoint required for Render & cloud hosts):
DEFAULT_SUPABASE_URL = "postgresql+asyncpg://postgres.fnpdmupnbrgopfnnmfgu:etpPil2MOmHqqnJp@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SUPABASE_URL)
# If the DATABASE_URL in environment still points to the direct IPv6 hostname, automatically redirect to IPv4 pooler:
if "db.fnpdmupnbrgopfnnmfgu.supabase.co" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("db.fnpdmupnbrgopfnnmfgu.supabase.co", "aws-0-ap-southeast-2.pooler.supabase.com").replace("postgres:", "postgres.fnpdmupnbrgopfnnmfgu:")
if ("sqlite" in DATABASE_URL) and not os.getenv("USE_LOCAL_SQLITE"):
    DATABASE_URL = DEFAULT_SUPABASE_URL

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


