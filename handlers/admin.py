import html
import logging
import math
from dataclasses import dataclass
from typing import Any
from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from database import crud
from database.db import get_session
from database.models import BonusPack, Broadcast
from keyboards.inline import (
    get_admin_back_keyboard,
    get_admin_broadcast_preview_keyboard,
    get_admin_broadcast_status_keyboard,
    get_admin_broadcast_wait_keyboard,
    get_admin_milestones_keyboard,
    get_admin_panel_keyboard,
    get_admin_referral_keyboard,
    get_admin_referral_reject_keyboard,
    get_admin_vocab_pagination_keyboard,
    get_appoint_admin_confirm_keyboard,
    get_remove_admin_confirm_keyboard,
    get_super_admin_management_keyboard,
)
from keyboards.reply import get_main_menu_keyboard
from services.ai_vocabulary_generator import ai_generator
from services.broadcast_service import (
    detect_message_type,
    is_broadcast_running,
    launch_broadcast_task,
    request_cancel_broadcast,
)
from services.i18n import i18n

logger = logging.getLogger(__name__)


@dataclass
class PendingBroadcastDraft:
    admin_id: int
    source_chat_id: int
    source_message_id: int
    message_type: str


# In-memory admin interaction states: "waiting_broadcast" or "waiting_new_admin_id"
_ADMIN_INPUT_STATE: dict[int, str] = {}
_ADMIN_BROADCAST_DRAFTS: dict[int, PendingBroadcastDraft] = {}


def is_admin_waiting_for_input(user_id: int) -> bool:
    return user_id in _ADMIN_INPUT_STATE


def _admin_home_text(role: str) -> str:
    today = settings.today()
    role_badge = "👑 Super Admin (Owner)" if role == "super_admin" else "🛡 Moderator (Admin)"
    return (
        f"🔐 <b>English C2 Quiz Bot — Admin Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Rolingiz: <b>{role_badge}</b>\n"
        f"📅 Bugungi sana ({settings.TIMEZONE}): <b>{today}</b>\n"
        f"🤖 AI Provider: <b>{html.escape(settings.AI_PROVIDER)}</b> (<code>{html.escape(settings.AI_MODEL)}</code>)\n"
        f"🕒 Avtomatik jadval:\n"
        f"   • <b>{settings.DAILY_GENERATION_HOUR:02d}:{settings.DAILY_GENERATION_MINUTE:02d}</b> — Yangi 10 ta so‘z generatsiyasi\n"
        f"   • <b>{settings.DAILY_SEND_HOUR:02d}:{settings.DAILY_SEND_MINUTE:02d}</b> — Kunlik dars tarqatmasi\n"
        f"   • <b>{settings.REMINDER_HOUR:02d}:{settings.REMINDER_MINUTE:02d}</b> — Kechki tekshiruv va eslatma\n\n"
        f"👇 Quyidagi bo‘limlardan birini tanlang:"
    )


def _format_broadcast_status_text(bcast: Broadcast) -> str:
    total = bcast.total_recipients
    sent = bcast.success_count
    failed = bcast.failed_count
    processed = sent + failed
    remaining = max(0, total - processed)
    pct = round((processed / total) * 100) if total > 0 else 100

    return (
        f"📢 <b>BROADCAST STATUS (#{bcast.id})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Holat: <b>{html.escape(bcast.status.upper())}</b>\n"
        f"📝 Xabar turi: <b>{html.escape(bcast.message_type)}</b>\n\n"
        f"👥 Jami: <b>{total:,}</b>\n"
        f"✅ Yuborildi: <b>{sent:,}</b>\n"
        f"❌ Xatolik: <b>{failed:,}</b>\n"
        f"⏳ Qolgan: <b>{remaining:,}</b>\n"
        f"📊 Progress: <b>{pct}%</b>"
    ).replace(",", " ")


async def admin_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    _ADMIN_INPUT_STATE.pop(user_id, None)

    async with get_session() as session:
        role = await crud.get_admin_role(session, user_id)
        lang = await crud.get_user_language(session, user_id)

    if role is None:
        await update.message.reply_text("⛔ Sizda admin huquqi yo‘q.")
        return

    is_super = role == "super_admin"
    await update.message.reply_text(
        text=_admin_home_text(role),
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard(is_super_admin=is_super, lang=lang),
    )


async def handle_admin_input_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """
    Intercepts messages from an admin when they are in `waiting_broadcast`
    or `waiting_new_admin_id` state.
    Returns True if handled, False if message should proceed to normal routing.
    """
    if not update.effective_user or not update.message:
        return False

    user_id = update.effective_user.id
    state = _ADMIN_INPUT_STATE.get(user_id)
    if not state:
        return False

    async with get_session() as session:
        role = await crud.get_admin_role(session, user_id)

    if role is None:
        _ADMIN_INPUT_STATE.pop(user_id, None)
        return False

    msg = update.message

    # 1. Super Admin entering new Moderator's Telegram ID
    if state == "waiting_new_admin_id":
        if role != "super_admin":
            _ADMIN_INPUT_STATE.pop(user_id, None)
            await msg.reply_text("⛔ Faqat Super Admin yangi admin qo‘sha oladi.")
            return True

        raw_text = (msg.text or "").strip()
        if not raw_text.isdigit():
            await msg.reply_text(
                "⚠️ <b>Xato!</b> Telegram ID faqat raqamlardan iborat bo‘lishi kerak.\n"
                "Qaytadan yuboring yoki bekor qiling:",
                parse_mode="HTML",
                reply_markup=get_admin_back_keyboard("admin:admins"),
            )
            return True

        candidate_id = int(raw_text)
        async with get_session() as session:
            ok, reason, candidate_user = await crud.validate_new_moderator_candidate(
                session, candidate_id
            )

        if not ok:
            error_map = {
                "IS_SUPER_ADMIN": "⚠️ Bu Telegram ID Super Admin'ga tegishli!",
                "ALREADY_ADMIN": "⚠️ Ushbu foydalanuvchi allaqachon admin sifatida qo‘shilgan!",
                "MAX_ADMIN_LIMIT_REACHED": "⚠️ Maksimal 1 ta qo‘shimcha admin (Moderator) mavjud. Yangi qo‘shish uchun avval mavjud moderatorni o‘chiring.",
                "USER_NOT_FOUND": "⚠️ Ushbu Telegram ID bazada topilmadi! Yangi admin avval botga kirib /start bosgan bo‘lishi shart.",
            }
            await msg.reply_text(
                text=error_map.get(reason, "⚠️ Noma'lum xatolik."),
                parse_mode="HTML",
                reply_markup=get_admin_back_keyboard("admin:admins"),
            )
            return True

        _ADMIN_INPUT_STATE.pop(user_id, None)
        uname = (
            f"@{html.escape(candidate_user.username)}"
            if candidate_user and candidate_user.username
            else html.escape(candidate_user.full_name if candidate_user else "No username")
        )
        confirm_text = (
            f"👑 <b>YANGI ADMIN</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Username: <b>{uname}</b>\n"
            f"🆔 Telegram ID: <code>{candidate_id}</code>\n"
            f"🔐 Role: <b>Moderator</b>"
        )
        await msg.reply_text(
            text=confirm_text,
            parse_mode="HTML",
            reply_markup=get_appoint_admin_confirm_keyboard(candidate_id),
        )
        return True

    # 2. Admin sending Broadcast message (text, photo, video, audio, voice, doc, gif, sticker)
    if state == "waiting_broadcast":
        _ADMIN_INPUT_STATE.pop(user_id, None)
        msg_type = detect_message_type(msg)
        draft = PendingBroadcastDraft(
            admin_id=user_id,
            source_chat_id=msg.chat_id,
            source_message_id=msg.message_id,
            message_type=msg_type,
        )
        _ADMIN_BROADCAST_DRAFTS[user_id] = draft

        async with get_session() as session:
            counts = await crud.get_broadcast_audience_counts(session)

        # Send an exact copy of the message back as preview
        await context.bot.copy_message(
            chat_id=msg.chat_id,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id,
        )

        preview_text = (
            f"📢 <b>BROADCAST PREVIEW</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Jami foydalanuvchilar: <b>{counts['total_users']:,}</b>\n"
            f"📨 Yuborilishi mumkin: <b>{counts['sendable_users']:,}</b>\n"
            f"🚫 Bloklagan yoki faol bo‘lmaganlar: <b>{counts['blocked_or_disabled']:,}</b>\n"
            f"📝 Xabar turi: <b>{html.escape(msg_type)}</b>\n\n"
            f"<i>Yuqoridagi xabar barcha faol foydalanuvchilarga asl formatida yuborilsinmi?</i>"
        ).replace(",", " ")

        await msg.reply_text(
            text=preview_text,
            parse_mode="HTML",
            reply_markup=get_admin_broadcast_preview_keyboard(),
        )
        return True

    return False


async def admin_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    user_id = update.effective_user.id
    async with get_session() as session:
        role = await crud.get_admin_role(session, user_id)
        lang = await crud.get_user_language(session, user_id)

    if role is None:
        await query.answer("⛔ Sizda admin huquqi yo‘q!", show_alert=True)
        return

    is_super = role == "super_admin"
    data = query.data
    today = settings.today()

    if data == "admin:home":
        _ADMIN_INPUT_STATE.pop(user_id, None)
        await query.answer()
        await query.edit_message_text(
            text=_admin_home_text(role),
            parse_mode="HTML",
            reply_markup=get_admin_panel_keyboard(is_super_admin=is_super, lang=lang),
        )
        return

    # ==========================================================================
    # 📢 ADMIN BROADCAST SYSTEM CALLBACKS (Section 14)
    # ==========================================================================
    if data in {"admin:broadcast", "admin:bcast_edit"}:
        await query.answer()
        _ADMIN_INPUT_STATE[user_id] = "waiting_broadcast"
        text = (
            "📢 <b>Barcha foydalanuvchilarga xabar yuborish (Broadcast)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Yubormoqchi bo‘lgan xabaringizni shu yerga jo‘nating.\n\n"
            "✅ <b>Qo‘llab-quvvatlanadi:</b>\n"
            "• Oddiy matn (formatlash, emoji va havolalar bilan)\n"
            "• Rasm + caption\n"
            "• Video + caption\n"
            "• Audio va Voice message\n"
            "• Hujjat (PDF, DOCX va b.)\n"
            "• GIF animatsiya va Sticker\n\n"
            "<i>Xabar yuborishingiz bilan oldindan ko‘rish (Preview) oynasi chiqadi.</i>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_broadcast_wait_keyboard(),
        )
        return

    if data == "admin:bcast_cancel_input":
        _ADMIN_INPUT_STATE.pop(user_id, None)
        _ADMIN_BROADCAST_DRAFTS.pop(user_id, None)
        await query.answer("❌ Broadcast bekor qilindi.")
        await query.edit_message_text(
            text=_admin_home_text(role),
            parse_mode="HTML",
            reply_markup=get_admin_panel_keyboard(is_super_admin=is_super, lang=lang),
        )
        return

    if data == "admin:bcast_confirm":
        draft = _ADMIN_BROADCAST_DRAFTS.pop(user_id, None)
        if draft is None:
            await query.answer("⚠️ Xabar topilmadi. Qaytadan yuboring.", show_alert=True)
            return

        async with get_session() as session:
            running = await crud.get_running_broadcast(session)
            if running is not None or is_broadcast_running():
                await query.answer(
                    "⚠️ Hozirda boshqa broadcast tarqatilmoqda! U tugashini kuting.",
                    show_alert=True,
                )
                return

            bcast = await crud.create_broadcast_job(
                session=session,
                created_by=user_id,
                source_chat_id=draft.source_chat_id,
                source_message_id=draft.source_message_id,
                message_type=draft.message_type,
            )

        await query.answer("🚀 Broadcast tarqatish boshlandi!")
        launch_broadcast_task(context.bot, bcast.id)

        await query.edit_message_text(
            text=_format_broadcast_status_text(bcast),
            parse_mode="HTML",
            reply_markup=get_admin_broadcast_status_keyboard(
                bcast.id, is_running=True
            ),
        )
        return

    if data.startswith("admin:bcast_status:"):
        await query.answer("🔄 Yangilandi")
        parts = data.split(":")
        bcast_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        async with get_session() as session:
            bcast = await crud.get_broadcast_by_id(session, bcast_id)
        if bcast is None:
            return
        await query.edit_message_text(
            text=_format_broadcast_status_text(bcast),
            parse_mode="HTML",
            reply_markup=get_admin_broadcast_status_keyboard(
                bcast.id, is_running=(bcast.status == "running")
            ),
        )
        return

    if data.startswith("admin:bcast_stop:"):
        parts = data.split(":")
        bcast_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        stopped = await request_cancel_broadcast(bcast_id)
        await query.answer(
            "⏹ Yuborish to‘xtatildi!" if stopped else "ℹ️ Broadcast allaqachon yakunlangan."
        )
        async with get_session() as session:
            bcast = await crud.get_broadcast_by_id(session, bcast_id)
        if bcast:
            await query.edit_message_text(
                text=_format_broadcast_status_text(bcast),
                parse_mode="HTML",
                reply_markup=get_admin_broadcast_status_keyboard(
                    bcast.id, is_running=False
                ),
            )
        return

    if data == "admin:bcast_history":
        await query.answer()
        async with get_session() as session:
            history = await crud.get_recent_broadcasts(session, limit=10)

        if not history:
            body = "<i>Hozircha broadcast tarixi mavjud emas.</i>"
        else:
            h_lines: list[str] = []
            for b in history:
                started = (
                    b.started_at.strftime("%Y-%m-%d %H:%M") if b.started_at else "-"
                )
                ended = (
                    b.completed_at.strftime("%H:%M:%S") if b.completed_at else "..."
                )
                h_lines.append(
                    f"<b>#{b.id}</b> [{html.escape(b.status.upper())}] — <i>{html.escape(b.message_type)}</i>\n"
                    f"   🕒 {started} → {ended}\n"
                    f"   👥 Jami: <b>{b.total_recipients}</b> | ✅ <b>{b.success_count}</b> | ❌ <b>{b.failed_count}</b>"
                )
            body = "\n\n".join(h_lines)

        text = (
            f"📜 <b>Broadcast Tarixi (So‘nggi 10 ta)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{body}"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard("admin:home"),
        )
        return

    # ==========================================================================
    # 🎁 REFERRAL MANAGEMENT CALLBACKS (Section 10)
    # ==========================================================================
    if data == "admin:referrals":
        await query.answer()
        async with get_session() as session:
            ov = await crud.get_admin_referral_overview(session)

        text = (
            f"🎁 <b>Referral Tizimi Boshqaruvi</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Jami referral: <b>{ov['total']}</b>\n"
            f"✅ Tasdiqlangan referral: <b>{ov['confirmed']}</b>\n"
            f"⏳ Kutilayotgan referral: <b>{ov['pending']}</b>\n"
            f"🚫 Rad etilgan referral: <b>{ov['rejected']}</b>\n"
            f"⚠️ Shubhali referral: <b>{ov['suspicious']}</b>\n"
            f"🎁 Berilgan mukofotlar: <b>{ov['rewards_given']}</b>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_referral_keyboard(is_super_admin=is_super),
        )
        return

    if data == "admin:ref_top":
        await query.answer()
        async with get_session() as session:
            top_refs = await crud.get_top_referrers(session, limit=15)

        if not top_refs:
            body = "<i>Hozircha tasdiqlangan referrallar yo‘q.</i>"
        else:
            lines: list[str] = []
            for idx, (u, cnt) in enumerate(top_refs, start=1):
                uname = f"@{html.escape(u.username)}" if u.username else html.escape(u.full_name)
                lines.append(
                    f"{idx}. <b>{uname}</b> (<code>{u.user_id}</code>) — ✅ <b>{cnt} referrals</b>"
                )
            body = "\n".join(lines)

        text = (
            f"🏆 <b>Top Referrers (TOP-15)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{body}"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard("admin:referrals"),
        )
        return

    if data == "admin:ref_rewards":
        await query.answer()
        async with get_session() as session:
            rewards = await crud.get_recent_referral_rewards_for_admin(session, limit=12)

        if not rewards:
            body = "<i>Hozircha ochilgan mukofotlar yo‘q.</i>"
        else:
            r_lines: list[str] = []
            for r in rewards:
                ts = r.unlocked_at.strftime("%Y-%m-%d %H:%M") if r.unlocked_at else "-"
                r_lines.append(
                    f"🎁 User <code>{r.user_id}</code> — <b>{html.escape(r.reward_type)}</b> "
                    f"(Milestone: {r.milestone}) [{ts}]"
                )
            body = "\n".join(r_lines)

        text = (
            f"🎁 <b>Berilgan Referral Mukofotlari</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{body}"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard("admin:referrals"),
        )
        return

    if data.startswith("admin:ref_list:"):
        await query.answer()
        suspicious_only = data.endswith(":suspicious")
        async with get_session() as session:
            refs = await crud.get_referrals_list_for_admin(
                session, suspicious_only=suspicious_only, limit=10
            )

        title = (
            "🚫 <b>Shubhali Referrallar</b>"
            if suspicious_only
            else "⏳ <b>So‘nggi Referrallar</b>"
        )
        if not refs:
            body = "<i>Ro‘yxat bo‘sh.</i>"
        else:
            ref_lines: list[str] = []
            for r in refs:
                flag = " ⚠️ [SHUBHALI]" if r.is_suspicious else ""
                ref_lines.append(
                    f"<b>#{r.id}</b> [{html.escape(r.status.upper())}]{flag}\n"
                    f"   👤 Taklif qiluvchi: <code>{r.referrer_user_id}</code> → Yangi: <code>{r.referred_user_id}</code>"
                )
            body = "\n\n".join(ref_lines)

        await query.edit_message_text(
            text=f"{title}\n━━━━━━━━━━━━━━━━━━━━\n{body}",
            parse_mode="HTML",
            reply_markup=get_admin_referral_reject_keyboard(refs, "admin:referrals"),
        )
        return

    if data.startswith("admin:ref_reject:"):
        parts = data.split(":")
        ref_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        async with get_session() as session:
            rejected = await crud.reject_referral_by_id(session, ref_id)
            refs = await crud.get_referrals_list_for_admin(session, limit=10)

        if rejected:
            await query.answer(f"🚫 Referral #{ref_id} rad etildi!")
        else:
            await query.answer("⚠️ Referral topilmadi.", show_alert=True)

        ref_lines = [
            f"<b>#{r.id}</b> [{html.escape(r.status.upper())}]\n"
            f"   👤 <code>{r.referrer_user_id}</code> → <code>{r.referred_user_id}</code>"
            for r in refs
        ]
        await query.edit_message_text(
            text="⏳ <b>So‘nggi Referrallar</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            + ("\n\n".join(ref_lines) if ref_lines else "<i>Bo‘sh</i>"),
            parse_mode="HTML",
            reply_markup=get_admin_referral_reject_keyboard(refs, "admin:referrals"),
        )
        return

    if data == "admin:ref_milestones":
        if not is_super:
            await query.answer("⛔ Faqat Super Admin milestone qiymatlarini o‘zgartira oladi!", show_alert=True)
            return
        await query.answer()
        async with get_session() as session:
            packs = list(
                (
                    await session.execute(
                        select(BonusPack).order_by(BonusPack.id)
                    )
                )
                .scalars()
                .all()
            )
        text = (
            "⚙️ <b>Referral Milestone Qiymatlarini Sozlash</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Har bir bonus pack ochilishi uchun talab etiladigan tasdiqlangan referrallar sonini ➖ va ➕ tugmalari orqali o‘zgartirishingiz mumkin:"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_milestones_keyboard(packs),
        )
        return

    if data.startswith("admin:ref_ms_set:"):
        if not is_super:
            await query.answer("⛔ Faqat Super Admin!", show_alert=True)
            return
        parts = data.split(":")
        pack_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        new_val = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
        async with get_session() as session:
            await crud.update_bonus_pack_milestone(session, pack_id, new_val)
            packs = list(
                (
                    await session.execute(
                        select(BonusPack).order_by(BonusPack.id)
                    )
                )
                .scalars()
                .all()
            )
        await query.answer(f"✅ Yangilandi: {new_val} ta referral")
        await query.edit_message_text(
            text=(
                "⚙️ <b>Referral Milestone Qiymatlarini Sozlash</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Har bir bonus pack ochilishi uchun talab etiladigan tasdiqlangan referrallar soni:"
            ),
            parse_mode="HTML",
            reply_markup=get_admin_milestones_keyboard(packs),
        )
        return

    # ==========================================================================
    # 👑 MULTI-ADMIN SYSTEM CALLBACKS (Section 15 — SUPER ADMIN ONLY)
    # ==========================================================================
    if data.startswith("admin:admins"):
        if not is_super:
            await query.answer(
                "⛔ Faqat Super Admin adminlarni boshqara oladi!",
                show_alert=True,
            )
            return

        if data == "admin:admins":
            _ADMIN_INPUT_STATE.pop(user_id, None)
            await query.answer()
            async with get_session() as session:
                mods = await crud.get_active_moderators(session)

            mod_info = (
                f"🛡 Qo‘shimcha Admin (Moderator): <code>{mods[0].telegram_id}</code>"
                if mods
                else "🛡 Qo‘shimcha Admin (Moderator): <i>Qo‘shilmagan (0/1)</i>"
            )
            text = (
                f"👑 <b>Adminlar Boshqaruvi (Multi-Admin System)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 Super Admin (Owner): <code>{settings.ADMIN_ID}</code>\n"
                f"{mod_info}\n\n"
                f"<i>Eslatma: Maksimal 1 ta qo‘shimcha Moderator tayinlash mumkin.</i>"
            )
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=get_super_admin_management_keyboard(),
            )
            return

        if data == "admin:admins_add":
            async with get_session() as session:
                mods = await crud.get_active_moderators(session)
            if len(mods) >= 1:
                await query.answer(
                    "⚠️ Maksimal 1 ta qo‘shimcha admin mavjud! Avval uni o‘chiring.",
                    show_alert=True,
                )
                return

            await query.answer()
            _ADMIN_INPUT_STATE[user_id] = "waiting_new_admin_id"
            await query.edit_message_text(
                text=(
                    "➕ <b>Yangi admin qo‘shish</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Yangi adminning Telegram ID raqamini yuboring.\n\n"
                    "<i>⚠️ Eslatma: Yangi admin avval botga kirib /start bosgan bo‘lishi kerak.</i>"
                ),
                parse_mode="HTML",
                reply_markup=get_admin_back_keyboard("admin:admins"),
            )
            return

        if data.startswith("admin:admins_confirm_add:"):
            parts = data.split(":")
            cand_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            async with get_session() as session:
                record, status = await crud.appoint_moderator_admin(
                    session=session,
                    candidate_telegram_id=cand_id,
                    added_by_super_admin_id=user_id,
                )
                cand_lang = await crud.get_user_language(session, cand_id)

            if record is None:
                await query.answer(f"⚠️ Xatolik: {status}", show_alert=True)
                return

            await query.answer("✅ Yangi Moderator tayinlandi!")
            await query.edit_message_text(
                text=(
                    f"✅ <b>Yangi Admin muvaffaqiyatli tayinlandi!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 Telegram ID: <code>{cand_id}</code>\n"
                    f"🔐 Role: <b>Moderator</b>"
                ),
                parse_mode="HTML",
                reply_markup=get_admin_back_keyboard("admin:admins"),
            )

            # Notify new Moderator and refresh their main ReplyKeyboard with 🔐 Admin panel
            try:
                await context.bot.send_message(
                    chat_id=cand_id,
                    text=(
                        "👑 <b>Tabriklaymiz!</b> Sizga <b>Moderator (Admin)</b> huquqi berildi.\n"
                        "Endi menyudagi <b>🔐 Admin panel</b> tugmasi yoki /admin buyrug‘i orqali boshqaruv paneliga kirishingiz mumkin!"
                    ),
                    parse_mode="HTML",
                    reply_markup=get_main_menu_keyboard(
                        lang=cand_lang,
                        user_id=cand_id,
                        is_admin_override=True,
                    ),
                )
            except Exception as exc:
                logger.warning("Could not send moderator promotion message to %s: %s", cand_id, exc)
            return

        if data == "admin:admins_list":
            await query.answer()
            async with get_session() as session:
                mods = await crud.get_active_moderators(session)
                lines = [
                    f"1. 👑 <b>Super Admin (Owner)</b> — <code>{settings.ADMIN_ID}</code> (.env)"
                ]
                for idx, m in enumerate(mods, start=2):
                    u = await crud.get_user_by_telegram_id(session, m.telegram_id)
                    uname = (
                        f" (@{html.escape(u.username)})"
                        if u and u.username
                        else (f" ({html.escape(u.full_name)})" if u else "")
                    )
                    lines.append(
                        f"{idx}. 🛡 <b>Moderator</b> — <code>{m.telegram_id}</code>{uname}"
                    )

            await query.edit_message_text(
                text=(
                    "👥 <b>Adminlar Ro‘yxati</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    + "\n\n".join(lines)
                ),
                parse_mode="HTML",
                reply_markup=get_admin_back_keyboard("admin:admins"),
            )
            return

        if data == "admin:admins_remove_menu":
            async with get_session() as session:
                mods = await crud.get_active_moderators(session)
                if not mods:
                    await query.answer(
                        "ℹ️ Hozirda qo‘shimcha Moderator mavjud emas.",
                        show_alert=True,
                    )
                    return
                mod = mods[0]
                u = await crud.get_user_by_telegram_id(session, mod.telegram_id)

            await query.answer()
            uname = (
                f"@{html.escape(u.username)}"
                if u and u.username
                else html.escape(u.full_name if u else "Moderator")
            )
            await query.edit_message_text(
                text=(
                    f"🗑 <b>Adminni o‘chirishni tasdiqlang</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 Foydalanuvchi: <b>{uname}</b>\n"
                    f"🆔 Telegram ID: <code>{mod.telegram_id}</code>\n"
                    f"🔐 Role: <b>Moderator</b>\n\n"
                    f"<i>ℹ️ Adminlik huquqi olib tashlanganda foydalanuvchining IELTS akkaunti, XP, streak va referral natijalari to‘liq saqlanib qoladi.</i>"
                ),
                parse_mode="HTML",
                reply_markup=get_remove_admin_confirm_keyboard(mod.telegram_id),
            )
            return

        if data.startswith("admin:admins_confirm_rm:"):
            parts = data.split(":")
            mod_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            async with get_session() as session:
                removed, reason = await crud.remove_moderator_admin(
                    session=session,
                    moderator_telegram_id=mod_id,
                    removed_by_super_admin_id=user_id,
                )
                mod_lang = await crud.get_user_language(session, mod_id)

            if not removed:
                await query.answer(f"⚠️ Xatolik: {reason}", show_alert=True)
                return

            await query.answer("✅ Moderator adminlikdan o‘chirildi.")
            await query.edit_message_text(
                text=(
                    f"✅ <b>Moderator (<code>{mod_id}</code>) admin huquqidan o‘chirildi.</b>\n"
                    f"Uning oddiy foydalanuvchi akkaunti va barcha o‘quv natijalari saqlab qolindi."
                ),
                parse_mode="HTML",
                reply_markup=get_admin_back_keyboard("admin:admins"),
            )

            try:
                await context.bot.send_message(
                    chat_id=mod_id,
                    text="ℹ️ Sizning Moderator (Admin) huquqingiz Super Admin tomonidan yakunlandi. Barcha o‘quv natijalaringiz, XP va streak saqlab qolindi!",
                    parse_mode="HTML",
                    reply_markup=get_main_menu_keyboard(
                        lang=mod_lang,
                        user_id=mod_id,
                        is_admin_override=False,
                    ),
                )
            except Exception:
                pass
            return

    # ==========================================================================
    # EXISTING ADMIN PANEL SECTIONS (AI Generator, Vocab, Lesson, Stats, Users)
    # ==========================================================================
    if data in {"admin:ai_status", "admin:ai_replenish_reserve"}:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from services.gemini_free_tier_policy import gemini_quota_tracker

        async with get_session() as session:
            if data == "admin:ai_replenish_reserve":
                await query.answer("⏳ Free Tier kvotasi doirasida zaxira tekshirilmoqda...")
                await ai_generator.gradually_replenish_vocabulary_reserve(session)
            else:
                await query.answer()

            unused_reserve = await ai_generator.ensure_postgres_reserve_seeded(session)
            summary = await crud.get_generation_summary(session)
            logs = await crud.get_recent_generation_logs(session, limit=5)

        snap = gemini_quota_tracker.get_dashboard_snapshot(
            whitelist=ai_generator.whitelist,
            reserve_unused_count=unused_reserve,
            reserve_target_min=settings.RESERVE_MIN_WORDS,
            reserve_target_max=settings.RESERVE_MAX_WORDS,
        )
        aq = snap["active_model_quota"]
        errs = snap["errors"]
        res_info = snap["reserve"]

        model_rows: list[str] = []
        for m_info in snap["models"]:
            st_icon = (
                "🟢"
                if m_info["status"] == "AVAILABLE"
                else ("⏳" if m_info["status"] == "COOLDOWN_429" else "🔴")
            )
            model_rows.append(
                f"   {st_icon} <code>{html.escape(m_info['model'])}</code> — "
                f"RPD: <b>{m_info['rpd_used']}/{m_info['rpd_limit']}</b> "
                f"(qoldi: <b>{m_info['rpd_remaining']}</b>)"
            )
        models_block = "\n".join(model_rows)

        log_lines: list[str] = []
        for log in logs:
            ts = log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else "-"
            status_icon = (
                "✅"
                if log.generation_status in {"SUCCESS", "FALLBACK_RESERVE"}
                else ("ℹ️" if log.generation_status == "ALREADY_EXISTS" else "❌")
            )
            err_part = (
                f"\n   ⚠️ <i>{html.escape(log.error_message[:100])}</i>"
                if log.error_message
                else ""
            )
            log_lines.append(
                f"{status_icon} <b>{log.lesson_date}</b> [{html.escape(log.generation_status)}] — "
                f"📚 {log.generated_count} | ♻️ {log.rejected_duplicates} | 🔄 {log.retry_count} ({ts}){err_part}"
            )

        logs_block = (
            "\n".join(log_lines)
            if log_lines
            else "<i>Hozircha generatsiya tarixi yo‘q.</i>"
        )
        ai_state_str = (
            "🟡 Vaqtincha to‘xtatilgan (PostgreSQL Reserve Mode)"
            if snap["ai_temporarily_disabled"]
            else "🟢 Faol (Google AI Studio Free Tier)"
        )
        last_err_line = (
            f"\n   • So‘nggi xato: <code>{html.escape(str(errs['last_error']))}</code>"
            if errs.get("last_error")
            else ""
        )

        text = (
            f"🤖 <b>GEMINI FREE TIER — API MONITORING DASHBOARD</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 Siyosat: <b>{html.escape(snap['billing_policy'])}</b>\n"
            f"🛡 Pullik API'lar bloklangan: <b>Ha ✅ ($0.00 kafolat)</b>\n"
            f"📡 AI Holati: <b>{ai_state_str}</b>\n"
            f"🧠 Faol Free Tier Model: <code>{html.escape(snap['active_model'])}</code>\n"
            f"🔑 API Key: <b>{'Sozlangan ✅' if ai_generator._has_valid_api_key() else 'Zaxira (Reserve) rejim ⚠️'}</b>\n\n"
            f"📊 <b>Bugungi So‘rovlar va Qolgan Free Tier Kvota ({snap['date']}):</b>\n"
            f"• Bugungi jami so‘rovlar: <b>{snap['total_requests_today']} ta</b> (✅ Muvaffaqiyatli: <b>{snap['successful_requests_today']}</b>)\n"
            f"• Sarflangan tokenlar (bugun): <b>{snap['total_tokens_today']:,}</b>\n"
            f"• Faol model RPD (kunlik): <b>{aq['rpd_used']}/{aq['rpd_limit']}</b> (Qolgan kvota: <b>{aq['rpd_remaining']} so‘rov</b>)\n"
            f"• Faol model RPM (daqiqalik): <b>{aq['rpm_used']}/{aq['rpm_limit']}</b> (Qolgan: <b>{aq['rpm_remaining']} RPM</b>)\n"
            f"• Faol model TPM (token/daq): <b>{aq['tpm_used']:,}/{aq['tpm_limit']:,}</b>\n"
            f"• Umumiy Free Tier qolgan RPD: <b>{snap['combined_free_rpd_remaining']:,} / {snap['combined_free_rpd_limit']:,}</b>\n\n"
            f"⚠️ <b>API Xatolar Monitoringi (Bugun):</b>\n"
            f"• 404 (Model topilmadi): <b>{errs['errors_404']}</b> | 429 (Kvota limiti): <b>{errs['errors_429']}</b>\n"
            f"• Validatsiya rad etgan: <b>{errs['errors_validation']}</b> | Boshqa: <b>{errs['errors_other']}</b>"
            f"{last_err_line}\n\n"
            f"🏦 <b>PostgreSQL Lug‘at Zaxirasi (100–300 maqsad):</b>\n"
            f"• Ishlatilmagan noyob zaxira: <b>{res_info['unused_count']} ta</b> "
            f"({'✅ Normada' if res_info['healthy'] else '⏳ To‘ldirilmoqda'}: {res_info['target_min']}–{res_info['target_max']})\n"
            f"• Bugungi zaxiraga murojaatlar: <b>{res_info['fallbacks_today']} marta</b>\n\n"
            f"📋 <b>Tasdiqlangan Free Tier Modellar Whitelist:</b>\n"
            f"{models_block}\n\n"
            f"📜 <b>Bazadagi umumiy tarix ({summary['total_runs']} run | {summary['total_generated']} so‘z):</b>\n"
            f"{logs_block}"
        ).replace(",", " ")

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔄 Monitoringni yangilash", callback_data="admin:ai_status"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏦 Zaxirani +10 ta boyitish (Free Tier)",
                        callback_data="admin:ai_replenish_reserve",
                    )
                ],
                [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin:home")],
            ]
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    if data.startswith("admin:vocab:"):
        await query.answer()
        parts = data.split(":")
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
        page_size = 8

        async with get_session() as session:
            items, total = await crud.get_vocabulary_paginated(
                session, page=page, page_size=page_size
            )

        total_pages = max(1, math.ceil(total / page_size))
        lines_v: list[str] = []
        for v in items:
            lines_v.append(
                f"<b>#{v.id}. {html.escape(v.advanced_word)}</b> ({html.escape(v.cefr_level)} | {html.escape(v.category)})\n"
                f"   🔹 Simple: {html.escape(v.simple_word)}\n"
                f"   🔑 Normalized: <code>{html.escape(v.normalized_expression)}</code>\n"
                f"   🇺🇿 {html.escape(v.translation_uz)}\n"
                f"   🇷🇺 {html.escape(v.translation_ru)}"
            )

        body = (
            "\n\n".join(lines_v)
            if lines_v
            else "<i>Bazaga hali vocabulary qo‘shilmagan.</i>"
        )
        text = (
            f"📚 <b>Barcha C1–C2 Vocabulary ({total} ta noyob ibora)</b>\n"
            f"Sahifa: <b>{page}/{total_pages}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{body}"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_vocab_pagination_keyboard(page, total_pages),
        )
        return

    if data == "admin:today_lesson":
        await query.answer()
        async with get_session() as session:
            words = await crud.get_daily_lesson_words(session, today)

        if not words:
            text = (
                f"📅 <b>Bugungi dars ({today})</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ Bugungi dars hali generatsiya qilinmagan.\n"
                f"Pastdagi <b>🔄 Yangi darsni generatsiya qilish</b> tugmasini bosib yaratishingiz mumkin."
            )
        else:
            w_lines: list[str] = []
            for idx, w in enumerate(words, start=1):
                w_lines.append(
                    f"<b>{idx}. {html.escape(w.advanced_word)}</b> ({html.escape(w.cefr_level)}) — {html.escape(w.simple_word)}\n"
                    f"   🇺🇿 {html.escape(w.translation_uz)} | 🇷🇺 {html.escape(w.translation_ru)}"
                )
            text = (
                f"📅 <b>Bugungi dars ({today}) — {len(words)} ta ibora</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                + "\n\n".join(w_lines)
            )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard(),
        )
        return

    if data == "admin:stats":
        await query.answer()
        async with get_session() as session:
            stats = await crud.get_bot_statistics(session, today)
            gen_sum = await crud.get_generation_summary(session)
            ref_ov = await crud.get_admin_referral_overview(session)

        lc = stats["lang_counts"]
        text = (
            f"📊 <b>Bot Umumiy Statistikasi</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
            f"✅ Faol foydalanuvchilar: <b>{stats['active_users']}</b>\n\n"
            f"🌍 <b>Tillar bo‘yicha taqsimot:</b>\n"
            f"• 🇺🇿 O‘zbekcha: <b>{lc.get('uz', 0)}</b>\n"
            f"• 🇷🇺 Русский: <b>{lc.get('ru', 0)}</b>\n"
            f"• 🇬🇧 English: <b>{lc.get('en', 0)}</b>\n\n"
            f"🎁 <b>Referral ko‘rsatkichlari:</b>\n"
            f"• Jami takliflar: <b>{ref_ov['total']}</b> (✅ Tasdiqlangan: <b>{ref_ov['confirmed']}</b>)\n"
            f"• Ochilgan mukofotlar: <b>{ref_ov['rewards_given']}</b>\n\n"
            f"📚 <b>Vocabulary va Darslar:</b>\n"
            f"• Jami noyob C1–C2 iboralar: <b>{stats['total_vocab']} ta</b>\n"
            f"• Jami kunlik darslar: <b>{stats['total_lessons']} kun</b>\n"
            f"• Rad etilgan takroriy iboralar: <b>{gen_sum['total_rejected']} ta</b>\n\n"
            f"📅 <b>Bugungi faollik ({today}):</b>\n"
            f"• So‘zlarni yodlaganlar: <b>{stats['today_memorized']} kishi</b>\n"
            f"• Quizni yakunlaganlar: <b>{stats['today_completed']} kishi</b>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard(),
        )
        return

    if data == "admin:users":
        await query.answer()
        async with get_session() as session:
            top_users = await crud.get_top_users(session, limit=15)

        if not top_users:
            body = "<i>Hozircha foydalanuvchilar yo‘q.</i>"
        else:
            u_lines: list[str] = []
            for idx, u in enumerate(top_users, start=1):
                status_icon = "🟢" if u.is_active else "🔴"
                uname = f" (@{html.escape(u.username)})" if u.username else ""
                u_lines.append(
                    f"{idx}. {status_icon} <b>{html.escape(u.full_name)}</b>{uname}\n"
                    f"   🆔 <code>{u.user_id}</code> | 💎 {u.xp} XP | 🔥 {u.streak} kun | 🧠 {u.total_quizzes} quiz"
                )
            body = "\n\n".join(u_lines)

        text = (
            f"👥 <b>Foydalanuvchilar (TOP-15)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{body}"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard(),
        )
        return

    if data == "admin:generate":
        async with get_session() as session:
            existing_lesson = await crud.get_daily_lesson_by_date(session, today)
            if existing_lesson is not None:
                await query.answer(
                    f"ℹ️ Bugungi ({today}) dars allaqachon mavjud! Ikkinchi marta yaratilmaydi.",
                    show_alert=True,
                )
                words = await crud.get_daily_lesson_words(session, today)
                text = (
                    f"ℹ️ <b>Bugungi dars ({today}) allaqachon yaratilgan!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Qoidaga muvofiq bir kun uchun dars ikki marta generatsiya qilinmaydi.\n"
                    f"Bugungi darsda <b>{len(words)} ta</b> noyob C1–C2 ibora mavjud."
                )
                await query.edit_message_text(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=get_admin_back_keyboard(),
                )
                return

            await query.answer("⏳ Yangi 10 ta C1–C2 ibora generatsiya qilinmoqda...")
            gen_result = await ai_generator.generate_daily_lesson(
                session=session,
                target_date=today,
                word_count=settings.DAILY_WORD_COUNT,
            )

        if gen_result.success:
            text = (
                f"✅ <b>Yangi kunlik dars muvaffaqiyatli yaratildi!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 Sana: <b>{today}</b>\n"
                f"🔹 Holat: <b>{html.escape(gen_result.status)}</b>\n"
                f"📚 Yaratilgan noyob iboralar: <b>{gen_result.generated_count} ta</b>\n"
                f"♻️ Rad etilgan takrorlar: <b>{gen_result.rejected_duplicates} ta</b>\n"
                f"🔄 Qayta urinishlar: <b>{gen_result.retry_count} ta</b>"
            )
        else:
            text = (
                f"❌ <b>Generatsiya muvaffaqiyatsiz tugadi!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 Sana: <b>{today}</b>\n"
                f"♻️ Rad etilgan takrorlar: <b>{gen_result.rejected_duplicates} ta</b>\n"
                f"⚠️ Xato: <code>{html.escape(str(gen_result.error_message))}</code>"
            )

        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard(),
        )
        return

    if data == "admin:settings":
        await query.answer()
        text = (
            f"⚙️ <b>Bot Tizim Sozlamalari (.env)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 Timezone: <code>{html.escape(settings.TIMEZONE)}</code>\n"
            f"🌅 Kunlik generatsiya vaqti: <b>{settings.DAILY_GENERATION_HOUR:02d}:{settings.DAILY_GENERATION_MINUTE:02d}</b>\n"
            f"☀️ Kunlik yuborish vaqti: <b>{settings.DAILY_SEND_HOUR:02d}:{settings.DAILY_SEND_MINUTE:02d}</b>\n"
            f"🌙 Kechki eslatma vaqti: <b>{settings.REMINDER_HOUR:02d}:{settings.REMINDER_MINUTE:02d}</b>\n\n"
            f"📚 Kunlik so‘zlar soni: <b>{settings.DAILY_WORD_COUNT} ta</b>\n"
            f"⏱ Quiz savol vaqti: <b>{settings.QUIZ_TIME_LIMIT} soniya</b>\n"
            f"⭐ Har bir to‘g‘ri javob: <b>+{settings.POINTS_PER_CORRECT_ANSWER} XP</b>\n"
            f"🌍 Standart til: <b>{html.escape(settings.DEFAULT_LANGUAGE)}</b>\n"
            f"🤖 AI Provider / Model: <b>{html.escape(settings.AI_PROVIDER)} / {html.escape(settings.AI_MODEL)}</b>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard(),
        )
        return
