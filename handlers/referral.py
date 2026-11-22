import html
from typing import Any
from telegram import Bot, Update
from telegram.ext import ContextTypes

from database import crud
from database.db import get_session
from keyboards.inline import (
    get_bonus_pack_card_keyboard,
    get_my_rewards_keyboard,
    get_referral_back_keyboard,
    get_referral_dashboard_keyboard,
)
from keyboards.reply import get_main_menu_keyboard
from services.i18n import i18n

_CACHED_BOT_USERNAME: str | None = None


async def _get_bot_username(bot: Bot) -> str:
    global _CACHED_BOT_USERNAME
    if _CACHED_BOT_USERNAME:
        return _CACHED_BOT_USERNAME
    if bot.username:
        _CACHED_BOT_USERNAME = bot.username
        return _CACHED_BOT_USERNAME
    try:
        me = await bot.get_me()
        if me and me.username:
            _CACHED_BOT_USERNAME = me.username
            return _CACHED_BOT_USERNAME
    except Exception:
        pass
    return "IELTSMasterBot"


def build_personal_referral_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def _build_dashboard_text(
    lang: str,
    summary: dict[str, Any],
    referral_link: str,
) -> str:
    next_pack = summary["next_pack"]
    confirmed = summary["confirmed"]
    if next_pack is not None:
        next_reward_title = html.escape(next_pack.title)
        progress_str = f"{confirmed}/{next_pack.required_referrals}"
    else:
        next_reward_title = i18n.t("referral_all_unlocked", lang=lang)
        progress_str = f"{confirmed}/20 ✅"

    badge = summary.get("badge", "")
    badge_line = f"🏅 <b>Badge:</b> {html.escape(badge)}\n" if badge else ""

    return i18n.t(
        "referral_dashboard",
        lang=lang,
        invited=summary["invited"],
        confirmed=confirmed,
        unlocked_count=summary["unlocked_count"],
        next_reward=next_reward_title,
        progress=progress_str,
        badge_line=badge_line,
        referral_link=html.escape(referral_link),
    )


async def show_referral_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.effective_user:
        return

    tg_user = update.effective_user
    bot_username = await _get_bot_username(context.bot)
    ref_link = build_personal_referral_link(bot_username, tg_user.id)

    async with get_session() as session:
        _, user_settings, _ = await crud.get_or_create_user(
            session=session,
            user_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name or "Learner",
        )
        lang = user_settings.language_code
        summary = await crud.get_user_referral_summary(session, tg_user.id)

    text = _build_dashboard_text(lang, summary, ref_link)
    kb = get_referral_dashboard_keyboard(lang, ref_link)

    if update.message:
        await update.message.reply_text(
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
        )


async def referral_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    user_id = update.effective_user.id
    data = query.data

    if data == "referral:dashboard":
        await query.answer()
        await show_referral_menu(update, context)
        return

    async with get_session() as session:
        lang = await crud.get_user_language(session, user_id)

        if data == "referral:main_menu":
            await query.answer()
            is_admin = await crud.is_any_admin(session, user_id)
            main_kb = get_main_menu_keyboard(
                lang=lang, user_id=user_id, is_admin_override=is_admin
            )
            if query.message:
                await query.message.reply_text(
                    text=i18n.t(
                        "welcome_message",
                        lang=lang,
                        name=html.escape(
                            update.effective_user.full_name or "Learner"
                        ),
                    ),
                    parse_mode="HTML",
                    reply_markup=main_kb,
                )
            return

        if data == "referral:rewards":
            await query.answer()
            summary = await crud.get_user_referral_summary(session, user_id)
            text = i18n.t(
                "my_rewards_title",
                lang=lang,
                confirmed=summary["confirmed"],
            )
            kb = get_my_rewards_keyboard(
                lang=lang,
                packs=summary["packs"],
                unlocked_types=summary["unlocked_types"],
                confirmed_count=summary["confirmed"],
            )
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
            return

        if data.startswith("referral:pack:"):
            parts = data.split(":")
            pack_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            word_idx = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

            pack, words = await crud.get_bonus_pack_with_words(session, pack_id)
            if pack is None or not words:
                await query.answer("Pack not found.", show_alert=True)
                return

            # Server-side authorization check: prevent accessing locked packs
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
            word_idx = max(0, min(word_idx, len(words) - 1))
            prog = await crud.update_user_bonus_word_progress(
                session=session,
                user_id=user_id,
                pack_id=pack.id,
                viewed_count=word_idx + 1,
                total_words=len(words),
            )

            header = (
                i18n.t(
                    "pack_header",
                    lang=lang,
                    pack_title=html.escape(pack.title),
                    index=word_idx + 1,
                    total=len(words),
                    completed_words=prog.completed_words,
                    completed_quizzes=prog.completed_quizzes,
                )
                + "\n\n"
            )
            card_body = i18n.format_word_card(
                vocab=words[word_idx],
                lang=lang,
            )
            kb = get_bonus_pack_card_keyboard(
                lang=lang,
                pack_id=pack.id,
                current_index=word_idx,
                total=len(words),
            )
            await query.edit_message_text(
                text=header + card_body,
                parse_mode="HTML",
                reply_markup=kb,
            )
            return

        if data == "referral:stats":
            await query.answer()
            summary = await crud.get_user_referral_summary(session, user_id)
            confirmed = summary["confirmed"]
            unlocked_types = summary["unlocked_types"]
            ms_lines: list[str] = []
            for pack in summary["packs"]:
                is_open = (
                    pack.pack_type in unlocked_types
                    or confirmed >= pack.required_referrals
                )
                icon = "✅" if is_open else "🔒"
                ms_lines.append(
                    f"{icon} <b>{pack.required_referrals} ref</b> — {html.escape(pack.title)}"
                )

            status_badge = summary["badge"] or "🌱 Learner"
            text = i18n.t(
                "referral_stats_text",
                lang=lang,
                invited=summary["invited"],
                confirmed=confirmed,
                pending=summary["pending"],
                unlocked_count=summary["unlocked_count"],
                status_badge=html.escape(status_badge),
                milestones_list="\n".join(ms_lines),
            )
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=get_referral_back_keyboard(lang),
            )
            return

        if data == "referral:leaderboard":
            await query.answer()
            top_referrers = await crud.get_top_referrers(session, limit=10)
            user_rank, user_confirmed = await crud.get_user_referral_rank(
                session, user_id
            )

            if not top_referrers:
                text = i18n.t("referral_leaderboard_empty", lang=lang)
            else:
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                rows: list[str] = []
                for idx, (u, ref_cnt) in enumerate(top_referrers, start=1):
                    medal = medals.get(idx, f"<b>{idx}.</b>")
                    display_name = (
                        f"@{html.escape(u.username)}"
                        if u.username
                        else html.escape(u.full_name or f"User {u.user_id}")
                    )
                    special_badge = (
                        " 🏆" if ref_cnt >= 20 else (" 👑" if ref_cnt >= 10 else "")
                    )
                    rows.append(
                        f"{medal} <b>{display_name}</b>{special_badge} — <b>{ref_cnt} referrals</b>"
                    )
                text = i18n.t(
                    "referral_leaderboard_title",
                    lang=lang,
                    rows="\n".join(rows),
                    user_rank=user_rank,
                    user_confirmed=user_confirmed,
                )

            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=get_referral_back_keyboard(lang),
            )
            return
