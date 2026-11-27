from telegram import KeyboardButton, ReplyKeyboardMarkup
from config import settings
from services.i18n import i18n


def get_main_menu_keyboard(
    lang: str,
    user_id: int | None = None,
    is_admin_override: bool | None = None,
) -> ReplyKeyboardMarkup:
    rows = [
        [
            KeyboardButton(i18n.t("menu_daily_lesson", lang=lang)),
            KeyboardButton(i18n.t("menu_start_quiz", lang=lang)),
        ],
        [
            KeyboardButton(i18n.t("menu_mock_test", lang=lang)),
            KeyboardButton(i18n.t("menu_referral", lang=lang)),
        ],
        [
            KeyboardButton(i18n.t("menu_leaderboard", lang=lang)),
            KeyboardButton(i18n.t("menu_statistics", lang=lang)),
        ],
        [
            KeyboardButton(i18n.t("menu_learned_words", lang=lang)),
            KeyboardButton(i18n.t("menu_settings", lang=lang)),
        ],
    ]
    show_admin = False
    if is_admin_override is not None:
        show_admin = is_admin_override
    elif user_id is not None and settings.is_admin(user_id):
        show_admin = True

    if show_admin:
        rows[-1].append(KeyboardButton(i18n.t("menu_admin", lang=lang)))

    return ReplyKeyboardMarkup(rows, resize_keyboard=True)
