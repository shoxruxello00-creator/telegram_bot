from urllib.parse import quote
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.models import BonusPack
from services.i18n import i18n


def get_language_selection_keyboard(prefix: str = "set_lang") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇺🇿 O‘zbekcha", callback_data=f"{prefix}:uz"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data=f"{prefix}:ru"),
                InlineKeyboardButton("🇬🇧 English", callback_data=f"{prefix}:en"),
            ]
        ]
    )


def get_morning_notification_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    i18n.t("menu_daily_lesson", lang=lang),
                    callback_data="lesson:open:0",
                )
            ]
        ]
    )


def get_lesson_card_keyboard(
    lang: str, current_index: int, total: int
) -> InlineKeyboardMarkup:
    nav_row: list[InlineKeyboardButton] = []
    if current_index > 0:
        nav_row.append(
            InlineKeyboardButton(
                i18n.t("btn_prev", lang=lang),
                callback_data=f"lesson:page:{current_index - 1}",
            )
        )
    nav_row.append(
        InlineKeyboardButton(
            f"📖 {current_index + 1}/{total}",
            callback_data="lesson:noop",
        )
    )
    if current_index < total - 1:
        nav_row.append(
            InlineKeyboardButton(
                i18n.t("btn_next", lang=lang),
                callback_data=f"lesson:page:{current_index + 1}",
            )
        )

    rows: list[list[InlineKeyboardButton]] = [
        nav_row,
        [
            InlineKeyboardButton(
                i18n.t("btn_send_all_cards", lang=lang),
                callback_data="lesson:send_all",
            )
        ],
        [
            InlineKeyboardButton(
                i18n.t("btn_memorized", lang=lang),
                callback_data="lesson:memorized",
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def get_memorized_only_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    i18n.t("btn_memorized", lang=lang),
                    callback_data="lesson:memorized",
                )
            ]
        ]
    )


def get_start_quiz_keyboard(lang: str, practice: bool = False) -> InlineKeyboardMarkup:
    cb = "quiz:start:practice" if practice else "quiz:start:daily"
    btn_text = (
        i18n.t("btn_practice_quiz", lang=lang)
        if practice
        else i18n.t("btn_start_quiz_now", lang=lang)
    )
    return InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, callback_data=cb)]])


def get_settings_keyboard(
    lang: str, reminders_enabled: bool, broadcast_enabled: bool = True
) -> InlineKeyboardMarkup:
    rem_btn_key = (
        "btn_toggle_reminders_on" if reminders_enabled else "btn_toggle_reminders_off"
    )
    bcast_btn_key = (
        "btn_toggle_broadcast_on" if broadcast_enabled else "btn_toggle_broadcast_off"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    i18n.t("btn_change_language", lang=lang),
                    callback_data="settings:change_lang",
                )
            ],
            [
                InlineKeyboardButton(
                    i18n.t(rem_btn_key, lang=lang),
                    callback_data="settings:toggle_reminders",
                )
            ],
            [
                InlineKeyboardButton(
                    i18n.t(bcast_btn_key, lang=lang),
                    callback_data="settings:toggle_broadcast",
                )
            ],
        ]
    )


def get_learned_words_pagination_keyboard(
    lang: str, page: int, total_pages: int
) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                i18n.t("btn_prev", lang=lang),
                callback_data=f"learned:page:{page - 1}",
            )
        )
    nav.append(
        InlineKeyboardButton(f"{page}/{total_pages}", callback_data="lesson:noop")
    )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                i18n.t("btn_next", lang=lang),
                callback_data=f"learned:page:{page + 1}",
            )
        )
    return InlineKeyboardMarkup([nav])


# ==============================================================================
# REFERRAL & REWARDS INLINE KEYBOARDS (Sections 4, 5, 7)
# ==============================================================================


def build_telegram_share_url(lang: str, referral_link: str) -> str:
    share_text = i18n.t("referral_share_text", lang=lang)
    return f"https://t.me/share/url?url={quote(referral_link)}&text={quote(share_text)}"


def get_referral_dashboard_keyboard(
    lang: str, referral_link: str
) -> InlineKeyboardMarkup:
    share_url = build_telegram_share_url(lang, referral_link)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    i18n.t("btn_share_link", lang=lang),
                    url=share_url,
                )
            ],
            [
                InlineKeyboardButton(
                    i18n.t("btn_my_rewards", lang=lang),
                    callback_data="referral:rewards",
                ),
                InlineKeyboardButton(
                    i18n.t("btn_referral_stats", lang=lang),
                    callback_data="referral:stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    i18n.t("btn_referral_leaderboard", lang=lang),
                    callback_data="referral:leaderboard",
                )
            ],
            [
                InlineKeyboardButton(
                    i18n.t("btn_main_menu", lang=lang),
                    callback_data="referral:main_menu",
                )
            ],
        ]
    )


def get_referral_back_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    i18n.t("btn_back", lang=lang),
                    callback_data="referral:dashboard",
                )
            ]
        ]
    )


def get_my_rewards_keyboard(
    lang: str,
    packs: list[BonusPack],
    unlocked_types: set[str],
    confirmed_count: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for pack in packs:
        is_unlocked = (
            pack.pack_type in unlocked_types
            or confirmed_count >= pack.required_referrals
        )
        prefix = "✅" if is_unlocked else "🔒"
        suffix = (
            ""
            if is_unlocked
            else f" ({confirmed_count}/{pack.required_referrals})"
        )
        rows.append(
            [
                InlineKeyboardButton(
                    f"{prefix} {pack.title}{suffix}",
                    callback_data=f"referral:pack:{pack.id}:0",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                i18n.t("btn_back", lang=lang),
                callback_data="referral:dashboard",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def get_bonus_pack_card_keyboard(
    lang: str, pack_id: int, current_index: int, total: int
) -> InlineKeyboardMarkup:
    nav_row: list[InlineKeyboardButton] = []
    if current_index > 0:
        nav_row.append(
            InlineKeyboardButton(
                i18n.t("btn_prev", lang=lang),
                callback_data=f"referral:pack:{pack_id}:{current_index - 1}",
            )
        )
    nav_row.append(
        InlineKeyboardButton(
            f"📖 {current_index + 1}/{total}",
            callback_data="lesson:noop",
        )
    )
    if current_index < total - 1:
        nav_row.append(
            InlineKeyboardButton(
                i18n.t("btn_next", lang=lang),
                callback_data=f"referral:pack:{pack_id}:{current_index + 1}",
            )
        )

    return InlineKeyboardMarkup(
        [
            nav_row,
            [
                InlineKeyboardButton(
                    i18n.t("btn_pack_quiz", lang=lang),
                    callback_data=f"quiz:pack:{pack_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    i18n.t("btn_back_to_rewards", lang=lang),
                    callback_data="referral:rewards",
                )
            ],
        ]
    )


# ==============================================================================
# ADMIN PANEL, REFERRAL MANAGEMENT, BROADCAST & MULTI-ADMIN KEYBOARDS
# ==============================================================================


def get_admin_panel_keyboard(is_super_admin: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                "📢 Barcha foydalanuvchilarga xabar",
                callback_data="admin:broadcast",
            )
        ],
        [
            InlineKeyboardButton(
                "🎁 Referral boshqaruvi", callback_data="admin:referrals"
            ),
            InlineKeyboardButton(
                "🤖 AI Generator holati", callback_data="admin:ai_status"
            ),
        ],
        [
            InlineKeyboardButton(
                "📚 Barcha vocabulary", callback_data="admin:vocab:1"
            ),
            InlineKeyboardButton(
                "📅 Bugungi dars", callback_data="admin:today_lesson"
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Bot statistikasi", callback_data="admin:stats"
            ),
            InlineKeyboardButton(
                "👥 Foydalanuvchilar", callback_data="admin:users"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Yangi darsni generatsiya qilish",
                callback_data="admin:generate",
            ),
            InlineKeyboardButton(
                "⚙️ Sozlamalar", callback_data="admin:settings"
            ),
        ],
    ]
    if is_super_admin:
        rows.append(
            [
                InlineKeyboardButton(
                    "👑 Adminlar boshqaruvi", callback_data="admin:admins"
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def get_admin_referral_keyboard(is_super_admin: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                "🏆 Top referrers", callback_data="admin:ref_top"
            ),
            InlineKeyboardButton(
                "🎁 Berilgan mukofotlar", callback_data="admin:ref_rewards"
            ),
        ],
        [
            InlineKeyboardButton(
                "⏳ So‘nggi referrallar", callback_data="admin:ref_list:all"
            ),
            InlineKeyboardButton(
                "🚫 Shubhali referral", callback_data="admin:ref_list:suspicious"
            ),
        ],
    ]
    if is_super_admin:
        rows.append(
            [
                InlineKeyboardButton(
                    "⚙️ Milestone qiymatlarini sozlash",
                    callback_data="admin:ref_milestones",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin:home")]
    )
    return InlineKeyboardMarkup(rows)


def get_admin_referral_reject_keyboard(
    referrals: list, back_cb: str = "admin:referrals"
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ref in referrals[:6]:
        if ref.status != "rejected":
            rows.append(
                [
                    InlineKeyboardButton(
                        f"🚫 Rad etish #{ref.id} ({ref.referred_user_id})",
                        callback_data=f"admin:ref_reject:{ref.id}",
                    )
                ]
            )
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def get_admin_milestones_keyboard(packs: list[BonusPack]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for pack in packs:
        minus_val = max(1, pack.required_referrals - 1)
        plus_val = pack.required_referrals + 1
        rows.append(
            [
                InlineKeyboardButton(
                    f"➖",
                    callback_data=f"admin:ref_ms_set:{pack.id}:{minus_val}",
                ),
                InlineKeyboardButton(
                    f"{pack.title[:22]} ({pack.required_referrals})",
                    callback_data="lesson:noop",
                ),
                InlineKeyboardButton(
                    f"➕",
                    callback_data=f"admin:ref_ms_set:{pack.id}:{plus_val}",
                ),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "🔙 Referral boshqaruvi", callback_data="admin:referrals"
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def get_admin_broadcast_wait_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📜 Broadcast tarixi", callback_data="admin:bcast_history"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Bekor qilish", callback_data="admin:bcast_cancel_input"
                )
            ],
        ]
    )


def get_admin_broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Hammaga yuborish", callback_data="admin:bcast_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ Xabarni o‘zgartirish", callback_data="admin:bcast_edit"
                ),
                InlineKeyboardButton(
                    "❌ Bekor qilish", callback_data="admin:bcast_cancel_input"
                ),
            ],
        ]
    )


def get_admin_broadcast_status_keyboard(
    broadcast_id: int, is_running: bool = True
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                "🔄 Holatni yangilash",
                callback_data=f"admin:bcast_status:{broadcast_id}",
            )
        ]
    ]
    if is_running:
        rows.append(
            [
                InlineKeyboardButton(
                    "⏹ Yuborishni to‘xtatish",
                    callback_data=f"admin:bcast_stop:{broadcast_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "📜 Broadcast tarixi", callback_data="admin:bcast_history"
            ),
            InlineKeyboardButton("🔙 Admin Panel", callback_data="admin:home"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def get_super_admin_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Admin qo‘shish", callback_data="admin:admins_add"
                ),
                InlineKeyboardButton(
                    "👥 Adminlar ro‘yxati", callback_data="admin:admins_list"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🗑 Adminni o‘chirish", callback_data="admin:admins_remove_menu"
                )
            ],
            [
                InlineKeyboardButton("🔙 Orqaga", callback_data="admin:home")
            ],
        ]
    )


def get_appoint_admin_confirm_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Admin qilib tayinlash",
                    callback_data=f"admin:admins_confirm_add:{candidate_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Bekor qilish", callback_data="admin:admins"
                )
            ],
        ]
    )


def get_remove_admin_confirm_keyboard(moderator_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Ha, adminlikdan o‘chirish",
                    callback_data=f"admin:admins_confirm_rm:{moderator_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Bekor qilish", callback_data="admin:admins"
                )
            ],
        ]
    )


def get_admin_vocab_pagination_keyboard(
    page: int, total_pages: int
) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(
            InlineKeyboardButton("⬅️ Oldingi", callback_data=f"admin:vocab:{page - 1}")
        )
    nav.append(
        InlineKeyboardButton(f"{page}/{max(1, total_pages)}", callback_data="lesson:noop")
    )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton("Keyingi ➡️", callback_data=f"admin:vocab:{page + 1}")
        )
    rows = []
    if nav:
        rows.append(nav)
    rows.append(
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin:home")]
    )
    return InlineKeyboardMarkup(rows)


def get_admin_back_keyboard(back_cb: str = "admin:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Orqaga", callback_data=back_cb)]]
    )
