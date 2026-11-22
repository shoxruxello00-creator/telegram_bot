import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from database import crud
from database.db import get_session
from keyboards.inline import (
    get_lesson_card_keyboard,
    get_memorized_only_keyboard,
    get_start_quiz_keyboard,
)
from services.i18n import i18n
from services.lesson_service import ensure_daily_lesson


async def show_daily_lesson(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Display today's 10 new C1–C2 expressions in the user's selected language.
    """
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    today = settings.today()

    async with get_session() as session:
        _, user_settings, _ = await crud.get_or_create_user(
            session=session,
            user_id=user_id,
            username=update.effective_user.username,
            full_name=update.effective_user.full_name or "Learner",
        )
        lang = user_settings.language_code

        words, _ = await ensure_daily_lesson(
            session=session,
            target_date=today,
            bot=context.bot,
        )

    if not words:
        target_msg = update.message or (
            update.callback_query.message if update.callback_query else None
        )
        if target_msg:
            await target_msg.reply_text(
                text=i18n.t("lesson_not_ready", lang=lang),
                parse_mode="HTML",
            )
        return

    card_text = i18n.format_word_card(
        vocab=words[0],
        lang=lang,
        index=1,
        total=len(words),
        lesson_date=str(today),
    )
    kb = get_lesson_card_keyboard(lang=lang, current_index=0, total=len(words))

    if update.message:
        await update.message.reply_text(
            text=card_text,
            parse_mode="HTML",
            reply_markup=kb,
        )
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            text=card_text,
            parse_mode="HTML",
            reply_markup=kb,
        )


async def lesson_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle inline callbacks for daily lesson:
    - `lesson:page:<index>`: Navigate between cards 1..10
    - `lesson:open:<index>`: Open lesson card in a new message
    - `lesson:send_all`: Send all 10 words as separate messages followed by ✅ YODLADIM button
    - `lesson:memorized`: Mark today's 10 words as memorized and unlock the 10-question quiz
    - `lesson:noop`: Page indicator button
    """
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    data = query.data
    if data == "lesson:noop":
        await query.answer()
        return

    user_id = update.effective_user.id
    today = settings.today()

    async with get_session() as session:
        lang = await crud.get_user_language(session, user_id)

        if data == "lesson:memorized":
            progress = await crud.mark_lesson_memorized(session, user_id, today)
            await query.answer(i18n.t("btn_memorized", lang=lang))

            if progress.is_completed:
                text = i18n.t(
                    "quiz_already_completed",
                    lang=lang,
                    score=progress.score,
                    total=settings.DAILY_WORD_COUNT,
                    earned_xp=progress.earned_xp,
                )
                kb = get_start_quiz_keyboard(lang=lang, practice=True)
            else:
                text = i18n.t(
                    "memorized_confirmed",
                    lang=lang,
                    time_limit=settings.QUIZ_TIME_LIMIT,
                    points=settings.POINTS_PER_CORRECT_ANSWER,
                )
                kb = get_start_quiz_keyboard(lang=lang, practice=False)

            if query.message:
                await query.message.reply_text(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
            return

        words, _ = await ensure_daily_lesson(
            session=session,
            target_date=today,
            bot=context.bot,
        )

    if not words:
        await query.answer(i18n.t("lesson_not_ready", lang=lang), show_alert=True)
        return

    if data.startswith("lesson:page:") or data.startswith("lesson:open:"):
        await query.answer()
        parts = data.split(":")
        idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        idx = max(0, min(idx, len(words) - 1))

        card_text = i18n.format_word_card(
            vocab=words[idx],
            lang=lang,
            index=idx + 1,
            total=len(words),
            lesson_date=str(today),
        )
        kb = get_lesson_card_keyboard(
            lang=lang, current_index=idx, total=len(words)
        )
        if data.startswith("lesson:page:"):
            await query.edit_message_text(
                text=card_text,
                parse_mode="HTML",
                reply_markup=kb,
            )
        elif query.message:
            await query.message.reply_text(
                text=card_text,
                parse_mode="HTML",
                reply_markup=kb,
            )
        return

    if data == "lesson:send_all":
        await query.answer()
        if not query.message:
            return
        chat_id = query.message.chat_id
        total = len(words)
        for idx, vocab in enumerate(words, start=1):
            card_text = i18n.format_word_card(
                vocab=vocab,
                lang=lang,
                index=idx,
                total=total,
                lesson_date=str(today),
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=card_text,
                parse_mode="HTML",
            )
            await asyncio.sleep(0.08)

        footer_text = i18n.t("all_words_sent_footer", lang=lang)
        await context.bot.send_message(
            chat_id=chat_id,
            text=footer_text,
            parse_mode="HTML",
            reply_markup=get_memorized_only_keyboard(lang=lang),
        )
