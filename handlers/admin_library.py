import html
import io
import logging
import math
import os
from datetime import date
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from database import crud
from database.db import get_session
from services.admin_library_service import (
    admin_library_manager,
    filter_archive_items,
    generate_randomized_quiz_from_items,
)
from services.i18n import i18n

logger = logging.getLogger(__name__)

# Per-admin ephemeral UI state (authorized admins only; persistent progress lives in PostgreSQL)
_ADMIN_LIB_INPUT_STATE: dict[int, str] = {}
_ADMIN_ACTIVE_FILTER: dict[int, dict[str, str]] = {}
_ADMIN_FLASHCARD_VIEW: dict[int, dict[str, Any]] = {}
_ADMIN_QUIZ_SESSION: dict[int, dict[str, Any]] = {}
_ADMIN_LAST_WRONG_IDS: dict[int, list[int]] = {}

PAGE_SIZE = 8

MODE_LABELS_UZ: dict[str, str] = {
    "all": "📚 Barcha so‘zlar",
    "unmemorized": "⬜ Yodlanmagan so‘zlar",
    "memorized": "✅ Yodlangan so‘zlar",
    "difficult": "⚠️ Qiyin so‘zlar",
    "incorrect": "❌ Testda xato qilinganlar",
    "today": "📅 Bugungi so‘zlar",
    "last_7d": "🗓 Oxirgi 7 kunlik",
    "last_30d": "📆 Oxirgi 30 kunlik",
    "srs_due": "🔄 Takrorlash vaqti kelganlar",
    "custom": "🔎 Filtrlangan so‘zlar",
}

STATUS_ICONS: dict[str, str] = {
    "memorized": "✅",
    "difficult": "⚠️",
    "later": "⏳",
    "unmemorized": "⬜",
}


def _get_filter_for_admin(admin_id: int) -> dict[str, str]:
    return _ADMIN_ACTIVE_FILTER.setdefault(
        admin_id,
        {
            "mode": "all",
            "q": "",
            "category": "",
            "date_from": "",
            "date_to": "",
        },
    )


def _apply_admin_filter(
    items: list[dict[str, Any]], flt: dict[str, str]
) -> list[dict[str, Any]]:
    mode = flt.get("mode", "all")
    eff_mode = "all" if mode == "custom" else mode
    return filter_archive_items(
        items=items,
        mode=eff_mode,
        search_query=flt.get("q", ""),
        category=flt.get("category", ""),
        date_from=flt.get("date_from", ""),
        date_to=flt.get("date_to", ""),
    )


def _filter_summary_line(flt: dict[str, str]) -> str:
    parts: list[str] = [MODE_LABELS_UZ.get(flt.get("mode", "all"), flt.get("mode", "all"))]
    if flt.get("q"):
        parts.append(f"Qidiruv: «{html.escape(flt['q'])}»")
    if flt.get("category"):
        parts.append(f"Turkum: {html.escape(flt['category'])}")
    if flt.get("date_from") or flt.get("date_to"):
        d_from = flt.get("date_from") or "..."
        d_to = flt.get("date_to") or "..."
        parts.append(f"Sana: {html.escape(d_from)} — {html.escape(d_to)}")
    return " | ".join(parts)


async def _load_admin_context(
    user_id: int,
) -> tuple[str | None, str, list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
    """
    Strictly enforce backend admin authorization via PostgreSQL `admins` / `SUPER_ADMIN`
    and load the permanent vocabulary archive + personal progress for this admin.
    """
    async with get_session() as session:
        role = await crud.get_admin_role(session, user_id)
        if role is None:
            return None, "uz", [], {}, None
        lang = await crud.get_user_language(session, user_id)
        items, stats, saved_session = (
            await admin_library_manager.get_enriched_items_and_stats_pg(session, user_id)
        )
        return role, lang, items, stats, saved_session


def _build_hub_keyboard(
    lang: str, saved_session: dict[str, Any] | None
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if saved_session and saved_session.get("archive_ids"):
        cur = int(saved_session.get("current_index", 0)) + 1
        tot = int(saved_session.get("total", len(saved_session["archive_ids"])))
        rows.append(
            [
                InlineKeyboardButton(
                    f"▶️ Sessiyani davom ettirish ({min(cur, tot)}/{tot})",
                    callback_data="adm_lib:fc_resume",
                )
            ]
        )

    webapp_url = (
        os.getenv("WEBAPP_URL", "").strip()
        or os.getenv("RENDER_EXTERNAL_URL", "").strip()
    )
    if webapp_url.startswith("https://"):
        base = webapp_url.rstrip("/")
        rows.append(
            [
                InlineKeyboardButton(
                    "🚀 Mini App Kutubxona (3D Flashcards)",
                    web_app=WebAppInfo(url=f"{base}/?admin_lib=1"),
                )
            ]
        )

    rows.extend(
        [
            [
                InlineKeyboardButton(
                    i18n.t("admin_lib_sub_all", lang=lang),
                    callback_data="adm_lib:list:all:1",
                ),
                InlineKeyboardButton(
                    i18n.t("admin_lib_sub_memorize", lang=lang),
                    callback_data="adm_lib:mem_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    i18n.t("admin_lib_sub_quiz", lang=lang),
                    callback_data="adm_lib:quiz_menu",
                ),
                InlineKeyboardButton(
                    i18n.t("admin_lib_sub_search", lang=lang),
                    callback_data="adm_lib:search_prompt",
                ),
            ],
            [
                InlineKeyboardButton(
                    i18n.t("admin_lib_sub_date", lang=lang),
                    callback_data="adm_lib:dates",
                ),
                InlineKeyboardButton(
                    i18n.t("admin_lib_sub_revision", lang=lang),
                    callback_data="adm_lib:revision",
                ),
            ],
            [
                InlineKeyboardButton(
                    i18n.t("admin_lib_sub_stats", lang=lang),
                    callback_data="adm_lib:stats",
                ),
                InlineKeyboardButton(
                    i18n.t("admin_lib_sub_export", lang=lang),
                    callback_data="adm_lib:export_menu",
                ),
            ],
            [
                InlineKeyboardButton("🔙 Admin Panel", callback_data="admin:home"),
            ],
        ]
    )
    return InlineKeyboardMarkup(rows)


def _format_hub_text(lang: str, stats: dict[str, Any]) -> str:
    title = i18n.t("admin_lib_menu", lang=lang)
    return (
        f"🏛 <b>{html.escape(title)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Doimiy arxivdagi jami so‘zlar: <b>{stats['total_archived']} ta</b>\n"
        f"📅 Bugun qo‘shilgan: <b>+{stats['added_today']} ta</b> | Shu hafta: <b>+{stats['added_this_week']} ta</b>\n"
        f"✅ Yodlangan: <b>{stats['memorized_count']} ta</b> ({stats['completion_percentage']}%)\n"
        f"⬜ Yodlanmagan: <b>{stats['unmemorized_count']} ta</b> | ⚠️ Qiyin: <b>{stats['difficult_count']} ta</b>\n"
        f"🔄 Takrorlash kerak (SRS): <b>{stats['revision_due_count']} ta</b>\n"
        f"🎯 Test aniqligi: <b>{stats['quiz_accuracy']}%</b>\n\n"
        f"<i>Barcha so‘zlar har kuni avtomatik saqlanadi va hech qachon o‘chib ketmaydi. Bo‘limni tanlang:</i>"
    )


def _render_flashcard_view(
    item: dict[str, Any],
    idx: int,
    total: int,
    side: str,
    lang: str,
    mode_label: str,
) -> tuple[str, InlineKeyboardMarkup]:
    st_icon = STATUS_ICONS.get(item.get("admin_status", "unmemorized"), "⬜")
    header = (
        f"🧠 <b>FLASHCARD — {idx + 1}/{total}</b> | {st_icon}\n"
        f"📂 Rejim: <b>{html.escape(mode_label)}</b>\n"
        f"📅 Sana: <code>{html.escape(item['original_generation_date'])}</code> | "
        f"🏷 <code>{html.escape(item['category'])}</code> ({html.escape(item['cefr_level'])})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    if side == "front":
        body = (
            f"🔤 <b>FRONT (Oddiy inglizcha ifoda):</b>\n\n"
            f"👉 <b>{html.escape(item['basic_expression'])}</b>\n\n"
            f"✍️ <i>{html.escape(item.get('basic_example_en', ''))}</i>\n\n"
            f"💡 <i>Advanced ekvivalentni eslab ko‘ring, so‘ng kartani aylantiring:</i>"
        )
        flip_btn = InlineKeyboardButton(
            i18n.t("admin_fc_flip_back", lang=lang),
            callback_data="adm_lib:fc_flip:back",
        )
    else:
        ru_line = (
            f"🇷🇺 <b>Перевод:</b> {html.escape(item['translation_ru'])}\n"
            if item.get("translation_ru")
            else ""
        )
        body = (
            f"🔤 <b>BASIC:</b> {html.escape(item['basic_expression'])}\n"
            f"💎 <b>ADVANCED:</b> <code>{html.escape(item['advanced_expression'])}</code>\n\n"
            f"🇺🇿 <b>Tarjima:</b> {html.escape(item['translation_uz'])}\n"
            f"{ru_line}"
            f"📖 <b>Izoh va qo‘llanilishi:</b> <i>{html.escape(item['definition_en'])}</i>\n\n"
            f"🎓 <b>Misol:</b> <i>{html.escape(item['example_en'])}</i>\n"
            f"📚 <b>IELTS Usage:</b> <b>{html.escape(item.get('usage_context', 'Writing & Speaking'))}</b>"
        )
        flip_btn = InlineKeyboardButton(
            i18n.t("admin_fc_flip_front", lang=lang),
            callback_data="adm_lib:fc_flip:front",
        )

    nav_row: list[InlineKeyboardButton] = []
    if idx > 0:
        nav_row.append(
            InlineKeyboardButton(
                f"⬅️ {i18n.t('admin_fc_prev', lang=lang)}",
                callback_data="adm_lib:fc_nav:prev",
            )
        )
    if idx < total - 1:
        nav_row.append(
            InlineKeyboardButton(
                f"{i18n.t('admin_fc_next', lang=lang)} ➡️",
                callback_data="adm_lib:fc_nav:next",
            )
        )

    rows: list[list[InlineKeyboardButton]] = [
        [flip_btn],
        [
            InlineKeyboardButton(
                f"✅ {i18n.t('admin_fc_memorized', lang=lang)}",
                callback_data="adm_lib:fc_act:memorized",
            ),
            InlineKeyboardButton(
                f"⚠️ {i18n.t('admin_fc_difficult', lang=lang)}",
                callback_data="adm_lib:fc_act:difficult",
            ),
            InlineKeyboardButton(
                f"⏳ {i18n.t('admin_fc_later', lang=lang)}",
                callback_data="adm_lib:fc_act:later",
            ),
        ],
    ]
    if nav_row:
        rows.append(nav_row)
    rows.append(
        [
            InlineKeyboardButton(
                "💾 Saqlab menyuga qaytish", callback_data="adm_lib:home"
            )
        ]
    )
    return header + body, InlineKeyboardMarkup(rows)


def _render_quiz_question_view(
    q_state: dict[str, Any], feedback_banner: str = ""
) -> tuple[str, InlineKeyboardMarkup]:
    idx = int(q_state["index"])
    questions = q_state["questions"]
    total = len(questions)
    q = questions[idx]

    letters = ["A", "B", "C", "D"]
    opt_lines = [
        f"<b>{letters[i]})</b> {html.escape(opt)}"
        for i, opt in enumerate(q["options"])
    ]
    prefix = f"{feedback_banner}\n━━━━━━━━━━━━━━━━━━━━\n" if feedback_banner else ""
    text = (
        f"{prefix}"
        f"📝 <b>BARCHA SO‘ZLARDAN TEST — {idx + 1}/{total}</b>\n"
        f"🏷 <code>{html.escape(q['category'])}</code> | 📊 {html.escape(q['cefr_level'])}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔤 <b>«{html.escape(q['basic_expression'])}»</b>\n"
        f"🇺🇿 <i>({html.escape(q['translation_uz'])})</i>\n\n"
        f"Yuqoridagi oddiy ifodaning <b>Advanced IELTS</b> ekvivalentini toping:\n\n"
        + "\n".join(opt_lines)
    )

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("A", callback_data="adm_lib:q_ans:0"),
                InlineKeyboardButton("B", callback_data="adm_lib:q_ans:1"),
                InlineKeyboardButton("C", callback_data="adm_lib:q_ans:2"),
                InlineKeyboardButton("D", callback_data="adm_lib:q_ans:3"),
            ],
            [
                InlineKeyboardButton(
                    "⏹ Testni yakunlash va natijani ko‘rish",
                    callback_data="adm_lib:q_finish",
                )
            ],
        ]
    )
    return text, kb


async def _start_flashcard_session_for_admin(
    query: Any,
    user_id: int,
    lang: str,
    candidate_items: list[dict[str, Any]],
    mode: str,
    batch_size_raw: str,
) -> None:
    if not candidate_items:
        await query.answer("⚠️ Tanlangan rejimda so‘zlar topilmadi!", show_alert=True)
        return

    if batch_size_raw == "all":
        selected = candidate_items
    else:
        limit = int(batch_size_raw) if batch_size_raw.isdigit() else 10
        selected = candidate_items[: max(1, limit)]

    archive_ids = [int(x["id"]) for x in selected]
    async with get_session() as session:
        await admin_library_manager.save_learning_session_pg(
            session=session,
            admin_id=user_id,
            mode=mode,
            archive_ids=archive_ids,
            current_index=0,
            filter_meta=_get_filter_for_admin(user_id),
        )

    _ADMIN_FLASHCARD_VIEW[user_id] = {
        "mode": mode,
        "archive_ids": archive_ids,
        "index": 0,
        "side": "front",
    }
    text, kb = _render_flashcard_view(
        item=selected[0],
        idx=0,
        total=len(selected),
        side="front",
        lang=lang,
        mode_label=MODE_LABELS_UZ.get(mode, mode),
    )
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)


async def _render_paginated_list_message(
    edit_or_reply: Any,
    user_id: int,
    items: list[dict[str, Any]],
    page: int,
    is_callback: bool = True,
) -> None:
    flt = _get_filter_for_admin(user_id)
    filtered = _apply_admin_filter(items, flt)
    total = len(filtered)
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(page, total_pages))

    slice_items = filtered[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    if not slice_items:
        body = "<i>Ushbu filtr bo‘yicha so‘zlar topilmadi.</i>"
    else:
        lines: list[str] = []
        for idx, it in enumerate(slice_items, start=(page - 1) * PAGE_SIZE + 1):
            st_icon = STATUS_ICONS.get(it.get("admin_status", "unmemorized"), "⬜")
            lines.append(
                f"{idx}. {st_icon} <b>{html.escape(it['basic_expression'])}</b> ➡️ "
                f"<code>{html.escape(it['advanced_expression'])}</code>\n"
                f"   🇺🇿 {html.escape(it['translation_uz'])} | 📅 {html.escape(it['original_generation_date'])} | 🏷 {html.escape(it['category'])}"
            )
        body = "\n\n".join(lines)

    text = (
        f"📚 <b>Doimiy Lug‘at Arxivi ({total} ta so‘z)</b>\n"
        f"🔍 Filtr: <b>{_filter_summary_line(flt)}</b>\n"
        f"📄 Sahifa: <b>{page}/{total_pages}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{body}"
    )

    nav: list[InlineKeyboardButton] = []
    mode_key = flt.get("mode", "all")
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                "⬅️ Oldingi", callback_data=f"adm_lib:list:{mode_key}:{page - 1}"
            )
        )
    nav.append(
        InlineKeyboardButton(f"{page}/{total_pages}", callback_data="lesson:noop")
    )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                "Keyingi ➡️", callback_data=f"adm_lib:list:{mode_key}:{page + 1}"
            )
        )

    rows: list[list[InlineKeyboardButton]] = [nav]
    if total > 0:
        rows.append(
            [
                InlineKeyboardButton(
                    f"🧠 Yodlash ({total} ta)",
                    callback_data=f"adm_lib:size_menu:{mode_key}",
                ),
                InlineKeyboardButton(
                    "📝 Test ishlash",
                    callback_data=f"adm_lib:quiz_size:{mode_key}",
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    "📥 Shu ro‘yxatni eksport qilish",
                    callback_data="adm_lib:exp_cur_menu",
                )
            ]
        )
    rows.append([InlineKeyboardButton("🔙 Kutubxona menyusi", callback_data="adm_lib:home")])
    kb = InlineKeyboardMarkup(rows)

    if is_callback:
        await edit_or_reply.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
    else:
        await edit_or_reply.reply_text(text=text, parse_mode="HTML", reply_markup=kb)


async def handle_admin_library_text_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """
    Handles text inputs from authorized admins when searching vocabulary,
    entering a custom date range (`YYYY-MM-DD..YYYY-MM-DD`), or specifying a custom quiz question count.
    """
    if not update.effective_user or not update.message or not update.message.text:
        return False

    user_id = update.effective_user.id
    input_mode = _ADMIN_LIB_INPUT_STATE.get(user_id)
    if not input_mode:
        return False

    role, lang, items, _, _ = await _load_admin_context(user_id)
    if role is None:
        _ADMIN_LIB_INPUT_STATE.pop(user_id, None)
        return False

    raw = update.message.text.strip()

    # 1. Instant Search Input
    if input_mode == "search":
        _ADMIN_LIB_INPUT_STATE.pop(user_id, None)
        _ADMIN_ACTIVE_FILTER[user_id] = {
            "mode": "custom",
            "q": raw,
            "category": "",
            "date_from": "",
            "date_to": "",
        }
        await _render_paginated_list_message(
            update.message, user_id, items, page=1, is_callback=False
        )
        return True

    # 2. Custom Date or Date Range Input (YYYY-MM-DD or YYYY-MM-DD..YYYY-MM-DD)
    if input_mode == "custom_date":
        if ".." in raw:
            parts = [p.strip() for p in raw.split("..", 1)]
        elif " " in raw:
            parts = [p.strip() for p in raw.split(None, 1)]
        else:
            parts = [raw, raw]

        try:
            d_from = date.fromisoformat(parts[0])
            d_to = date.fromisoformat(parts[1])
            if d_from > d_to:
                d_from, d_to = d_to, d_from
        except ValueError:
            await update.message.reply_text(
                "⚠️ <b>Sana formati noto‘g‘ri!</b>\n"
                "Namuna: <code>2026-11-22..2026-11-26</code> yoki bitta sana <code>2026-11-24</code>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_lib:dates")]]
                ),
            )
            return True

        _ADMIN_LIB_INPUT_STATE.pop(user_id, None)
        _ADMIN_ACTIVE_FILTER[user_id] = {
            "mode": "custom",
            "q": "",
            "category": "",
            "date_from": str(d_from),
            "date_to": str(d_to),
        }
        await _render_paginated_list_message(
            update.message, user_id, items, page=1, is_callback=False
        )
        return True

    # 3. Custom Quiz Question Count Input
    if input_mode.startswith("custom_quiz:"):
        quiz_mode = input_mode.split(":", 1)[1]
        if not raw.isdigit() or int(raw) < 1:
            await update.message.reply_text(
                "⚠️ Iltimos, savollar sonini musbat butun son ko‘rinishida yozing (masalan: <code>25</code>):",
                parse_mode="HTML",
            )
            return True

        _ADMIN_LIB_INPUT_STATE.pop(user_id, None)
        req_count = min(int(raw), 500)
        flt = _get_filter_for_admin(user_id)
        if quiz_mode != "custom":
            candidates = filter_archive_items(items, mode=quiz_mode)
        else:
            candidates = _apply_admin_filter(items, flt)

        if not candidates:
            await update.message.reply_text(
                "⚠️ Ushbu bo‘limda test tuzish uchun so‘zlar topilmadi.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Kutubxona", callback_data="adm_lib:home")]]
                ),
            )
            return True

        questions = generate_randomized_quiz_from_items(
            candidate_items=candidates,
            all_archive_items=items,
            question_count=req_count,
        )
        _ADMIN_QUIZ_SESSION[user_id] = {
            "mode": quiz_mode,
            "questions": questions,
            "index": 0,
            "submissions": [],
        }
        q_text, q_kb = _render_quiz_question_view(_ADMIN_QUIZ_SESSION[user_id])
        await update.message.reply_text(text=q_text, parse_mode="HTML", reply_markup=q_kb)
        return True

    return False


async def admin_library_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    user_id = update.effective_user.id
    role, lang, items, stats, saved_session = await _load_admin_context(user_id)
    if role is None:
        await query.answer("⛔ Sizda admin huquqi yo‘q!", show_alert=True)
        return

    data = query.data
    items_by_id = {int(x["id"]): x for x in items}

    # --------------------------------------------------------------------------
    # 1. ADMIN LIBRARY HUB
    # --------------------------------------------------------------------------
    if data == "adm_lib:home":
        _ADMIN_LIB_INPUT_STATE.pop(user_id, None)
        await query.answer()
        await query.edit_message_text(
            text=_format_hub_text(lang, stats),
            parse_mode="HTML",
            reply_markup=_build_hub_keyboard(lang, saved_session),
        )
        return

    # --------------------------------------------------------------------------
    # 2. PAGINATED VOCABULARY BROWSER (`adm_lib:list:<mode>:<page>`)
    # --------------------------------------------------------------------------
    if data.startswith("adm_lib:list:"):
        await query.answer()
        parts = data.split(":")
        mode = parts[2] if len(parts) > 2 else "all"
        page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
        if mode != "custom":
            _ADMIN_ACTIVE_FILTER[user_id] = {
                "mode": mode,
                "q": "",
                "category": "",
                "date_from": "",
                "date_to": "",
            }
        await _render_paginated_list_message(query, user_id, items, page=page, is_callback=True)
        return

    # --------------------------------------------------------------------------
    # 3. MEMORIZATION MODES & SESSION SIZE SELECTOR (Section 5)
    # --------------------------------------------------------------------------
    if data == "adm_lib:mem_menu":
        await query.answer()
        cnt_unmem = stats["unmemorized_count"]
        cnt_mem = stats["memorized_count"]
        cnt_diff = stats["difficult_count"]
        cnt_inc = stats["incorrect_count"]
        cnt_today = stats["added_today"]
        cnt_7d = stats["added_this_week"]
        cnt_30d = stats["added_this_month"]

        rows: list[list[InlineKeyboardButton]] = []
        if saved_session and saved_session.get("archive_ids"):
            cur = int(saved_session.get("current_index", 0)) + 1
            tot = int(saved_session.get("total", len(saved_session["archive_ids"])))
            rows.append(
                [
                    InlineKeyboardButton(
                        f"▶️ Oxirgi sessiyani davom ettirish ({min(cur, tot)}/{tot})",
                        callback_data="adm_lib:fc_resume",
                    )
                ]
            )

        rows.extend(
            [
                [
                    InlineKeyboardButton(
                        f"📚 Barcha so‘zlar ({stats['total_archived']})",
                        callback_data="adm_lib:size_menu:all",
                    ),
                    InlineKeyboardButton(
                        f"⬜ Yodlanmagan ({cnt_unmem})",
                        callback_data="adm_lib:size_menu:unmemorized",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        f"✅ Yodlangan ({cnt_mem})",
                        callback_data="adm_lib:size_menu:memorized",
                    ),
                    InlineKeyboardButton(
                        f"⚠️ Qiyin so‘zlar ({cnt_diff})",
                        callback_data="adm_lib:size_menu:difficult",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        f"❌ Xato javob berilgan ({cnt_inc})",
                        callback_data="adm_lib:size_menu:incorrect",
                    ),
                    InlineKeyboardButton(
                        f"📅 Bugungi so‘zlar ({cnt_today})",
                        callback_data="adm_lib:size_menu:today",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        f"🗓 Oxirgi 7 kun ({cnt_7d})",
                        callback_data="adm_lib:size_menu:last_7d",
                    ),
                    InlineKeyboardButton(
                        f"📆 Oxirgi 30 kun ({cnt_30d})",
                        callback_data="adm_lib:size_menu:last_30d",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📅 Maxsus sana oralig‘i",
                        callback_data="adm_lib:custom_date_prompt",
                    ),
                    InlineKeyboardButton(
                        "🏷 Turkum (Category) bo‘yicha",
                        callback_data="adm_lib:cat_menu",
                    ),
                ],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="adm_lib:home")],
            ]
        )

        text = (
            "🧠 <b>SO‘ZLARNI YODLASH REJIMINI TANLANG</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Har bir admin uchun yodlash jarayoni va sessiyasi alohida saqlanadi.\n"
            "Kerakli to‘plamni tanlang:"
        )
        await query.edit_message_text(
            text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows)
        )
        return

    if data == "adm_lib:cat_menu":
        await query.answer()
        cats = stats.get("categories", {})
        rows: list[list[InlineKeyboardButton]] = []
        for cat_name, cnt in sorted(cats.items()):
            rows.append(
                [
                    InlineKeyboardButton(
                        f"🏷 {cat_name} ({cnt} ta)",
                        callback_data=f"adm_lib:set_cat:{cat_name}",
                    )
                ]
            )
        rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="adm_lib:mem_menu")])
        await query.edit_message_text(
            text="🏷 <b>Turkum (Category) bo‘yicha tanlang:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if data.startswith("adm_lib:set_cat:"):
        await query.answer()
        cat_name = data.split(":", 2)[2]
        _ADMIN_ACTIVE_FILTER[user_id] = {
            "mode": "custom",
            "q": "",
            "category": cat_name,
            "date_from": "",
            "date_to": "",
        }
        await _render_paginated_list_message(query, user_id, items, page=1, is_callback=True)
        return

    if data.startswith("adm_lib:size_menu:"):
        mode = data.split(":", 2)[2]
        flt = _get_filter_for_admin(user_id)
        candidates = (
            _apply_admin_filter(items, flt)
            if mode == "custom"
            else filter_archive_items(items, mode=mode)
        )
        avail = len(candidates)
        if avail == 0:
            await query.answer("⚠️ Ushbu rejimda hozircha so‘zlar yo‘q!", show_alert=True)
            return

        await query.answer()
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "10 ta", callback_data=f"adm_lib:fc_start:{mode}:10"
                    ),
                    InlineKeyboardButton(
                        "20 ta", callback_data=f"adm_lib:fc_start:{mode}:20"
                    ),
                    InlineKeyboardButton(
                        "50 ta", callback_data=f"adm_lib:fc_start:{mode}:50"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "100 ta", callback_data=f"adm_lib:fc_start:{mode}:100"
                    ),
                    InlineKeyboardButton(
                        f"♾ Barchasi ({avail} ta)",
                        callback_data=f"adm_lib:fc_start:{mode}:all",
                    ),
                ],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="adm_lib:mem_menu")],
            ]
        )
        await query.edit_message_text(
            text=(
                f"🎯 <b>Sessiya hajmini tanlang</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📂 Rejim: <b>{html.escape(MODE_LABELS_UZ.get(mode, mode))}</b>\n"
                f"📚 Mavjud so‘zlar: <b>{avail} ta</b>\n\n"
                f"Nechta so‘zdan iborat flashcard sessiyasini boshlaymiz?"
            ),
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    # --------------------------------------------------------------------------
    # 4. INTERACTIVE FLASHCARDS & RESUME SESSION (Section 6)
    # --------------------------------------------------------------------------
    if data.startswith("adm_lib:fc_start:"):
        _, _, mode, size_raw = data.split(":", 3)
        flt = _get_filter_for_admin(user_id)
        candidates = (
            _apply_admin_filter(items, flt)
            if mode == "custom"
            else filter_archive_items(items, mode=mode)
        )
        await query.answer("🧠 Flashcard sessiyasi boshlandi!")
        await _start_flashcard_session_for_admin(
            query, user_id, lang, candidates, mode, size_raw
        )
        return

    if data == "adm_lib:fc_resume":
        if not saved_session or not saved_session.get("archive_ids"):
            await query.answer("ℹ️ Saqlangan faol sessiya topilmadi.", show_alert=True)
            return
        aids = [int(x) for x in saved_session["archive_ids"] if int(x) in items_by_id]
        if not aids:
            await query.answer("⚠️ Sessiyadagi so‘zlar topilmadi.", show_alert=True)
            return
        idx = max(0, min(int(saved_session.get("current_index", 0)), len(aids) - 1))
        mode = str(saved_session.get("mode", "all"))
        _ADMIN_FLASHCARD_VIEW[user_id] = {
            "mode": mode,
            "archive_ids": aids,
            "index": idx,
            "side": "front",
        }
        await query.answer("▶️ Sessiya davom ettirilmoqda!")
        text, kb = _render_flashcard_view(
            item=items_by_id[aids[idx]],
            idx=idx,
            total=len(aids),
            side="front",
            lang=lang,
            mode_label=MODE_LABELS_UZ.get(mode, mode),
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("adm_lib:fc_flip:"):
        target_side = data.split(":", 2)[2]
        fc = _ADMIN_FLASHCARD_VIEW.get(user_id)
        if not fc and saved_session:
            aids = [int(x) for x in saved_session["archive_ids"] if int(x) in items_by_id]
            fc = {
                "mode": saved_session.get("mode", "all"),
                "archive_ids": aids,
                "index": min(int(saved_session.get("current_index", 0)), max(0, len(aids) - 1)),
                "side": target_side,
            }
            _ADMIN_FLASHCARD_VIEW[user_id] = fc
        if not fc or not fc.get("archive_ids"):
            await query.answer("⚠️ Sessiya topilmadi.", show_alert=True)
            return

        fc["side"] = target_side
        idx = int(fc["index"])
        aid = int(fc["archive_ids"][idx])
        await query.answer()
        text, kb = _render_flashcard_view(
            item=items_by_id[aid],
            idx=idx,
            total=len(fc["archive_ids"]),
            side=target_side,
            lang=lang,
            mode_label=MODE_LABELS_UZ.get(fc["mode"], fc["mode"]),
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("adm_lib:fc_nav:"):
        direction = data.split(":", 2)[2]
        fc = _ADMIN_FLASHCARD_VIEW.get(user_id)
        if not fc or not fc.get("archive_ids"):
            await query.answer("⚠️ Sessiya topilmadi.", show_alert=True)
            return
        aids = fc["archive_ids"]
        idx = int(fc["index"])
        new_idx = max(0, idx - 1) if direction == "prev" else min(len(aids) - 1, idx + 1)
        fc["index"] = new_idx
        fc["side"] = "front"

        async with get_session() as session:
            await admin_library_manager.save_learning_session_pg(
                session=session,
                admin_id=user_id,
                mode=fc["mode"],
                archive_ids=aids,
                current_index=new_idx,
            )

        await query.answer()
        text, kb = _render_flashcard_view(
            item=items_by_id[int(aids[new_idx])],
            idx=new_idx,
            total=len(aids),
            side="front",
            lang=lang,
            mode_label=MODE_LABELS_UZ.get(fc["mode"], fc["mode"]),
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        return

    if data.startswith("adm_lib:fc_act:"):
        action = data.split(":", 2)[2]  # memorized | difficult | later
        fc = _ADMIN_FLASHCARD_VIEW.get(user_id)
        if not fc or not fc.get("archive_ids"):
            await query.answer("⚠️ Sessiya topilmadi.", show_alert=True)
            return
        aids = fc["archive_ids"]
        idx = int(fc["index"])
        aid = int(aids[idx])

        async with get_session() as session:
            res = await admin_library_manager.update_flashcard_progress_pg(
                session=session,
                admin_id=user_id,
                archive_id=aid,
                action=action,
                session_index=idx,
            )

        toast_map = {
            "memorized": f"✅ Yodlandi! Keyingi takrorlash: {res['interval_days']} kundan keyin",
            "difficult": "⚠️ Qiyin so‘zlarga qo‘shildi (ertaga takrorlanadi)",
            "later": "⏳ Keyinroq ko‘rish uchun belgilandi",
        }
        await query.answer(toast_map.get(action, "✅ Saqlandi"))

        if idx >= len(aids) - 1:
            _ADMIN_FLASHCARD_VIEW.pop(user_id, None)
            done_text = (
                f"🎉 <b>Flashcard sessiyasi muvaffaqiyatli yakunlandi!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📚 Ko‘rib chiqilgan so‘zlar: <b>{len(aids)} ta</b>\n"
                f"📂 Rejim: <b>{html.escape(MODE_LABELS_UZ.get(fc['mode'], fc['mode']))}</b>\n\n"
                f"Endi shu so‘zlar bo‘yicha test ishlab bilimingizni mustahkamlashingiz mumkin:"
            )
            done_kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📝 Test ishlash",
                            callback_data=f"adm_lib:quiz_size:{fc['mode']}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🧠 Yana yodlash", callback_data="adm_lib:mem_menu"
                        ),
                        InlineKeyboardButton(
                            "🔙 Kutubxona", callback_data="adm_lib:home"
                        ),
                    ],
                ]
            )
            await query.edit_message_text(
                text=done_text, parse_mode="HTML", reply_markup=done_kb
            )
            return

        next_idx = idx + 1
        fc["index"] = next_idx
        fc["side"] = "front"
        next_item = dict(items_by_id[int(aids[next_idx])])
        text, kb = _render_flashcard_view(
            item=next_item,
            idx=next_idx,
            total=len(aids),
            side="front",
            lang=lang,
            mode_label=MODE_LABELS_UZ.get(fc["mode"], fc["mode"]),
        )
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
        return

    # --------------------------------------------------------------------------
    # 5. ALL VOCABULARY ABCD QUIZ & RETRY INCORRECT ANSWERS (Section 7)
    # --------------------------------------------------------------------------
    if data == "adm_lib:quiz_menu":
        await query.answer()
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"📚 Barcha so‘zlardan ({stats['total_archived']})",
                        callback_data="adm_lib:quiz_size:all",
                    )
                ],
                [
                    InlineKeyboardButton(
                        f"⬜ Yodlanmaganlardan ({stats['unmemorized_count']})",
                        callback_data="adm_lib:quiz_size:unmemorized",
                    ),
                    InlineKeyboardButton(
                        f"⚠️ Qiyin so‘zlardan ({stats['difficult_count']})",
                        callback_data="adm_lib:quiz_size:difficult",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        f"❌ Xato qilinganlardan ({stats['incorrect_count']})",
                        callback_data="adm_lib:quiz_size:incorrect",
                    ),
                    InlineKeyboardButton(
                        f"🔄 Takrorlash (SRS) ({stats['revision_due_count']})",
                        callback_data="adm_lib:quiz_size:srs_due",
                    ),
                ],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="adm_lib:home")],
            ]
        )
        await query.edit_message_text(
            text=(
                "📝 <b>BARCHA SO‘ZLARDAN INTERAKTIV TEST (ABCD)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Test bazadagi saqlangan so‘zlardan avtomatik (Gemini API limitini sarflamasdan) tuziladi.\n"
                "Qaysi so‘zlar bazasidan test ishlamoqchisiz?"
            ),
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    if data.startswith("adm_lib:quiz_size:"):
        mode = data.split(":", 2)[2]
        flt = _get_filter_for_admin(user_id)
        candidates = (
            _apply_admin_filter(items, flt)
            if mode == "custom"
            else filter_archive_items(items, mode=mode)
        )
        avail = len(candidates)
        if avail == 0:
            await query.answer("⚠️ Ushbu to‘plamda hozircha so‘zlar yo‘q!", show_alert=True)
            return

        await query.answer()
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "10 savol", callback_data=f"adm_lib:quiz_start:{mode}:10"
                    ),
                    InlineKeyboardButton(
                        "20 savol", callback_data=f"adm_lib:quiz_start:{mode}:20"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "50 savol", callback_data=f"adm_lib:quiz_start:{mode}:50"
                    ),
                    InlineKeyboardButton(
                        "100 savol", callback_data=f"adm_lib:quiz_start:{mode}:100"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "✍️ Maxsus savollar sonini kiritish",
                        callback_data=f"adm_lib:quiz_custom:{mode}",
                    )
                ],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="adm_lib:quiz_menu")],
            ]
        )
        await query.edit_message_text(
            text=(
                f"📝 <b>Savollar sonini tanlang</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📂 To‘plam: <b>{html.escape(MODE_LABELS_UZ.get(mode, mode))}</b>\n"
                f"📚 Mavjud so‘zlar: <b>{avail} ta</b>"
            ),
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    if data.startswith("adm_lib:quiz_custom:"):
        mode = data.split(":", 2)[2]
        _ADMIN_LIB_INPUT_STATE[user_id] = f"custom_quiz:{mode}"
        await query.answer()
        await query.edit_message_text(
            text=(
                "✍️ <b>Nechta savoldan iborat test tuzilsin?</b>\n"
                "Sonni xabar sifatida yozib yuboring (masalan: <code>15</code> yoki <code>40</code>):"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_lib:quiz_menu")]]
            ),
        )
        return

    if data.startswith("adm_lib:quiz_start:"):
        _, _, mode, count_str = data.split(":", 3)
        flt = _get_filter_for_admin(user_id)
        candidates = (
            _apply_admin_filter(items, flt)
            if mode == "custom"
            else filter_archive_items(items, mode=mode)
        )
        if not candidates:
            await query.answer("⚠️ So‘zlar topilmadi!", show_alert=True)
            return

        q_count = int(count_str) if count_str.isdigit() else 10
        questions = generate_randomized_quiz_from_items(
            candidate_items=candidates,
            all_archive_items=items,
            question_count=q_count,
        )
        _ADMIN_QUIZ_SESSION[user_id] = {
            "mode": mode,
            "questions": questions,
            "index": 0,
            "submissions": [],
        }
        await query.answer("🚀 Test boshlandi!")
        q_text, q_kb = _render_quiz_question_view(_ADMIN_QUIZ_SESSION[user_id])
        await query.edit_message_text(text=q_text, parse_mode="HTML", reply_markup=q_kb)
        return

    if data == "adm_lib:quiz_retry":
        wrong_ids = _ADMIN_LAST_WRONG_IDS.get(user_id, [])
        candidates = [items_by_id[aid] for aid in wrong_ids if aid in items_by_id]
        if not candidates:
            await query.answer("🎉 Xato javoblar qolmagan!", show_alert=True)
            return
        questions = generate_randomized_quiz_from_items(
            candidate_items=candidates,
            all_archive_items=items,
            question_count=len(candidates),
        )
        _ADMIN_QUIZ_SESSION[user_id] = {
            "mode": "retry_wrong",
            "questions": questions,
            "index": 0,
            "submissions": [],
        }
        await query.answer("🔄 Xatolar ustida test boshlandi!")
        q_text, q_kb = _render_quiz_question_view(_ADMIN_QUIZ_SESSION[user_id])
        await query.edit_message_text(text=q_text, parse_mode="HTML", reply_markup=q_kb)
        return

    if data.startswith("adm_lib:q_ans:") or data == "adm_lib:q_finish":
        q_sess = _ADMIN_QUIZ_SESSION.get(user_id)
        if not q_sess:
            await query.answer("⚠️ Faol test topilmadi.", show_alert=True)
            return

        feedback = ""
        if data.startswith("adm_lib:q_ans:"):
            opt_idx = int(data.split(":", 2)[2])
            cur_q = q_sess["questions"][int(q_sess["index"])]
            chosen_text = cur_q["options"][opt_idx]
            is_corr = opt_idx == int(cur_q["correct_option"])
            q_sess["submissions"].append(
                {
                    "archive_id": cur_q["archive_id"],
                    "selected_text": chosen_text,
                }
            )
            if is_corr:
                await query.answer("✅ To‘g‘ri javob!")
                feedback = (
                    f"✅ <b>Oldingi savol: TO‘G‘RI!</b>\n"
                    f"💎 <code>{html.escape(cur_q['advanced_expression'])}</code> — {html.escape(cur_q['translation_uz'])}\n"
                    f"💡 <i>{html.escape(cur_q['example_en'])}</i>"
                )
            else:
                await query.answer("❌ Xato! To‘g‘ri javob izohda ko‘rsatildi.")
                feedback = (
                    f"❌ <b>Oldingi savol: XATO</b> (Tanlandi: {html.escape(chosen_text)})\n"
                    f"✅ To‘g‘ri javob: <code>{html.escape(cur_q['advanced_expression'])}</code> — {html.escape(cur_q['translation_uz'])}\n"
                    f"📖 <i>{html.escape(cur_q['definition_en'])}</i>"
                )
            q_sess["index"] = int(q_sess["index"]) + 1
        else:
            await query.answer("🏁 Test yakunlandi")

        # Move to next question if not finished
        if (
            data != "adm_lib:q_finish"
            and int(q_sess["index"]) < len(q_sess["questions"])
        ):
            q_text, q_kb = _render_quiz_question_view(q_sess, feedback_banner=feedback)
            await query.edit_message_text(text=q_text, parse_mode="HTML", reply_markup=q_kb)
            return

        # Finish & persist quiz results
        _ADMIN_QUIZ_SESSION.pop(user_id, None)
        submissions = q_sess.get("submissions", [])
        if not submissions:
            await query.edit_message_text(
                text="ℹ️ Test javoblarsiz to‘xtatildi.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Kutubxona", callback_data="adm_lib:home")]]
                ),
            )
            return

        async with get_session() as session:
            result = await admin_library_manager.submit_admin_quiz_pg(
                session=session,
                admin_id=user_id,
                filter_mode=q_sess["mode"],
                submissions=submissions,
            )

        wrong_ids = result["wrong_archive_ids"]
        _ADMIN_LAST_WRONG_IDS[user_id] = wrong_ids
        wrong_details = [d for d in result["details"] if not d["is_correct"]]

        review_block = ""
        if wrong_details:
            w_lines = []
            for d in wrong_details[:10]:
                w_lines.append(
                    f"• <b>{html.escape(d['basic_expression'])}</b> ➡️ "
                    f"<code>{html.escape(d['advanced_expression'])}</code>\n"
                    f"  🇺🇿 {html.escape(d['translation_uz'])} | ❌ Tanlangan: <i>{html.escape(d['selected_text'])}</i>"
                )
            more = (
                f"\n<i>... va yana {len(wrong_details) - 10} ta xato so‘z</i>"
                if len(wrong_details) > 10
                else ""
            )
            review_block = (
                f"\n\n🧐 <b>Xatolar tahlili (Incorrect Answer Review):</b>\n"
                + "\n".join(w_lines)
                + more
            )

        res_rows: list[list[InlineKeyboardButton]] = []
        if wrong_ids:
            res_rows.append(
                [
                    InlineKeyboardButton(
                        f"🔄 Xatolarni qayta ishlash ({len(wrong_ids)} ta)",
                        callback_data="adm_lib:quiz_retry",
                    )
                ]
            )
        res_rows.append(
            [
                InlineKeyboardButton("📝 Yangi test", callback_data="adm_lib:quiz_menu"),
                InlineKeyboardButton("🔙 Kutubxona", callback_data="adm_lib:home"),
            ]
        )

        res_text = (
            f"🏁 <b>TEST YAKUNLANDI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ To‘g‘ri javoblar: <b>{result['correct_count']}/{result['question_count']}</b>\n"
            f"🎯 Aniqlik (Accuracy): <b>{result['accuracy']}%</b>\n"
            f"⚠️ Xato javoblar: <b>{len(wrong_ids)} ta</b> (avtomatik SRS takrorlashga qo‘shildi)"
            f"{review_block}"
        )
        await query.edit_message_text(
            text=res_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(res_rows)
        )
        return

    # --------------------------------------------------------------------------
    # 6. SEARCH & BROWSE BY DATE (Sections 4, 5, 11)
    # --------------------------------------------------------------------------
    if data == "adm_lib:search_prompt":
        _ADMIN_LIB_INPUT_STATE[user_id] = "search"
        await query.answer()
        await query.edit_message_text(
            text=(
                "🔍 <b>SO‘ZLARNI TEZKOR QIDIRISH</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Quyidagilardan istalgan birini yozib yuboring:\n"
                "• Oddiy so‘z (Basic expression)\n"
                "• Advanced ibora\n"
                "• O‘zbekcha yoki ruscha tarjima\n"
                "• Turkum (masalan: <code>phrasal_verb</code>, <code>collocation</code>)\n"
                "• Yaratilgan sana (masalan: <code>2026-11-24</code>)"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_lib:home")]]
            ),
        )
        return

    if data == "adm_lib:dates":
        await query.answer()
        dates_map = stats.get("dates", {})
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton(
                    f"📅 Bugun ({stats['added_today']})",
                    callback_data="adm_lib:list:today:1",
                ),
                InlineKeyboardButton(
                    f"🗓 7 kun ({stats['added_this_week']})",
                    callback_data="adm_lib:list:last_7d:1",
                ),
                InlineKeyboardButton(
                    f"📆 30 kun ({stats['added_this_month']})",
                    callback_data="adm_lib:list:last_30d:1",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📅 Maxsus sana oralig‘ini kiritish",
                    callback_data="adm_lib:custom_date_prompt",
                )
            ],
        ]
        for d_str, cnt in list(dates_map.items())[:8]:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"📆 {d_str} — {cnt} ta so‘z",
                        callback_data=f"adm_lib:set_date:{d_str}",
                    )
                ]
            )
        rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="adm_lib:home")])
        await query.edit_message_text(
            text=(
                "📅 <b>SANA BO‘YICHA SO‘ZLAR</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Tayyor davrni yoki aniq generatsiya sanasini tanlang:"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if data.startswith("adm_lib:set_date:"):
        await query.answer()
        d_str = data.split(":", 2)[2]
        _ADMIN_ACTIVE_FILTER[user_id] = {
            "mode": "custom",
            "q": "",
            "category": "",
            "date_from": d_str,
            "date_to": d_str,
        }
        await _render_paginated_list_message(query, user_id, items, page=1, is_callback=True)
        return

    if data == "adm_lib:custom_date_prompt":
        _ADMIN_LIB_INPUT_STATE[user_id] = "custom_date"
        await query.answer()
        await query.edit_message_text(
            text=(
                "📅 <b>MAXSUS SANA ORALIG‘I</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Boshlanish va tugash sanasini <code>YYYY-MM-DD..YYYY-MM-DD</code> formatida yuboring:\n\n"
                "Namuna: <code>2026-11-22..2026-11-26</code>"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_lib:dates")]]
            ),
        )
        return

    # --------------------------------------------------------------------------
    # 7. SMART REVISION / SPACED REPETITION (Section 8)
    # --------------------------------------------------------------------------
    if data == "adm_lib:revision":
        await query.answer()
        due_cnt = stats["revision_due_count"]
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"🧠 Flashcard orqali takrorlash ({due_cnt} ta)",
                        callback_data="adm_lib:size_menu:srs_due",
                    )
                ],
                [
                    InlineKeyboardButton(
                        f"📝 Takrorlash testi ({due_cnt} ta)",
                        callback_data="adm_lib:quiz_size:srs_due",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📋 Takrorlash navbatini ko‘rish",
                        callback_data="adm_lib:list:srs_due:1",
                    )
                ],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="adm_lib:home")],
            ]
        )
        await query.edit_message_text(
            text=(
                "🔄 <b>AQLLI TAKRORLASH TIZIMI (SPACED REPETITION)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📐 Intervallar: <b>1 kun → 3 kun → 7 kun → 14 kun → 30 kun</b>\n\n"
                f"🔔 Hozir takrorlash kerak: <b>{due_cnt} ta so‘z</b>\n"
                f"   • ⚠️ Qiyin deb belgilanganlar: <b>{stats['difficult_count']} ta</b>\n"
                f"   • ❌ Testda xato qilinganlar: <b>{stats['incorrect_count']} ta</b>\n\n"
                "<i>Tizim birinchi navbatda qiyin va testda xato qilingan so‘zlarni chiqaradi.</i>"
            ),
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    # --------------------------------------------------------------------------
    # 8. REAL ADMIN MEMORIZATION STATISTICS (Section 10)
    # --------------------------------------------------------------------------
    if data == "adm_lib:stats":
        await query.answer()
        cat_lines = "\n".join(
            f"   • <code>{html.escape(k)}</code>: <b>{v} ta</b>"
            for k, v in sorted(stats.get("categories", {}).items())
        )
        text = (
            f"📊 <b>YODLASH VA ARXIV STATISTIKASI (REAL DB)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Jami arxivlangan so‘zlar: <b>{stats['total_archived']} ta</b>\n"
            f"📅 Bugun qo‘shilgan: <b>{stats['added_today']} ta</b>\n"
            f"🗓 Shu hafta qo‘shilgan: <b>{stats['added_this_week']} ta</b>\n"
            f"📆 Shu oy qo‘shilgan: <b>{stats['added_this_month']} ta</b>\n\n"
            f"✅ Yodlangan so‘zlar: <b>{stats['memorized_count']} ta</b>\n"
            f"⬜ Yodlanmagan so‘zlar: <b>{stats['unmemorized_count']} ta</b>\n"
            f"⚠️ Qiyin so‘zlar: <b>{stats['difficult_count']} ta</b>\n"
            f"🔄 Takrorlash talab qilinadigan: <b>{stats['revision_due_count']} ta</b>\n"
            f"🎯 Quiz aniqligi: <b>{stats['quiz_accuracy']}%</b> ({stats['total_quizzes_taken']} ta test)\n"
            f"🏆 Umumiy o‘zlashtirish ko‘rsatkichi: <b>{stats['completion_percentage']}%</b>\n\n"
            f"🏷 <b>Turkumlar kesimida:</b>\n{cat_lines}"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔄 Yangilash", callback_data="adm_lib:stats"
                        ),
                        InlineKeyboardButton(
                            "🔙 Kutubxona", callback_data="adm_lib:home"
                        ),
                    ]
                ]
            ),
        )
        return

    # --------------------------------------------------------------------------
    # 9. EXPORT IN CSV / XLSX / PDF (Section 11)
    # --------------------------------------------------------------------------
    if data in {"adm_lib:export_menu", "adm_lib:exp_cur_menu"}:
        await query.answer()
        flt = _get_filter_for_admin(user_id)
        cur_filtered = _apply_admin_filter(items, flt)
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📄 CSV (Barchasi)", callback_data="adm_lib:exp:all:csv"
                    ),
                    InlineKeyboardButton(
                        "📊 XLSX (Barchasi)", callback_data="adm_lib:exp:all:xlsx"
                    ),
                    InlineKeyboardButton(
                        "📕 PDF (Barchasi)", callback_data="adm_lib:exp:all:pdf"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        f"📄 CSV (Filtr: {len(cur_filtered)})",
                        callback_data="adm_lib:exp:filtered:csv",
                    ),
                    InlineKeyboardButton(
                        f"📊 XLSX (Filtr: {len(cur_filtered)})",
                        callback_data="adm_lib:exp:filtered:xlsx",
                    ),
                    InlineKeyboardButton(
                        f"📕 PDF (Filtr: {len(cur_filtered)})",
                        callback_data="adm_lib:exp:filtered:pdf",
                    ),
                ],
                [InlineKeyboardButton("🔙 Kutubxona", callback_data="adm_lib:home")],
            ]
        )
        await query.edit_message_text(
            text=(
                f"📥 <b>LUG‘AT ARXIVINI EKSPORT QILISH</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 Jami arxiv: <b>{len(items)} ta so‘z</b>\n"
                f"🔍 Joriy filtr ({_filter_summary_line(flt)}): <b>{len(cur_filtered)} ta so‘z</b>\n\n"
                f"Kerakli formatni tanlang (CSV, Excel XLSX yoki PDF):"
            ),
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    if data.startswith("adm_lib:exp:"):
        _, _, scope, fmt = data.split(":", 3)
        export_items = (
            items
            if scope == "all"
            else _apply_admin_filter(items, _get_filter_for_admin(user_id))
        )
        if not export_items:
            await query.answer("⚠️ Eksport qilish uchun so‘zlar topilmadi!", show_alert=True)
            return

        await query.answer(f"⏳ {fmt.upper()} fayl tayyorlanmoqda...")
        file_bytes, _, filename = admin_library_manager.build_export_bytes(
            export_items, fmt=fmt
        )
        if query.message:
            await query.message.reply_document(
                document=io.BytesIO(file_bytes),
                filename=filename,
                caption=(
                    f"📥 <b>Shoxrux AI — Doimiy Lug‘at Arxivi ({fmt.upper()})</b>\n"
                    f"📚 Eksport qilingan so‘zlar: <b>{len(export_items)} ta</b>"
                ),
                parse_mode="HTML",
            )
        return
