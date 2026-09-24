import asyncio
import logging
import html
from typing import Optional, Callable, Awaitable, List
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


def detect_section_changes(cache, current: SectionInfo) -> List[str]:
    """Detects differences between previous cached state and current state."""
    changes = []
    if cache.enrolled != current.enrolled:
        changes.append(
            f"👥 <b>المسجلين:</b> تغير من <code>{cache.enrolled}</code> إلى <code>{current.enrolled}</code> (المتاح: {current.available_seats})"
        )
    if cache.capacity != current.capacity:
        changes.append(
            f"📊 <b>السعة الكلية:</b> تغيرت من <code>{cache.capacity}</code> إلى <code>{current.capacity}</code>"
        )
    if (cache.instructor or "").strip() != (current.instructor or "").strip():
        old_inst = html.escape(cache.instructor or "غير محدد")
        new_inst = html.escape(current.instructor or "غير محدد")
        changes.append(f"👨‍🏫 <b>المدرس:</b> تغير من <i>{old_inst}</i> إلى <i>{new_inst}</i>")
    if (cache.days or "").strip() != (current.days or "").strip():
        old_days = html.escape(cache.days or "-")
        new_days = html.escape(current.days or "-")
        changes.append(f"📅 <b>الأيام:</b> تغيرت من <i>{old_days}</i> إلى <i>{new_days}</i>")

    old_time = f"{cache.time_from or ''} - {cache.time_to or ''}".strip(" -")
    new_time = f"{current.time_from or ''} - {current.time_to or ''}".strip(" -")
    if old_time != new_time:
        changes.append(f"⏰ <b>الموعد:</b> تغير من <i>{html.escape(old_time or '-')}</i> إلى <i>{html.escape(new_time or '-')}</i>")

    if (cache.room or "").strip() != (current.room or "").strip():
        old_room = html.escape(cache.room or "-")
        new_room = html.escape(current.room or "-")
        changes.append(f"🏢 <b>القاعة:</b> تغيرت من <i>{old_room}</i> إلى <i>{new_room}</i>")

    if (cache.notes or "").strip() != (current.notes or "").strip():
        new_notes = html.escape(current.notes or "تمت إزالة الملاحظات")
        changes.append(f"📝 <b>الملاحظات:</b> {new_notes}")

    return changes


def format_change_alert(section: SectionInfo, changes: List[str]) -> str:
    """Formats a detailed notification message when any section property changes."""
    course_name = html.escape(str(section.course_name or ""))
    course_id = html.escape(str(section.course_id or ""))
    sec_no = html.escape(str(section.section or ""))

    changes_body = "\n".join(f"• {c}" for c in changes)
    return (
        "📢 <b>تنبيه رصد تغيير في الشعبة!</b> 📢\n\n"
        f"📚 <b>المادة:</b> {course_name} (<code>{course_id}</code>)\n"
        f"🔢 <b>الشعبة:</b> <code>{sec_no}</code>\n\n"
        f"🔍 <b>التغييرات المرصودة:</b>\n"
        f"{changes_body}\n\n"
        f"⏱ <b>وقت التحديث:</b> {datetime.now().strftime('%I:%M:%S %p')}"
    )


class SectionMonitor:
    """
    Background worker that periodically checks watched university course sections.
    Supports both SEAT availability monitoring and CHANGE tracking with deduplication.
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
        Checks a single section, compares with cache, and triggers notifications:
        - If seats open (FULL -> AVAILABLE): alerts 'SEAT' subscribers.
        - If any property changed: alerts 'CHANGE' subscribers.
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

            # 1. Check for field changes (for 'CHANGE' tracker subscribers)
            if cache is not None:
                detected_changes = detect_section_changes(cache, section_info)
                if detected_changes:
                    logger.info(f"Detected {len(detected_changes)} change(s) in {course_id}-{section_no}")
                    change_subs = await get_subscribers_for_section(session, course_id, section_no, sub_type="CHANGE")
                    if change_subs and self.notify_callback:
                        change_text = format_change_alert(section_info, detected_changes)
                        for sub, user in change_subs:
                            try:
                                await self.notify_callback(user.telegram_id, change_text, course_id, section_no)
                                await log_notification(session, user.id, course_id, section_no, section_info.available_seats)
                            except Exception as ex:
                                logger.error(f"Failed to send change alert to {user.telegram_id}: {ex}")

            # 2. Check for seat transition FULL -> AVAILABLE (for 'SEAT' subscribers)
            previously_full = (cache is None) or cache.is_full or (cache.available_seats <= 0)
            currently_available = (not section_info.is_full) and (section_info.available_seats > 0)

            if previously_full and currently_available:
                logger.info(
                    f"🎉 SEAT AVAILABLE in {course_id} sec {section_no}! "
                    f"Seats: {section_info.available_seats}/{section_info.capacity}"
                )

                seat_subs = await get_subscribers_for_section(session, course_id, section_no, sub_type="SEAT")
                alert_text = format_available_alert(section_info)

                for sub, user in seat_subs:
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
                        except Exception as ex:
                            logger.error(f"Failed to notify user {user.telegram_id}: {ex}")

            elif section_info.is_full or section_info.available_seats <= 0:
                if cache and not cache.is_full:
                    logger.info(f"Section {course_id} sec {section_no} is full again. Resetting notifications.")
                    await reset_subscription_notification(session, course_id, section_no)

            # 3. Update cache record with full details
            await update_section_cache(
                session=session,
                course_id=course_id,
                section_no=section_no,
                course_name=section_info.course_name,
                capacity=section_info.capacity,
                enrolled=section_info.enrolled,
                available_seats=section_info.available_seats,
                is_full=section_info.is_full,
                instructor=section_info.instructor,
                days=section_info.days,
                time_from=section_info.time_from,
                time_to=section_info.time_to,
                room=section_info.room,
                notes=section_info.notes,
            )

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
            try:
                start_time = asyncio.get_event_loop().time()
                await self.run_cycle()
                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(1.0, self.check_interval - elapsed)

                logger.debug(f"Monitor cycle finished in {elapsed:.1f}s. Sleeping {sleep_time:.1f}s.")
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    def stop(self) -> None:
        """Stops the monitoring worker."""
        logger.info("Stopping SectionMonitor worker...")
        self.is_running = False
