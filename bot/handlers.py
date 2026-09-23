import html
import logging
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from fetcher.mutah import MutahFetcher, SectionInfo
from db.database import async_session
from db.crud import (
    get_or_create_user,
    add_subscription,
    remove_subscription,
    get_user_subscriptions,
    get_section_cache,
    update_section_cache,
)
from bot.keyboards import (
    get_section_keyboard,
    get_unwatch_confirm_keyboard,
)

logger = logging.getLogger(__name__)


def format_section_card(section: SectionInfo, is_watched: bool = False) -> str:
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
        lines.append("🔔 <b>حالة المراقبة:</b> مفعلة (ستصلك رسالة فور توفر مقعد)")

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
    welcome_text = (
        f"مرحباً بك يا <b>{user_name}</b> في <b>بوت مراقبة مواد جامعة مؤتة</b> 🎓\n\n"
        "هذا البوت يساعدك على مراقبة الشُعب الدراسية المغلقة، وإشعارك في اللحظة التي يتوفر فيها أي مقعد شاغر فوراً! ⚡️\n\n"
        "📋 <b>الأوامر المتاحة:</b>\n"
        "• <code>/watch &lt;رقم_المادة&gt; &lt;الشعبة&gt;</code> - بدء مراقبة شعبة (مثال: <code>/watch 0209100 1</code>)\n"
        "• <code>/unwatch &lt;رقم_المادة&gt; &lt;الشعبة&gt;</code> - إلغاء مراقبة شعبة\n"
        "• <code>/check &lt;رقم_المادة&gt; [الشعبة]</code> - فحص فوري لحالة مادة أو شعبة\n"
        "• <code>/list</code> - عرض الشعب التي تراقبها حالياً\n"
        "• <code>/help</code> - عرض شرح استخدام البوت بالتفصيل\n\n"
        "💡 <b>ابدأ الآن بإرسال:</b> <code>/watch 0209100 1</code>"
    )

    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /help command."""
    help_text = (
        "📖 <b>دليل استخدام بوت مراقبة مقاعد جامعة مؤتة</b>\n\n"
        "1️⃣ <b>كيف أراقب شعبة ممتلئة؟</b>\n"
        "اكتب الأمر <code>/watch</code> متبوعاً برقم المادة ثم رقم الشعبة:\n"
        "<code>/watch 0209100 1</code>\n"
        "يقوم البوت بالتحقق من الشعبة فوراً وتفعيل المراقبة الآلية في الخلفية.\n\n"
        "2️⃣ <b>كيف يتم الإشعار؟</b>\n"
        "يقوم النظام بفحص بوابة التسجيل دورياً، وفور إلغاء تسجيل أي طالب أو زيادة السعة، "
        "ستصلك رسالة تنبيه عاجلة برابط البوابة لحجز المقعد مباشرة.\n\n"
        "3️⃣ <b>كيف أفحص مادة دون مراقبتها؟</b>\n"
        "استخدم الأمر <code>/check</code>:\n"
        "• <code>/check 0209100 1</code> (لفحص شعبة معينة)\n"
        "• <code>/check 0209100</code> (لعرض كافة شُعب المادة)\n\n"
        "4️⃣ <b>إلغاء المراقبة:</b>\n"
        "<code>/unwatch 0209100 1</code> أو عبر الضغط على زر الإلغاء في قائمة <code>/list</code>."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /watch <course_id> <section_no>."""
    user = update.effective_user
    if not user or not update.message:
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ <b>صيغة الأمر غير صحيحة.</b>\n"
            "الاستخدام الصحيح:\n"
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

        sub, created = await add_subscription(
            session=session,
            user_id=db_user.id,
            course_id=course_id,
            section_no=section_no,
            course_name=section_info.course_name,
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
        )

    card_text = format_section_card(section_info, is_watched=True)

    if section_info.available_seats > 0:
        reply_text = (
            "🟢 <b>تنبيه: يوجد مقاعد متاحة بالفعل الآن!</b>\n\n"
            f"{card_text}\n\n"
            "⚡️ سارع بالتسجيل الآن قبل اكتمال السعة! تم حفظ المراقبة في حال أُغلقت لاحقاً."
        )
    else:
        reply_text = (
            "✅ <b>تمت إضافة المراقبة بنجاح!</b>\n\n"
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
        removed = await remove_subscription(session, db_user.id, course_id, section_no)

    if removed:
        await update.message.reply_text(
            f"✅ تم إلغاء مراقبة الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> بنجاح.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"ℹ️ أنت لا تراقب الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code> حالياً.",
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
            f"📚 <b>نتائج الاستعلام للمادة:</b> {course_name_esc} (<code>{html.escape(course_id)}</code>)\n"
            f"عدد الشُعب: <b>{len(sections)}</b>\n\n"
        )
        body = []
        for s in sections:
            status_ico = "🔴" if s.is_full else "🟢"
            avail = f"متاح {s.available_seats}" if s.available_seats > 0 else "ممتلئة"
            inst = html.escape(s.instructor or "بدون مدرس")
            d = html.escape(s.days or "-")
            body.append(
                f"{status_ico} <b>شعبة {html.escape(s.section)}</b> | {avail} ({s.enrolled}/{s.capacity}) | {inst} | {d}"
            )

        full_text = header + "\n".join(body) + f"\n\n💡 لمراقبة أي شعبة: <code>/watch {html.escape(course_id)} &lt;الشعبة&gt;</code>"
        await status_msg.edit_text(full_text, parse_mode=ParseMode.HTML)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /list to show all watched courses."""
    user = update.effective_user
    if not user or not update.message:
        return

    async with async_session() as session:
        db_user = await get_or_create_user(session, user.id)
        subs = await get_user_subscriptions(session, db_user.id, active_only=True)

    if not subs:
        await update.message.reply_text(
            "📭 أنت لا تراقب أي شعبة حالياً.\n\n"
            "لبدء مراقبة شعبة جديدة، أرسل:\n"
            "<code>/watch &lt;رقم_المادة&gt; &lt;رقم_الشعبة&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    text = f"📋 <b>قائمة الشُعب التي تراقبها حالياً ({len(subs)}):</b>\n\n"
    for i, sub in enumerate(subs, 1):
        name = html.escape(sub.course_name or "مادة")
        cid = html.escape(sub.course_id)
        sec = html.escape(sub.section_no)
        text += (
            f"{i}. <b>{name}</b>\n"
            f"   • رقم المادة: <code>{cid}</code>\n"
            f"   • الشعبة: <code>{sec}</code>\n"
            f"   • لإلغاء المراقبة: <code>/unwatch {cid} {sec}</code>\n\n"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


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
                await remove_subscription(session, db_user.id, course_id, section_no)

            await query.edit_message_text(
                f"✅ تم إلغاء مراقبة الشعبة <code>{html.escape(section_no)}</code> للمادة <code>{html.escape(course_id)}</code>.",
                parse_mode=ParseMode.HTML,
            )

    elif data == "cancel":
        await query.edit_message_text("تم الإلغاء.", parse_mode=ParseMode.HTML)
