import html
import logging
import os
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from database import crud
from database.db import get_session
from services.i18n import i18n
from services.mock_test_service import (
    ADMIN_SUPPORT_URL,
    ADMIN_SUPPORT_USERNAME,
    MOCK_TEST_CATEGORIES,
    format_price_uzs,
    mock_test_manager,
)

logger = logging.getLogger(__name__)

# In-memory wizard state for authorized admins (persistent data lives in PostgreSQL)
_ADMIN_MOCK_STATE: dict[int, dict[str, Any]] = {}

CATEGORY_ICONS: dict[str, str] = {
    "Reading": "📘",
    "Listening": "🎧",
    "Writing": "✍️",
    "Speaking": "🎙",
    "Full Mock Test": "🏛",
}


# ==============================================================================
# PUBLIC USER CATALOG & MY MOCK TESTS
# ==============================================================================


def _build_public_catalog_view(
    tests: list[dict[str, Any]], lang: str
) -> tuple[str, InlineKeyboardMarkup]:
    headers = {
        "uz": (
            "📝 <b>IELTS MOCK TEST KATALOGI</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Haqiqiy imtihon formatidagi Reading, Listening, Writing, Speaking va Full Mock Testlar.\n\n"
        ),
        "ru": (
            "📝 <b>КАТАЛОГ IELTS MOCK TEST</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Полные пробные тесты IELTS (Reading, Listening, Writing, Speaking и Full Mock Test).\n\n"
        ),
        "en": (
            "📝 <b>IELTS MOCK TEST CATALOG</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Exam-grade Reading, Listening, Writing, Speaking, and Full IELTS Mock Tests.\n\n"
        ),
    }
    header = headers.get(lang, headers["uz"])

    if not tests:
        empty_msg = {
            "uz": "<i>Hozircha faol Mock Testlar mavjud emas.</i>",
            "ru": "<i>Пока нет доступных Mock Test.</i>",
            "en": "<i>No published Mock Tests available yet.</i>",
        }
        body = empty_msg.get(lang, empty_msg["uz"])
    else:
        lines: list[str] = []
        for idx, t in enumerate(tests, start=1):
            cat_icon = CATEGORY_ICONS.get(t["category"], "📝")
            lock_badge = "🔓 Ochiq" if t["is_unlocked"] else "🔒 Yopiq"
            if lang == "ru":
                lock_badge = "🔓 Открыт" if t["is_unlocked"] else "🔒 Закрыт"
            elif lang == "en":
                lock_badge = "🔓 Unlocked" if t["is_unlocked"] else "🔒 Locked"

            lines.append(
                f"<b>{idx}. {cat_icon} {html.escape(t['title'])}</b> [{lock_badge}]\n"
                f"   🏷 {html.escape(t['category'])} | ⏱ {t['duration_minutes']} min | "
                f"❓ {t['questions_count']} savol\n"
                f"   💰 Narxi: <b>{html.escape(t['price_formatted'])}</b>\n"
                f"   📖 <i>{html.escape(t['description'][:130])}</i>"
            )
        body = "\n\n".join(lines)

    rows: list[list[InlineKeyboardButton]] = []
    for idx, t in enumerate(tests, start=1):
        status_icon = "🔓" if t["is_unlocked"] else "🔒"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{status_icon} #{idx} {t['title'][:34]} ({t['price_formatted']})",
                    callback_data=f"mock:view:{t['id']}",
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
                    "🚀 Mini App Mock Test Marketplace",
                    web_app=WebAppInfo(url=f"{base}/?mock_tests=1"),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                i18n.t("mock_btn_my_tests", lang=lang),
                callback_data="mock:my_tests",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                i18n.t("mock_btn_contact_admin", lang=lang),
                callback_data="mock:contact",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                i18n.t("mock_btn_back", lang=lang),
                callback_data="mock:back_main",
            )
        ]
    )
    return header + body, InlineKeyboardMarkup(rows)


async def show_mock_test_catalog(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    async with get_session() as session:
        lang = await crud.get_user_language(session, user_id)
        tests = await mock_test_manager.list_public_mock_tests_pg(session, user_id)

    text, kb = _build_public_catalog_view(tests, lang)
    await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=kb)


async def _deliver_protected_test_materials(
    query: Any,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    test_data: dict[str, Any],
    lang: str,
) -> None:
    intro = (
        f"🚀 <b>{html.escape(test_data['title'])}</b>\n"
        f"🏷 Turkum: <b>{html.escape(test_data['category'])}</b> | "
        f"⏱ Davomiyligi: <b>{test_data['duration_minutes']} daqiqa</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Ko‘rsatma (Instructions):</b>\n"
        f"{html.escape(test_data.get('instructions') or test_data['description'])}\n\n"
        f"📂 <b>Test materiallari va javoblar kaliti quyida yuborilmoqda:</b>"
    )
    await context.bot.send_message(chat_id=chat_id, text=intro, parse_mode="HTML")

    for mat in test_data.get("files", []):
        ftype = mat.get("file_type", "text")
        m_title = mat.get("title", "Mock Test Material")
        role_label = mat.get("material_role", "question_paper").replace("_", " ").upper()
        caption = f"📎 <b>[{html.escape(role_label)}] {html.escape(m_title)}</b>"
        fid = mat.get("telegram_file_id")

        try:
            if fid and ftype in ("pdf", "document"):
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=fid,
                    caption=caption,
                    parse_mode="HTML",
                )
            elif fid and ftype == "audio":
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=fid,
                    caption=caption,
                    parse_mode="HTML",
                )
            elif fid and ftype == "voice":
                await context.bot.send_voice(
                    chat_id=chat_id,
                    voice=fid,
                    caption=caption,
                    parse_mode="HTML",
                )
            elif fid and ftype == "image":
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=fid,
                    caption=caption,
                    parse_mode="HTML",
                )
            elif mat.get("text_content"):
                msg_text = (
                    f"{caption}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"{html.escape(str(mat['text_content']))}"
                )
                await context.bot.send_message(
                    chat_id=chat_id, text=msg_text, parse_mode="HTML"
                )
        except Exception as exc:
            logger.warning("Failed to deliver mock test material %s: %s", m_title, exc)


async def mock_user_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    user_id = update.effective_user.id
    data = query.data

    async with get_session() as session:
        lang = await crud.get_user_language(session, user_id)
        role = await crud.get_admin_role(session, user_id)
        is_admin = role is not None

        if data == "mock:catalog":
            await query.answer()
            tests = await mock_test_manager.list_public_mock_tests_pg(session, user_id)
            text, kb = _build_public_catalog_view(tests, lang)
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
            return

        if data == "mock:contact":
            await query.answer()
            support_text = (
                f"💬 <b>ADMIN BILAN BOG‘LANISH</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{html.escape(i18n.t('mock_support_message', lang=lang))}"
            )
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            i18n.t("mock_btn_write_admin", lang=lang),
                            url=ADMIN_SUPPORT_URL,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            i18n.t("mock_btn_back", lang=lang),
                            callback_data="mock:catalog",
                        )
                    ],
                ]
            )
            await query.edit_message_text(
                text=support_text, parse_mode="HTML", reply_markup=kb
            )
            return

        if data == "mock:my_tests":
            await query.answer()
            unlocked = await mock_test_manager.list_user_unlocked_tests_pg(
                session, user_id
            )
            if not unlocked:
                text = (
                    f"🔓 <b>{html.escape(i18n.t('mock_btn_my_tests', lang=lang))}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Sizda hozircha ochilgan Mock Testlar yo‘q.</i>\n\n"
                    f"{html.escape(i18n.t('mock_support_message', lang=lang))}"
                )
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                i18n.t("mock_btn_write_admin", lang=lang),
                                url=ADMIN_SUPPORT_URL,
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                i18n.t("mock_btn_back", lang=lang),
                                callback_data="mock:catalog",
                            )
                        ],
                    ]
                )
                await query.edit_message_text(
                    text=text, parse_mode="HTML", reply_markup=kb
                )
                return

            lines: list[str] = []
            rows: list[list[InlineKeyboardButton]] = []
            for idx, t in enumerate(unlocked, start=1):
                exp_str = (
                    t["access_expires_at"][:16].replace("T", " ")
                    if t.get("access_expires_at")
                    else "♾ Doimiy (Permanent)"
                )
                lines.append(
                    f"<b>{idx}. 🔓 {html.escape(t['title'])}</b>\n"
                    f"   🏷 {html.escape(t['category'])} | ⏱ {t['duration_minutes']} daqiqa\n"
                    f"   📅 Ruxsat muddati: <b>{html.escape(exp_str)}</b>"
                )
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"🚀 Boshlash: {t['title'][:26]}",
                            callback_data=f"mock:start:{t['id']}",
                        ),
                        InlineKeyboardButton(
                            "📥 Materiallar",
                            callback_data=f"mock:materials:{t['id']}",
                        ),
                    ]
                )

            rows.append(
                [
                    InlineKeyboardButton(
                        i18n.t("mock_btn_back", lang=lang),
                        callback_data="mock:catalog",
                    )
                ]
            )
            text = (
                f"🔓 <b>{html.escape(i18n.t('mock_btn_my_tests', lang=lang))} ({len(unlocked)} ta)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                + "\n\n".join(lines)
            )
            await query.edit_message_text(
                text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows)
            )
            return

        if data.startswith("mock:view:"):
            await query.answer()
            tid = int(data.split(":", 2)[2])
            tests = await mock_test_manager.list_public_mock_tests_pg(session, user_id)
            target = next((x for x in tests if int(x["id"]) == tid), None)
            if target is None:
                await query.answer("⚠️ Mock Test topilmadi.", show_alert=True)
                return

            cat_icon = CATEGORY_ICONS.get(target["category"], "📝")
            status_line = (
                "🔓 <b>Ochiq (Sizga ruxsat berilgan)</b>"
                if target["is_unlocked"]
                else "🔒 <b>Yopiq (Locked)</b>"
            )
            exp_line = (
                f"\n⏳ Muddati: <b>{html.escape(str(target['access_expires_at'])[:16].replace('T', ' '))}</b>"
                if target.get("access_expires_at")
                else ""
            )

            detail_text = (
                f"{cat_icon} <b>{html.escape(target['title'])}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷 Turkum: <b>{html.escape(target['category'])}</b>\n"
                f"💰 Narxi: <b>{html.escape(target['price_formatted'])}</b>\n"
                f"⏱ Davomiyligi: <b>{target['duration_minutes']} daqiqa</b>\n"
                f"❓ Savollar soni: <b>{target['questions_count']} ta</b>\n"
                f"📎 Materiallar: <b>{target['materials_count']} ta fayl/bo‘lim</b>\n"
                f"📌 Holati: {status_line}{exp_line}\n\n"
                f"📖 <b>Tavsif:</b>\n{html.escape(target['description'])}\n\n"
                f"ℹ️ <i>{html.escape(i18n.t('mock_support_message', lang=lang))}</i>"
            )

            rows = []
            if target["is_unlocked"]:
                rows.append(
                    [
                        InlineKeyboardButton(
                            i18n.t("mock_btn_start_test", lang=lang),
                            callback_data=f"mock:start:{tid}",
                        )
                    ]
                )
                rows.append(
                    [
                        InlineKeyboardButton(
                            i18n.t("mock_btn_download_materials", lang=lang),
                            callback_data=f"mock:materials:{tid}",
                        )
                    ]
                )
            else:
                rows.append(
                    [
                        InlineKeyboardButton(
                            i18n.t("mock_btn_write_admin", lang=lang),
                            url=ADMIN_SUPPORT_URL,
                        )
                    ]
                )

            rows.append(
                [
                    InlineKeyboardButton(
                        i18n.t("mock_btn_my_tests", lang=lang),
                        callback_data="mock:my_tests",
                    ),
                    InlineKeyboardButton(
                        i18n.t("mock_btn_contact_admin", lang=lang),
                        callback_data="mock:contact",
                    ),
                ]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        i18n.t("mock_btn_back", lang=lang),
                        callback_data="mock:catalog",
                    )
                ]
            )
            await query.edit_message_text(
                text=detail_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return

        if data.startswith(("mock:start:", "mock:materials:")):
            tid = int(data.split(":", 2)[2])
            ok, reason, protected_data = (
                await mock_test_manager.get_protected_materials_pg(
                    session, user_id, tid, is_admin=is_admin
                )
            )
            if not ok or protected_data is None:
                await query.answer(
                    f"🔒 Ushbu Mock Test yopiq! Ruxsat olish uchun {ADMIN_SUPPORT_USERNAME} bilan bog‘laning.",
                    show_alert=True,
                )
                return

            await query.answer("🚀 Mock Test materiallari yuborilmoqda...")
            if query.message:
                await _deliver_protected_test_materials(
                    query, context, query.message.chat_id, protected_data, lang
                )
            return

        if data == "mock:back_main":
            await query.answer()
            await query.edit_message_text(
                text="🏠 <b>Asosiy menyu</b> — quyidagi bo‘limlardan birini tanlang:",
                parse_mode="HTML",
            )
            return


# ==============================================================================
# ADMIN PANEL — MOCK TEST MANAGEMENT & 9-STEP WIZARD
# ==============================================================================


def _admin_mock_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Mock Test qo‘shish", callback_data="adm_mock:add_start"
                ),
                InlineKeyboardButton(
                    "💰 Narxini belgilash", callback_data="adm_mock:price_list"
                ),
            ],
            [
                InlineKeyboardButton(
                    "✏️ Mock Testni tahrirlash", callback_data="adm_mock:edit_list"
                ),
                InlineKeyboardButton(
                    "👤 Foydalanuvchiga Mock Test berish",
                    callback_data="adm_mock:grant_tests",
                ),
            ],
            [
                InlineKeyboardButton(
                    "👥 Testga ega foydalanuvchilar",
                    callback_data="adm_mock:holders:all",
                ),
                InlineKeyboardButton(
                    "🔒 Ruxsatni bekor qilish", callback_data="adm_mock:revoke_list"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📚 Barcha Mock Testlar", callback_data="adm_mock:all_tests"
                ),
                InlineKeyboardButton(
                    "🗑 Mock Testni o‘chirish", callback_data="adm_mock:del_list"
                ),
            ],
            [
                InlineKeyboardButton("🔙 Admin Panel", callback_data="admin:home"),
            ],
        ]
    )


def _format_wizard_preview(draft: dict[str, Any]) -> str:
    mats = draft.get("materials", [])
    mat_lines = [
        f"   {idx}. [{html.escape(m['file_type'].upper())} / {html.escape(m['material_role'])}] {html.escape(m['title'])}"
        for idx, m in enumerate(mats, start=1)
    ]
    mat_block = "\n".join(mat_lines) if mat_lines else "   <i>Materiallar yuklanmagan</i>"
    prev_img = "Ha ✅" if draft.get("preview_image_file_id") else "Yo‘q"

    return (
        f"👁 <b>8-QADAM: MOCK TEST PREVIEW</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Nomi: <b>{html.escape(draft.get('title', ''))}</b>\n"
        f"🏷 Turkum: <b>{html.escape(draft.get('category', 'Full Mock Test'))}</b>\n"
        f"💰 Narxi: <b>{html.escape(format_price_uzs(int(draft.get('price_uzs', 0))))}</b>\n"
        f"⏱ Davomiyligi: <b>{draft.get('duration_minutes', 60)} daqiqa</b>\n"
        f"❓ Savollar soni: <b>{draft.get('questions_count', 40)} ta</b>\n"
        f"🖼 Preview rasm: <b>{prev_img}</b>\n\n"
        f"📖 <b>Tavsif:</b>\n{html.escape(draft.get('description', ''))}\n\n"
        f"📂 <b>Yuklangan materiallar ({len(mats)} ta):</b>\n{mat_block}\n\n"
        f"<b>9-QADAM:</b> Barcha ma'lumotlar to‘g‘ri bo‘lsa, <b>✅ Tasdiqlash va Nashr qilish</b> tugmasini bosing:"
    )


async def handle_admin_mock_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """
    Handles text and media uploads (PDF, Audio, Voice, Image, Text) from authorized admins
    during the 9-step Add Mock Test workflow, Edit/Price workflow, or User Search/Custom Duration.
    """
    if not update.effective_user or not update.message:
        return False

    user_id = update.effective_user.id
    st = _ADMIN_MOCK_STATE.get(user_id)
    if not st:
        return False

    async with get_session() as session:
        role = await crud.get_admin_role(session, user_id)
        if role is None:
            _ADMIN_MOCK_STATE.pop(user_id, None)
            return False

        msg = update.message
        step = st.get("step", "")
        draft = st.setdefault("draft", {})

        # Step 1: Enter test name
        if step == "add_step1_name":
            if not msg.text or not msg.text.strip():
                await msg.reply_text("⚠️ Iltimos, Mock Test nomini matn ko‘rinishida yuboring:")
                return True
            draft["title"] = msg.text.strip()
            st["step"] = "add_step2_category"
            cat_rows = [
                [
                    InlineKeyboardButton(
                        f"{CATEGORY_ICONS.get(c, '📝')} {c}",
                        callback_data=f"adm_mock:set_cat:{c}",
                    )
                ]
                for c in MOCK_TEST_CATEGORIES
            ]
            cat_rows.append(
                [InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_mock:home")]
            )
            await msg.reply_text(
                f"✅ Nomi: <b>{html.escape(draft['title'])}</b>\n\n"
                f"<b>2-QADAM:</b> Mock Test turkumini (Category) tanlang:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(cat_rows),
            )
            return True

        # Step 3: Enter description
        if step == "add_step3_desc":
            if not msg.text or not msg.text.strip():
                await msg.reply_text("⚠️ Iltimos, test tavsifini (description) yozib yuboring:")
                return True
            draft["description"] = msg.text.strip()
            st["step"] = "add_step4_price"
            await msg.reply_text(
                "<b>4-QADAM:</b> Mock Test narxini so‘mda (UZS) kiriting (masalan: <code>45000</code> yoki bepul bo‘lsa <code>0</code>):",
                parse_mode="HTML",
            )
            return True

        # Step 4: Enter UZS price
        if step == "add_step4_price":
            raw_num = (msg.text or "").replace(" ", "").replace(",", "").strip()
            if not raw_num.isdigit():
                await msg.reply_text("⚠️ Narxni faqat raqam bilan kiriting (masalan: <code>45000</code>):", parse_mode="HTML")
                return True
            draft["price_uzs"] = int(raw_num)
            st["step"] = "add_step5_duration"
            await msg.reply_text(
                "<b>5-QADAM:</b> Test davomiyligini daqiqada kiriting (masalan: <code>60</code> yoki <code>165 84</code> — 165 daqiqa, 84 ta savol):",
                parse_mode="HTML",
            )
            return True

        # Step 5: Enter duration (& optional question count)
        if step == "add_step5_duration":
            parts = (msg.text or "").strip().split()
            if not parts or not parts[0].isdigit():
                await msg.reply_text("⚠️ Davomiylikni raqamda kiriting (masalan: <code>60</code>):", parse_mode="HTML")
                return True
            draft["duration_minutes"] = max(5, int(parts[0]))
            draft["questions_count"] = (
                int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 40
            )
            draft["materials"] = []
            st["step"] = "add_step6_materials"
            st["current_role"] = "question_paper"
            await msg.reply_text(
                "<b>6-QADAM: Test materiallarini yuklang</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Qo‘llab-quvvatlanadi:\n"
                "• 📄 PDF hujjatlar (Document)\n"
                "• 🎧 Audio / Voice fayllar\n"
                "• 🖼 Rasmlar (Photo)\n"
                "• 📝 Matn (savollar, javoblar varaqasi yoki Answer Key)\n\n"
                "Fayl yoki matnni ketma-ket yuboring. Yakunlagach pastdagi tugmani bosing:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "📄 Savollar", callback_data="adm_mock:role:question_paper"
                            ),
                            InlineKeyboardButton(
                                "🎧 Audio", callback_data="adm_mock:role:audio_track"
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                "📝 Answer Sheet", callback_data="adm_mock:role:answer_sheet"
                            ),
                            InlineKeyboardButton(
                                "🔑 Answer Key", callback_data="adm_mock:role:answer_key"
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                "✅ Materiallar yuklandi (7-qadamga o‘tish)",
                                callback_data="adm_mock:step7_preview_img",
                            )
                        ],
                    ]
                ),
            )
            return True

        # Step 6 (or Edit add material): Receive PDF, Audio, Image, or Text
        if step in ("add_step6_materials", "edit_add_material"):
            mat_role = st.get("current_role", "question_paper")
            mat_entry: dict[str, Any] | None = None

            if msg.document:
                is_pdf = (msg.document.mime_type or "").endswith("pdf")
                mat_entry = {
                    "file_type": "pdf" if is_pdf else "document",
                    "material_role": mat_role,
                    "title": msg.caption or msg.document.file_name or "PDF Document",
                    "telegram_file_id": msg.document.file_id,
                    "file_name": msg.document.file_name,
                    "mime_type": msg.document.mime_type,
                }
            elif msg.audio:
                mat_entry = {
                    "file_type": "audio",
                    "material_role": "audio_track",
                    "title": msg.caption or msg.audio.title or msg.audio.file_name or "Listening Audio",
                    "telegram_file_id": msg.audio.file_id,
                    "file_name": msg.audio.file_name,
                    "mime_type": msg.audio.mime_type,
                }
            elif msg.voice:
                mat_entry = {
                    "file_type": "voice",
                    "material_role": "audio_track",
                    "title": msg.caption or "Voice Audio Track",
                    "telegram_file_id": msg.voice.file_id,
                }
            elif msg.photo:
                mat_entry = {
                    "file_type": "image",
                    "material_role": mat_role,
                    "title": msg.caption or "Test Image Material",
                    "telegram_file_id": msg.photo[-1].file_id,
                }
            elif msg.text and msg.text.strip():
                mat_entry = {
                    "file_type": "text",
                    "material_role": mat_role,
                    "title": f"{mat_role.replace('_', ' ').title()} Text",
                    "text_content": msg.text.strip(),
                }

            if mat_entry is None:
                await msg.reply_text("⚠️ Iltimos, PDF, Audio, Rasm yoki Matn yuboring:")
                return True

            if step == "edit_add_material":
                tid = int(st["test_id"])
                await mock_test_manager.add_material_to_test_pg(
                    session, user_id, tid, mat_entry
                )
                _ADMIN_MOCK_STATE.pop(user_id, None)
                await msg.reply_text(
                    f"✅ Material Mock Test #{tid} ga muvaffaqiyatli qo‘shildi!",
                    reply_markup=_admin_mock_home_keyboard(),
                )
                return True

            mats = draft.setdefault("materials", [])
            mats.append(mat_entry)
            await msg.reply_text(
                f"✅ <b>Material #{len(mats)} qabul qilindi:</b> [{html.escape(mat_entry['file_type'].upper())} / {html.escape(mat_entry['material_role'])}]\n"
                f"Yana fayl yuborishingiz yoki 7-qadamga o‘tishingiz mumkin:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔑 Keyingisi: Answer Key",
                                callback_data="adm_mock:role:answer_key",
                            ),
                            InlineKeyboardButton(
                                "📝 Answer Sheet",
                                callback_data="adm_mock:role:answer_sheet",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                "➡️ 7-qadam: Preview rasm yuklash",
                                callback_data="adm_mock:step7_preview_img",
                            )
                        ],
                    ]
                ),
            )
            return True

        # Step 7: Optional preview image
        if step == "add_step7_preview_img":
            if msg.photo:
                draft["preview_image_file_id"] = msg.photo[-1].file_id
            st["step"] = "add_step8_preview"
            await msg.reply_text(
                text=_format_wizard_preview(draft),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✅ 9-QADAM: Tasdiqlash va Nashr qilish",
                                callback_data="adm_mock:publish_confirm",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "❌ Bekor qilish", callback_data="adm_mock:home"
                            )
                        ],
                    ]
                ),
            )
            return True

        # Update price in UZS
        if step == "set_price_uzs":
            raw_num = (msg.text or "").replace(" ", "").replace(",", "").strip()
            if not raw_num.isdigit():
                await msg.reply_text("⚠️ Narxni faqat raqamda kiriting (masalan: <code>50000</code>):", parse_mode="HTML")
                return True
            tid = int(st["test_id"])
            updated = await mock_test_manager.update_mock_test_pg(
                session, user_id, tid, {"price_uzs": int(raw_num)}
            )
            _ADMIN_MOCK_STATE.pop(user_id, None)
            await msg.reply_text(
                f"✅ Mock Test narxi yangilandi: <b>{html.escape(updated['price_formatted'] if updated else raw_num)}</b>",
                parse_mode="HTML",
                reply_markup=_admin_mock_home_keyboard(),
            )
            return True

        # Edit field (title / description / duration)
        if step.startswith("edit_field:"):
            field_name = step.split(":", 1)[1]
            tid = int(st["test_id"])
            val_raw = (msg.text or "").strip()
            if not val_raw:
                return True
            updates: dict[str, Any] = {}
            if field_name == "duration_minutes":
                if not val_raw.isdigit():
                    await msg.reply_text("⚠️ Daqiqani raqamda kiriting:")
                    return True
                updates["duration_minutes"] = int(val_raw)
            else:
                updates[field_name] = val_raw
            await mock_test_manager.update_mock_test_pg(session, user_id, tid, updates)
            _ADMIN_MOCK_STATE.pop(user_id, None)
            await msg.reply_text(
                f"✅ Mock Test #{tid} ma'lumoti yangilandi!",
                reply_markup=_admin_mock_home_keyboard(),
            )
            return True

        # Search registered users for granting access
        if step == "grant_search_user":
            tid = int(st["test_id"])
            q_str = (msg.text or "").strip()
            _ADMIN_MOCK_STATE.pop(user_id, None)
            users, total, _ = await mock_test_manager.search_registered_users_pg(
                session, query_str=q_str, page=1, page_size=8
            )
            rows: list[list[InlineKeyboardButton]] = []
            for u in users:
                uname = f" (@{u['username']})" if u.get("username") else ""
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"👤 {u['full_name'][:22]}{uname} [{u['user_id']}]",
                            callback_data=f"adm_mock:g_user:{tid}:{u['user_id']}",
                        )
                    ]
                )
            if q_str.isdigit() and not any(int(u["user_id"]) == int(q_str) for u in users):
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"🆔 Bevosita ID: {q_str} ga berish",
                            callback_data=f"adm_mock:g_user:{tid}:{q_str}",
                        )
                    ]
                )
            rows.append(
                [
                    InlineKeyboardButton(
                        "🔙 Orqaga", callback_data=f"adm_mock:g_test:{tid}:1"
                    )
                ]
            )
            await msg.reply_text(
                f"🔍 <b>Qidiruv natijalari ({total} ta):</b> «{html.escape(q_str)}»\n"
                f"Foydalanuvchini tanlang:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return True

        # Custom access duration in days
        if step == "grant_custom_days":
            raw_days = (msg.text or "").strip()
            if not raw_days.isdigit() or int(raw_days) < 1:
                await msg.reply_text("⚠️ Kunlar sonini musbat butun son bilan kiriting (masalan: <code>14</code>):", parse_mode="HTML")
                return True
            tid = int(st["test_id"])
            target_uid = int(st["target_user_id"])
            _ADMIN_MOCK_STATE.pop(user_id, None)
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"✅ Tasdiqlash ({raw_days} kun)",
                            callback_data=f"adm_mock:g_exec:{tid}:{target_uid}:custom:{raw_days}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ Bekor qilish", callback_data="adm_mock:home"
                        )
                    ],
                ]
            )
            await msg.reply_text(
                f"📋 <b>Ruxsatni tasdiqlang:</b>\n"
                f"👤 Foydalanuvchi ID: <code>{target_uid}</code>\n"
                f"📝 Mock Test ID: <b>#{tid}</b>\n"
                f"⏳ Muddat: <b>{raw_days} kun</b>",
                parse_mode="HTML",
                reply_markup=kb,
            )
            return True

    return False


async def admin_mock_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    user_id = update.effective_user.id
    data = query.data

    async with get_session() as session:
        role = await crud.get_admin_role(session, user_id)
        if role is None:
            await query.answer("⛔ Sizda admin huquqi yo‘q!", show_alert=True)
            return

        all_tests = await mock_test_manager.list_all_mock_tests_admin_pg(session)
        tests_by_id = {int(t["id"]): t for t in all_tests}

        # 1. Admin Mock Test Home
        if data == "adm_mock:home":
            _ADMIN_MOCK_STATE.pop(user_id, None)
            await query.answer()
            holders = await mock_test_manager.list_access_holders_pg(session)
            text = (
                f"📝 <b>MOCK TEST BOSHQARUVI</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📚 Jami Mock Testlar: <b>{len(all_tests)} ta</b>\n"
                f"👥 Ruxsat berilgan faol foydalanuvchilar: <b>{len(holders)} ta</b>\n"
                f"💬 Qo‘llab-quvvatlash: <b>{ADMIN_SUPPORT_USERNAME}</b>\n\n"
                f"👇 Kerakli boshqaruv bo‘limini tanlang:"
            )
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=_admin_mock_home_keyboard(),
            )
            return

        # 2. Start 9-Step Add Mock Test Wizard
        if data == "adm_mock:add_start":
            _ADMIN_MOCK_STATE[user_id] = {"step": "add_step1_name", "draft": {}}
            await query.answer()
            await query.edit_message_text(
                text=(
                    "➕ <b>YANGI MOCK TEST QO‘SHISH (1/9 QADAM)</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "<b>1-QADAM:</b> Mock Test nomini yozib yuboring\n"
                    "<i>(Masalan: IELTS Academic Reading Mock #2)</i>:"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_mock:home")]]
                ),
            )
            return

        if data.startswith("adm_mock:set_cat:"):
            cat = data.split(":", 2)[2]
            st = _ADMIN_MOCK_STATE.setdefault(user_id, {"draft": {}})
            st["draft"]["category"] = cat
            st["step"] = "add_step3_desc"
            await query.answer(f"Turkum: {cat}")
            await query.edit_message_text(
                text=(
                    f"✅ Turkum: <b>{html.escape(cat)}</b>\n\n"
                    f"<b>3-QADAM:</b> Mock Test tavsifini (Description) yozib yuboring:"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_mock:home")]]
                ),
            )
            return

        if data.startswith("adm_mock:role:"):
            new_role = data.split(":", 2)[2]
            st = _ADMIN_MOCK_STATE.get(user_id)
            if st:
                st["current_role"] = new_role
            await query.answer(f"Material turi tanlandi: {new_role}")
            return

        if data == "adm_mock:step7_preview_img":
            st = _ADMIN_MOCK_STATE.setdefault(user_id, {"draft": {}})
            st["step"] = "add_step7_preview_img"
            await query.answer()
            await query.edit_message_text(
                text=(
                    "<b>7-QADAM:</b> Mock Test muqovasi uchun <b>Preview rasm</b> yuboring "
                    "yoki o‘tkazib yuborish tugmasini bosing:"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⏭ O‘tkazib yuborish (8-qadam Preview)",
                                callback_data="adm_mock:step8_preview",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "❌ Bekor qilish", callback_data="adm_mock:home"
                            )
                        ],
                    ]
                ),
            )
            return

        if data == "adm_mock:step8_preview":
            st = _ADMIN_MOCK_STATE.get(user_id)
            if not st or not st.get("draft"):
                await query.answer("⚠️ Qoralama topilmadi.", show_alert=True)
                return
            st["step"] = "add_step8_preview"
            await query.answer()
            await query.edit_message_text(
                text=_format_wizard_preview(st["draft"]),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✅ 9-QADAM: Tasdiqlash va Nashr qilish",
                                callback_data="adm_mock:publish_confirm",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "❌ Bekor qilish", callback_data="adm_mock:home"
                            )
                        ],
                    ]
                ),
            )
            return

        if data == "adm_mock:publish_confirm":
            st = _ADMIN_MOCK_STATE.pop(user_id, None)
            if not st or not st.get("draft"):
                await query.answer("⚠️ Qoralama topilmadi.", show_alert=True)
                return
            created = await mock_test_manager.create_mock_test_pg(
                session, user_id, st["draft"]
            )
            await query.answer("🎉 Mock Test nashr qilindi!")
            await query.edit_message_text(
                text=(
                    f"🎉 <b>Mock Test muvaffaqiyatli yaratildi va katalogga chiqarildi!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 ID: <b>#{created['id']}</b>\n"
                    f"📌 Nomi: <b>{html.escape(created['title'])}</b>\n"
                    f"🏷 Turkum: <b>{html.escape(created['category'])}</b>\n"
                    f"💰 Narxi: <b>{html.escape(created['price_formatted'])}</b>\n"
                    f"📂 Materiallar: <b>{len(created.get('files', []))} ta</b>"
                ),
                parse_mode="HTML",
                reply_markup=_admin_mock_home_keyboard(),
            )
            return

        # 3. Set Price in UZS (`adm_mock:price_list`, `adm_mock:price_sel:<id>`)
        if data == "adm_mock:price_list":
            await query.answer()
            rows = [
                [
                    InlineKeyboardButton(
                        f"💰 #{t['id']} {t['title'][:28]} ({t['price_formatted']})",
                        callback_data=f"adm_mock:price_sel:{t['id']}",
                    )
                ]
                for t in all_tests
            ]
            rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="adm_mock:home")])
            await query.edit_message_text(
                text="💰 <b>Narxini o‘zgartirmoqchi bo‘lgan Mock Testni tanlang:</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return

        if data.startswith("adm_mock:price_sel:"):
            tid = int(data.split(":", 2)[2])
            t = tests_by_id.get(tid)
            if not t:
                return
            _ADMIN_MOCK_STATE[user_id] = {"step": "set_price_uzs", "test_id": tid}
            await query.answer()
            await query.edit_message_text(
                text=(
                    f"💰 <b>{html.escape(t['title'])}</b>\n"
                    f"Joriy narxi: <b>{html.escape(t['price_formatted'])}</b>\n\n"
                    f"Yangi narxni so‘mda (UZS) yozib yuboring (masalan: <code>55000</code>):"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_mock:home")]]
                ),
            )
            return

        # 4. Edit Mock Test & Upload Materials (`adm_mock:edit_list`, `adm_mock:edit_sel:<id>`)
        if data == "adm_mock:edit_list":
            await query.answer()
            rows = [
                [
                    InlineKeyboardButton(
                        f"✏️ #{t['id']} {t['title'][:32]}",
                        callback_data=f"adm_mock:edit_sel:{t['id']}",
                    )
                ]
                for t in all_tests
            ]
            rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="adm_mock:home")])
            await query.edit_message_text(
                text="✏️ <b>Tahrirlamoqchi bo‘lgan Mock Testni tanlang:</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return

        if data.startswith("adm_mock:edit_sel:"):
            tid = int(data.split(":", 2)[2])
            t = tests_by_id.get(tid)
            if not t:
                return
            await query.answer()
            pub_label = "🟢 Nashr qilingan" if t["is_published"] else "🟡 Yashirilgan"
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📌 Nomini o‘zgartirish",
                            callback_data=f"adm_mock:ef:{tid}:title",
                        ),
                        InlineKeyboardButton(
                            "📖 Tavsifni o‘zgartirish",
                            callback_data=f"adm_mock:ef:{tid}:description",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "💰 Narxini o‘zgartirish",
                            callback_data=f"adm_mock:price_sel:{tid}",
                        ),
                        InlineKeyboardButton(
                            "⏱ Vaqtini o‘zgartirish",
                            callback_data=f"adm_mock:ef:{tid}:duration_minutes",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "📎 Yangi PDF/Audio/Matn qo‘shish",
                            callback_data=f"adm_mock:add_mat:{tid}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            f"👁 Holat: {pub_label} (Almashtirish)",
                            callback_data=f"adm_mock:toggle_pub:{tid}",
                        )
                    ],
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="adm_mock:edit_list")],
                ]
            )
            await query.edit_message_text(
                text=(
                    f"✏️ <b>Mock Test #{tid}: {html.escape(t['title'])}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷 Turkum: <b>{html.escape(t['category'])}</b>\n"
                    f"💰 Narxi: <b>{html.escape(t['price_formatted'])}</b>\n"
                    f"⏱ Vaqti: <b>{t['duration_minutes']} daqiqa</b>\n"
                    f"📂 Materiallar: <b>{len(t.get('files', []))} ta</b>\n"
                    f"👥 Ruxsatga ega foydalanuvchilar: <b>{t['active_users_count']} ta</b>"
                ),
                parse_mode="HTML",
                reply_markup=kb,
            )
            return

        if data.startswith("adm_mock:ef:"):
            _, _, tid_s, field_name = data.split(":", 3)
            _ADMIN_MOCK_STATE[user_id] = {
                "step": f"edit_field:{field_name}",
                "test_id": int(tid_s),
            }
            await query.answer()
            await query.edit_message_text(
                text=f"✍️ Yangi qiymatni yozib yuboring (<code>{html.escape(field_name)}</code>):",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Bekor qilish", callback_data=f"adm_mock:edit_sel:{tid_s}")]]
                ),
            )
            return

        if data.startswith("adm_mock:add_mat:"):
            tid = int(data.split(":", 2)[2])
            _ADMIN_MOCK_STATE[user_id] = {
                "step": "edit_add_material",
                "test_id": tid,
                "current_role": "question_paper",
            }
            await query.answer()
            await query.edit_message_text(
                text=(
                    f"📎 <b>Mock Test #{tid} uchun yangi material yuboring:</b>\n"
                    f"PDF hujjat, Audio fayl, Rasm yoki Matn jo‘nating:"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "📄 Savollar", callback_data="adm_mock:role:question_paper"
                            ),
                            InlineKeyboardButton(
                                "🎧 Audio", callback_data="adm_mock:role:audio_track"
                            ),
                            InlineKeyboardButton(
                                "🔑 Answer Key", callback_data="adm_mock:role:answer_key"
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                "❌ Bekor qilish",
                                callback_data=f"adm_mock:edit_sel:{tid}",
                            )
                        ],
                    ]
                ),
            )
            return

        if data.startswith("adm_mock:toggle_pub:"):
            tid = int(data.split(":", 2)[2])
            t = tests_by_id.get(tid)
            if not t:
                return
            await mock_test_manager.update_mock_test_pg(
                session, user_id, tid, {"is_published": not t["is_published"]}
            )
            await query.answer("✅ Nashr holati yangilandi!")
            await query.edit_message_text(
                text="✅ Mock Test nashr holati o‘zgartirildi.",
                reply_markup=_admin_mock_home_keyboard(),
            )
            return

        # 5. Manual User Access Grant (`👤 Foydalanuvchiga Mock Test berish`)
        if data == "adm_mock:grant_tests":
            await query.answer()
            rows = [
                [
                    InlineKeyboardButton(
                        f"📝 #{t['id']} {t['title'][:34]}",
                        callback_data=f"adm_mock:g_test:{t['id']}:1",
                    )
                ]
                for t in all_tests
            ]
            rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="adm_mock:home")])
            await query.edit_message_text(
                text=(
                    "👤 <b>FOYDALANUVCHIGA MOCK TEST BERISH (1-QADAM)</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Qaysi Mock Testga ruxsat bermoqchisiz?"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return

        if data.startswith("adm_mock:g_test:"):
            _, _, tid_s, page_s = data.split(":", 3)
            tid = int(tid_s)
            page = int(page_s)
            await query.answer()
            users, total, total_pages = await mock_test_manager.search_registered_users_pg(
                session, query_str="", page=page, page_size=8
            )
            rows = [
                [
                    InlineKeyboardButton(
                        "🔍 ID, username yoki ism bo‘yicha qidirish",
                        callback_data=f"adm_mock:g_search:{tid}",
                    )
                ]
            ]
            for u in users:
                uname = f" (@{u['username']})" if u.get("username") else ""
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"👤 {u['full_name'][:22]}{uname} [{u['user_id']}]",
                            callback_data=f"adm_mock:g_user:{tid}:{u['user_id']}",
                        )
                    ]
                )
            nav: list[InlineKeyboardButton] = []
            if page > 1:
                nav.append(
                    InlineKeyboardButton(
                        "⬅️", callback_data=f"adm_mock:g_test:{tid}:{page - 1}"
                    )
                )
            nav.append(
                InlineKeyboardButton(
                    f"{page}/{total_pages}", callback_data="lesson:noop"
                )
            )
            if page < total_pages:
                nav.append(
                    InlineKeyboardButton(
                        "➡️", callback_data=f"adm_mock:g_test:{tid}:{page + 1}"
                    )
                )
            if total_pages > 1:
                rows.append(nav)
            rows.append(
                [InlineKeyboardButton("🔙 Orqaga", callback_data="adm_mock:grant_tests")]
            )
            t_title = tests_by_id.get(tid, {}).get("title", f"#{tid}")
            await query.edit_message_text(
                text=(
                    f"👤 <b>FOYDALANUVCHINI TANLANG</b>\n"
                    f"📝 Test: <b>{html.escape(t_title)}</b>\n"
                    f"👥 Ro‘yxatdan o‘tganlar: <b>{total} ta</b>"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return

        if data.startswith("adm_mock:g_search:"):
            tid = int(data.split(":", 2)[2])
            _ADMIN_MOCK_STATE[user_id] = {"step": "grant_search_user", "test_id": tid}
            await query.answer()
            await query.edit_message_text(
                text=(
                    "🔍 <b>Foydalanuvchining Telegram ID'si, @username yoki ismini yozib yuboring:</b>"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Bekor qilish", callback_data=f"adm_mock:g_test:{tid}:1")]]
                ),
            )
            return

        if data.startswith("adm_mock:g_user:"):
            _, _, tid_s, uid_s = data.split(":", 3)
            tid = int(tid_s)
            target_uid = int(uid_s)
            await query.answer()
            u_obj = await crud.get_user_by_telegram_id(session, target_uid)
            u_name = u_obj.full_name if u_obj else f"User {target_uid}"
            u_uname = f"@{u_obj.username}" if (u_obj and u_obj.username) else "-"
            t_title = tests_by_id.get(tid, {}).get("title", f"#{tid}")

            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "♾ Doimiy (Permanent)",
                            callback_data=f"adm_mock:g_exec:{tid}:{target_uid}:permanent",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⏱ 24 soat",
                            callback_data=f"adm_mock:g_exec:{tid}:{target_uid}:24h",
                        ),
                        InlineKeyboardButton(
                            "📅 7 kun",
                            callback_data=f"adm_mock:g_exec:{tid}:{target_uid}:7d",
                        ),
                        InlineKeyboardButton(
                            "📆 30 kun",
                            callback_data=f"adm_mock:g_exec:{tid}:{target_uid}:30d",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "✍️ Maxsus muddat (kunlarda)",
                            callback_data=f"adm_mock:g_custom:{tid}:{target_uid}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 Orqaga", callback_data=f"adm_mock:g_test:{tid}:1"
                        )
                    ],
                ]
            )
            await query.edit_message_text(
                text=(
                    f"👤 <b>TANLANGAN FOYDALANUVCHI PROFILI</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 Telegram ID: <code>{target_uid}</code>\n"
                    f"👤 Ism: <b>{html.escape(u_name)}</b>\n"
                    f"🔗 Username: <b>{html.escape(u_uname)}</b>\n"
                    f"📝 Berilayotgan test: <b>{html.escape(t_title)}</b>\n\n"
                    f"⏳ <b>Ruxsat muddatini tanlang:</b>"
                ),
                parse_mode="HTML",
                reply_markup=kb,
            )
            return

        if data.startswith("adm_mock:g_custom:"):
            _, _, tid_s, uid_s = data.split(":", 3)
            _ADMIN_MOCK_STATE[user_id] = {
                "step": "grant_custom_days",
                "test_id": int(tid_s),
                "target_user_id": int(uid_s),
            }
            await query.answer()
            await query.edit_message_text(
                text="✍️ Necha kunlik ruxsat berilsin? Raqam yozib yuboring (masalan: <code>14</code>):",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_mock:home")]]
                ),
            )
            return

        if data.startswith("adm_mock:g_exec:"):
            parts = data.split(":", 4)
            tid = int(parts[2])
            target_uid = int(parts[3])
            dur_code = parts[4]

            res = await mock_test_manager.grant_access_pg(
                session=session,
                admin_id=user_id,
                target_user_id=target_uid,
                test_id=tid,
                duration_code=dur_code,
            )
            if not res.get("ok"):
                await query.answer(
                    "⚠️ Ushbu foydalanuvchida bu testga allaqachon faol doimiy ruxsat mavjud!",
                    show_alert=True,
                )
                return

            await query.answer("🎉 Ruxsat berildi va foydalanuvchiga xabar yuborildi!")
            target_lang = await crud.get_user_language(session, target_uid)
            notify_text = (
                f"{i18n.t('mock_grant_notification', lang=target_lang)}\n\n"
                f"📝 <b>{html.escape(res['test_title'])}</b>\n"
                f"⏳ Muddat: <b>{html.escape(res['duration_label'])}</b>"
            )
            try:
                await context.bot.send_message(
                    chat_id=target_uid,
                    text=notify_text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    i18n.t("mock_btn_my_tests", lang=target_lang),
                                    callback_data="mock:my_tests",
                                )
                            ]
                        ]
                    ),
                )
            except Exception as exc:
                logger.info("Could not notify user %s of mock test grant: %s", target_uid, exc)

            await query.edit_message_text(
                text=(
                    f"✅ <b>Mock Test ruxsati muvaffaqiyatli taqdim etildi!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 Foydalanuvchi ID: <code>{target_uid}</code>\n"
                    f"📝 Test: <b>{html.escape(res['test_title'])}</b>\n"
                    f"⏳ Muddat: <b>{html.escape(res['duration_label'])}</b>"
                ),
                parse_mode="HTML",
                reply_markup=_admin_mock_home_keyboard(),
            )
            return

        # 6. Users with Access (`👥 Testga ega foydalanuvchilar`) & Revoke (`🔒 Ruxsatni bekor qilish`)
        if data.startswith("adm_mock:holders:") or data == "adm_mock:revoke_list":
            await query.answer()
            holders = await mock_test_manager.list_access_holders_pg(session)
            if not holders:
                await query.edit_message_text(
                    text="👥 Hozircha hech bir foydalanuvchiga Mock Test ruxsati berilmagan.",
                    reply_markup=_admin_mock_home_keyboard(),
                )
                return

            lines = []
            rows = []
            for idx, h in enumerate(holders[:12], start=1):
                uname = f" (@{html.escape(h['username'])})" if h.get("username") else ""
                lines.append(
                    f"{idx}. 👤 <b>{html.escape(h['full_name'])}</b>{uname} [<code>{h['user_id']}</code>]\n"
                    f"   📝 {html.escape(h['test_title'])} | ⏳ {html.escape(h['duration_label'])}"
                )
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"🔒 Bekor qilish: {h['full_name'][:18]} — #{h['mock_test_id']}",
                            callback_data=f"adm_mock:rev_exec:{h['mock_test_id']}:{h['user_id']}",
                        )
                    ]
                )
            rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="adm_mock:home")])
            await query.edit_message_text(
                text=(
                    f"👥 <b>TESTGA EGA FOYDALANUVCHILAR ({len(holders)} ta)</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    + "\n\n".join(lines)
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return

        if data.startswith("adm_mock:rev_exec:"):
            _, _, tid_s, uid_s = data.split(":", 3)
            res = await mock_test_manager.revoke_access_pg(
                session, user_id, int(uid_s), int(tid_s)
            )
            if res.get("ok"):
                await query.answer("🔒 Ruxsat bekor qilindi!")
            else:
                await query.answer("⚠️ Faol ruxsat topilmadi.", show_alert=True)
            await query.edit_message_text(
                text=f"🔒 Foydalanuvchi <code>{uid_s}</code> uchun Mock Test #{tid_s} ruxsati bekor qilindi.",
                parse_mode="HTML",
                reply_markup=_admin_mock_home_keyboard(),
            )
            return

        # 7. All Mock Tests (`📚 Barcha Mock Testlar`) & Delete (`🗑 Mock Testni o‘chirish`)
        if data == "adm_mock:all_tests":
            await query.answer()
            lines = []
            for t in all_tests:
                pub_icon = "🟢" if t["is_published"] else "🟡"
                lines.append(
                    f"{pub_icon} <b>#{t['id']}. {html.escape(t['title'])}</b>\n"
                    f"   🏷 {html.escape(t['category'])} | 💰 {html.escape(t['price_formatted'])} | "
                    f"📂 {len(t.get('files', []))} material | 👥 {t['active_users_count']} user"
                )
            body = "\n\n".join(lines) if lines else "<i>Mock Testlar yo‘q.</i>"
            await query.edit_message_text(
                text=f"📚 <b>BARCHA MOCK TESTLAR ({len(all_tests)} ta)</b>\n━━━━━━━━━━━━━━━━━━━━\n{body}",
                parse_mode="HTML",
                reply_markup=_admin_mock_home_keyboard(),
            )
            return

        if data == "adm_mock:del_list":
            await query.answer()
            rows = [
                [
                    InlineKeyboardButton(
                        f"🗑 O‘chirish: #{t['id']} {t['title'][:30]}",
                        callback_data=f"adm_mock:del_exec:{t['id']}",
                    )
                ]
                for t in all_tests
            ]
            rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="adm_mock:home")])
            await query.edit_message_text(
                text="🗑 <b>O‘chirmoqchi bo‘lgan Mock Testni tanlang:</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return

        if data.startswith("adm_mock:del_exec:"):
            tid = int(data.split(":", 2)[2])
            ok = await mock_test_manager.delete_mock_test_pg(session, user_id, tid)
            await query.answer("🗑 Mock Test o‘chirildi!" if ok else "⚠️ Topilmadi")
            await query.edit_message_text(
                text=f"🗑 Mock Test #{tid} bazadan o‘chirildi.",
                reply_markup=_admin_mock_home_keyboard(),
            )
            return
