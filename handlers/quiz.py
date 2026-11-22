import html
import logging
from dataclasses import dataclass, field
from datetime import date
from telegram import Poll, Update
from telegram.ext import ContextTypes

from config import settings
from database import crud
from database.db import get_session
from database.models import Vocabulary
from keyboards.inline import get_memorized_only_keyboard, get_start_quiz_keyboard
from services.i18n import i18n
from services.lesson_service import ensure_daily_lesson

logger = logging.getLogger(__name__)


@dataclass
class ActiveQuizItem:
    vocab_id: int
    simple_word: str
    advanced_word: str
    cefr_level: str
    translation_uz: str
    translation_ru: str
    definition_en: str
    example_en: str
    question_uz: str | None
    question_ru: str | None
    question_en: str | None
    options: list[str]
    correct_option: int


@dataclass
class ActiveQuizSession:
    user_id: int
    chat_id: int
    lang: str
    lesson_date: date
    practice_mode: bool
    items: list[ActiveQuizItem]
    bonus_pack_id: int | None = None
    bonus_pack_title: str | None = None
    current_index: int = 0
    score: int = 0
    word_results: list[tuple[int, bool]] = field(default_factory=list)
    active_poll_id: str | None = None


_USER_QUIZ_SESSIONS: dict[int, ActiveQuizSession] = {}
_POLL_TO_USER: dict[str, int] = {}


def _build_quiz_item(v: Vocabulary) -> ActiveQuizItem:
    return ActiveQuizItem(
        vocab_id=v.id,
        simple_word=v.simple_word,
        advanced_word=v.advanced_word,
        cefr_level=v.cefr_level,
        translation_uz=v.translation_uz,
        translation_ru=v.translation_ru,
        definition_en=v.definition_en,
        example_en=v.example_en,
        question_uz=v.quiz_question_uz,
        question_ru=v.quiz_question_ru,
        question_en=v.quiz_question_en,
        options=v.get_options(),
        correct_option=v.correct_option,
    )


def _format_poll_question(
    item: ActiveQuizItem, lang: str, current: int, total: int
) -> str:
    if lang == "uz":
        q_body = item.question_uz or i18n.t(
            "quiz_default_question",
            lang="uz",
            simple_word=item.simple_word,
            translation=item.translation_uz,
        )
    elif lang == "ru":
        q_body = item.question_ru or i18n.t(
            "quiz_default_question",
            lang="ru",
            simple_word=item.simple_word,
            translation=item.translation_ru,
        )
    else:
        q_body = item.question_en or i18n.t(
            "quiz_default_question",
            lang="en",
            simple_word=item.simple_word,
            definition_en=item.definition_en,
        )

    full_q = i18n.t(
        "quiz_question_header",
        lang=lang,
        current=current,
        total=total,
        cefr_level=item.cefr_level,
        question=q_body,
    )
    return full_q[:295]


def _format_poll_explanation(item: ActiveQuizItem, lang: str) -> str:
    if lang == "uz":
        translation = item.translation_uz
    elif lang == "ru":
        translation = item.translation_ru
    else:
        translation = item.definition_en

    expl = i18n.t(
        "quiz_explanation",
        lang=lang,
        advanced_word=item.advanced_word,
        translation=translation,
        definition_en=item.definition_en,
        example_en=item.example_en,
    )
    return expl[:195]


def _cancel_timeout_jobs(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    if not context.job_queue:
        return
    job_name = f"quiz_timeout_{user_id}"
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()


async def start_quiz_command_or_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.effective_user or not update.effective_chat:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    today = settings.today()

    async with get_session() as session:
        _, user_settings, _ = await crud.get_or_create_user(
            session=session,
            user_id=user_id,
            username=update.effective_user.username,
            full_name=update.effective_user.full_name or "Learner",
        )
        lang = user_settings.language_code
        progress = await crud.get_or_create_daily_progress(session, user_id, today)

        if not progress.is_memorized:
            if update.message:
                await update.message.reply_text(
                    text=i18n.t("need_memorize_first", lang=lang),
                    parse_mode="HTML",
                    reply_markup=get_memorized_only_keyboard(lang=lang),
                )
            return

        if progress.is_completed:
            if update.message:
                await update.message.reply_text(
                    text=i18n.t(
                        "quiz_already_completed",
                        lang=lang,
                        score=progress.score,
                        total=settings.DAILY_WORD_COUNT,
                        earned_xp=progress.earned_xp,
                    ),
                    parse_mode="HTML",
                    reply_markup=get_start_quiz_keyboard(lang=lang, practice=True),
                )
            return

        words, _ = await ensure_daily_lesson(
            session=session, target_date=today, bot=context.bot
        )

    if not words:
        if update.message:
            await update.message.reply_text(
                text=i18n.t("lesson_not_ready", lang=lang),
                parse_mode="HTML",
            )
        return

    await _launch_quiz_session(
        context=context,
        user_id=user_id,
        chat_id=chat_id,
        lang=lang,
        today=today,
        words=words,
        practice_mode=False,
    )


async def quiz_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Callback for:
    - `quiz:start:daily`
    - `quiz:start:practice`
    - `quiz:pack:<pack_id>` (Special Bonus Pack Quiz)
    """
    query = update.callback_query
    if not query or not query.data or not update.effective_user or not query.message:
        return

    user_id = update.effective_user.id
    chat_id = query.message.chat_id
    today = settings.today()
    data = query.data

    if data.startswith("quiz:pack:"):
        parts = data.split(":")
        pack_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        async with get_session() as session:
            lang = await crud.get_user_language(session, user_id)
            pack, words = await crud.get_bonus_pack_with_words(session, pack_id)
            if pack is None or not words:
                await query.answer("Pack not found.", show_alert=True)
                return
            unlocked = await crud.is_pack_unlocked_for_user(session, user_id, pack)
            if not unlocked:
                summary = await crud.get_user_referral_summary(session, user_id)
                await query.answer(
                    i18n.t(
                        "pack_locked_alert",
                        lang=lang,
                        required=pack.required_referrals,
                        confirmed=summary["confirmed"],
                    ),
                    show_alert=True,
                )
                return

        await query.answer()
        await _launch_quiz_session(
            context=context,
            user_id=user_id,
            chat_id=chat_id,
            lang=lang,
            today=today,
            words=words[:10],
            practice_mode=False,
            bonus_pack_id=pack.id,
            bonus_pack_title=pack.title,
        )
        return

    await query.answer()
    practice_mode = data.endswith(":practice")

    async with get_session() as session:
        lang = await crud.get_user_language(session, user_id)
        progress = await crud.get_or_create_daily_progress(session, user_id, today)

        if not progress.is_memorized and not practice_mode:
            await query.message.reply_text(
                text=i18n.t("need_memorize_first", lang=lang),
                parse_mode="HTML",
                reply_markup=get_memorized_only_keyboard(lang=lang),
            )
            return

        if progress.is_completed and not practice_mode:
            practice_mode = True

        words, _ = await ensure_daily_lesson(
            session=session, target_date=today, bot=context.bot
        )

    if not words:
        await query.message.reply_text(
            text=i18n.t("lesson_not_ready", lang=lang),
            parse_mode="HTML",
        )
        return

    await _launch_quiz_session(
        context=context,
        user_id=user_id,
        chat_id=chat_id,
        lang=lang,
        today=today,
        words=words,
        practice_mode=practice_mode,
    )


async def _launch_quiz_session(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    lang: str,
    today: date,
    words: list[Vocabulary],
    practice_mode: bool,
    bonus_pack_id: int | None = None,
    bonus_pack_title: str | None = None,
) -> None:
    _cancel_timeout_jobs(context, user_id)
    old_session = _USER_QUIZ_SESSIONS.pop(user_id, None)
    if old_session and old_session.active_poll_id:
        _POLL_TO_USER.pop(old_session.active_poll_id, None)

    quiz_items = [_build_quiz_item(v) for v in words]
    quiz_session = ActiveQuizSession(
        user_id=user_id,
        chat_id=chat_id,
        lang=lang,
        lesson_date=today,
        practice_mode=practice_mode,
        items=quiz_items,
        bonus_pack_id=bonus_pack_id,
        bonus_pack_title=bonus_pack_title,
    )
    _USER_QUIZ_SESSIONS[user_id] = quiz_session
    await _send_next_quiz_poll(context, quiz_session)


async def _send_next_quiz_poll(
    context: ContextTypes.DEFAULT_TYPE,
    quiz_session: ActiveQuizSession,
) -> None:
    _cancel_timeout_jobs(context, quiz_session.user_id)

    if quiz_session.current_index >= len(quiz_session.items):
        await _finalize_quiz_session(context, quiz_session)
        return

    idx = quiz_session.current_index
    item = quiz_session.items[idx]
    total = len(quiz_session.items)

    question_text = _format_poll_question(
        item=item, lang=quiz_session.lang, current=idx + 1, total=total
    )
    explanation_text = _format_poll_explanation(item=item, lang=quiz_session.lang)
    options = [opt[:95] for opt in item.options]

    poll_msg = await context.bot.send_poll(
        chat_id=quiz_session.chat_id,
        question=question_text,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=item.correct_option,
        explanation=explanation_text,
        is_anonymous=False,
        open_period=settings.QUIZ_TIME_LIMIT,
    )

    if poll_msg.poll:
        poll_id = poll_msg.poll.id
        quiz_session.active_poll_id = poll_id
        _POLL_TO_USER[poll_id] = quiz_session.user_id

    if context.job_queue:
        context.job_queue.run_once(
            _quiz_poll_timeout_job,
            when=settings.QUIZ_TIME_LIMIT + 3,
            data={"user_id": quiz_session.user_id, "question_index": idx},
            name=f"quiz_timeout_{quiz_session.user_id}",
        )


async def _quiz_poll_timeout_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data if context.job else {}
    if not isinstance(job_data, dict):
        return
    user_id = job_data.get("user_id")
    q_idx = job_data.get("question_index")
    if user_id is None:
        return

    quiz_session = _USER_QUIZ_SESSIONS.get(user_id)
    if not quiz_session or quiz_session.current_index != q_idx:
        return

    if quiz_session.active_poll_id:
        _POLL_TO_USER.pop(quiz_session.active_poll_id, None)
        quiz_session.active_poll_id = None

    curr_item = quiz_session.items[quiz_session.current_index]
    quiz_session.word_results.append((curr_item.vocab_id, False))
    quiz_session.current_index += 1

    await _send_next_quiz_poll(context, quiz_session)


async def poll_answer_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    poll_answer = update.poll_answer
    if not poll_answer:
        return

    poll_id = poll_answer.poll_id
    user_id = _POLL_TO_USER.pop(poll_id, None)
    if user_id is None and poll_answer.user:
        user_id = poll_answer.user.id
    if user_id is None:
        return

    quiz_session = _USER_QUIZ_SESSIONS.get(user_id)
    if not quiz_session:
        return

    _cancel_timeout_jobs(context, user_id)
    quiz_session.active_poll_id = None

    if quiz_session.current_index >= len(quiz_session.items):
        return

    current_item = quiz_session.items[quiz_session.current_index]
    chosen_ids = poll_answer.option_ids or []
    is_correct = (
        len(chosen_ids) > 0 and chosen_ids[0] == current_item.correct_option
    )

    if is_correct:
        quiz_session.score += 1

    quiz_session.word_results.append((current_item.vocab_id, is_correct))
    quiz_session.current_index += 1

    await _send_next_quiz_poll(context, quiz_session)


async def _finalize_quiz_session(
    context: ContextTypes.DEFAULT_TYPE,
    quiz_session: ActiveQuizSession,
) -> None:
    _USER_QUIZ_SESSIONS.pop(quiz_session.user_id, None)
    if quiz_session.active_poll_id:
        _POLL_TO_USER.pop(quiz_session.active_poll_id, None)

    total = len(quiz_session.items)
    score = quiz_session.score
    accuracy = round((score / total) * 100) if total > 0 else 0
    lang = quiz_session.lang

    # Special Bonus Pack Quiz Completion
    if quiz_session.bonus_pack_id is not None:
        async with get_session() as session:
            _, earned_xp = await crud.record_bonus_pack_quiz_completion(
                session=session,
                user_id=quiz_session.user_id,
                pack_id=quiz_session.bonus_pack_id,
                score=score,
            )
            user, _, _ = await crud.get_or_create_user(session, quiz_session.user_id)

        feedback = (
            i18n.t("quiz_feedback_excellent", lang=lang)
            if accuracy >= 80
            else i18n.t("quiz_feedback_good", lang=lang)
        )
        summary_text = i18n.t(
            "quiz_completed_title",
            lang=lang,
            score=score,
            total=total,
            accuracy=accuracy,
            earned_xp=earned_xp,
            total_xp=user.xp,
            streak=user.streak,
            best_streak=user.best_streak,
            feedback=feedback,
        )
        await context.bot.send_message(
            chat_id=quiz_session.chat_id,
            text=summary_text,
            parse_mode="HTML",
        )
        return

    if quiz_session.practice_mode:
        summary_text = i18n.t(
            "quiz_practice_completed",
            lang=lang,
            score=score,
            total=total,
            accuracy=accuracy,
        )
        await context.bot.send_message(
            chat_id=quiz_session.chat_id,
            text=summary_text,
            parse_mode="HTML",
        )
        return

    referrer_id: int | None = None
    referrer_lang = "uz"
    confirmed_count = 0
    newly_unlocked = []

    async with get_session() as session:
        user, _, earned_xp = await crud.complete_daily_quiz(
            session=session,
            user_id=quiz_session.user_id,
            target_date=quiz_session.lesson_date,
            score=score,
            total_questions=total,
            word_results=quiz_session.word_results,
        )
        # Confirm pending referral if this was the user's first completed daily quiz
        (
            referrer_id,
            confirmed_count,
            newly_unlocked,
        ) = await crud.confirm_referral_and_unlock_rewards(
            session=session,
            referred_user_id=quiz_session.user_id,
        )
        if referrer_id is not None:
            referrer_lang = await crud.get_user_language(session, referrer_id)

    if accuracy >= 80:
        feedback = i18n.t("quiz_feedback_excellent", lang=lang)
    elif accuracy >= 50:
        feedback = i18n.t("quiz_feedback_good", lang=lang)
    else:
        feedback = i18n.t("quiz_feedback_keep_trying", lang=lang)

    summary_text = i18n.t(
        "quiz_completed_title",
        lang=lang,
        score=score,
        total=total,
        accuracy=accuracy,
        earned_xp=earned_xp,
        total_xp=user.xp,
        streak=user.streak,
        best_streak=user.best_streak,
        feedback=feedback,
    )

    await context.bot.send_message(
        chat_id=quiz_session.chat_id,
        text=summary_text,
        parse_mode="HTML",
    )

    # Notify referrer when their friend finishes their first IELTS quiz!
    if referrer_id is not None:
        unlocked_lines: list[str] = []
        for pack in newly_unlocked:
            unlocked_lines.append(
                i18n.t(
                    "referral_reward_unlocked_line",
                    lang=referrer_lang,
                    reward_title=html.escape(pack.title),
                )
            )
        notif_text = i18n.t(
            "referral_confirmed_notification",
            lang=referrer_lang,
            total_confirmed=confirmed_count,
            unlocked_block="".join(unlocked_lines),
        )
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=notif_text,
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning(
                "Could not send referral confirmation notification to %s: %s",
                referrer_id,
                exc,
            )
