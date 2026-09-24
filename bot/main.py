import asyncio
import logging
import sys
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    PORTAL_URL,
    PORTAL_TIMEOUT_SECONDS,
    SESSION_CACHE_TTL_SECONDS,
    CHECK_INTERVAL_SECONDS,
    REQUEST_DELAY_SECONDS,
    LOG_LEVEL,
)
from db.database import init_db
from fetcher.mutah import MutahFetcher
from worker.monitor import SectionMonitor
from bot.keyboards import get_alert_keyboard
from bot.handlers import (
    start_command,
    help_command,
    watch_command,
    unwatch_command,
    track_command,
    untrack_command,
    check_command,
    list_command,
    admin_command,
    callback_query_handler,
    text_message_handler,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)
logger = logging.getLogger("CourseBot")


async def start_health_server(port: int):
    """
    Lightweight HTTP server to satisfy Render/Railway/Koyeb health-checks
    allowing the bot to run as a free web service.
    """
    async def handle_client(reader, writer):
        try:
            await reader.read(1024)
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/plain; charset=utf-8\r\n"
                "Connection: close\r\n\r\n"
                "Mutah Course Bot is Running Healthy!\n"
            )
            writer.write(response.encode("utf-8"))
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logger.info(f"🌐 Health-check HTTP server listening on port {port}")
    return server


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a friendly message if possible."""
    err_str = str(context.error or "")
    if "Message is not modified" in err_str:
        return

    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ حدث خطأ أثناء معالجة الطلب، يرجى المحاولة مرة أخرى.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


def build_application(token: str, fetcher: MutahFetcher) -> Application:
    """Builds and configures the python-telegram-bot application."""
    application = ApplicationBuilder().token(token).build()

    # Share fetcher instance in bot_data
    application.bot_data["fetcher"] = fetcher

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("watch", watch_command))
    application.add_handler(CommandHandler("unwatch", unwatch_command))
    application.add_handler(CommandHandler("track", track_command))
    application.add_handler(CommandHandler("untrack", untrack_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("admin", admin_command))

    # Register inline button handler
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    # Register text message handler (for direct course ID search)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    # Register error handler
    application.add_error_handler(error_handler)

    return application


async def main() -> None:
    # Ensure Windows console displays Arabic correctly
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error(
            "\n"
            "==========================================================\n"
            "❌ خطأ: لم يتم ضبط توكن البوت TELEGRAM_BOT_TOKEN!\n"
            "يرجى فتح ملف .env وإضافة توكن البوت المستخرج من @BotFather:\n"
            "TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ\n"
            "==========================================================\n"
        )
        sys.exit(1)

    # 1. Initialize Database tables
    logger.info("Initializing database...")
    await init_db()

    # Optional: Start health server if running on cloud platforms (Render, Railway, Koyeb)
    port_env = os.getenv("PORT")
    if port_env:
        try:
            port = int(port_env)
            await start_health_server(port)
        except Exception as e:
            logger.warning(f"Could not bind health-check server on port {port_env}: {e}")

    # 2. Initialize Fetcher
    fetcher = MutahFetcher(
        base_url=PORTAL_URL,
        timeout=PORTAL_TIMEOUT_SECONDS,
        session_ttl=SESSION_CACHE_TTL_SECONDS,
    )
    fetcher.refresh_session()

    # 3. Build Telegram Application
    application = build_application(TELEGRAM_BOT_TOKEN, fetcher)

    # 4. Define Telegram notification callback for SectionMonitor
    async def send_seat_alert(
        telegram_id: int, message: str, course_id: str, section_no: str
    ) -> bool:
        try:
            await application.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=get_alert_keyboard(course_id, section_no),
            )
            return True
        except Exception as e:
            logger.error(f"Error sending message to {telegram_id}: {e}")
            return False

    # 5. Initialize SectionMonitor worker
    monitor = SectionMonitor(
        fetcher=fetcher,
        notify_callback=send_seat_alert,
        check_interval=CHECK_INTERVAL_SECONDS,
        request_delay=REQUEST_DELAY_SECONDS,
    )

    # 6. Start Bot and Background Worker together
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("🤖 Telegram bot polling started successfully!")

        # Launch monitor task
        monitor_task = asyncio.create_task(monitor.start())

        try:
            # Keep running until cancelled
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
            logger.info("Shutdown requested...")
        finally:
            monitor.stop()
            monitor_task.cancel()
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            logger.info("Bot and monitor stopped cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
