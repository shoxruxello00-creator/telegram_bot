import html
import logging
from datetime import date
from telegram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import crud
from database.models import Vocabulary
from services.ai_vocabulary_generator import GenerationResult, ai_generator

logger = logging.getLogger(__name__)


async def notify_admins(bot: Bot | None, message_html: str) -> None:
    if bot is None:
        return
    admin_ids = set(settings.ADMIN_IDS)
    if settings.ADMIN_ID:
        admin_ids.add(settings.ADMIN_ID)
    for admin_id in admin_ids:
        if not admin_id:
            continue
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message_html,
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Could not send alert to admin %s: %s", admin_id, exc)


async def ensure_daily_lesson(
    session: AsyncSession,
    target_date: date | None = None,
    bot: Bot | None = None,
) -> tuple[list[Vocabulary], GenerationResult | None]:
    """
    Retrieve the 10 vocabulary items for `target_date`.
    If not yet created in PostgreSQL, automatically runs the AI generator once.
    Idempotent across restarts.
    """
    lesson_date = target_date or settings.today()
    existing_words = await crud.get_daily_lesson_words(session, lesson_date)
    if existing_words:
        return existing_words, None

    gen_result = await ai_generator.generate_daily_lesson(
        session=session,
        target_date=lesson_date,
        word_count=settings.DAILY_WORD_COUNT,
    )

    if not gen_result.success:
        alert_text = (
            f"🚨 <b>AI Vocabulary Generator Ogohlantirishi!</b>\n\n"
            f"📅 Sana: <b>{lesson_date}</b>\n"
            f"❌ Holat: <b>{html.escape(gen_result.status)}</b>\n"
            f"🔢 Topilgan noyob so‘zlar: <b>{gen_result.generated_count}/{settings.DAILY_WORD_COUNT}</b>\n"
            f"♻️ Rad etilgan takroriy so‘zlar: <b>{gen_result.rejected_duplicates}</b>\n"
            f"🔄 Qayta urinishlar: <b>{gen_result.retry_count}</b>\n"
            f"⚠️ Xato: <code>{html.escape(str(gen_result.error_message or 'Unknown'))}</code>\n\n"
            f"<i>Eslatma: Qoidaga muvofiq foydalanuvchilarga eski takroriy so‘zlar yuborilmadi.</i>"
        )
        await notify_admins(bot, alert_text)
        return [], gen_result

    words = await crud.get_daily_lesson_words(session, lesson_date)
    return words, gen_result
