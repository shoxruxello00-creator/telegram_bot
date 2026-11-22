import asyncio
import html
import logging
from datetime import time
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import Application, ContextTypes

from config import settings
from database import crud
from database.db import get_session
from keyboards.inline import get_lesson_card_keyboard, get_morning_notification_keyboard
from services.i18n import i18n
from services.lesson_service import ensure_daily_lesson, notify_admins

logger = logging.getLogger(__name__)


async def job_generate_daily_lesson(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    00:05 Asia/Tashkent — Generates 10 new C1–C2 expressions, validates against all
    historical words in PostgreSQL, and saves today's lesson.
    """
    today = settings.today()
    logger.info("[Scheduler 00:05] Running daily vocabulary generation for %s", today)
    async with get_session() as session:
        words, gen_result = await ensure_daily_lesson(
            session=session,
            target_date=today,
            bot=context.bot,
        )
        if gen_result and gen_result.success and gen_result.status != "ALREADY_EXISTS":
            msg = (
                f"✅ <b>Kunlik dars avtomatik yaratildi ({today})</b>\n"
                f"🔹 Holat: <b>{html.escape(gen_result.status)}</b>\n"
                f"📚 Yangi C1–C2 iboralar: <b>{len(words)} ta</b>\n"
                f"♻️ Rad etilgan takrorlar: <b>{gen_result.rejected_duplicates} ta</b>"
            )
            await notify_admins(context.bot, msg)


async def job_send_morning_lessons(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    08:00 Asia/Tashkent — Sends the localized morning greeting and today's 10 new
    C1–C2 expressions to all active users in their selected language.
    """
    today = settings.today()
    logger.info("[Scheduler 08:00] Broadcasting morning C1–C2 lesson for %s", today)

    async with get_session() as session:
        words, _ = await ensure_daily_lesson(
            session=session,
            target_date=today,
            bot=context.bot,
        )
        if not words:
            logger.error(
                "[Scheduler 08:00] Today's lesson (%s) is not available. Skipping broadcast to avoid duplicates.",
                today,
            )
            return

        active_users = await crud.get_all_active_users_with_settings(session)
        sent_count = 0
        blocked_count = 0

        for user, user_settings in active_users:
            lang = user_settings.language_code
            greeting_text = i18n.t("morning_notification", lang=lang)
            first_card_text = i18n.format_word_card(
                vocab=words[0],
                lang=lang,
                index=1,
                total=len(words),
                lesson_date=str(today),
            )
            card_kb = get_lesson_card_keyboard(
                lang=lang, current_index=0, total=len(words)
            )

            try:
                await context.bot.send_message(
                    chat_id=user.user_id,
                    text=greeting_text,
                    parse_mode="HTML",
                )
                await context.bot.send_message(
                    chat_id=user.user_id,
                    text=first_card_text,
                    parse_mode="HTML",
                    reply_markup=card_kb,
                )
                sent_count += 1
                await asyncio.sleep(0.05)
            except RetryAfter as rate_err:
                await asyncio.sleep(rate_err.retry_after + 1)
            except (Forbidden, BadRequest) as exc:
                logger.info(
                    "User %s blocked or deactivated bot (%s). Marking inactive.",
                    user.user_id,
                    exc,
                )
                await crud.set_user_active_status(session, user.user_id, False)
                blocked_count += 1
            except TelegramError as tg_err:
                logger.warning(
                    "Telegram error sending morning lesson to %s: %s",
                    user.user_id,
                    tg_err,
                )

        logger.info(
            "[Scheduler 08:00] Completed morning broadcast: sent=%d, blocked=%d",
            sent_count,
            blocked_count,
        )


async def job_send_evening_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    20:00 Asia/Tashkent — Checks each user's daily completion status:
    - If completed: sends localized congratulatory message.
    - If not completed (and reminders_enabled): sends localized reminder in user's language.
    """
    today = settings.today()
    logger.info("[Scheduler 20:00] Running evening completion check for %s", today)

    async with get_session() as session:
        active_users = await crud.get_all_active_users_with_settings(session)
        reminded_count = 0
        congrats_count = 0

        for user, user_settings in active_users:
            if not user_settings.reminders_enabled:
                continue

            lang = user_settings.language_code
            progress = await crud.get_or_create_daily_progress(
                session, user.user_id, today
            )

            try:
                if progress.is_completed:
                    msg_text = i18n.t(
                        "evening_congrats",
                        lang=lang,
                        name=html.escape(user.full_name),
                        xp=user.xp,
                        streak=user.streak,
                    )
                    await context.bot.send_message(
                        chat_id=user.user_id,
                        text=msg_text,
                        parse_mode="HTML",
                    )
                    congrats_count += 1
                else:
                    msg_text = i18n.t(
                        "evening_reminder",
                        lang=lang,
                        streak=user.streak,
                    )
                    kb = get_morning_notification_keyboard(lang=lang)
                    await context.bot.send_message(
                        chat_id=user.user_id,
                        text=msg_text,
                        parse_mode="HTML",
                        reply_markup=kb,
                    )
                    reminded_count += 1
                await asyncio.sleep(0.05)
            except RetryAfter as rate_err:
                await asyncio.sleep(rate_err.retry_after + 1)
            except (Forbidden, BadRequest) as exc:
                logger.info(
                    "User %s blocked or deactivated bot during 20:00 check (%s).",
                    user.user_id,
                    exc,
                )
                await crud.set_user_active_status(session, user.user_id, False)
            except TelegramError as tg_err:
                logger.warning(
                    "Telegram error sending 20:00 message to %s: %s",
                    user.user_id,
                    tg_err,
                )

        logger.info(
            "[Scheduler 20:00] Completed evening check: reminded=%d, congratulated=%d",
            reminded_count,
            congrats_count,
        )


def setup_scheduled_jobs(application: Application) -> None:
    """
    Register the 00:05, 08:00, and 20:00 daily jobs in Asia/Tashkent timezone.
    """
    job_queue = application.job_queue
    if job_queue is None:
        logger.error("JobQueue is not available! Ensure python-telegram-bot[job-queue] is installed.")
        return

    tz = settings.tz

    gen_time = time(
        hour=settings.DAILY_GENERATION_HOUR,
        minute=settings.DAILY_GENERATION_MINUTE,
        tzinfo=tz,
    )
    send_time = time(
        hour=settings.DAILY_SEND_HOUR,
        minute=settings.DAILY_SEND_MINUTE,
        tzinfo=tz,
    )
    reminder_time = time(
        hour=settings.REMINDER_HOUR,
        minute=settings.REMINDER_MINUTE,
        tzinfo=tz,
    )

    job_queue.run_daily(
        job_generate_daily_lesson,
        time=gen_time,
        name="daily_vocabulary_generation_00_05",
    )
    job_queue.run_daily(
        job_send_morning_lessons,
        time=send_time,
        name="daily_morning_lesson_08_00",
    )
    job_queue.run_daily(
        job_send_evening_reminders,
        time=reminder_time,
        name="daily_evening_reminder_20_00",
    )

    logger.info(
        "Scheduled jobs configured in %s timezone: Generation=%02d:%02d, MorningSend=%02d:%02d, EveningReminder=%02d:%02d",
        settings.TIMEZONE,
        settings.DAILY_GENERATION_HOUR,
        settings.DAILY_GENERATION_MINUTE,
        settings.DAILY_SEND_HOUR,
        settings.DAILY_SEND_MINUTE,
        settings.REMINDER_HOUR,
        settings.REMINDER_MINUTE,
    )
