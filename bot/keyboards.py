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
    """Keyboard for a single section status display."""
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
            InlineKeyboardButton("🌐 بوابة جريدة المواد", url=PORTAL_URL),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_unwatch_confirm_keyboard(course_id: str, section_no: str) -> InlineKeyboardMarkup:
    """Keyboard to confirm removal of a subscription."""
    keyboard = [
        [
            InlineKeyboardButton(
                "نعم، إلغاء المراقبة",
                callback_data=f"unwatch_confirm:{course_id}:{section_no}",
            ),
            InlineKeyboardButton("تراجع", callback_data="cancel"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
