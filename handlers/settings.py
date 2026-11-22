from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from database import crud
from database.db import get_session
from keyboards.inline import get_language_selection_keyboard, get_settings_keyboard
from services.i18n import i18n


def _format_settings_text(
    lang: str, reminders_enabled: bool, broadcast_enabled: bool = True
) -> str:
    rem_status = (
        i18n.t("reminders_on", lang=lang)
        if reminders_enabled
        else i18n.t("reminders_off", lang=lang)
    )
    bcast_status = (
        i18n.t("reminders_on", lang=lang)
        if broadcast_enabled
        else i18n.t("reminders_off", lang=lang)
    )
    return i18n.t(
        "settings_title",
        lang=lang,
        reminders_status=rem_status,
        broadcast_status=bcast_status,
        timezone=settings.TIMEZONE,
    )


async def show_settings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.effective_user or not update.message:
        return

    tg_user = update.effective_user

    async with get_session() as session:
        _, user_settings, _ = await crud.get_or_create_user(
            session=session,
            user_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name or "Learner",
        )

    lang = user_settings.language_code
    bcast_on = getattr(user_settings, "broadcast_enabled", True)
    text = _format_settings_text(
        lang, user_settings.reminders_enabled, bcast_on
    )
    kb = get_settings_keyboard(
        lang, user_settings.reminders_enabled, bcast_on
    )
    await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=kb)


async def settings_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    user_id = update.effective_user.id
    data = query.data

    if data == "settings:change_lang":
        await query.answer()
        await query.edit_message_text(
            text="🌍 Choose your language / Tilni tanlang / Выберите язык",
            reply_markup=get_language_selection_keyboard(prefix="set_lang"),
        )
        return

    if data == "settings:toggle_reminders":
        async with get_session() as session:
            user_settings = await crud.toggle_user_reminders(session, user_id)

        lang = user_settings.language_code
        toast = (
            i18n.t("reminders_toggled_on", lang=lang)
            if user_settings.reminders_enabled
            else i18n.t("reminders_toggled_off", lang=lang)
        )
        await query.answer(toast, show_alert=False)

        bcast_on = getattr(user_settings, "broadcast_enabled", True)
        text = _format_settings_text(
            lang, user_settings.reminders_enabled, bcast_on
        )
        kb = get_settings_keyboard(
            lang, user_settings.reminders_enabled, bcast_on
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        return

    if data == "settings:toggle_broadcast":
        async with get_session() as session:
            user_settings = await crud.toggle_user_broadcast(session, user_id)

        lang = user_settings.language_code
        bcast_on = getattr(user_settings, "broadcast_enabled", True)
        toast = (
            i18n.t("broadcast_toggled_on", lang=lang)
            if bcast_on
            else i18n.t("broadcast_toggled_off", lang=lang)
        )
        await query.answer(toast, show_alert=False)

        text = _format_settings_text(
            lang, user_settings.reminders_enabled, bcast_on
        )
        kb = get_settings_keyboard(
            lang, user_settings.reminders_enabled, bcast_on
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        return
