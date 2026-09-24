from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import PORTAL_URL


def get_alert_keyboard(course_id: str, section_no: str) -> InlineKeyboardMarkup:
    """Keyboard attached to the urgent seat alert."""
    keyboard = [
        [
            InlineKeyboardButton("🌐 فتح بوابة التسجيل", url=PORTAL_URL),
        ],
        [
            InlineKeyboardButton(
                "❌ إلغاء مراقبة هذه الشعبة",
                callback_data=f"unwatch:{course_id}:{section_no}",
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_section_keyboard(course_id: str, section_no: str) -> InlineKeyboardMarkup:
    """Keyboard for a single section status display for seat watching."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🔄 فحص فوري للحالة",
                callback_data=f"refresh:{course_id}:{section_no}",
            ),
            InlineKeyboardButton(
                "❌ إلغاء المراقبة",
                callback_data=f"unwatch:{course_id}:{section_no}",
            ),
        ],
        [
            InlineKeyboardButton("🔙 رجوع لشُعب المادة", callback_data=f"refresh_course:{course_id}"),
            InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"),
        ],
        [
            InlineKeyboardButton("🌐 بوابة جريدة المواد", url=PORTAL_URL),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_track_keyboard(course_id: str, section_no: str) -> InlineKeyboardMarkup:
    """Keyboard for a section tracked for changes."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🔄 فحص فوري للحالة",
                callback_data=f"refresh:{course_id}:{section_no}",
            ),
            InlineKeyboardButton(
                "❌ إلغاء التتبع",
                callback_data=f"untrack:{course_id}:{section_no}",
            ),
        ],
        [
            InlineKeyboardButton("🔙 رجوع لشُعب المادة", callback_data=f"refresh_course:{course_id}"),
            InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"),
        ],
        [
            InlineKeyboardButton("🌐 بوابة جريدة المواد", url=PORTAL_URL),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_unwatch_confirm_keyboard(course_id: str, section_no: str) -> InlineKeyboardMarkup:
    """Keyboard to confirm removal of a seat subscription."""
    keyboard = [
        [
            InlineKeyboardButton(
                "نعم، إلغاء المراقبة",
                callback_data=f"unwatch_confirm:{course_id}:{section_no}",
            ),
            InlineKeyboardButton("🔙 تراجع ورجوع", callback_data="show_list"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_untrack_confirm_keyboard(course_id: str, section_no: str) -> InlineKeyboardMarkup:
    """Keyboard to confirm removal of a change tracking subscription."""
    keyboard = [
        [
            InlineKeyboardButton(
                "نعم، إلغاء التتبع",
                callback_data=f"untrack_confirm:{course_id}:{section_no}",
            ),
            InlineKeyboardButton("🔙 تراجع ورجوع", callback_data="show_list"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_course_sections_keyboard(course_id: str, sections: list) -> InlineKeyboardMarkup:
    """Generates interactive buttons for all sections of a course."""
    keyboard = []
    for s in sections:
        sec_no = str(s.section)
        avail = s.available_seats
        if s.is_full:
            label = f"🔴 شعبة {sec_no} (ممتلئة) 🔔 راقب"
            cb = f"quick_watch:{course_id}:{sec_no}"
        else:
            label = f"🟢 شعبة {sec_no} (متاح {avail}) 👁 تتبع"
            cb = f"quick_track:{course_id}:{sec_no}"

        details_btn = InlineKeyboardButton("📋 تفاصيل", callback_data=f"details:{course_id}:{sec_no}")
        action_btn = InlineKeyboardButton(label, callback_data=cb)
        keyboard.append([action_btn, details_btn])

    keyboard.append([
        InlineKeyboardButton("🔄 تحديث الكل", callback_data=f"refresh_course:{course_id}"),
        InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"),
    ])
    keyboard.append([
        InlineKeyboardButton("🌐 بوابة التسجيل", url=PORTAL_URL),
    ])
    return InlineKeyboardMarkup(keyboard)


def get_quick_sub_keyboard(course_id: str, section_no: str, is_full: bool) -> InlineKeyboardMarkup:
    """Generates options when viewing a single section details."""
    keyboard = [
        [
            InlineKeyboardButton("🔔 مراقبة مقعد", callback_data=f"quick_watch:{course_id}:{section_no}"),
            InlineKeyboardButton("👁 تتبع التغييرات", callback_data=f"quick_track:{course_id}:{section_no}"),
        ],
        [
            InlineKeyboardButton("🔄 تحديث", callback_data=f"refresh:{course_id}:{section_no}"),
            InlineKeyboardButton("🔙 رجوع للشُعب", callback_data=f"refresh_course:{course_id}"),
        ],
        [
            InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_list_dashboard_keyboard(subs: list) -> InlineKeyboardMarkup:
    """Generates inline cancel buttons for subscriptions list."""
    keyboard = []
    for sub in subs[:15]:  # limit to top 15 buttons to fit Telegram limits
        sub_type_icon = "🔔" if sub.sub_type == "SEAT" else "👁"
        btn_label = f"❌ إلغاء {sub_type_icon} {sub.course_id} ش({sub.section_no})"
        cb = f"unwatch_confirm:{sub.course_id}:{sub.section_no}" if sub.sub_type == "SEAT" else f"untrack_confirm:{sub.course_id}:{sub.section_no}"
        keyboard.append([InlineKeyboardButton(btn_label, callback_data=cb)])

    keyboard.append([
        InlineKeyboardButton("🔄 تحديث القائمة", callback_data="refresh_list"),
        InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"),
    ])
    keyboard.append([
        InlineKeyboardButton("🌐 بوابة الجامعة", url=PORTAL_URL),
    ])
    return InlineKeyboardMarkup(keyboard)


def get_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Main menu keyboard shown with /start and /help."""
    keyboard = [
        [
            InlineKeyboardButton("📋 شُعبي المراقبة (لوحة التحكم)", callback_data="show_list"),
        ],
        [
            InlineKeyboardButton("📖 طريقة الاستخدام", callback_data="show_help"),
            InlineKeyboardButton("🌐 بوابة التسجيل", url=PORTAL_URL),
        ],
    ]
    if is_admin:
        keyboard.append([
            InlineKeyboardButton("👑 لوحة تحكم الأدمن (قاعدة البيانات)", callback_data="admin_panel"),
        ])
    return InlineKeyboardMarkup(keyboard)


def get_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for Admin Control Panel."""
    keyboard = [
        [
            InlineKeyboardButton("👥 عرض الطلاب المسجلين", callback_data="admin_users"),
            InlineKeyboardButton("📊 إحصائيات عامة", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="admin_panel"),
            InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)






