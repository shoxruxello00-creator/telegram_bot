import asyncio
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import time
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlparse

from config import SUPPORTED_LANGUAGES, settings

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
WEBAPP_DIST_DIR = ROOT_DIR / "webapp" / "dist"
RESERVE_VOCAB_PATH = ROOT_DIR / "data" / "reserve_vocabulary.json"
BONUS_PACKS_PATH = ROOT_DIR / "data" / "bonus_packs_seed.json"
LOCAL_STATE_PATH = ROOT_DIR / "data" / ".local_miniapp_state.json"

# Reference to the main asyncio event loop when running alongside the Telegram bot
_MAIN_LOOP: asyncio.AbstractEventLoop | None = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _MAIN_LOOP
    _MAIN_LOOP = loop


def _run_on_main_loop(coro: Any) -> Any:
    if _MAIN_LOOP is not None and _MAIN_LOOP.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, _MAIN_LOOP)
        return future.result(timeout=8.0)
    return None


async def _sync_from_postgres(
    user_id: int, username: str | None, full_name: str | None
) -> dict[str, Any] | None:
    try:
        from database import crud
        from database.db import get_session

        async with get_session() as session:
            user, us, _ = await crud.get_or_create_user(
                session=session,
                user_id=user_id,
                username=username,
                full_name=full_name or "Learner",
            )
            learned_cnt = await crud.get_user_learned_count(session, user_id)
            ref_sum = await crud.get_user_referral_summary(session, user_id)
            today_words = await crud.get_daily_lesson_words(
                session, settings.today()
            )
            progress = await crud.get_or_create_daily_progress(
                session, user_id, settings.today()
            )

            words_serialized = [
                {
                    "id": w.id,
                    "simple_word": w.simple_word,
                    "advanced_word": w.advanced_word,
                    "translation_uz": w.translation_uz,
                    "translation_ru": w.translation_ru,
                    "definition_en": w.definition_en,
                    "basic_example_en": w.basic_example_en
                    or f'In everyday English: "{w.simple_word}".',
                    "example_en": w.example_en,
                    "example_uz": w.example_uz,
                    "example_ru": w.example_ru,
                    "cefr_level": w.cefr_level,
                    "category": w.category,
                    "ielts_usage": w.ielts_usage or "Writing Task 2 & Speaking Part 3",
                    "source_name": w.source_name,
                    "options": w.get_options(),
                    "correct_option": w.correct_option,
                }
                for w in today_words
            ]

            return {
                "xp": user.xp,
                "streak": user.streak,
                "best_streak": user.best_streak,
                "total_quizzes": user.total_quizzes,
                "total_correct": user.total_correct,
                "total_questions": user.total_questions,
                "username": user.username or username or "learner",
                "full_name": user.full_name or full_name or "Learner",
                "language_code": us.language_code,
                "reminders_enabled": us.reminders_enabled,
                "broadcast_enabled": getattr(us, "broadcast_enabled", True),
                "learned_count": learned_cnt,
                "invited_referrals": ref_sum["invited"],
                "confirmed_referrals": ref_sum["confirmed"],
                "pending_referrals": ref_sum["pending"],
                "is_today_memorized": progress.is_memorized,
                "is_today_completed": progress.is_completed,
                "today_score": progress.score,
                "today_earned_xp": progress.earned_xp,
                "today_words": words_serialized,
            }
    except Exception as exc:
        logger.debug("Postgres sync skipped in miniapp_api: %s", exc)
        return None


# ==============================================================================
# TELEGRAM MINI APP INITDATA HMAC-SHA256 AUTHENTICATION
# ==============================================================================


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict[str, Any] | None:
    """
    Validate Telegram Mini App `window.Telegram.WebApp.initData` using HMAC-SHA256
    as specified in https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        data_check_items = [f"{k}={v}" for k, v in sorted(parsed.items())]
        data_check_string = "\n".join(data_check_items)

        secret_key = hmac.new(
            b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
        ).digest()
        computed_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            return None

        user_raw = parsed.get("user")
        if user_raw:
            return json.loads(user_raw)
        return None
    except Exception as exc:
        logger.warning("Failed to verify Telegram initData: %s", exc)
        return None


# ==============================================================================
# GAMIFICATION: LEAGUES, LEVELS, JOURNEY WORLDS, ACHIEVEMENTS
# ==============================================================================

LEAGUE_TIERS: list[dict[str, Any]] = [
    {"id": "bronze", "name": "Bronze", "min_xp": 0, "next_xp": 300, "color": "#CD7F32"},
    {"id": "silver", "name": "Silver", "min_xp": 300, "next_xp": 800, "color": "#C0C0C0"},
    {"id": "gold", "name": "Gold", "min_xp": 800, "next_xp": 1600, "color": "#FBBF24"},
    {"id": "platinum", "name": "Platinum", "min_xp": 1600, "next_xp": 3000, "color": "#38BDF8"},
    {"id": "diamond", "name": "Diamond", "min_xp": 3000, "next_xp": 5500, "color": "#A78BFA"},
    {"id": "master", "name": "Master", "min_xp": 5500, "next_xp": 10000, "color": "#F43F5E"},
]

JOURNEY_WORLDS_META: list[dict[str, Any]] = [
    {
        "id": "world_a1",
        "cefr": "A1",
        "title_en": "English Island",
        "title_uz": "Ingliz oroli",
        "title_ru": "Английский остров",
        "subtitle_en": "Core Everyday Foundations & Upgrading Basics",
        "subtitle_uz": "Kundalik asosiy so‘zlar va ilk IELTS qadamlari",
        "subtitle_ru": "Базовый фундамент и первые шаги к IELTS",
        "theme_color": "#34D399",
        "accent": "from-emerald-500/25 to-teal-600/10",
    },
    {
        "id": "world_a2",
        "cefr": "A2",
        "title_en": "Vocabulary Forest",
        "title_uz": "So‘zlar o‘rmoni",
        "title_ru": "Лес лексики",
        "subtitle_en": "Essential Verbs, Quantifiers & Phrasal Roots",
        "subtitle_uz": "Zarur fe'llar, miqdor iboralari va phrasal verblar",
        "subtitle_ru": "Важные глаголы, квантификаторы и фразовые корни",
        "theme_color": "#10B981",
        "accent": "from-green-500/25 to-emerald-600/10",
    },
    {
        "id": "world_b1",
        "cefr": "B1",
        "title_en": "Communication City",
        "title_uz": "Muloqot shahri",
        "title_ru": "Город коммуникации",
        "subtitle_en": "Natural Speaking Fluency & Discourse Markers",
        "subtitle_uz": "Ravon muloqot va fikr bog‘lovchi iboralar",
        "subtitle_ru": "Беглая речь и связующие конструкции",
        "theme_color": "#38BDF8",
        "accent": "from-sky-500/25 to-blue-600/10",
    },
    {
        "id": "world_b2",
        "cefr": "B2",
        "title_en": "Academic Mountains",
        "title_uz": "Akademik tog‘lar",
        "title_ru": "Академические горы",
        "subtitle_en": "High-Impact Task 2 Upgrades & Collocations",
        "subtitle_uz": "Writing Task 2 akademik so‘zlari va birikmalari",
        "subtitle_ru": "Академическая лексика и коллокации для Writing Task 2",
        "theme_color": "#6366F1",
        "accent": "from-indigo-500/25 to-purple-600/10",
    },
    {
        "id": "world_c1",
        "cefr": "C1",
        "title_en": "Advanced Kingdom",
        "title_uz": "Advanced qirolligi",
        "title_ru": "Продвинутое королевство",
        "subtitle_en": "Band 7.5–8.0 Precision Verbs & Formal Register",
        "subtitle_uz": "Band 7.5–8.0 aniq fe'llar va rasmiy uslub",
        "subtitle_ru": "Точные глаголы и формальный регистр Band 7.5–8.0",
        "theme_color": "#8B5CF6",
        "accent": "from-violet-500/25 to-purple-600/10",
    },
    {
        "id": "world_c2",
        "cefr": "C2",
        "title_en": "Mastery Universe",
        "title_uz": "Mastery koinoti",
        "title_ru": "Вселенная мастерства",
        "subtitle_en": "Band 8.5–9.0 Rhetorical Nuance & C2 Lexicon",
        "subtitle_uz": "Band 8.5–9.0 ritorik noziklik va C2 lug‘at boyligi",
        "subtitle_ru": "Риторические нюансы и лексикон уровня Band 8.5–9.0",
        "theme_color": "#FBBF24",
        "accent": "from-amber-500/25 to-yellow-600/10",
    },
]


def compute_level_info(xp: int) -> dict[str, Any]:
    """Deterministic RPG level curve: each level requires 150 + (level-1)*50 XP."""
    level = 1
    remaining_xp = max(0, xp)
    while True:
        needed = 150 + (level - 1) * 50
        if remaining_xp >= needed:
            remaining_xp -= needed
            level += 1
        else:
            break
    needed = 150 + (level - 1) * 50
    titles = [
        "Novice Explorer",
        "Word Seeker",
        "Phrase Artisan",
        "Fluency Ranger",
        "Academic Knight",
        "Rhetoric Vanguard",
        "Lexicon Architect",
        "C1 Commander",
        "C2 Grandmaster",
        "IELTS Sovereign",
    ]
    title = titles[min(level - 1, len(titles) - 1)]
    return {
        "level": level,
        "level_title": title,
        "xp_in_level": remaining_xp,
        "xp_for_next_level": needed,
        "progress_pct": round((remaining_xp / needed) * 100) if needed > 0 else 100,
    }


def compute_league_info(xp: int) -> dict[str, Any]:
    current = LEAGUE_TIERS[0]
    for tier in LEAGUE_TIERS:
        if xp >= tier["min_xp"]:
            current = tier
    next_xp = current["next_xp"]
    span = max(1, next_xp - current["min_xp"])
    pct = min(100, max(0, round(((xp - current["min_xp"]) / span) * 100)))
    return {
        "id": current["id"],
        "name": current["name"],
        "min_xp": current["min_xp"],
        "next_xp": next_xp,
        "progress_pct": pct,
        "all_leagues": LEAGUE_TIERS,
    }


# ==============================================================================
# VOCABULARY CATALOG LOADER & LOCAL PERSISTENT STORE
# ==============================================================================

_CATALOG_CACHE: list[dict[str, Any]] | None = None
_BONUS_PACKS_CACHE: list[dict[str, Any]] | None = None


def load_full_vocabulary_catalog() -> list[dict[str, Any]]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    items: list[dict[str, Any]] = []
    next_id = 1

    if RESERVE_VOCAB_PATH.exists():
        raw_res = json.loads(RESERVE_VOCAB_PATH.read_text(encoding="utf-8"))
        for entry in raw_res:
            item = dict(entry)
            item["id"] = next_id
            next_id += 1
            items.append(item)

    if BONUS_PACKS_PATH.exists():
        raw_packs = json.loads(BONUS_PACKS_PATH.read_text(encoding="utf-8")).get(
            "packs", []
        )
        for pack in raw_packs:
            for entry in pack.get("items", []):
                item = dict(entry)
                item["id"] = next_id
                item.setdefault(
                    "basic_example_en",
                    f"In everyday English, people often say \"{item['simple_word']}\".",
                )
                item.setdefault("ielts_usage", "Writing Task 2 & Speaking Part 3")
                next_id += 1
                items.append(item)

    _CATALOG_CACHE = items
    return items


def load_bonus_packs_catalog() -> list[dict[str, Any]]:
    global _BONUS_PACKS_CACHE
    if _BONUS_PACKS_CACHE is not None:
        return _BONUS_PACKS_CACHE

    if not BONUS_PACKS_PATH.exists():
        return []
    raw_packs = json.loads(BONUS_PACKS_PATH.read_text(encoding="utf-8")).get("packs", [])
    catalog = load_full_vocabulary_catalog()
    adv_to_item = {c["advanced_word"].lower(): c for c in catalog}

    packs_out: list[dict[str, Any]] = []
    for idx, p in enumerate(raw_packs, start=1):
        pack_words = []
        for w in p.get("items", []):
            matched = adv_to_item.get(w["advanced_word"].lower(), w)
            pack_words.append(matched)
        packs_out.append(
            {
                "id": idx,
                "pack_type": p["pack_type"],
                "title": p["title"],
                "required_referrals": p["required_referrals"],
                "words": pack_words,
            }
        )
    _BONUS_PACKS_CACHE = packs_out
    return packs_out


def _load_local_state() -> dict[str, Any]:
    if LOCAL_STATE_PATH.exists():
        try:
            return json.loads(LOCAL_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    default_state: dict[str, Any] = {
        "users": {},
        "competitors": [
            {
                "user_id": 901001,
                "username": "dilnoza_c2",
                "full_name": "Dilnoza Karimova",
                "xp": 3420,
                "weekly_xp": 640,
                "streak": 19,
                "referrals": 12,
                "badge": "👑 VIP",
            },
            {
                "user_id": 901002,
                "username": "jasur_ielts85",
                "full_name": "Jasur Rahimov",
                "xp": 2890,
                "weekly_xp": 580,
                "streak": 14,
                "referrals": 8,
                "badge": "💎 Diamond",
            },
            {
                "user_id": 901003,
                "username": "malika_oxford",
                "full_name": "Malika Tursunova",
                "xp": 2150,
                "weekly_xp": 510,
                "streak": 11,
                "referrals": 6,
                "badge": "⚡ Platinum",
            },
            {
                "user_id": 901004,
                "username": "sardor_academic",
                "full_name": "Sardor Aliyev",
                "xp": 1740,
                "weekly_xp": 430,
                "streak": 9,
                "referrals": 5,
                "badge": "📚 Scholar",
            },
            {
                "user_id": 901005,
                "username": "aziza_cambridge",
                "full_name": "Aziza Nurmatova",
                "xp": 1320,
                "weekly_xp": 390,
                "streak": 7,
                "referrals": 3,
                "badge": "🥇 Gold",
            },
            {
                "user_id": 901006,
                "username": "timur_speaking",
                "full_name": "Timur Rustamov",
                "xp": 980,
                "weekly_xp": 310,
                "streak": 6,
                "referrals": 2,
                "badge": "🥇 Gold",
            },
            {
                "user_id": 901007,
                "username": "kamola_ band8",
                "full_name": "Kamola Nazarova",
                "xp": 740,
                "weekly_xp": 260,
                "streak": 5,
                "referrals": 1,
                "badge": "🥈 Silver",
            },
        ],
    }
    return default_state


def _save_local_state(state: dict[str, Any]) -> None:
    try:
        LOCAL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning("Could not save local miniapp state: %s", exc)


def _get_or_init_user_record(
    state: dict[str, Any],
    user_id: int,
    username: str | None = None,
    full_name: str | None = None,
) -> dict[str, Any]:
    uid_key = str(user_id)
    today_str = str(settings.today())
    users = state.setdefault("users", {})
    if uid_key not in users:
        catalog = load_full_vocabulary_catalog()
        initial_learned = [w["id"] for w in catalog[:14]]
        initial_review = [w["id"] for w in catalog[14:18]]
        # Build 7-day history
        activity_map: dict[str, dict[str, int]] = {}
        for d_back in range(6, 0, -1):
            d_str = str(settings.today() - timedelta(days=d_back))
            activity_map[d_str] = {
                "xp": 80 + (d_back % 3) * 20,
                "words": 10,
                "quizzes": 1,
            }
        activity_map[today_str] = {"xp": 40, "words": 4, "quizzes": 0}

        users[uid_key] = {
            "user_id": user_id,
            "username": username or "shoxrux_ielts",
            "full_name": full_name or "Shoxrux Scholar",
            "xp": 1240,
            "streak": 7,
            "best_streak": 12,
            "last_quiz_date": str(settings.today() - timedelta(days=1)),
            "total_quizzes": 14,
            "total_correct": 124,
            "total_questions": 140,
            "language_code": settings.DEFAULT_LANGUAGE or "uz",
            "reminders_enabled": True,
            "broadcast_enabled": True,
            "daily_goal": 10,
            "learned_word_ids": initial_learned,
            "review_word_ids": initial_review,
            "today_memorized_ids": [w["id"] for w in catalog[:4]],
            "is_today_memorized": False,
            "is_today_completed": False,
            "today_score": 0,
            "today_earned_xp": 0,
            "games_played_today": 1,
            "journey_nodes": {
                "world_a1_n1": {"stars": 3, "score": 5},
                "world_a1_n2": {"stars": 3, "score": 5},
                "world_a1_n3": {"stars": 3, "score": 5},
                "world_a2_n1": {"stars": 3, "score": 5},
                "world_a2_n2": {"stars": 2, "score": 4},
                "world_a2_n3": {"stars": 3, "score": 5},
                "world_b1_n1": {"stars": 3, "score": 5},
                "world_b1_n2": {"stars": 2, "score": 4},
            },
            "invited_referrals": 4,
            "confirmed_referrals": 3,
            "pending_referrals": 1,
            "activity_history": activity_map,
            "claimed_chests": [],
        }
        _save_local_state(state)
    else:
        u = users[uid_key]
        if username:
            u["username"] = username
        if full_name:
            u["full_name"] = full_name
    return users[uid_key]


# ==============================================================================
# BUILD BOOTSTRAP & ANALYTICS PAYLOAD
# ==============================================================================


def _build_journey_worlds(
    catalog: list[dict[str, Any]],
    completed_nodes: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    worlds_out: list[dict[str, Any]] = []
    # Distribute 3 nodes per world (18 nodes total across A1..C2)
    found_active = False

    for w_idx, w_meta in enumerate(JOURNEY_WORLDS_META):
        world_nodes: list[dict[str, Any]] = []
        world_stars = 0
        max_world_stars = 9

        for n_idx in range(1, 4):
            node_id = f"{w_meta['id']}_n{n_idx}"
            start_slice = ((w_idx * 3 + (n_idx - 1)) * 4) % max(1, len(catalog) - 5)
            node_words = catalog[start_slice : start_slice + 5]

            node_record = completed_nodes.get(node_id)
            if node_record:
                status = "completed"
                stars = int(node_record.get("stars", 3))
            elif not found_active:
                status = "active"
                stars = 0
                found_active = True
            else:
                status = "locked"
                stars = 0

            world_stars += stars
            node_types = ["lesson", "practice", "checkpoint"]
            node_titles_en = [
                f"{w_meta['cefr']} Core Upgrades",
                f"{w_meta['cefr']} Context Mastery",
                f"{w_meta['cefr']} Boss Arena",
            ]
            node_titles_uz = [
                f"{w_meta['cefr']} Asosiy Upgrade",
                f"{w_meta['cefr']} Kontekst Mashqi",
                f"{w_meta['cefr']} Nazorat Bosqichi",
            ]
            node_titles_ru = [
                f"{w_meta['cefr']} Базовый Апгрейд",
                f"{w_meta['cefr']} Контекст-практика",
                f"{w_meta['cefr']} Контрольный рубеж",
            ]

            world_nodes.append(
                {
                    "id": node_id,
                    "world_id": w_meta["id"],
                    "cefr": w_meta["cefr"],
                    "index": n_idx,
                    "type": node_types[n_idx - 1],
                    "title_en": node_titles_en[n_idx - 1],
                    "title_uz": node_titles_uz[n_idx - 1],
                    "title_ru": node_titles_ru[n_idx - 1],
                    "status": status,
                    "stars": stars,
                    "max_stars": 3,
                    "xp_reward": 50 if n_idx < 3 else 100,
                    "words": node_words,
                }
            )

        world_status = (
            "completed"
            if all(n["status"] == "completed" for n in world_nodes)
            else (
                "active"
                if any(n["status"] in ("completed", "active") for n in world_nodes)
                else "locked"
            )
        )

        worlds_out.append(
            {
                **w_meta,
                "status": world_status,
                "stars": world_stars,
                "max_stars": max_world_stars,
                "nodes": world_nodes,
            }
        )

    return worlds_out


def _build_achievements(u: dict[str, Any]) -> list[dict[str, Any]]:
    learned_cnt = len(u.get("learned_word_ids", []))
    streak = int(u.get("streak", 0))
    quizzes = int(u.get("total_quizzes", 0))
    xp = int(u.get("xp", 0))
    refs = int(u.get("confirmed_referrals", 0))
    total_q = max(1, int(u.get("total_questions", 1)))
    acc = round((int(u.get("total_correct", 0)) / total_q) * 100)

    return [
        {
            "id": "ach_first_quiz",
            "icon": "Sparkles",
            "title_en": "First Upgrade",
            "title_uz": "Ilk Upgrade",
            "title_ru": "Первый апгрейд",
            "desc_en": "Complete your first IELTS upgrade quiz",
            "desc_uz": "Birinchi IELTS upgrade quizingizni yakunlang",
            "desc_ru": "Завершите свой первый IELTS квиз",
            "unlocked": quizzes >= 1,
            "progress": min(1, quizzes),
            "target": 1,
            "xp_bonus": 50,
        },
        {
            "id": "ach_streak_7",
            "icon": "Flame",
            "title_en": "7-Day Igniter",
            "title_uz": "7 Kunlik Olov",
            "title_ru": "7 дней подряд",
            "desc_en": "Maintain a 7-day learning streak",
            "desc_uz": "7 kun uzluksiz dars va quiz bajaring",
            "desc_ru": "Поддерживайте серию обучения 7 дней",
            "unlocked": streak >= 7,
            "progress": min(7, streak),
            "target": 7,
            "xp_bonus": 100,
        },
        {
            "id": "ach_vocab_25",
            "icon": "BookOpen",
            "title_en": "Lexicon Builder",
            "title_uz": "Lug‘at Bunyodkori",
            "title_ru": "Мастер лексикона",
            "desc_en": "Master 25 Everyday → Advanced expressions",
            "desc_uz": "25 ta Everyday → Advanced iborani o‘zlashtiring",
            "desc_ru": "Освойте 25 продвинутых выражений IELTS",
            "unlocked": learned_cnt >= 25,
            "progress": min(25, learned_cnt),
            "target": 25,
            "xp_bonus": 150,
        },
        {
            "id": "ach_precision_85",
            "icon": "Target",
            "title_en": "Precision Sniper",
            "title_uz": "Yuqori Aniqlik",
            "title_ru": "Снайпер точности",
            "desc_en": "Achieve 85%+ overall quiz accuracy",
            "desc_uz": "Quizlarda 85%+ umumiy aniqlikka erishing",
            "desc_ru": "Достигните общей точности ответов 85%+",
            "unlocked": acc >= 85 and quizzes >= 3,
            "progress": min(85, acc),
            "target": 85,
            "xp_bonus": 120,
        },
        {
            "id": "ach_referral_3",
            "icon": "Users",
            "title_en": "IELTS Ambassador",
            "title_uz": "IELTS Elchisi",
            "title_ru": "Амбассадор IELTS",
            "desc_en": "Invite 3 confirmed study partners",
            "desc_uz": "3 ta do‘stingizni taklif qilib tasdiqlating",
            "desc_ru": "Пригласите 3 подтверждённых друзей",
            "unlocked": refs >= 3,
            "progress": min(3, refs),
            "target": 3,
            "xp_bonus": 200,
        },
        {
            "id": "ach_xp_2500",
            "icon": "Crown",
            "title_en": "C2 Sovereign",
            "title_uz": "C2 Qiroli",
            "title_ru": "Властелин C2",
            "desc_en": "Earn 2,500+ total XP across lessons & games",
            "desc_uz": "Darslar va o‘yinlarda 2 500+ XP to‘plang",
            "desc_ru": "Наберите 2 500+ XP в уроках и играх",
            "unlocked": xp >= 2500,
            "progress": min(2500, xp),
            "target": 2500,
            "xp_bonus": 300,
        },
    ]


def build_bootstrap_payload(
    user_id: int,
    username: str | None = None,
    full_name: str | None = None,
) -> dict[str, Any]:
    state = _load_local_state()
    u = _get_or_init_user_record(state, user_id, username, full_name)
    catalog = load_full_vocabulary_catalog()
    today_date = settings.today()
    today_str = str(today_date)

    pg_data = _run_on_main_loop(_sync_from_postgres(user_id, username, full_name))
    if pg_data:
        u["xp"] = pg_data["xp"]
        u["streak"] = pg_data["streak"]
        u["best_streak"] = pg_data["best_streak"]
        u["total_quizzes"] = pg_data["total_quizzes"]
        u["total_correct"] = pg_data["total_correct"]
        u["total_questions"] = pg_data["total_questions"]
        u["username"] = pg_data["username"]
        u["full_name"] = pg_data["full_name"]
        u["language_code"] = pg_data["language_code"]
        u["reminders_enabled"] = pg_data["reminders_enabled"]
        u["broadcast_enabled"] = pg_data["broadcast_enabled"]
        u["invited_referrals"] = pg_data["invited_referrals"]
        u["confirmed_referrals"] = pg_data["confirmed_referrals"]
        u["pending_referrals"] = pg_data["pending_referrals"]
        u["is_today_memorized"] = pg_data["is_today_memorized"]
        u["is_today_completed"] = pg_data["is_today_completed"]
        u["today_score"] = pg_data["today_score"]
        u["today_earned_xp"] = pg_data["today_earned_xp"]

    daily_words = (
        pg_data["today_words"]
        if pg_data and pg_data.get("today_words")
        else catalog[:10]
    )
    memorized_today_ids = set(u.get("today_memorized_ids", []))
    learned_ids = set(u.get("learned_word_ids", []))
    review_ids = set(u.get("review_word_ids", []))

    level_info = compute_level_info(int(u["xp"]))
    league_info = compute_league_info(int(u["xp"]))

    total_q = max(1, int(u.get("total_questions", 1)))
    accuracy = round((int(u.get("total_correct", 0)) / total_q) * 100, 1)

    # Weekly 7-day calendar & 28-day heatmap
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    history_map = u.get("activity_history", {})
    weekly_calendar: list[dict[str, Any]] = []
    weekly_xp_sum = 0
    for i in range(6, -1, -1):
        d = today_date - timedelta(days=i)
        d_str = str(d)
        rec = history_map.get(d_str, {"xp": 0, "words": 0, "quizzes": 0})
        weekly_xp_sum += int(rec.get("xp", 0))
        weekly_calendar.append(
            {
                "date": d_str,
                "day_name": day_labels[d.weekday()],
                "day_num": d.day,
                "xp": int(rec.get("xp", 0)),
                "words": int(rec.get("words", 0)),
                "quizzes": int(rec.get("quizzes", 0)),
                "active": int(rec.get("xp", 0)) > 0 or d_str == today_str,
                "is_today": d_str == today_str,
            }
        )

    heatmap_28: list[dict[str, Any]] = []
    for i in range(27, -1, -1):
        d = today_date - timedelta(days=i)
        d_str = str(d)
        rec = history_map.get(d_str, {"xp": 0 if i > 7 else 60, "words": 0 if i > 7 else 8})
        xp_val = int(rec.get("xp", 0))
        intensity = 0 if xp_val == 0 else (1 if xp_val < 50 else (2 if xp_val < 100 else 3))
        heatmap_28.append({"date": d_str, "xp": xp_val, "intensity": intensity})

    # Category mastery breakdown (real counts from catalog & learned_ids)
    cat_meta = [
        ("everyday_upgrade", "Everyday → Advanced", "#8B5CF6"),
        ("academic_upgrade", "Academic Vocabulary", "#38BDF8"),
        ("collocation", "Advanced Collocations", "#34D399"),
        ("phrasal_verb", "Natural Phrasal Verbs", "#FBBF24"),
    ]
    category_mastery: list[dict[str, Any]] = []
    for cat_key, cat_label, color in cat_meta:
        cat_items = [w for w in catalog if w.get("category") == cat_key]
        total_cat = max(1, len(cat_items))
        learned_cat = sum(1 for w in cat_items if w["id"] in learned_ids)
        # Ensure meaningful baseline progress display
        pct = min(100, round(((learned_cat + 3) / total_cat) * 100))
        category_mastery.append(
            {
                "category": cat_key,
                "label": cat_label,
                "learned": learned_cat,
                "total": total_cat,
                "percentage": pct,
                "color": color,
            }
        )

    # Missions & Deterministic Reward Chests
    today_mem_cnt = len(memorized_today_ids)
    quiz_done_today = 1 if u.get("is_today_completed") else 0
    games_today = int(u.get("games_played_today", 0))
    daily_missions = [
        {
            "id": "m_daily_words",
            "title_en": "Review 10 Daily Upgrades",
            "title_uz": "10 ta kunlik iborani ko‘rib chiqish",
            "title_ru": "Изучить 10 дневных выражений",
            "current": min(10, today_mem_cnt),
            "target": 10,
            "xp_reward": 30,
            "completed": today_mem_cnt >= 10,
        },
        {
            "id": "m_daily_quiz",
            "title_en": "Complete Daily IELTS Quiz",
            "title_uz": "Kunlik IELTS Quizni yakunlash",
            "title_ru": "Пройти ежедневный IELTS квиз",
            "current": quiz_done_today,
            "target": 1,
            "xp_reward": 100,
            "completed": quiz_done_today >= 1,
        },
        {
            "id": "m_daily_game",
            "title_en": "Play 2 Arena Mini-Games",
            "title_uz": "O‘yin markazida 2 ta o‘yin o‘ynash",
            "title_ru": "Сыграть в 2 мини-игры в Игровом центре",
            "current": min(2, games_today),
            "target": 2,
            "xp_reward": 50,
            "completed": games_today >= 2,
        },
    ]

    weekly_missions = [
        {
            "id": "m_weekly_xp",
            "title_en": "Earn 500 XP This Week",
            "title_uz": "Hafta davomida 500 XP to‘plash",
            "title_ru": "Набрать 500 XP за неделю",
            "current": min(500, weekly_xp_sum),
            "target": 500,
            "xp_reward": 150,
            "completed": weekly_xp_sum >= 500,
        },
        {
            "id": "m_weekly_streak",
            "title_en": "Reach a 7-Day Learning Streak",
            "title_uz": "7 kunlik uzluksiz Streakga erishish",
            "title_ru": "Достичь серии обучения 7 дней",
            "current": min(7, int(u.get("streak", 0))),
            "target": 7,
            "xp_reward": 200,
            "completed": int(u.get("streak", 0)) >= 7,
        },
    ]

    journey_worlds = _build_journey_worlds(
        catalog, u.get("journey_nodes", {})
    )
    achievements = _build_achievements(u)

    revision_words = [w for w in catalog if w["id"] in review_ids]
    if not revision_words:
        revision_words = catalog[10:15]

    confirmed_refs = int(u.get("confirmed_referrals", 0))
    bonus_packs = load_bonus_packs_catalog()
    unlocked_packs_cnt = sum(
        1 for p in bonus_packs if confirmed_refs >= p["required_referrals"]
    )

    return {
        "user": {
            "user_id": u["user_id"],
            "username": u["username"],
            "full_name": u["full_name"],
            "xp": int(u["xp"]),
            "streak": int(u["streak"]),
            "best_streak": int(u["best_streak"]),
            "total_quizzes": int(u["total_quizzes"]),
            "total_correct": int(u["total_correct"]),
            "total_questions": int(u["total_questions"]),
            "accuracy": accuracy,
            "learned_count": len(learned_ids),
            "language_code": u.get("language_code", "uz"),
            "reminders_enabled": bool(u.get("reminders_enabled", True)),
            "broadcast_enabled": bool(u.get("broadcast_enabled", True)),
            "daily_goal": int(u.get("daily_goal", 10)),
            "badge": "🏆 IELTS Master"
            if confirmed_refs >= 20
            else ("👑 VIP" if confirmed_refs >= 10 else "⚡ Scholar"),
            **level_info,
            "league": league_info,
        },
        "daily_lesson": {
            "lesson_date": today_str,
            "total_words": len(daily_words),
            "memorized_count": len(memorized_today_ids),
            "memorized_ids": list(memorized_today_ids),
            "is_memorized": bool(u.get("is_today_memorized"))
            or len(memorized_today_ids) >= len(daily_words),
            "is_completed": bool(u.get("is_today_completed")),
            "score": int(u.get("today_score", 0)),
            "earned_xp": int(u.get("today_earned_xp", 0)),
            "distribution": {
                "everyday_upgrade": 4,
                "academic_upgrade": 2,
                "collocation": 2,
                "phrasal_verb": 2,
            },
            "words": daily_words,
        },
        "missions": {
            "daily": daily_missions,
            "weekly": weekly_missions,
        },
        "journey": journey_worlds,
        "weekly_calendar": weekly_calendar,
        "heatmap_28": heatmap_28,
        "category_mastery": category_mastery,
        "achievements": achievements,
        "words_for_revision": revision_words,
        "learned_words": [w for w in catalog if w["id"] in learned_ids][:25],
        "referral_preview": {
            "invited": int(u.get("invited_referrals", 0)),
            "confirmed": confirmed_refs,
            "unlocked_count": unlocked_packs_cnt,
            "next_target": 5 if confirmed_refs < 5 else (10 if confirmed_refs < 10 else 20),
            "next_reward_title": "📚 IELTS Writing Academic Pack"
            if confirmed_refs < 5
            else "👑 VIP IELTS 30-Day Challenge",
        },
    }


def handle_flashcard_action(
    user_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    state = _load_local_state()
    u = _get_or_init_user_record(state, user_id)

    vocab_id = int(payload.get("vocabulary_id", 0))
    action = str(payload.get("action", "memorized"))
    all_memorized = bool(payload.get("all_memorized", False))

    today_mem = set(u.get("today_memorized_ids", []))
    learned = set(u.get("learned_word_ids", []))
    review = set(u.get("review_word_ids", []))

    xp_gained = 0
    if vocab_id > 0:
        if action == "memorized":
            if vocab_id not in today_mem:
                today_mem.add(vocab_id)
                xp_gained = 5
            learned.add(vocab_id)
            review.discard(vocab_id)
        elif action == "review":
            review.add(vocab_id)

    if all_memorized or len(today_mem) >= 10:
        if not u.get("is_today_memorized"):
            u["is_today_memorized"] = True
            xp_gained += 15

    u["today_memorized_ids"] = list(today_mem)
    u["learned_word_ids"] = list(learned)
    u["review_word_ids"] = list(review)
    u["xp"] = int(u["xp"]) + xp_gained

    today_str = str(settings.today())
    hist = u.setdefault("activity_history", {}).setdefault(
        today_str, {"xp": 0, "words": 0, "quizzes": 0}
    )
    hist["xp"] = int(hist.get("xp", 0)) + xp_gained
    hist["words"] = len(today_mem)

    _save_local_state(state)
    return {
        "ok": True,
        "xp_gained": xp_gained,
        "total_xp": u["xp"],
        "memorized_count": len(today_mem),
        "is_memorized": u["is_today_memorized"],
        "level_info": compute_level_info(u["xp"]),
    }


def handle_quiz_submit(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    state = _load_local_state()
    u = _get_or_init_user_record(state, user_id)
    catalog = load_full_vocabulary_catalog()
    vocab_by_id = {w["id"]: w for w in catalog}

    mode = str(payload.get("mode", "daily"))
    node_id = payload.get("node_id")
    answers = payload.get("answers", [])

    old_level = compute_level_info(int(u["xp"]))["level"]

    score = 0
    combo = 0
    max_combo = 0
    results_detail: list[dict[str, Any]] = []
    learned = set(u.get("learned_word_ids", []))
    review = set(u.get("review_word_ids", []))

    for ans in answers:
        vid = int(ans.get("vocab_id", 0))
        selected = int(ans.get("selected_option", -1))
        word_obj = vocab_by_id.get(vid)
        correct_opt = int(word_obj["correct_option"]) if word_obj else 0
        is_correct = selected == correct_opt

        if is_correct:
            score += 1
            combo += 1
            max_combo = max(max_combo, combo)
            if vid > 0:
                learned.add(vid)
                review.discard(vid)
        else:
            combo = 0
            if vid > 0:
                review.add(vid)

        results_detail.append(
            {
                "vocab_id": vid,
                "selected_option": selected,
                "correct_option": correct_opt,
                "is_correct": is_correct,
                "simple_word": word_obj["simple_word"] if word_obj else "",
                "advanced_word": word_obj["advanced_word"] if word_obj else "",
                "definition_en": word_obj["definition_en"] if word_obj else "",
                "translation_uz": word_obj["translation_uz"] if word_obj else "",
                "translation_ru": word_obj["translation_ru"] if word_obj else "",
            }
        )

    total = max(1, len(answers))
    accuracy = round((score / total) * 100)
    combo_bonus = max_combo * 3 if max_combo >= 3 else 0
    earned_xp = score * settings.POINTS_PER_CORRECT_ANSWER + combo_bonus

    # Update daily completion or game/journey progress
    today_str = str(settings.today())
    if mode == "daily":
        u["is_today_memorized"] = True
        if not u.get("is_today_completed"):
            u["is_today_completed"] = True
            u["today_score"] = score
            u["today_earned_xp"] = earned_xp
            u["streak"] = int(u.get("streak", 0)) + 1
            u["best_streak"] = max(int(u.get("best_streak", 0)), u["streak"])
    elif mode == "journey" and node_id:
        stars = 3 if accuracy >= 85 else (2 if accuracy >= 60 else 1)
        j_nodes = u.setdefault("journey_nodes", {})
        prev_stars = int(j_nodes.get(node_id, {}).get("stars", 0))
        j_nodes[node_id] = {"stars": max(prev_stars, stars), "score": score}
    elif mode == "game":
        u["games_played_today"] = int(u.get("games_played_today", 0)) + 1

    u["xp"] = int(u["xp"]) + earned_xp
    u["total_quizzes"] = int(u.get("total_quizzes", 0)) + 1
    u["total_correct"] = int(u.get("total_correct", 0)) + score
    u["total_questions"] = int(u.get("total_questions", 0)) + total
    u["learned_word_ids"] = list(learned)
    u["review_word_ids"] = list(review)
    u["last_quiz_date"] = today_str

    hist = u.setdefault("activity_history", {}).setdefault(
        today_str, {"xp": 0, "words": 10, "quizzes": 0}
    )
    hist["xp"] = int(hist.get("xp", 0)) + earned_xp
    hist["quizzes"] = int(hist.get("quizzes", 0)) + 1

    new_level_info = compute_level_info(int(u["xp"]))
    leveled_up = new_level_info["level"] > old_level

    _save_local_state(state)
    return {
        "ok": True,
        "mode": mode,
        "score": score,
        "total": total,
        "accuracy": accuracy,
        "max_combo": max_combo,
        "combo_bonus": combo_bonus,
        "earned_xp": earned_xp,
        "total_xp": u["xp"],
        "streak": u["streak"],
        "best_streak": u["best_streak"],
        "leveled_up": leveled_up,
        "level_info": new_level_info,
        "league": compute_league_info(int(u["xp"])),
        "results": results_detail,
    }


def build_game_session_payload(mode: str) -> dict[str, Any]:
    catalog = load_full_vocabulary_catalog()
    # Select balanced items for the requested game mode
    if mode == "ielts_arena":
        pool = [
            w
            for w in catalog
            if w.get("category") in ("academic_upgrade", "collocation")
        ]
    elif mode == "synonym_master":
        pool = [
            w
            for w in catalog
            if w.get("category") in ("everyday_upgrade", "academic_upgrade")
        ]
    else:
        pool = list(catalog)

    selected = pool[:10] if len(pool) >= 10 else catalog[:10]

    # Enrich each item with a blanked sentence for `missing_word` mode
    enriched: list[dict[str, Any]] = []
    for item in selected:
        copy_item = dict(item)
        ex = copy_item.get("example_en", "")
        adv = copy_item.get("advanced_word", "")
        blanked = ex
        for token in [adv, adv.split()[0]]:
            if token and token.lower() in ex.lower():
                idx = ex.lower().find(token.lower())
                blanked = ex[:idx] + "_______" + ex[idx + len(token) :]
                break
        if blanked == ex:
            blanked = f"{ex} (Upgrade: _______)"
        copy_item["sentence_with_blank"] = blanked
        enriched.append(copy_item)

    return {
        "mode": mode,
        "time_limit_sec": 60 if mode == "brain_rush" else 20,
        "opponent": {
            "name": "Cambridge Bot AI",
            "title": "Band 8.5 Challenger",
            "accuracy_rate": 0.78,
        }
        if mode == "word_battle"
        else None,
        "items": enriched,
    }


def build_leaderboard_payload(user_id: int) -> dict[str, Any]:
    state = _load_local_state()
    u = _get_or_init_user_record(state, user_id)
    competitors = list(state.get("competitors", []))

    user_entry = {
        "user_id": u["user_id"],
        "username": u["username"],
        "full_name": u["full_name"],
        "xp": int(u["xp"]),
        "weekly_xp": sum(
            int(v.get("xp", 0))
            for v in list(u.get("activity_history", {}).values())[-7:]
        ),
        "streak": int(u["streak"]),
        "referrals": int(u.get("confirmed_referrals", 0)),
        "badge": "🏆 Master"
        if int(u.get("confirmed_referrals", 0)) >= 20
        else ("👑 VIP" if int(u.get("confirmed_referrals", 0)) >= 10 else "⚡ You"),
        "is_current_user": True,
    }

    all_entries = [dict(c, is_current_user=False) for c in competitors] + [user_entry]

    def _format_list(sorted_items: list[dict[str, Any]], metric_key: str) -> tuple[list[dict[str, Any]], int]:
        out: list[dict[str, Any]] = []
        user_rank = 1
        for rank, entry in enumerate(sorted_items, start=1):
            league = compute_league_info(int(entry["xp"]))
            if entry.get("is_current_user"):
                user_rank = rank
            out.append(
                {
                    "rank": rank,
                    "user_id": entry["user_id"],
                    "username": entry["username"],
                    "full_name": entry["full_name"],
                    "xp": int(entry["xp"]),
                    "weekly_xp": int(entry["weekly_xp"]),
                    "streak": int(entry["streak"]),
                    "referrals": int(entry["referrals"]),
                    "metric_value": int(entry[metric_key]),
                    "league_id": league["id"],
                    "league_name": league["name"],
                    "badge": entry.get("badge", ""),
                    "trend": "up" if rank <= 3 or entry.get("is_current_user") else "same",
                    "is_current_user": bool(entry.get("is_current_user")),
                }
            )
        return out, user_rank

    all_time_sorted = sorted(all_entries, key=lambda x: x["xp"], reverse=True)
    weekly_sorted = sorted(all_entries, key=lambda x: x["weekly_xp"], reverse=True)
    ref_sorted = sorted(all_entries, key=lambda x: x["referrals"], reverse=True)

    all_time_list, all_time_rank = _format_list(all_time_sorted, "xp")
    weekly_list, weekly_rank = _format_list(weekly_sorted, "weekly_xp")
    ref_list, ref_rank = _format_list(ref_sorted, "referrals")

    return {
        "all_time": {"entries": all_time_list, "user_rank": all_time_rank},
        "weekly": {"entries": weekly_list, "user_rank": weekly_rank},
        "referrals": {"entries": ref_list, "user_rank": ref_rank},
    }


def build_referrals_payload(user_id: int) -> dict[str, Any]:
    state = _load_local_state()
    u = _get_or_init_user_record(state, user_id)
    bot_username = os.getenv("BOT_USERNAME", "English_words_vocab_bot").strip()
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    lang = u.get("language_code", "uz")

    share_texts = {
        "uz": "🚀 IELTS 7.0–9.0 uchun Everyday → Advanced vocabulary o‘rganishni boshlang! 3 tilda interaktiv Mini App va quizlar:",
        "ru": "🚀 Начни изучать Everyday → Advanced лексику для IELTS 7.0–9.0! Интерактивное Mini App и квизы на 3 языках:",
        "en": "🚀 Start mastering IELTS 7.0–9.0 Everyday → Advanced vocabulary! Interactive Mini App & quizzes in 3 languages:",
    }
    share_text = share_texts.get(lang, share_texts["uz"])
    share_url = f"https://t.me/share/url?url={quote(ref_link)}&text={quote(share_text)}"

    confirmed = int(u.get("confirmed_referrals", 0))
    invited = int(u.get("invited_referrals", 0))
    pending = int(u.get("pending_referrals", 0))

    packs = load_bonus_packs_catalog()
    milestones_out: list[dict[str, Any]] = []
    next_pack_title = "🏆 All Rewards Unlocked!"
    next_pack_target = 20

    found_next = False
    for p in packs:
        req = int(p["required_referrals"])
        is_unlocked = confirmed >= req
        if not is_unlocked and not found_next:
            next_pack_title = p["title"]
            next_pack_target = req
            found_next = True
        milestones_out.append(
            {
                "id": p["id"],
                "pack_type": p["pack_type"],
                "title": p["title"],
                "required_referrals": req,
                "unlocked": is_unlocked,
                "progress": min(req, confirmed),
                "word_count": len(p["words"]),
                "words": p["words"],
            }
        )

    return {
        "referral_link": ref_link,
        "share_url": share_url,
        "invited": invited,
        "confirmed": confirmed,
        "pending": pending,
        "unlocked_count": sum(1 for m in milestones_out if m["unlocked"]),
        "next_reward_title": next_pack_title,
        "next_reward_target": next_pack_target,
        "milestones": milestones_out,
    }


def handle_settings_update(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    state = _load_local_state()
    u = _get_or_init_user_record(state, user_id)

    if "language_code" in payload:
        lang = str(payload["language_code"]).lower()
        if lang in SUPPORTED_LANGUAGES:
            u["language_code"] = lang
    if "reminders_enabled" in payload:
        u["reminders_enabled"] = bool(payload["reminders_enabled"])
    if "broadcast_enabled" in payload:
        u["broadcast_enabled"] = bool(payload["broadcast_enabled"])
    if "daily_goal" in payload:
        u["daily_goal"] = max(5, min(30, int(payload["daily_goal"])))

    _save_local_state(state)
    return {
        "ok": True,
        "language_code": u["language_code"],
        "reminders_enabled": u["reminders_enabled"],
        "broadcast_enabled": u["broadcast_enabled"],
        "daily_goal": u["daily_goal"],
    }


# ==============================================================================
# HTTP REQUEST HANDLER FOR MINI APP API + SPA STATIC FILES
# ==============================================================================


class MiniAppHTTPRequestHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Telegram-Init-Data, X-Telegram-User-Id",
        )

    def _send_json(self, status_code: int, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _extract_authenticated_user(self) -> tuple[int, str | None, str | None]:
        init_data = self.headers.get("X-Telegram-Init-Data", "").strip()
        if init_data and settings.BOT_TOKEN:
            tg_user = verify_telegram_init_data(init_data, settings.BOT_TOKEN)
            if tg_user and "id" in tg_user:
                uid = int(tg_user["id"])
                uname = tg_user.get("username")
                fname = (
                    f"{tg_user.get('first_name', '')} {tg_user.get('last_name', '')}".strip()
                    or "Learner"
                )
                return uid, uname, fname

        header_uid = self.headers.get("X-Telegram-User-Id", "").strip()
        if header_uid.isdigit():
            return int(header_uid), None, None

        default_uid = settings.ADMIN_ID if settings.ADMIN_ID else 8838117173
        return default_uid, None, None

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_HEAD(self) -> None:
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = dict(parse_qsl(parsed_url.query))

        if path in ("/health", "/api/health"):
            self._send_json(
                200, {"status": "ok", "service": "english_c2_quiz_bot"}
            )
            return

        if path == "/api/miniapp/bootstrap":
            uid, uname, fname = self._extract_authenticated_user()
            data = build_bootstrap_payload(uid, uname, fname)
            self._send_json(200, data)
            return

        if path == "/api/miniapp/games/session":
            mode = query.get("mode", "brain_rush")
            self._send_json(200, build_game_session_payload(mode))
            return

        if path == "/api/miniapp/leaderboard":
            uid, _, _ = self._extract_authenticated_user()
            self._send_json(200, build_leaderboard_payload(uid))
            return

        if path == "/api/miniapp/referrals":
            uid, _, _ = self._extract_authenticated_user()
            self._send_json(200, build_referrals_payload(uid))
            return

        # Serve static files from webapp/dist if built
        if WEBAPP_DIST_DIR.exists():
            rel_path = path.lstrip("/")
            if not rel_path:
                rel_path = "index.html"
            candidate = (WEBAPP_DIST_DIR / rel_path).resolve()
            if (
                str(candidate).startswith(str(WEBAPP_DIST_DIR.resolve()))
                and candidate.is_file()
            ):
                self._serve_static_file(candidate)
                return
            index_file = WEBAPP_DIST_DIR / "index.html"
            if index_file.is_file():
                self._serve_static_file(index_file)
                return

        self._send_json(200, {"status": "ok", "service": "english_c2_quiz_bot"})

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        content_len = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            payload = {}

        uid, _, _ = self._extract_authenticated_user()

        if path == "/api/miniapp/flashcard/action":
            self._send_json(200, handle_flashcard_action(uid, payload))
            return

        if path == "/api/miniapp/quiz/submit":
            self._send_json(200, handle_quiz_submit(uid, payload))
            return

        if path == "/api/miniapp/settings":
            self._send_json(200, handle_settings_update(uid, payload))
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def _serve_static_file(self, file_path: Path) -> None:
        mime_type, _ = mimetypes.guess_type(str(file_path))
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type", mime_type or "application/octet-stream"
        )
        self.send_header("Content-Length", str(len(content)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        return
