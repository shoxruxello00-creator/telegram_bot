import html
import math
from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from database import crud
from database.db import get_session
from keyboards.inline import get_learned_words_pagination_keyboard
from services.i18n import i18n


async def show_statistics(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Display user's personal XP, Streak, Best Streak, Learned Words, Quiz Accuracy,
    and Today's Lesson status in their selected language.
    """
    if not update.effective_user or not update.message:
        return

    tg_user = update.effective_user
    today = settings.today()

    async with get_session() as session:
        user, user_settings, _ = await crud.get_or_create_user(
            session=session,
            user_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name or "Learner",
        )
        lang = user_settings.language_code
        learned_count = await crud.get_user_learned_count(session, tg_user.id)
        progress = await crud.get_or_create_daily_progress(session, tg_user.id, today)
        user_badge = await crud.get_user_badge(session, tg_user.id)

    accuracy = (
        round((user.total_correct / user.total_questions) * 100, 1)
        if user.total_questions > 0
        else 0.0
    )

    if progress.is_completed:
        today_status = i18n.t("today_status_done", lang=lang, score=progress.score)
    elif progress.is_memorized:
        today_status = i18n.t("today_status_memorized", lang=lang)
    else:
        today_status = i18n.t("today_status_pending", lang=lang)

    badge_str = f"[{html.escape(user_badge)}]" if user_badge else ""

    text = i18n.t(
        "stats_message",
        lang=lang,
        name=html.escape(user.full_name),
        badge=badge_str,
        xp=user.xp,
        streak=user.streak,
        best_streak=user.best_streak,
        learned_count=learned_count,
        total_quizzes=user.total_quizzes,
        accuracy=accuracy,
        total_correct=user.total_correct,
        total_questions=user.total_questions,
        today_status=today_status,
    )

    await update.message.reply_text(text=text, parse_mode="HTML")


async def show_leaderboard(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Display TOP-10 Leaderboard by XP and Streak in the user's selected language.
    """
    if not update.effective_user or not update.message:
        return

    tg_user = update.effective_user

    async with get_session() as session:
        user, user_settings, _ = await crud.get_or_create_user(
            session=session,
            user_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name or "Learner",
        )
        lang = user_settings.language_code
        top_users = await crud.get_top_users(session, limit=10)
        user_rank = await crud.get_user_rank(session, tg_user.id)

    if not top_users:
        await update.message.reply_text(
            text=i18n.t("leaderboard_empty", lang=lang),
            parse_mode="HTML",
        )
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    rows_list: list[str] = []
    for rank, u in enumerate(top_users, start=1):
        badge = medals.get(rank, f"<b>{rank}.</b>")
        safe_name = html.escape(u.full_name or u.username or f"User {u.user_id}")
        rows_list.append(
            f"{badge} <b>{safe_name}</b> — 💎 {u.xp} XP | 🔥 {u.streak}"
        )

    text = i18n.t(
        "leaderboard_message",
        lang=lang,
        rows="\n".join(rows_list),
        user_rank=user_rank,
        user_xp=user.xp,
        user_streak=user.streak,
    )

    await update.message.reply_text(text=text, parse_mode="HTML")


def _format_learned_words_page(
    words: list, lang: str, page: int, total: int, page_size: int = 10
) -> str:
    total_pages = max(1, math.ceil(total / page_size))
    start_num = (page - 1) * page_size + 1
    lines: list[str] = []
    for idx, v in enumerate(words, start=start_num):
        if lang == "uz":
            meaning = v.translation_uz
        elif lang == "ru":
            meaning = v.translation_ru
        else:
            meaning = v.definition_en
        lines.append(
            f"<b>{idx}. {html.escape(v.advanced_word)}</b> ({html.escape(v.cefr_level)})\n"
            f"   🔹 Simple: {html.escape(v.simple_word)}\n"
            f"   📝 {html.escape(meaning)}"
        )

    return i18n.t(
        "learned_words_title",
        lang=lang,
        total=total,
        page=page,
        total_pages=total_pages,
        items="\n\n".join(lines),
    )


async def show_learned_words(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    page_size = 5

    async with get_session() as session:
        lang = await crud.get_user_language(session, user_id)
        words, total = await crud.get_user_learned_words_paginated(
            session, user_id=user_id, page=1, page_size=page_size
        )

    if total == 0 or not words:
        await update.message.reply_text(
            text=i18n.t("learned_words_empty", lang=lang),
            parse_mode="HTML",
        )
        return

    total_pages = max(1, math.ceil(total / page_size))
    text = _format_learned_words_page(
        words=words, lang=lang, page=1, total=total, page_size=page_size
    )
    kb = get_learned_words_pagination_keyboard(
        lang=lang, page=1, total_pages=total_pages
    )
    await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=kb)


async def learned_words_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    await query.answer()
    user_id = update.effective_user.id
    parts = query.data.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    page_size = 5

    async with get_session() as session:
        lang = await crud.get_user_language(session, user_id)
        words, total = await crud.get_user_learned_words_paginated(
            session, user_id=user_id, page=page, page_size=page_size
        )

    if not words:
        return

    total_pages = max(1, math.ceil(total / page_size))
    text = _format_learned_words_page(
        words=words, lang=lang, page=page, total=total, page_size=page_size
    )
    kb = get_learned_words_pagination_keyboard(
        lang=lang, page=page, total_pages=total_pages
    )
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
