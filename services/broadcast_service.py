import asyncio
import logging
from telegram import Bot, Message
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError

from database import crud
from database.db import get_session

logger = logging.getLogger(__name__)

# Active background tasks & cancellation flags
_ACTIVE_BROADCAST_TASKS: dict[int, asyncio.Task] = {}
_CANCEL_REQUESTED: set[int] = set()
_BROADCAST_LOCK = asyncio.Lock()


def detect_message_type(msg: Message) -> str:
    if msg.photo:
        return "photo"
    if msg.video:
        return "video"
    if msg.audio:
        return "audio"
    if msg.voice:
        return "voice"
    if msg.document:
        return "document"
    if msg.animation:
        return "animation"
    if msg.sticker:
        return "sticker"
    return "text"


def is_broadcast_running() -> bool:
    return any(not t.done() for t in _ACTIVE_BROADCAST_TASKS.values())


async def request_cancel_broadcast(broadcast_id: int) -> bool:
    _CANCEL_REQUESTED.add(broadcast_id)
    async with get_session() as session:
        bcast = await crud.get_broadcast_by_id(session, broadcast_id)
        if bcast and bcast.status == "running":
            await crud.finalize_broadcast_job(
                session, broadcast_id, status="cancelled"
            )
            return True
    return False


def launch_broadcast_task(bot: Bot, broadcast_id: int) -> None:
    if broadcast_id in _ACTIVE_BROADCAST_TASKS and not _ACTIVE_BROADCAST_TASKS[broadcast_id].done():
        return
    task = asyncio.create_task(_run_broadcast_loop(bot, broadcast_id))
    _ACTIVE_BROADCAST_TASKS[broadcast_id] = task


async def _run_broadcast_loop(bot: Bot, broadcast_id: int) -> None:
    async with _BROADCAST_LOCK:
        logger.info("Broadcast job #%d worker started.", broadcast_id)
        try:
            while True:
                if broadcast_id in _CANCEL_REQUESTED:
                    async with get_session() as session:
                        await crud.finalize_broadcast_job(
                            session, broadcast_id, status="cancelled"
                        )
                    logger.info("Broadcast job #%d cancelled by admin.", broadcast_id)
                    break

                async with get_session() as session:
                    bcast = await crud.get_broadcast_by_id(session, broadcast_id)
                    if bcast is None or bcast.status != "running":
                        break
                    recipients = await crud.get_pending_broadcast_recipients(
                        session, broadcast_id, limit=40
                    )

                if not recipients:
                    async with get_session() as session:
                        await crud.finalize_broadcast_job(
                            session, broadcast_id, status="completed"
                        )
                    logger.info("Broadcast job #%d completed.", broadcast_id)
                    break

                for rec in recipients:
                    if broadcast_id in _CANCEL_REQUESTED:
                        break

                    delivered = False
                    for attempt in range(2):
                        try:
                            await bot.copy_message(
                                chat_id=rec.user_id,
                                from_chat_id=bcast.source_chat_id,
                                message_id=bcast.source_message_id,
                            )
                            delivered = True
                            break
                        except RetryAfter as rate_err:
                            wait_secs = int(getattr(rate_err, "retry_after", 3)) + 1
                            logger.warning(
                                "Broadcast #%d hit RetryAfter; sleeping %ds",
                                broadcast_id,
                                wait_secs,
                            )
                            await asyncio.sleep(wait_secs)
                        except Forbidden as fb_err:
                            async with get_session() as session:
                                await crud.mark_broadcast_recipient_failed(
                                    session=session,
                                    recipient_id=rec.id,
                                    broadcast_id=broadcast_id,
                                    user_id=rec.user_id,
                                    error_message=f"Forbidden: {fb_err}",
                                    mark_user_inactive=True,
                                )
                            break
                        except (BadRequest, TelegramError) as tg_err:
                            async with get_session() as session:
                                await crud.mark_broadcast_recipient_failed(
                                    session=session,
                                    recipient_id=rec.id,
                                    broadcast_id=broadcast_id,
                                    user_id=rec.user_id,
                                    error_message=str(tg_err),
                                    mark_user_inactive=False,
                                )
                            break

                    if delivered:
                        async with get_session() as session:
                            await crud.mark_broadcast_recipient_sent(
                                session=session,
                                recipient_id=rec.id,
                                broadcast_id=broadcast_id,
                            )

                    # Respect Telegram global broadcast limit (~20 messages/sec)
                    await asyncio.sleep(0.05)

        except Exception as exc:
            logger.error("Unexpected error in broadcast job #%d: %s", broadcast_id, exc)
            async with get_session() as session:
                await crud.finalize_broadcast_job(
                    session, broadcast_id, status="failed"
                )
        finally:
            _CANCEL_REQUESTED.discard(broadcast_id)
            _ACTIVE_BROADCAST_TASKS.pop(broadcast_id, None)


async def resume_incomplete_broadcasts(bot: Bot) -> None:
    """
    On Render server restart, automatically resume any unfinished broadcast
    from PostgreSQL (`status == 'running'`) for remaining `pending` recipients.
    """
    async with get_session() as session:
        running = await crud.get_running_broadcast(session)
        if running is not None:
            logger.info(
                "Resuming unfinished broadcast job #%d after restart.",
                running.id,
            )
            launch_broadcast_task(bot, running.id)
