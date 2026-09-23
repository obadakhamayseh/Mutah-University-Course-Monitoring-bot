import asyncio
import logging
from typing import Optional, Callable, Awaitable
from datetime import datetime, timezone

from config import CHECK_INTERVAL_SECONDS, REQUEST_DELAY_SECONDS
from fetcher.mutah import MutahFetcher, SectionInfo
from db.database import async_session
from db.crud import (
    get_unique_active_sections,
    get_subscribers_for_section,
    get_section_cache,
    update_section_cache,
    mark_subscription_notified,
    reset_subscription_notification,
    log_notification,
)

logger = logging.getLogger(__name__)


import html

def format_available_alert(section: SectionInfo) -> str:
    """Formats an urgent notification message in Arabic when a seat opens."""
    course_name = html.escape(str(section.course_name or ""))
    course_id = html.escape(str(section.course_id or ""))
    sec_no = html.escape(str(section.section or ""))
    instructor = html.escape(str(section.instructor or "غير محدد"))
    days = html.escape(str(section.days or "-"))
    time_from = html.escape(str(section.time_from or "-"))
    time_to = html.escape(str(section.time_to or "-"))
    room = html.escape(str(section.room or "-"))

    return (
        "🚨 <b>تنبيه توفر مقعد شاغر!</b> 🚨\n\n"
        f"📚 <b>المادة:</b> {course_name} (<code>{course_id}</code>)\n"
        f"🔢 <b>الشعبة:</b> <code>{sec_no}</code>\n"
        f"👨‍🏫 <b>المدرس:</b> {instructor}\n"
        f"🟢 <b>المقاعد المتاحة حالياً:</b> <b>{section.available_seats}</b> من {section.capacity}\n"
        f"👥 <b>المسجلين:</b> {section.enrolled}\n"
        f"📅 <b>الأيام:</b> {days}\n"
        f"⏰ <b>الوقت:</b> {time_from} - {time_to}\n"
        f"🏢 <b>القاعة:</b> {room}\n\n"
        "⚡️ <b>سارع بالدخول إلى بوابة التسجيل وسجل المادة الآن!</b>"
    )


class SectionMonitor:
    """
    Background worker that periodically checks watched university course sections.
    Implements deduplication and detects state transitions (FULL -> AVAILABLE).
    """

    def __init__(
        self,
        fetcher: MutahFetcher,
        notify_callback: Optional[Callable[[int, str, str, str], Awaitable[bool]]] = None,
        check_interval: int = CHECK_INTERVAL_SECONDS,
        request_delay: float = REQUEST_DELAY_SECONDS,
    ):
        self.fetcher = fetcher
        self.notify_callback = notify_callback
        self.check_interval = check_interval
        self.request_delay = request_delay
        self.is_running = False

    async def check_single_section(self, course_id: str, section_no: str) -> None:
        """
        Checks a single section, compares with cache, and triggers notifications if seats opened.
        """
        logger.info(f"Checking section {course_id} - sec {section_no}...")

        section_info: Optional[SectionInfo] = await self.fetcher.get_section_async(
            course_id=course_id, section_no=section_no
        )

        if not section_info:
            logger.warning(
                f"Could not retrieve section data for {course_id} sec {section_no} from portal."
            )
            return

        async with async_session() as session:
            cache = await get_section_cache(session, course_id, section_no)

            # Determine state transition
            # Transition FULL -> AVAILABLE happens if:
            # 1. Previously known as full (or not in cache yet) AND currently has available seats > 0.
            previously_full = (cache is None) or cache.is_full or (cache.available_seats <= 0)
            currently_available = (not section_info.is_full) and (section_info.available_seats > 0)

            # Update cache record
            await update_section_cache(
                session=session,
                course_id=course_id,
                section_no=section_no,
                course_name=section_info.course_name,
                capacity=section_info.capacity,
                enrolled=section_info.enrolled,
                available_seats=section_info.available_seats,
                is_full=section_info.is_full,
            )

            if previously_full and currently_available:
                logger.info(
                    f"🎉 SEAT AVAILABLE in {course_id} sec {section_no}! "
                    f"Seats: {section_info.available_seats}/{section_info.capacity}"
                )

                subscribers = await get_subscribers_for_section(session, course_id, section_no)
                alert_text = format_available_alert(section_info)

                for sub, user in subscribers:
                    # Send alert only if not already notified for this opening
                    if sub.notified_at is None and self.notify_callback:
                        try:
                            sent = await self.notify_callback(
                                user.telegram_id,
                                alert_text,
                                course_id,
                                section_no,
                            )
                            if sent:
                                await mark_subscription_notified(session, sub.id)
                                await log_notification(
                                    session=session,
                                    user_id=user.id,
                                    course_id=course_id,
                                    section_no=section_no,
                                    available_seats=section_info.available_seats,
                                )
                                logger.info(
                                    f"Alert sent to user {user.telegram_id} for {course_id}-{section_no}"
                                )
                        except Exception as ex:
                            logger.error(f"Failed to notify user {user.telegram_id}: {ex}")

            elif section_info.is_full or section_info.available_seats <= 0:
                # If section became full again, reset notification state so future seat openings trigger alert
                if cache and not cache.is_full:
                    logger.info(
                        f"Section {course_id} sec {section_no} is full again. Resetting notifications."
                    )
                    await reset_subscription_notification(session, course_id, section_no)

    async def run_cycle(self) -> None:
        """Runs a single monitoring cycle across all distinct watched sections."""
        try:
            async with async_session() as session:
                unique_sections = await get_unique_active_sections(session)

            if not unique_sections:
                logger.debug("No active watched sections in database. Skipping cycle.")
                return

            logger.info(f"Starting cycle for {len(unique_sections)} unique watched section(s)...")

            for course_id, section_no in unique_sections:
                if not self.is_running:
                    break

                try:
                    await self.check_single_section(course_id, section_no)
                except Exception as e:
                    logger.error(
                        f"Unexpected error while checking {course_id}-{section_no}: {e}",
                        exc_info=True,
                    )

                # Polite rate-limiting between distinct section queries
                await asyncio.sleep(self.request_delay)

        except Exception as e:
            logger.error(f"Error during monitor cycle: {e}", exc_info=True)

    async def start(self) -> None:
        """Starts the periodic background monitoring loop."""
        self.is_running = True
        logger.info(
            f"SectionMonitor worker started (Interval: {self.check_interval}s, Delay: {self.request_delay}s)."
        )

        while self.is_running:
            start_time = asyncio.get_event_loop().time()
            await self.run_cycle()
            elapsed = asyncio.get_event_loop().time() - start_time
            sleep_time = max(1.0, self.check_interval - elapsed)

            logger.debug(f"Monitor cycle finished in {elapsed:.1f}s. Sleeping {sleep_time:.1f}s.")
            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break

    def stop(self) -> None:
        """Stops the monitoring worker."""
        logger.info("Stopping SectionMonitor worker...")
        self.is_running = False
