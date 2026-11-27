import asyncio
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from sqlalchemy import text
from telegram import MenuButtonWebApp, Update, WebAppInfo
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PollAnswerHandler,
    filters,
)

from config import settings
from database.db import close_db, engine, get_session, init_db
from handlers.admin import (
    admin_callback_handler,
    admin_command,
    handle_admin_input_message,
)
from handlers.admin_library import (
    admin_library_callback_handler,
    handle_admin_library_text_input,
)
from handlers.lesson import lesson_callback_handler, show_daily_lesson
from handlers.mock_test import (
    admin_mock_callback_handler,
    handle_admin_mock_input,
    mock_user_callback_handler,
    show_mock_test_catalog,
)
from handlers.quiz import (
    poll_answer_handler,
    quiz_callback_handler,
    start_quiz_command_or_menu,
)
from handlers.referral import referral_callback_handler, show_referral_menu
from handlers.settings import settings_callback_handler, show_settings
from handlers.start import language_selection_callback, start_command
from handlers.stats import (
    learned_words_callback,
    show_leaderboard,
    show_learned_words,
    show_statistics,
)
from services.admin_library_service import sync_permanent_vocabulary_archive_pg
from services.bonus_pack_service import ensure_bonus_packs_seeded
from services.broadcast_service import resume_incomplete_broadcasts
from services.i18n import i18n
from services.lesson_service import ensure_daily_lesson, notify_admins
from services.miniapp_api import MiniAppHTTPRequestHandler, set_main_event_loop
from services.mock_test_service import mock_test_manager
from services.scheduler_service import setup_scheduled_jobs

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class _HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","service":"english_c2_quiz_bot"}')

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def start_health_server() -> None:
    """
    Unconditionally bind the HTTP server (Health Check + Mini App REST API + Static SPA)
    on 0.0.0.0:$PORT (default 10000) so Render Web Service detects an open port immediately.
    """
    raw_port = os.getenv("PORT", "10000").strip()
    port = int(raw_port) if raw_port.isdigit() else 10000
    try:
        server = _ReusableThreadingHTTPServer(("0.0.0.0", port), MiniAppHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info("Render Health & Mini App HTTP server is listening on 0.0.0.0:%d", port)
    except Exception as exc:
        logger.warning("Could not bind health-check server on port %d: %s", port, exc)


async def _apply_sql_migrations() -> None:
    await init_db()
    if not MIGRATIONS_DIR.exists():
        return
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    async with engine.begin() as conn:
        for sql_file in sql_files:
            sql_content = sql_file.read_text(encoding="utf-8")
            active_lines = [
                line
                for line in sql_content.splitlines()
                if line.strip() and not line.strip().startswith("--")
            ]
            statements = [
                s.strip() for s in "\n".join(active_lines).split(";") if s.strip()
            ]
            for stmt in statements:
                await conn.execute(text(stmt))
    logger.info("All database migrations verified and applied.")


async def post_init(application: Application) -> None:
    """
    Executed on bot startup:
    1. Apply PostgreSQL tables & additive migrations.
    2. Pre-seed shared Referral Bonus Packs (100% Gemini Free Tier safe).
    3. Idempotently ensure today's 10 unique C1–C2 words exist.
    4. Register 00:05, 08:00, and 20:00 scheduled jobs in Asia/Tashkent timezone.
    5. Resume any unfinished Admin Broadcast job after a Render restart.
    """
    set_main_event_loop(asyncio.get_running_loop())
    await _apply_sql_migrations()
    async with get_session() as session:
        await ensure_bonus_packs_seeded(session)
        words, _ = await ensure_daily_lesson(
            session=session,
            target_date=settings.today(),
            bot=application.bot,
        )
        await sync_permanent_vocabulary_archive_pg(session)
        await mock_test_manager.ensure_seed_mock_tests_pg(session)
        logger.info(
            "Startup check: Today's lesson (%s) has %d unique C1–C2 expressions ready.",
            settings.today(),
            len(words),
        )
    setup_scheduled_jobs(application)
    await resume_incomplete_broadcasts(application.bot)

    webapp_url = (
        os.getenv("WEBAPP_URL", "").strip()
        or os.getenv("RENDER_EXTERNAL_URL", "").strip()
    )
    if webapp_url.startswith("https://"):
        logger.info("🌐 MINI APP URL FOR BOTFATHER: %s", webapp_url)
        try:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🚀 Shoxrux AI",
                    web_app=WebAppInfo(url=webapp_url),
                )
            )
            await notify_admins(
                application.bot,
                f"🚀 <b>Shoxrux AI IELTS Mini App tayyor!</b>\n\n"
                f"🔗 <b>BotFather uchun Mini App URL:</b>\n"
                f"<code>{webapp_url}</code>",
            )
        except Exception as exc:
            logger.warning("Could not set MenuButtonWebApp automatically: %s", exc)


async def post_shutdown(application: Application) -> None:
    await close_db()
    logger.info("Database connections closed cleanly.")


async def incoming_message_router(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    1. First check if an Admin/Moderator is sending a Broadcast message
       (text, photo, video, audio, voice, document, GIF, sticker) or entering a Moderator Telegram ID.
    2. Otherwise route multilingual ReplyKeyboard menu buttons across uz, ru, en.
    """
    if await handle_admin_input_message(update, context):
        return
    if await handle_admin_library_text_input(update, context):
        return
    if await handle_admin_mock_input(update, context):
        return

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    if text in i18n.all_values_for_key("menu_daily_lesson"):
        await show_daily_lesson(update, context)
    elif text in i18n.all_values_for_key("menu_start_quiz"):
        await start_quiz_command_or_menu(update, context)
    elif text in i18n.all_values_for_key("menu_mock_test") or text == "📝 MOCK TEST":
        await show_mock_test_catalog(update, context)
    elif text in i18n.all_values_for_key("menu_referral"):
        await show_referral_menu(update, context)
    elif text in i18n.all_values_for_key("menu_statistics"):
        await show_statistics(update, context)
    elif text in i18n.all_values_for_key("menu_leaderboard"):
        await show_leaderboard(update, context)
    elif text in i18n.all_values_for_key("menu_learned_words"):
        await show_learned_words(update, context)
    elif text in i18n.all_values_for_key("menu_settings"):
        await show_settings(update, context)
    elif text in i18n.all_values_for_key("menu_admin") or text in {
        "🛠 Admin Panel",
        "🛠 Админ-панель",
    }:
        await admin_command(update, context)
    else:
        await show_daily_lesson(update, context)


async def global_error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    logger.error("Unhandled exception while processing update:", exc_info=context.error)


def build_application() -> Application:
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        raise RuntimeError(
            "BOT_TOKEN is not configured! Please set BOT_TOKEN in your .env file."
        )

    application = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("lesson", show_daily_lesson))
    application.add_handler(CommandHandler("quiz", start_quiz_command_or_menu))
    application.add_handler(CommandHandler("mock", show_mock_test_catalog))
    application.add_handler(CommandHandler("referral", show_referral_menu))
    application.add_handler(CommandHandler("stats", show_statistics))
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    application.add_handler(CommandHandler("learned", show_learned_words))
    application.add_handler(CommandHandler("settings", show_settings))
    application.add_handler(CommandHandler("admin", admin_command))

    # Inline CallbackQuery Handlers
    application.add_handler(
        CallbackQueryHandler(language_selection_callback, pattern=r"^set_lang:")
    )
    application.add_handler(
        CallbackQueryHandler(lesson_callback_handler, pattern=r"^lesson:")
    )
    application.add_handler(
        CallbackQueryHandler(quiz_callback_handler, pattern=r"^quiz:")
    )
    application.add_handler(
        CallbackQueryHandler(mock_user_callback_handler, pattern=r"^mock:")
    )
    application.add_handler(
        CallbackQueryHandler(referral_callback_handler, pattern=r"^referral:")
    )
    application.add_handler(
        CallbackQueryHandler(learned_words_callback, pattern=r"^learned:")
    )
    application.add_handler(
        CallbackQueryHandler(settings_callback_handler, pattern=r"^settings:")
    )
    application.add_handler(
        CallbackQueryHandler(admin_callback_handler, pattern=r"^admin:")
    )
    application.add_handler(
        CallbackQueryHandler(admin_library_callback_handler, pattern=r"^adm_lib:")
    )
    application.add_handler(
        CallbackQueryHandler(admin_mock_callback_handler, pattern=r"^adm_mock:")
    )

    # Native Telegram Quiz Poll Answer Handler
    application.add_handler(PollAnswerHandler(poll_answer_handler))

    # Multilingual ReplyKeyboard & Admin Broadcast Media/Text Router
    application.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, incoming_message_router)
    )

    application.add_error_handler(global_error_handler)
    return application


def main() -> None:
    start_health_server()
    app = build_application()
    logger.info("Starting English C2 Quiz Bot (python-telegram-bot 22.3)...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
