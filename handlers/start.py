import html
import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import SUPPORTED_LANGUAGES
from database import crud
from database.db import get_session
from keyboards.inline import get_language_selection_keyboard
from keyboards.reply import get_main_menu_keyboard
from services.i18n import i18n

logger = logging.getLogger(__name__)


def _parse_referrer_id(args: list[str] | None) -> int | None:
    if not args:
        return None
    raw = args[0].strip()
    if raw.startswith("ref_"):
        id_part = raw[4:].strip()
        if id_part.isdigit():
            return int(id_part)
    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start [ref_USER_ID]
    1. Register or update user in PostgreSQL.
    2. If new user joined via `ref_USER_ID`, create a `pending` referral and notify referrer.
    3. Display language selection screen.
    """
    if not update.effective_user or not update.message:
        return

    tg_user = update.effective_user
    full_name = tg_user.full_name or tg_user.first_name or "Learner"
    referrer_id = _parse_referrer_id(context.args)

    notify_referrer_id: int | None = None
    referrer_lang = "uz"

    async with get_session() as session:
        _, _, is_new = await crud.get_or_create_user(
            session=session,
            user_id=tg_user.id,
            username=tg_user.username,
            full_name=full_name,
        )

        if referrer_id is not None:
            referral_obj, status_code = await crud.register_pending_referral(
                session=session,
                referrer_user_id=referrer_id,
                referred_user_id=tg_user.id,
                is_new_user=is_new,
            )
            if referral_obj is not None and status_code == "CREATED":
                notify_referrer_id = referrer_id
                referrer_lang = await crud.get_user_language(session, referrer_id)

    if notify_referrer_id is not None:
        try:
            await context.bot.send_message(
                chat_id=notify_referrer_id,
                text=i18n.t("referral_joined_notification", lang=referrer_lang),
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning(
                "Could not notify referrer %s about new pending referral: %s",
                notify_referrer_id,
                exc,
            )

    await update.message.reply_text(
        text="🌍 Choose your language / Tilni tanlang / Выберите язык",
        reply_markup=get_language_selection_keyboard(prefix="set_lang"),
    )


async def language_selection_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Callback for `set_lang:(uz|ru|en)` — Saves chosen language in PostgreSQL
    while preserving all learned words, XP, streak, and statistics.
    """
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    await query.answer()
    tg_user = update.effective_user
    parts = query.data.split(":")
    lang_code = parts[1].lower() if len(parts) > 1 else "uz"
    if lang_code not in SUPPORTED_LANGUAGES:
        lang_code = "uz"

    full_name = tg_user.full_name or tg_user.first_name or "Learner"

    async with get_session() as session:
        await crud.get_or_create_user(
            session=session,
            user_id=tg_user.id,
            username=tg_user.username,
            full_name=full_name,
            default_lang=lang_code,
        )
        await crud.set_user_language(
            session=session,
            user_id=tg_user.id,
            language_code=lang_code,
        )
        is_admin = await crud.is_any_admin(session, tg_user.id)

    await query.edit_message_text(
        text=i18n.t("language_updated", lang=lang_code),
        parse_mode="HTML",
    )

    welcome_text = i18n.t(
        "welcome_message",
        lang=lang_code,
        name=html.escape(full_name),
    )
    main_kb = get_main_menu_keyboard(
        lang=lang_code,
        user_id=tg_user.id,
        is_admin_override=is_admin,
    )

    if query.message:
        await query.message.reply_text(
            text=welcome_text,
            parse_mode="HTML",
            reply_markup=main_kb,
        )
