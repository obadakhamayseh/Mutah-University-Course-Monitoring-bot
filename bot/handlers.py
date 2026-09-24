import html
import logging
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import ADMIN_TELEGRAM_ID
from fetcher.mutah import MutahFetcher, SectionInfo
from db.database import async_session
from db.crud import (
    get_or_create_user,
    add_subscription,
    remove_subscription,
    get_user_subscriptions,
    get_section_cache,
    update_section_cache,
    get_admin_stats,
    get_all_users_with_subs,
)
from bot.keyboards import (
    get_section_keyboard,
    get_track_keyboard,
    get_unwatch_confirm_keyboard,
    get_untrack_confirm_keyboard,
    get_course_sections_keyboard,
    get_quick_sub_keyboard,
    get_list_dashboard_keyboard,
    get_main_menu_keyboard,
    get_admin_dashboard_keyboard,
)

logger = logging.getLogger(__name__)


def format_section_card(section: SectionInfo, is_watched: bool = False, watch_type: str = "SEAT") -> str:
    """Formats a detailed section information card in Arabic using HTML."""
    status_emoji = "🔴" if section.is_full else "🟢"
    status_text = "ممتلئة (لا يوجد مقاعد)" if section.is_full else f"متاحة ({section.available_seats} مقاعد شاغرة)"

    course_name = html.escape(str(section.course_name or ""))
    course_id = html.escape(str(section.course_id or ""))
    sec_no = html.escape(str(section.section or ""))
    instructor = html.escape(str(section.instructor or "غير محدد"))
    days = html.escape(str(section.days or "-"))
    time_from = html.escape(str(section.time_from or "-"))
    time_to = html.escape(str(section.time_to or "-"))
    room = html.escape(str(section.room or "-"))
    notes = html.escape(str(section.notes or ""))

    lines = [
        f"{status_emoji} <b>{course_name}</b>",
        f"🔖 <b>رقم المادة:</b> <code>{course_id}</code>",
        f"🔢 <b>الشعبة:</b> <code>{sec_no}</code>",
        f"👨‍🏫 <b>المدرس:</b> {instructor}",
        f"📊 <b>الحالة:</b> {status_text}",
        f"👥 <b>المسجلين:</b> {section.enrolled} / {section.capacity}",
        f"📅 <b>الأيام:</b> {days}",
        f"⏰ <b>التوقيت:</b> {time_from} - {time_to}",
        f"🏢 <b>القاعة:</b> {room}",
    ]
    if notes:
        lines.append(f"📝 <b>ملاحظات:</b> {notes}")

    check_time = datetime.now().strftime("%I:%M:%S %p")
    lines.append(f"⏱ <b>آخر فحص:</b> {check_time}")

    if is_watched:
        if watch_type == "CHANGE":
            lines.append("👁 <b>حالة التتبع:</b> مفعلة (ستصلك رسالة عند أي تغيير يطرأ على الشعبة)")
        else:
            lines.append("🔔 <b>حالة المراقبة:</b> مفعلة (ستصلك رسالة فور توفر مقعد شاغر)")

    return "\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    user = update.effective_user
    if not user:
        return

    async with async_session() as session:
        await get_or_create_user(
            session=session,
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )

    user_name = html.escape(user.first_name or "صديقي")
    is_admin = (ADMIN_TELEGRAM_ID is not None and user.id == ADMIN_TELEGRAM_ID)

    welcome_text = (
        f"مرحباً بك يا <b>{user_name}</b> في <b>بوت مراقبة وتتبع مواد جامعة مؤتة</b> 🎓✨\n\n"
        "⚡️ <b>طريقة الاستخدام السريعة (بدون كتابة أوامر):</b>\n"
        "فقط أرسل <b>رقم المادة</b> مباشرة هنا (مثال: <code>0209100</code>).\n"
        "وسيعرض لك البوت فوراً جميع شُعب المادة مع <b>أزرار تفاعلية</b>:\n"
        "• 🔔 <b>زر مراقبة مقعد:</b> للشعب الممتلئة (إشعار فوري عند توفر مقعد).\n"
        "• 👁 <b>زر تتبع الشعبة:</b> للشعب المفتوحة (إشعارك بأي تغيير في المدرس، القاعة، الموعد، أو المقاعد).\n"
        "• 📋 <b>زر التفاصيل:</b> لمعاينة كافة أوقات وقاعات الشعبة.\n\n"
        "📊 <b>إدارة الشُعب المراقبة:</b>\n"
        "اضغط على زر <b>«شُعبي المراقبة»</b> بالأسفل لإلغاء أو متابعة أي شعبة بنقرة واحدة!"
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard(is_admin=is_admin),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /help command."""
    user = update.effective_user
    is_admin = bool(user and ADMIN_TELEGRAM_ID is not None and user.id == ADMIN_TELEGRAM_ID)

    help_text = (
        "📖 <b>دليل استخدام بوت جامعة مؤتة</b> 💡\n\n"
        "✨ <b>لا داعي لكتابة أوامر يدوية بعد الآن!</b>\n"
        "1. اكتب فقط <b>رقم أي مادة</b> بالإنجليزية (مثال: <code>0209100</code>).\n"
        "2. ستظهر لك قائمة شُعب المادة كأزرار ملونة:\n"
        "   - 🔴 شعبة ممتلئة ⬅️ اضغط زر <b>🔔 راقب</b> لتنبيهك عند فتح مقعد.\n"
        "   - 🟢 شعبة متاحة ⬅️ اضغط زر <b>👁 تتبع</b> لتنبيهك عند أي تعديل بالبيانات.\n\n"
        "📋 <b>لوحة التحكم باشتراكاتك:</b>\n"
        "أرسل <code>/list</code> أو اضغط الزر أدناه لمعاينة وإلغاء مراقبة أي شعبة بضغطة زر واحدة."
    )
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard(is_admin=is_admin),
    )


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /watch <course_id> <section_no> (Seat Availability)."""
    user = update.effective_user
    if not user or not update.message:
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ <b>صيغة الأمر غير صحيحة.</b>\n"
            "الاستخدام الصحيح لمراقبة المقاعد:\n"
            "<code>/watch &lt;رقم_المادة&gt; &lt;رقم_الشعبة&gt;</code>\n\n"
            "مثال: <code>/watch 0209100 1</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    course_id = args[0].strip()
    section_no = args[1].strip()

    status_msg = await update.message.reply_text(
        f"⏳ جاري فحص الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> على موقع الجامعة...",
        parse_mode=ParseMode.HTML,
    )

    fetcher: MutahFetcher = context.bot_data["fetcher"]
    section_info = await fetcher.get_section_async(course_id, section_no)

    if not section_info:
        await status_msg.edit_text(
            f"❌ لم يتم العثور على الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> في جريدة المواد.\n"
            "يرجى التأكد من صحة رقم المادة ورقم الشعبة من الجدول الدراسي.",
            parse_mode=ParseMode.HTML,
        )
        return

    async with async_session() as session:
        db_user = await get_or_create_user(
            session=session,
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )

        await add_subscription(
            session=session,
            user_id=db_user.id,
            course_id=course_id,
            section_no=section_no,
            course_name=section_info.course_name,
            sub_type="SEAT",
        )

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

    card_text = format_section_card(section_info, is_watched=True, watch_type="SEAT")

    if section_info.available_seats > 0:
        reply_text = (
            "🟢 <b>تنبيه: يوجد مقاعد متاحة بالفعل الآن!</b>\n\n"
            f"{card_text}\n\n"
            "⚡️ سارع بالتسجيل الآن قبل اكتمال السعة! تم تفعيل المراقبة في حال أُغلقت لاحقاً."
        )
    else:
        reply_text = (
            "✅ <b>تم تفعيل مراقبة المقاعد الشاغرة بنجاح!</b>\n\n"
            f"{card_text}\n\n"
            "📡 سنقوم بمراقبة هذه الشعبة تلقائياً وإشعارك فور توفر أي مقعد شاغر."
        )

    await status_msg.edit_text(
        reply_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_section_keyboard(course_id, section_no),
    )


async def unwatch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /unwatch <course_id> <section_no>."""
    user = update.effective_user
    if not user or not update.message:
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ <b>صيغة الأمر غير صحيحة.</b>\n"
            "الاستخدام الصحيح:\n"
            "<code>/unwatch &lt;رقم_المادة&gt; &lt;رقم_الشعبة&gt;</code>\n\n"
            "مثال: <code>/unwatch 0209100 1</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    course_id = args[0].strip()
    section_no = args[1].strip()

    async with async_session() as session:
        db_user = await get_or_create_user(session, user.id)
        removed = await remove_subscription(session, db_user.id, course_id, section_no, sub_type="SEAT")

    if removed:
        await update.message.reply_text(
            f"✅ تم إلغاء مراقبة المقاعد للشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> بنجاح.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"ℹ️ أنت لا تراقب مقاعد الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> حالياً.",
            parse_mode=ParseMode.HTML,
        )


async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /track <course_id> <section_no> (Any Detail Changes)."""
    user = update.effective_user
    if not user or not update.message:
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ <b>صيغة الأمر غير صحيحة.</b>\n"
            "الاستخدام الصحيح لتتبع التغييرات:\n"
            "<code>/track &lt;رقم_المادة&gt; &lt;رقم_الشعبة&gt;</code>\n\n"
            "مثال: <code>/track 0209100 1</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    course_id = args[0].strip()
    section_no = args[1].strip()

    status_msg = await update.message.reply_text(
        f"⏳ جاري فحص الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> على موقع الجامعة وتفعيل التتبع...",
        parse_mode=ParseMode.HTML,
    )

    fetcher: MutahFetcher = context.bot_data["fetcher"]
    section_info = await fetcher.get_section_async(course_id, section_no)

    if not section_info:
        await status_msg.edit_text(
            f"❌ لم يتم العثور على الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> في جريدة المواد.",
            parse_mode=ParseMode.HTML,
        )
        return

    async with async_session() as session:
        db_user = await get_or_create_user(
            session=session,
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )

        await add_subscription(
            session=session,
            user_id=db_user.id,
            course_id=course_id,
            section_no=section_no,
            course_name=section_info.course_name,
            sub_type="CHANGE",
        )

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

    card_text = format_section_card(section_info, is_watched=True, watch_type="CHANGE")
    reply_text = (
        "👁 <b>تم تفعيل تتبع تغييرات الشعبة بنجاح!</b>\n\n"
        f"{card_text}\n\n"
        "📡 <b>سنقوم بإشعارك بأي تعديل يطرأ على هذه الشعبة:</b>\n"
        "• زيادة أو نقصان عدد المسجلين والمقاعد المتاحة\n"
        "• تغيير المدرس أو القاعة\n"
        "• تعديل المواعيد أو الأيام أو الملاحظات"
    )

    await status_msg.edit_text(
        reply_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_track_keyboard(course_id, section_no),
    )


async def untrack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /untrack <course_id> <section_no>."""
    user = update.effective_user
    if not user or not update.message:
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ <b>صيغة الأمر غير صحيحة.</b>\n"
            "الاستخدام الصحيح:\n"
            "<code>/untrack &lt;رقم_المادة&gt; &lt;رقم_الشعبة&gt;</code>\n\n"
            "مثال: <code>/untrack 0209100 1</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    course_id = args[0].strip()
    section_no = args[1].strip()

    async with async_session() as session:
        db_user = await get_or_create_user(session, user.id)
        removed = await remove_subscription(session, db_user.id, course_id, section_no, sub_type="CHANGE")

    if removed:
        await update.message.reply_text(
            f"✅ تم إلغاء تتبع التغييرات للشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> بنجاح.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"ℹ️ أنت لا تتتبع تغييرات الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> حالياً.",
            parse_mode=ParseMode.HTML,
        )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /check <course_id> [section_no]."""
    if not update.message:
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "⚠️ يرجى تحديد رقم المادة المراد فحصها.\n"
            "أمثلة:\n"
            "• <code>/check 0209100</code> (لفحص جميع شُعب المادة)\n"
            "• <code>/check 0209100 1</code> (لفحص شعبة معينة)",
            parse_mode=ParseMode.HTML,
        )
        return

    course_id = args[0].strip()
    section_no = args[1].strip() if len(args) > 1 else None

    fetcher: MutahFetcher = context.bot_data["fetcher"]

    status_msg = await update.message.reply_text(
        f"⏳ جاري الاستعلام عن المادة <code>{html.escape(course_id)}</code> من موقع الجامعة...",
        parse_mode=ParseMode.HTML,
    )

    if section_no:
        section = await fetcher.get_section_async(course_id, section_no)
        if not section:
            await status_msg.edit_text(
                f"❌ لم يتم العثور على الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code>.",
                parse_mode=ParseMode.HTML,
            )
            return

        text = format_section_card(section, is_watched=False)
        await status_msg.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_section_keyboard(course_id, section_no),
        )
    else:
        sections = await fetcher.search_course_async(course_id)
        if not sections:
            await status_msg.edit_text(
                f"❌ لم يتم العثور على أي شعبة مسجلة للمادة <code>{html.escape(course_id)}</code>.",
                parse_mode=ParseMode.HTML,
            )
            return

        course_name_esc = html.escape(sections[0].course_name)
        header = (
            f"📚 <b>شُعب مادة:</b> {course_name_esc} (<code>{html.escape(course_id)}</code>)\n"
            f"📊 عدد الشُعب الكلي: <b>{len(sections)}</b>\n\n"
            "اضغط على أي زر أدناه للاشتراك الفوري أو استعراض التفاصيل:\n"
            "• 🔔 <b>راقب:</b> للشعب الممتلئة (تنبيه فوري عند توفر مقعد)\n"
            "• 👁 <b>تتبع:</b> للشعب المتاحة (تنبيه عند أي تعديل)\n"
        )

        await status_msg.edit_text(
            header,
            parse_mode=ParseMode.HTML,
            reply_markup=get_course_sections_keyboard(course_id, sections),
        )


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /list to show watched courses and tracked sections with inline cancel buttons."""
    user = update.effective_user
    if not user or not update.message:
        return

    async with async_session() as session:
        db_user = await get_or_create_user(session, user.id)
async def format_dashboard_text(session, subs: list) -> str:
    """Helper to format the full detailed dashboard for a user's subscriptions."""
    seat_subs = [s for s in subs if s.sub_type == "SEAT"]
    change_subs = [s for s in subs if s.sub_type == "CHANGE"]

    parts = [f"📋 <b>لوحة التحكم باشتراكاتك ({len(subs)} شُعب):</b>\n"]

    if seat_subs:
        parts.append(f"🔔 <b>مراقبة المقاعد الشاغرة ({len(seat_subs)}):</b>")
        for i, sub in enumerate(seat_subs, 1):
            name = html.escape(sub.course_name or "مادة")
            cid = html.escape(sub.course_id)
            sec = html.escape(sub.section_no)
            cache = await get_section_cache(session, sub.course_id, sub.section_no)
            
            if cache:
                status_icon = "🔴" if cache.is_full else "🟢"
                status_str = f"ممتلئة ({cache.enrolled}/{cache.capacity})" if cache.is_full else f"شاغرة ({cache.available_seats} مقاعد متاحة)"
                inst = html.escape(cache.instructor or "غير محدد")
                days = html.escape(cache.days or "-")
                t_from = html.escape(cache.time_from or "-")
                t_to = html.escape(cache.time_to or "-")
                room = html.escape(cache.room or "-")
                notes = f" | ملاحظات: {html.escape(cache.notes)}" if cache.notes else ""
                
                parts.append(
                    f"{i}. {status_icon} <b>{name}</b>\n"
                    f"   • المادة: <code>{cid}</code> | الشعبة: <code>{sec}</code>\n"
                    f"   • الحالة: <b>{status_str}</b>\n"
                    f"   • المدرس: {inst}\n"
                    f"   • الأوقات: {days} ({t_from} - {t_to}) | القاعة: {room}{notes}\n"
                )
            else:
                parts.append(
                    f"{i}. 🔔 <b>{name}</b>\n"
                    f"   • المادة: <code>{cid}</code> | الشعبة: <code>{sec}</code>\n"
                )
        parts.append("")

    if change_subs:
        parts.append(f"👁 <b>تتبع التغييرات والتفاصيل ({len(change_subs)}):</b>")
        for i, sub in enumerate(change_subs, 1):
            name = html.escape(sub.course_name or "مادة")
            cid = html.escape(sub.course_id)
            sec = html.escape(sub.section_no)
            cache = await get_section_cache(session, sub.course_id, sub.section_no)
            
            if cache:
                status_icon = "🔴" if cache.is_full else "🟢"
                status_str = f"ممتلئة ({cache.enrolled}/{cache.capacity})" if cache.is_full else f"شاغرة ({cache.available_seats} مقاعد متاحة)"
                inst = html.escape(cache.instructor or "غير محدد")
                days = html.escape(cache.days or "-")
                t_from = html.escape(cache.time_from or "-")
                t_to = html.escape(cache.time_to or "-")
                room = html.escape(cache.room or "-")
                notes = f" | ملاحظات: {html.escape(cache.notes)}" if cache.notes else ""
                
                parts.append(
                    f"{i}. {status_icon} <b>{name}</b>\n"
                    f"   • المادة: <code>{cid}</code> | الشعبة: <code>{sec}</code>\n"
                    f"   • المسجلين: <b>{status_str}</b>\n"
                    f"   • المدرس: {inst}\n"
                    f"   • الأوقات: {days} ({t_from} - {t_to}) | القاعة: {room}{notes}\n"
                )
            else:
                parts.append(
                    f"{i}. 👁 <b>{name}</b>\n"
                    f"   • المادة: <code>{cid}</code> | الشعبة: <code>{sec}</code>\n"
                )

    parts.append("👇 <i>اضغط على أي زر لإلغاء المراقبة أو التحديث:</i>")
    return "\n".join(parts)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /list to show watched courses and tracked sections with full details."""
    user = update.effective_user
    if not user or not update.message:
        return

    async with async_session() as session:
        db_user = await get_or_create_user(session, user.id)
        subs = await get_user_subscriptions(session, db_user.id, active_only=True)

        if not subs:
            await update.message.reply_text(
                "📭 أنت لا تراقب أو تتتبع أي شعبة حالياً.\n\n"
                "💡 أرسل رقم أي مادة (مثل <code>0209100</code>) أو استخدم الأمر:\n"
                "• <code>/check &lt;رقم_المادة&gt;</code> للاستعراض والمراقبة بنقرة زر!",
                parse_mode=ParseMode.HTML,
            )
            return

        dashboard_text = await format_dashboard_text(session, subs)

    await update.message.reply_text(
        dashboard_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_list_dashboard_keyboard(subs),
    )


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline keyboard button clicks."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    data = query.data or ""
    user = update.effective_user
    if not user:
        return

    if data.startswith("refresh:"):
        parts = data.split(":")
        if len(parts) == 3:
            course_id, section_no = parts[1], parts[2]
            fetcher: MutahFetcher = context.bot_data["fetcher"]
            section = await fetcher.get_section_async(course_id, section_no)
            if section:
                text = format_section_card(section, is_watched=True)
                try:
                    await query.edit_message_text(
                        text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=get_section_keyboard(course_id, section_no),
                    )
                    await query.answer("تم تحديث الحالة اللحظية بنجاح ✅")
                except Exception as e:
                    if "Message is not modified" in str(e):
                        await query.answer("تم الفحص: لا يوجد تغيير في بيانات الشعبة ✅")
                    else:
                        raise
            else:
                await query.answer("تعذر جلب البيانات من بوابة الجامعة حالياً.", show_alert=True)

    elif data.startswith("unwatch:"):
        parts = data.split(":")
        if len(parts) == 3:
            course_id, section_no = parts[1], parts[2]
            await query.edit_message_reply_markup(
                reply_markup=get_unwatch_confirm_keyboard(course_id, section_no)
            )

    elif data.startswith("unwatch_confirm:"):
        parts = data.split(":")
        if len(parts) == 3:
            course_id, section_no = parts[1], parts[2]
            async with async_session() as session:
                db_user = await get_or_create_user(session, user.id)
                await remove_subscription(session, db_user.id, course_id, section_no, sub_type="SEAT")

            await query.edit_message_text(
                f"✅ تم إلغاء مراقبة المقاعد للشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code>.",
                parse_mode=ParseMode.HTML,
            )

    elif data.startswith("untrack:"):
        parts = data.split(":")
        if len(parts) == 3:
            course_id, section_no = parts[1], parts[2]
            await query.edit_message_reply_markup(
                reply_markup=get_untrack_confirm_keyboard(course_id, section_no)
            )

    elif data.startswith("untrack_confirm:"):
        parts = data.split(":")
        if len(parts) == 3:
            course_id, section_no = parts[1], parts[2]
            async with async_session() as session:
                db_user = await get_or_create_user(session, user.id)
                await remove_subscription(session, db_user.id, course_id, section_no, sub_type="CHANGE")

            await query.edit_message_text(
                f"✅ تم إلغاء تتبع التغييرات للشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code>.",
                parse_mode=ParseMode.HTML,
            )

    elif data.startswith("quick_watch:"):
        parts = data.split(":")
        if len(parts) == 3:
            course_id, section_no = parts[1], parts[2]
            fetcher: MutahFetcher = context.bot_data["fetcher"]
            section_info = await fetcher.get_section_async(course_id, section_no)
            if not section_info:
                await query.answer("لم يتم العثور على الشعبة في بوابة الجامعة.", show_alert=True)
                return

            async with async_session() as session:
                db_user = await get_or_create_user(session, user.id, user.username, user.first_name)
                await add_subscription(
                    session=session,
                    user_id=db_user.id,
                    course_id=course_id,
                    section_no=section_no,
                    course_name=section_info.course_name,
                    sub_type="SEAT",
                )
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

            card_text = format_section_card(section_info, is_watched=True, watch_type="SEAT")
            await query.edit_message_text(
                f"🔔 <b>تم تفعيل مراقبة المقاعد الشاغرة بنجاح!</b>\n\n{card_text}",
                parse_mode=ParseMode.HTML,
                reply_markup=get_section_keyboard(course_id, section_no),
            )
            await query.answer("تم تفعيل مراقبة المقعد بنجاح! 🔔")

    elif data.startswith("quick_track:"):
        parts = data.split(":")
        if len(parts) == 3:
            course_id, section_no = parts[1], parts[2]
            fetcher: MutahFetcher = context.bot_data["fetcher"]
            section_info = await fetcher.get_section_async(course_id, section_no)
            if not section_info:
                await query.answer("لم يتم العثور على الشعبة في بوابة الجامعة.", show_alert=True)
                return

            async with async_session() as session:
                db_user = await get_or_create_user(session, user.id, user.username, user.first_name)
                await add_subscription(
                    session=session,
                    user_id=db_user.id,
                    course_id=course_id,
                    section_no=section_no,
                    course_name=section_info.course_name,
                    sub_type="CHANGE",
                )
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

            card_text = format_section_card(section_info, is_watched=True, watch_type="CHANGE")
            await query.edit_message_text(
                f"👁 <b>تم تفعيل تتبع تغييرات الشعبة بنجاح!</b>\n\n{card_text}",
                parse_mode=ParseMode.HTML,
                reply_markup=get_track_keyboard(course_id, section_no),
            )
            await query.answer("تم تفعيل تتبع التغييرات بنجاح! 👁")

    elif data.startswith("details:"):
        parts = data.split(":")
        if len(parts) == 3:
            course_id, section_no = parts[1], parts[2]
            fetcher: MutahFetcher = context.bot_data["fetcher"]
            section = await fetcher.get_section_async(course_id, section_no)
            if section:
                text = format_section_card(section, is_watched=False)
                await query.edit_message_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_quick_sub_keyboard(course_id, section_no, section.is_full),
                )
            else:
                await query.answer("تعذر جلب تفاصيل الشعبة حالياً.", show_alert=True)

    elif data.startswith("refresh_course:"):
        course_id = data.split(":")[1]
        fetcher: MutahFetcher = context.bot_data["fetcher"]
        sections = await fetcher.search_course_async(course_id)
        if sections:
            course_name_esc = html.escape(sections[0].course_name)
            header = (
                f"📚 <b>شُعب مادة:</b> {course_name_esc} (<code>{html.escape(course_id)}</code>)\n"
                f"📊 عدد الشُعب الكلي: <b>{len(sections)}</b>\n\n"
                "اضغط على أي زر أدناه للاشتراك الفوري أو استعراض التفاصيل:\n"
                "• 🔔 <b>راقب:</b> للشعب الممتلئة (تنبيه فوري عند توفر مقعد)\n"
                "• 👁 <b>تتبع:</b> للشعب المتاحة (تنبيه عند أي تعديل)\n"
            )
            try:
                await query.edit_message_text(
                    header,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_course_sections_keyboard(course_id, sections),
                )
                await query.answer("تم تحديث قائمة الشُعب بنجاح ✅")
            except Exception as e:
                if "Message is not modified" in str(e):
                    await query.answer("تم الفحص: لا يوجد أي تغيير في شُعب المادة ✅")
                else:
                    raise
        else:
            await query.answer("تعذر جلب شُعب المادة حالياً.", show_alert=True)

    elif data == "refresh_list":
        async with async_session() as session:
            db_user = await get_or_create_user(session, user.id)
            subs = await get_user_subscriptions(session, db_user.id, active_only=True)

            if not subs:
                await query.edit_message_text(
                    "📭 أنت لا تراقب أو تتتبع أي شعبة حالياً.\n\n"
                    "💡 أرسل رقم أي مادة (مثل <code>0209100</code>) للاستعراض والمراقبة بنقرة زر!",
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_main_menu_keyboard(),
                )
                return

            dashboard_text = await format_dashboard_text(session, subs)

        try:
            await query.edit_message_text(
                dashboard_text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_list_dashboard_keyboard(subs),
            )
            await query.answer("تم تحديث القائمة بنجاح ✅")
        except Exception as e:
            if "Message is not modified" in str(e):
                await query.answer("القائمة محدثة بالفعل ✅")
            else:
                raise

    elif data == "show_list":
        async with async_session() as session:
            db_user = await get_or_create_user(session, user.id)
            subs = await get_user_subscriptions(session, db_user.id, active_only=True)

            if not subs:
                await query.edit_message_text(
                    "📭 أنت لا تراقب أو تتتبع أي شعبة حالياً.\n\n"
                    "💡 أرسل رقم أي مادة (مثل <code>0209100</code>) للاستعراض والمراقبة بنقرة زر!",
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_main_menu_keyboard(),
                )
                return

            dashboard_text = await format_dashboard_text(session, subs)

        await query.edit_message_text(
            dashboard_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_list_dashboard_keyboard(subs),
        )

    elif data == "show_help":
        help_text = (
            "📖 <b>طريقة استخدام البوت السريعة</b> 💡\n\n"
            "✨ <b>لا داعي لكتابة أوامر يدوية بعد الآن!</b>\n"
            "1. اكتب فقط <b>رقم أي مادة</b> بالإنجليزية (مثال: <code>0209100</code>).\n"
            "2. ستظهر لك قائمة شُعب المادة كأزرار ملونة:\n"
            "   - 🔴 شعبة ممتلئة ⬅️ اضغط زر <b>🔔 راقب</b> لتنبيهك عند فتح مقعد.\n"
            "   - 🟢 شعبة متاحة ⬅️ اضغط زر <b>👁 تتبع</b> لتنبيهك عند أي تعديل بالبيانات.\n\n"
            "📋 <b>لوحة التحكم:</b>\n"
            "اضغط زر «شُعبي المراقبة» لمعاينة وإلغاء مراقبة أي شعبة بضغطة زر واحدة."
        )
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(),
        )

    elif data == "admin_panel" or data == "admin_stats":
        if not ADMIN_TELEGRAM_ID or user.id != ADMIN_TELEGRAM_ID:
            await query.answer("⛔️ عذراً، هذه اللوحة مخصصة للأدمن فقط.", show_alert=True)
            return

        async with async_session() as session:
            stats = await get_admin_stats(session)

        text = (
            "👑 <b>لوحة تحكم الأدمن — إحصائيات قاعدة البيانات</b> 📊\n\n"
            f"👥 <b>إجمالي المستخدمين المسجلين:</b> <code>{stats['total_users']}</code>\n"
            f"📌 <b>إجمالي الاشتراكات النشطة:</b> <code>{stats['active_subs']}</code>\n"
            f"   • 🔔 مراقبة المقاعد: <code>{stats['seat_subs']}</code>\n"
            f"   • 👁 تتبع التغييرات: <code>{stats['change_subs']}</code>\n"
            f"🔍 <b>عدد الشُعب الفريدة قيد المراقبة:</b> <code>{stats['unique_sections']}</code>\n"
            f"📢 <b>إجمالي الإشعارات المرسلة:</b> <code>{stats['total_notifications']}</code>\n\n"
            f"⏱ <i>تم التحديث: {datetime.now().strftime('%I:%M:%S %p')}</i>"
        )
        try:
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_admin_dashboard_keyboard(),
            )
            await query.answer("تم تحديث إحصائيات الأدمن بنجاح ✅")
        except Exception as e:
            if "Message is not modified" in str(e):
                await query.answer("الإحصائيات محدثة بالفعل ✅")
            else:
                raise

    elif data == "admin_users":
        if not ADMIN_TELEGRAM_ID or user.id != ADMIN_TELEGRAM_ID:
            await query.answer("⛔️ عذراً، هذه اللوحة مخصصة للأدمن فقط.", show_alert=True)
            return

        async with async_session() as session:
            users_list = await get_all_users_with_subs(session, limit=40)

        if not users_list:
            await query.answer("لا يوجد مستخدمين مسجلين بعد.", show_alert=True)
            return

        lines = [f"👥 <b>قائمة الطلاب والمستخدمين المسجلين في البوت ({len(users_list)}):</b>\n"]
        for i, (u, subs_cnt) in enumerate(users_list, 1):
            name = html.escape(u.first_name or "بدون اسم")
            uname = f"@{html.escape(u.username)}" if u.username else "بدون يوزرنيم"
            lines.append(
                f"{i}. <b>{name}</b> ({uname})\n"
                f"   • آيدي تيليجرام: <code>{u.telegram_id}</code> | شُعب يراقبها: <b>{subs_cnt}</b>"
            )

        text = "\n".join(lines)
        if len(text) > 4000:
            text = text[:3900] + "\n... (تم اختصار القائمة لتناسب الحجم)"

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_dashboard_keyboard(),
        )

    elif data == "admin_back":
        is_admin = bool(ADMIN_TELEGRAM_ID and user.id == ADMIN_TELEGRAM_ID)
        welcome_text = (
            "مرحباً بك مجدداً في <b>بوت مراقبة وتتبع مواد جامعة مؤتة</b> 🎓✨\n\n"
            "فقط أرسل <b>رقم المادة</b> مباشرة هنا (مثال: <code>0209100</code>) للاستعراض والمراقبة بنقرة زر!"
        )
        await query.edit_message_text(
            welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(is_admin=is_admin),
        )

    elif data == "cancel":
        await query.edit_message_text("تم الإلغاء.", parse_mode=ParseMode.HTML)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /admin command strictly for ADMIN_TELEGRAM_ID."""
    user = update.effective_user
    if not user:
        return

    # Check admin ID
    if not ADMIN_TELEGRAM_ID or int(user.id) != int(ADMIN_TELEGRAM_ID):
        if update.message:
            await update.message.reply_text(
                f"⛔️ هذا الأمر مخصص لمدير البوت فقط.\n(معرف حسابك: <code>{user.id}</code>)",
                parse_mode=ParseMode.HTML,
            )
        return

    async with async_session() as session:
        stats = await get_admin_stats(session)

    text = (
        "👑 <b>أهلاً بك يا مدير النظام في لوحة تحكم الأدمن</b> 📊\n\n"
        f"👥 <b>إجمالي الطلاب المسجلين:</b> <code>{stats['total_users']}</code>\n"
        f"📌 <b>إجمالي الاشتراكات النشطة:</b> <code>{stats['active_subs']}</code>\n"
        f"   • 🔔 مراقبة المقاعد: <code>{stats['seat_subs']}</code>\n"
        f"   • 👁 تتبع التغييرات: <code>{stats['change_subs']}</code>\n"
        f"🔍 <b>شُعب فريدة قيد المراقبة الآن:</b> <code>{stats['unique_sections']}</code>\n"
        f"📢 <b>إشعارات مرسلة:</b> <code>{stats['total_notifications']}</code>\n"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_dashboard_keyboard(),
    )



async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles regular text messages. If user types a course ID directly (e.g., 0209100 or 209100),
    automatically fetch and display all sections with interactive buttons!
    Also ensures the user profile is stored in the database.
    """
    user = update.effective_user
    if not user or not update.message or not update.message.text:
        return

    # Automatically record/update any user interacting with the bot
    try:
        async with async_session() as session:
            await get_or_create_user(
                session=session,
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
            )
    except Exception as e:
        logger.error(f"Error recording user: {e}")

    text = update.message.text.strip()
    # Check if text looks like a course ID (5 to 10 digits)
    if text.isdigit() and len(text) in range(5, 12):
        course_id = text
        fetcher: MutahFetcher = context.bot_data["fetcher"]
        status_msg = await update.message.reply_text(
            f"🔍 جاري البحث عن شُعب المادة <code>{html.escape(course_id)}</code> من بوابة الجامعة...",
            parse_mode=ParseMode.HTML,
        )

        sections = await fetcher.search_course_async(course_id)
        if not sections:
            await status_msg.edit_text(
                f"❌ لم يتم العثور على أي شعبة للمادة <code>{html.escape(course_id)}</code>.\n"
                "يرجى التأكد من كتابة رقم المادة بشكل صحيح كما في الخطة الدراسية.",
                parse_mode=ParseMode.HTML,
            )
            return

        course_name_esc = html.escape(sections[0].course_name)
        header = (
            f"📚 <b>شُعب مادة:</b> {course_name_esc} (<code>{html.escape(course_id)}</code>)\n"
            f"📊 عدد الشُعب الكلي: <b>{len(sections)}</b>\n\n"
            "اضغط على أي زر أدناه للاشتراك الفوري أو استعراض التفاصيل:\n"
            "• 🔔 <b>راقب:</b> للشعب الممتلئة (تنبيه فوري عند توفر مقعد)\n"
            "• 👁 <b>تتبع:</b> للشعب المتاحة (تنبيه عند أي تعديل)\n"
        )
        await status_msg.edit_text(
            header,
            parse_mode=ParseMode.HTML,
            reply_markup=get_course_sections_keyboard(course_id, sections),
        )

