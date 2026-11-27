import asyncio
import json
import logging
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import settings
from services.admin_export_service import (
    export_vocabulary_csv,
    export_vocabulary_pdf,
    export_vocabulary_xlsx,
)
from services.normalizer import normalize_expression

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
RECOVERED_HIST_PATH = ROOT_DIR / "data" / "recovered_historical_vocabulary.json"
RESERVE_VOCAB_PATH = ROOT_DIR / "data" / "reserve_vocabulary.json"
BONUS_PACKS_PATH = ROOT_DIR / "data" / "bonus_packs_seed.json"
LOCAL_ADMIN_STATE_PATH = ROOT_DIR / "data" / ".local_admin_library.json"

# Spaced repetition intervals in days (Section 8)
SRS_INTERVALS_DAYS = [1, 3, 7, 14, 30]


def compute_next_srs(
    current_stage: int,
    action: str,
    now: datetime | None = None,
) -> tuple[str, int, int, datetime]:
    """
    Calculate updated status, srs_stage, interval_days, and next_review_at
    based on admin flashcard or quiz performance.
    Actions: 'memorized' | 'difficult' | 'later' | 'quiz_wrong' | 'quiz_correct'
    """
    ts = now or datetime.now(timezone.utc)
    if action in ("memorized", "quiz_correct"):
        next_stage = min(max(0, current_stage) + 1, len(SRS_INTERVALS_DAYS))
        interval = SRS_INTERVALS_DAYS[min(next_stage - 1, len(SRS_INTERVALS_DAYS) - 1)]
        return "memorized", next_stage, interval, ts + timedelta(days=interval)

    if action in ("difficult", "quiz_wrong"):
        return "difficult", 0, 1, ts + timedelta(days=1)

    # 'later' (KEYINROQ) -> review again in 12 hours / 1 day without marking memorized
    return "later", max(0, current_stage), 1, ts + timedelta(hours=12)


# ==============================================================================
# RECOVERABLE APPLICATION RECORDS LOADER (NO INVENTED ITEMS)
# ==============================================================================


def load_recoverable_seed_records() -> list[dict[str, Any]]:
    """
    Collect all authentic vocabulary items present in recoverable repository files:
    1. `data/recovered_historical_vocabulary.json` (19 historical launch items from commit fa3ff96, 2026-11-22)
    2. `data/reserve_vocabulary.json` (40 Everyday -> Advanced 4+2+2+2 items, 2026-11-23+)
    3. `data/bonus_packs_seed.json` (40 IELTS Milestone Bonus Pack items, 2026-11-23+)
    Deduplicated strictly by `normalized_expression`.
    """
    records: list[dict[str, Any]] = []
    seen_norms: set[str] = set()

    def _append_entry(
        raw: dict[str, Any],
        gen_date_str: str,
        origin_type: str,
    ) -> None:
        adv = str(raw.get("advanced_word") or raw.get("advanced_expression") or "").strip()
        basic = str(raw.get("simple_word") or raw.get("basic_expression") or "").strip()
        if not adv or not basic:
            return
        norm = normalize_expression(adv)
        if not norm or norm in seen_norms:
            return
        seen_norms.add(norm)

        opts = list(raw.get("options") or [])
        while len(opts) < 4:
            opts.append(f"Option {len(opts) + 1}")
        correct_opt = int(raw.get("correct_option", 0))
        if not (0 <= correct_opt < 4):
            correct_opt = 0
        opts[correct_opt] = adv

        records.append(
            {
                "normalized_expression": norm,
                "basic_expression": basic,
                "advanced_expression": adv,
                "translation_uz": str(raw.get("translation_uz", "") or ""),
                "translation_ru": str(raw.get("translation_ru", "") or ""),
                "definition_en": str(raw.get("definition_en", "") or ""),
                "basic_example_en": str(
                    raw.get("basic_example_en")
                    or f'In everyday English: "{basic}".'
                ),
                "example_en": str(raw.get("example_en", "") or ""),
                "example_uz": str(raw.get("example_uz", "") or ""),
                "example_ru": str(raw.get("example_ru", "") or ""),
                "usage_context": str(
                    raw.get("ielts_usage")
                    or raw.get("usage_context")
                    or "Writing Task 2 & Speaking Part 3"
                ),
                "cefr_level": str(raw.get("cefr_level", "B2–C1") or "B2–C1"),
                "category": str(raw.get("category", "everyday_upgrade") or "everyday_upgrade"),
                "original_generation_date": gen_date_str,
                "origin_type": origin_type,
                "options": opts[:4],
                "correct_option": correct_opt,
            }
        )

    # 1. Historical launch commit items (2026-11-22)
    if RECOVERED_HIST_PATH.exists():
        try:
            hist_list = json.loads(RECOVERED_HIST_PATH.read_text(encoding="utf-8"))
            for item in hist_list:
                _append_entry(
                    item,
                    str(item.get("original_generation_date", "2026-11-22")),
                    "historical_commit_fa3ff96",
                )
        except Exception as exc:
            logger.warning("Could not read recovered_historical_vocabulary.json: %s", exc)

    # 2. Bonus pack seed items (2026-11-23)
    if BONUS_PACKS_PATH.exists():
        try:
            packs = json.loads(BONUS_PACKS_PATH.read_text(encoding="utf-8")).get("packs", [])
            for p in packs:
                for item in p.get("items", []):
                    _append_entry(item, "2026-11-23", f"bonus_pack:{p.get('pack_type', 'pack')}")
        except Exception as exc:
            logger.warning("Could not read bonus_packs_seed.json: %s", exc)

    # 3. Current 4+2+2+2 reserve items distributed across launch dates (2026-11-23 .. today)
    if RESERVE_VOCAB_PATH.exists():
        try:
            res_list = json.loads(RESERVE_VOCAB_PATH.read_text(encoding="utf-8"))
            today_str = str(settings.today())
            for idx, item in enumerate(res_list[:40]):
                if idx < 10:
                    d_str = "2026-11-24"
                elif idx < 20:
                    d_str = "2026-11-25"
                elif idx < 30:
                    d_str = today_str
                else:
                    d_str = today_str
                _append_entry(item, d_str, "daily_curriculum")
        except Exception as exc:
            logger.warning("Could not read reserve_vocabulary.json: %s", exc)

    return records


# ==============================================================================
# POSTGRESQL PERMANENT ARCHIVE SYNCHRONIZATION (IDEMPOTENT & TRANSACTIONAL)
# ==============================================================================


async def sync_permanent_vocabulary_archive_pg(session: Any) -> dict[str, int]:
    """
    Idempotently synchronize:
    1. All rows in PostgreSQL `vocabulary` (preserving exact `daily_lessons.lesson_date`
       or `vocabulary.created_at::date` as `original_generation_date`).
    2. All recoverable application records (`recovered_historical_vocabulary.json` + seed records).
    Never deletes existing rows, never overwrites original generation dates,
    and makes zero Gemini API calls.
    """
    from sqlalchemy import select
    from database.models import (
        DailyLesson,
        DailyLessonItem,
        Vocabulary,
        VocabularyArchive,
    )

    existing_stmt = select(VocabularyArchive.normalized_expression)
    existing_norms = {
        row[0] for row in (await session.execute(existing_stmt)).all() if row[0]
    }
    initial_count = len(existing_norms)
    inserted_from_db = 0
    inserted_from_records = 0

    # Map vocabulary_id -> lesson_date from daily_lessons
    lesson_dates_stmt = select(
        DailyLessonItem.vocabulary_id, DailyLesson.lesson_date
    ).join(DailyLesson, DailyLesson.id == DailyLessonItem.lesson_id)
    vocab_lesson_dates: dict[int, date] = {
        vid: ldate for vid, ldate in (await session.execute(lesson_dates_stmt)).all()
    }

    # 1. Sync all rows from `vocabulary` table
    vocab_rows = list(
        (await session.execute(select(Vocabulary).order_by(Vocabulary.id)))
        .scalars()
        .all()
    )
    for v in vocab_rows:
        norm = v.normalized_expression or normalize_expression(v.advanced_word)
        if not norm or norm in existing_norms:
            continue
        gen_date = vocab_lesson_dates.get(v.id) or (
            v.created_at.date() if v.created_at else settings.today()
        )
        origin = "daily_lesson" if v.id in vocab_lesson_dates else "vocabulary_db"
        session.add(
            VocabularyArchive(
                vocabulary_id=v.id,
                normalized_expression=norm,
                basic_expression=v.simple_word,
                advanced_expression=v.advanced_word,
                translation_uz=v.translation_uz,
                translation_ru=v.translation_ru,
                definition_en=v.definition_en,
                basic_example_en=v.basic_example_en,
                example_en=v.example_en,
                example_uz=v.example_uz,
                example_ru=v.example_ru,
                usage_context=v.ielts_usage or "Writing Task 2 & Speaking Part 3",
                cefr_level=v.cefr_level or "B2–C1",
                category=v.category or "everyday_upgrade",
                original_generation_date=gen_date,
                origin_type=origin,
                option_a=v.option_a,
                option_b=v.option_b,
                option_c=v.option_c,
                option_d=v.option_d,
                correct_option=v.correct_option,
            )
        )
        existing_norms.add(norm)
        inserted_from_db += 1

    # 2. Sync recoverable historical & seed records not yet in archive
    for rec in load_recoverable_seed_records():
        norm = rec["normalized_expression"]
        if norm in existing_norms:
            continue
        try:
            gen_date = date.fromisoformat(rec["original_generation_date"])
        except ValueError:
            gen_date = settings.today()

        opts = rec["options"]
        session.add(
            VocabularyArchive(
                vocabulary_id=None,
                normalized_expression=norm,
                basic_expression=rec["basic_expression"],
                advanced_expression=rec["advanced_expression"],
                translation_uz=rec["translation_uz"],
                translation_ru=rec["translation_ru"],
                definition_en=rec["definition_en"],
                basic_example_en=rec["basic_example_en"],
                example_en=rec["example_en"],
                example_uz=rec["example_uz"],
                example_ru=rec["example_ru"],
                usage_context=rec["usage_context"],
                cefr_level=rec["cefr_level"],
                category=rec["category"],
                original_generation_date=gen_date,
                origin_type=rec["origin_type"],
                option_a=opts[0],
                option_b=opts[1],
                option_c=opts[2],
                option_d=opts[3],
                correct_option=rec["correct_option"],
            )
        )
        existing_norms.add(norm)
        inserted_from_records += 1

    if inserted_from_db > 0 or inserted_from_records > 0:
        await session.commit()

    logger.info(
        "Permanent vocabulary archive synced: existing=%d, from_db=%d, from_recoverable=%d, total=%d",
        initial_count,
        inserted_from_db,
        inserted_from_records,
        len(existing_norms),
    )
    return {
        "existing": initial_count,
        "inserted_from_db": inserted_from_db,
        "inserted_from_recoverable": inserted_from_records,
        "total": len(existing_norms),
    }


async def sync_daily_vocab_objects_to_archive_in_tx(
    session: Any,
    vocab_objects: list[Any],
    lesson_date: date,
) -> None:
    """
    Called inside `crud.save_generated_daily_lesson` transaction whenever Gemini
    generates 10 new daily items so the permanent library updates atomically.
    """
    from sqlalchemy import select
    from database.models import VocabularyArchive

    norms = [v.normalized_expression for v in vocab_objects if v.normalized_expression]
    if not norms:
        return
    existing_stmt = select(VocabularyArchive.normalized_expression).where(
        VocabularyArchive.normalized_expression.in_(norms)
    )
    existing = {row[0] for row in (await session.execute(existing_stmt)).all()}

    for v in vocab_objects:
        if not v.normalized_expression or v.normalized_expression in existing:
            continue
        session.add(
            VocabularyArchive(
                vocabulary_id=v.id,
                normalized_expression=v.normalized_expression,
                basic_expression=v.simple_word,
                advanced_expression=v.advanced_word,
                translation_uz=v.translation_uz,
                translation_ru=v.translation_ru,
                definition_en=v.definition_en,
                basic_example_en=v.basic_example_en,
                example_en=v.example_en,
                example_uz=v.example_uz,
                example_ru=v.example_ru,
                usage_context=v.ielts_usage or "Writing Task 2 & Speaking Part 3",
                cefr_level=v.cefr_level or "B2–C1",
                category=v.category or "everyday_upgrade",
                original_generation_date=lesson_date,
                origin_type="daily_lesson",
                option_a=v.option_a,
                option_b=v.option_b,
                option_c=v.option_c,
                option_d=v.option_d,
                correct_option=v.correct_option,
            )
        )
        existing.add(v.normalized_expression)


# ==============================================================================
# UNIFIED STORE ENGINE (POSTGRESQL + LOCAL FALLBACK FOR OFFLINE/DEV TESTS)
# ==============================================================================


def _load_local_admin_store() -> dict[str, Any]:
    state: dict[str, Any] = {
        "archive": [],
        "progress": {},  # admin_id_str -> { archive_id_str -> progress_dict }
        "sessions": {},  # admin_id_str -> session_dict
        "quiz_history": {},  # admin_id_str -> list[quiz_attempt]
    }
    if LOCAL_ADMIN_STATE_PATH.exists():
        try:
            state = json.loads(LOCAL_ADMIN_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Always idempotently sync recoverable records into local archive
    archive_list: list[dict[str, Any]] = state.setdefault("archive", [])
    existing_norms = {item["normalized_expression"] for item in archive_list}
    next_id = max((int(item["id"]) for item in archive_list), default=0) + 1
    changed = False

    for rec in load_recoverable_seed_records():
        if rec["normalized_expression"] not in existing_norms:
            entry = dict(rec)
            entry["id"] = next_id
            next_id += 1
            archive_list.append(entry)
            existing_norms.add(rec["normalized_expression"])
            changed = True

    if changed:
        _save_local_admin_store(state)
    return state


def _save_local_admin_store(state: dict[str, Any]) -> None:
    try:
        LOCAL_ADMIN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_ADMIN_STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning("Failed to save local admin library state: %s", exc)


async def _fetch_archive_and_progress_pg(
    session: Any, admin_id: int
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], list[dict[str, Any]]]:
    from sqlalchemy import desc, select
    from database.models import (
        AdminQuizHistory,
        AdminVocabProgress,
        VocabularyArchive,
    )

    await sync_permanent_vocabulary_archive_pg(session)

    arch_rows = list(
        (
            await session.execute(
                select(VocabularyArchive).order_by(
                    desc(VocabularyArchive.original_generation_date),
                    desc(VocabularyArchive.id),
                )
            )
        )
        .scalars()
        .all()
    )
    prog_rows = list(
        (
            await session.execute(
                select(AdminVocabProgress).where(
                    AdminVocabProgress.admin_id == admin_id
                )
            )
        )
        .scalars()
        .all()
    )
    quiz_rows = list(
        (
            await session.execute(
                select(AdminQuizHistory)
                .where(AdminQuizHistory.admin_id == admin_id)
                .order_by(desc(AdminQuizHistory.created_at))
                .limit(50)
            )
        )
        .scalars()
        .all()
    )

    prog_map: dict[int, dict[str, Any]] = {}
    for p in prog_rows:
        prog_map[p.archive_id] = {
            "status": p.status,
            "srs_stage": p.srs_stage,
            "interval_days": p.interval_days,
            "next_review_at": p.next_review_at.isoformat() if p.next_review_at else None,
            "last_reviewed_at": p.last_reviewed_at.isoformat() if p.last_reviewed_at else None,
            "review_count": p.review_count,
            "correct_count": p.correct_count,
            "wrong_count": p.wrong_count,
            "last_quiz_wrong": p.last_quiz_wrong,
        }

    items: list[dict[str, Any]] = []
    for a in arch_rows:
        items.append(
            {
                "id": a.id,
                "normalized_expression": a.normalized_expression,
                "basic_expression": a.basic_expression,
                "advanced_expression": a.advanced_expression,
                "translation_uz": a.translation_uz,
                "translation_ru": a.translation_ru or "",
                "definition_en": a.definition_en,
                "basic_example_en": a.basic_example_en or f'In everyday English: "{a.basic_expression}".',
                "example_en": a.example_en,
                "example_uz": a.example_uz or "",
                "example_ru": a.example_ru or "",
                "usage_context": a.usage_context,
                "cefr_level": a.cefr_level,
                "category": a.category,
                "original_generation_date": str(a.original_generation_date),
                "origin_type": a.origin_type,
                "options": a.get_options(),
                "correct_option": a.correct_option,
            }
        )

    quizzes = [
        {
            "id": q.id,
            "question_count": q.question_count,
            "correct_count": q.correct_count,
            "accuracy": q.accuracy,
            "wrong_archive_ids": q.wrong_archive_ids or [],
            "filter_mode": q.filter_mode,
            "created_at": q.created_at.isoformat() if q.created_at else "",
        }
        for q in quiz_rows
    ]
    return items, prog_map, quizzes


def _merge_items_with_progress(
    raw_items: list[dict[str, Any]],
    prog_map: dict[int, dict[str, Any]],
    now_iso: str,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in raw_items:
        aid = int(item["id"])
        p = prog_map.get(aid, {})
        status = p.get("status", "unmemorized")
        next_rev = p.get("next_review_at")
        last_wrong = bool(p.get("last_quiz_wrong", False))
        is_due = False
        if status == "difficult" or last_wrong:
            is_due = True
        elif next_rev and next_rev <= now_iso:
            is_due = True

        merged = dict(item)
        merged["admin_status"] = status
        merged["srs_stage"] = int(p.get("srs_stage", 0))
        merged["interval_days"] = int(p.get("interval_days", 0))
        merged["next_review_at"] = next_rev
        merged["review_count"] = int(p.get("review_count", 0))
        merged["correct_count"] = int(p.get("correct_count", 0))
        merged["wrong_count"] = int(p.get("wrong_count", 0))
        merged["last_quiz_wrong"] = last_wrong
        merged["is_revision_due"] = is_due
        enriched.append(merged)
    return enriched


def filter_archive_items(
    items: list[dict[str, Any]],
    mode: str = "all",
    search_query: str = "",
    category: str = "",
    date_from: str = "",
    date_to: str = "",
) -> list[dict[str, Any]]:
    """
    Filter archive items across all 10+ required memorization & revision modes,
    plus instant search, category, and custom date range.
    """
    today = settings.today()
    today_str = str(today)
    d7_str = str(today - timedelta(days=6))
    d30_str = str(today - timedelta(days=29))

    q = (search_query or "").strip().lower()
    cat = (category or "").strip().lower()

    filtered: list[dict[str, Any]] = []
    for item in items:
        status = item.get("admin_status", "unmemorized")
        gen_date = item.get("original_generation_date", "")

        if mode == "unmemorized" and status == "memorized":
            continue
        elif mode == "memorized" and status != "memorized":
            continue
        elif mode == "difficult" and status != "difficult":
            continue
        elif mode == "incorrect" and not (
            item.get("last_quiz_wrong") or int(item.get("wrong_count", 0)) > 0
        ):
            continue
        elif mode == "today" and gen_date != today_str:
            continue
        elif mode == "last_7d" and gen_date < d7_str:
            continue
        elif mode == "last_30d" and gen_date < d30_str:
            continue
        elif mode == "srs_due" and not item.get("is_revision_due"):
            continue

        if date_from and gen_date < date_from:
            continue
        if date_to and gen_date > date_to:
            continue

        if cat and cat != "all" and item.get("category", "").lower() != cat:
            continue

        if q:
            haystack = " ".join(
                [
                    str(item.get("basic_expression", "")),
                    str(item.get("advanced_expression", "")),
                    str(item.get("translation_uz", "")),
                    str(item.get("translation_ru", "")),
                    str(item.get("definition_en", "")),
                    str(item.get("category", "")),
                    str(gen_date),
                ]
            ).lower()
            if q not in haystack:
                continue

        filtered.append(item)

    # Smart Revision sorting: prioritize difficult & wrong-in-quiz first, then earliest next_review_at
    if mode == "srs_due":
        filtered.sort(
            key=lambda x: (
                0 if x.get("admin_status") == "difficult" else 1,
                0 if x.get("last_quiz_wrong") else 1,
                x.get("next_review_at") or "0000-00-00",
            )
        )

    return filtered


def compute_admin_statistics(
    items: list[dict[str, Any]],
    quizzes: list[dict[str, Any]],
) -> dict[str, Any]:
    today = settings.today()
    today_str = str(today)
    week_start_str = str(today - timedelta(days=6))
    month_start_str = str(today - timedelta(days=29))

    total = len(items)
    added_today = sum(1 for x in items if x["original_generation_date"] == today_str)
    added_week = sum(1 for x in items if x["original_generation_date"] >= week_start_str)
    added_month = sum(1 for x in items if x["original_generation_date"] >= month_start_str)

    memorized = sum(1 for x in items if x["admin_status"] == "memorized")
    difficult = sum(1 for x in items if x["admin_status"] == "difficult")
    unmemorized = max(0, total - memorized)
    revision_due = sum(1 for x in items if x.get("is_revision_due"))
    incorrect_cnt = sum(
        1 for x in items if x.get("last_quiz_wrong") or int(x.get("wrong_count", 0)) > 0
    )

    total_q_asked = sum(int(q.get("question_count", 0)) for q in quizzes)
    total_q_corr = sum(int(q.get("correct_count", 0)) for q in quizzes)
    quiz_accuracy = (
        round((total_q_corr / total_q_asked) * 100, 1)
        if total_q_asked > 0
        else 0.0
    )
    completion_pct = round((memorized / total) * 100, 1) if total > 0 else 0.0

    # Category counts & available dates
    cat_counts: dict[str, int] = {}
    date_counts: dict[str, int] = {}
    origin_counts: dict[str, int] = {}
    for x in items:
        c = x.get("category", "everyday_upgrade")
        cat_counts[c] = cat_counts.get(c, 0) + 1
        d = x.get("original_generation_date", "")
        if d:
            date_counts[d] = date_counts.get(d, 0) + 1
        o = x.get("origin_type", "daily_lesson")
        origin_counts[o] = origin_counts.get(o, 0) + 1

    return {
        "total_archived": total,
        "added_today": added_today,
        "added_this_week": added_week,
        "added_this_month": added_month,
        "memorized_count": memorized,
        "unmemorized_count": unmemorized,
        "difficult_count": difficult,
        "incorrect_count": incorrect_cnt,
        "revision_due_count": revision_due,
        "quiz_accuracy": quiz_accuracy,
        "total_quizzes_taken": len(quizzes),
        "completion_percentage": completion_pct,
        "categories": cat_counts,
        "dates": dict(sorted(date_counts.items(), reverse=True)),
        "origins": origin_counts,
    }


def generate_randomized_quiz_from_items(
    candidate_items: list[dict[str, Any]],
    all_archive_items: list[dict[str, Any]],
    question_count: int = 10,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """
    Generate an ABCD quiz with randomized answer positions and exactly one correct answer
    purely from stored vocabulary archive content (zero Gemini API requests!).
    """
    rng = random.Random(seed)
    pool = list(candidate_items)
    rng.shuffle(pool)
    selected = pool[: max(1, min(question_count, len(pool)))]

    all_adv_pool = [x["advanced_expression"] for x in all_archive_items]

    questions: list[dict[str, Any]] = []
    for item in selected:
        correct_adv = item["advanced_expression"]
        raw_opts = [o for o in item.get("options", []) if o]

        # Ensure 3 distinct plausible distractors + 1 exact correct answer
        distractors = [
            o
            for o in raw_opts
            if normalize_expression(o) != normalize_expression(correct_adv)
        ]
        if len(distractors) < 3:
            extra_candidates = [
                a
                for a in all_adv_pool
                if normalize_expression(a) != normalize_expression(correct_adv)
                and a not in distractors
            ]
            rng.shuffle(extra_candidates)
            distractors.extend(extra_candidates[: 3 - len(distractors)])

        four_choices = distractors[:3] + [correct_adv]
        rng.shuffle(four_choices)
        new_correct_idx = four_choices.index(correct_adv)

        questions.append(
            {
                "archive_id": item["id"],
                "basic_expression": item["basic_expression"],
                "advanced_expression": correct_adv,
                "translation_uz": item["translation_uz"],
                "translation_ru": item["translation_ru"],
                "definition_en": item["definition_en"],
                "basic_example_en": item["basic_example_en"],
                "example_en": item["example_en"],
                "usage_context": item["usage_context"],
                "cefr_level": item["cefr_level"],
                "category": item["category"],
                "original_generation_date": item["original_generation_date"],
                "options": four_choices,
                "correct_option": new_correct_idx,
            }
        )

    return questions


# ==============================================================================
# HIGH-LEVEL SERVICE OPERATIONS (SUPPORTS BOTH ASYNC PG & SYNC LOCAL FALLBACK)
# ==============================================================================


class AdminLibraryManager:
    """
    Unified manager used by both the Telegram Bot Admin Panel (async SQLAlchemy)
    and the Mini App Admin Dashboard REST API.
    """

    async def get_enriched_items_and_stats_pg(
        self, session: Any, admin_id: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
        from sqlalchemy import select
        from database.models import AdminLearningSession

        raw_items, prog_map, quizzes = await _fetch_archive_and_progress_pg(
            session, admin_id
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        items = _merge_items_with_progress(raw_items, prog_map, now_iso)
        stats = compute_admin_statistics(items, quizzes)

        sess_row = (
            await session.execute(
                select(AdminLearningSession).where(
                    AdminLearningSession.admin_id == admin_id
                )
            )
        ).scalar_one_or_none()
        saved_session = None
        if sess_row and not sess_row.is_completed and sess_row.archive_ids:
            saved_session = {
                "mode": sess_row.mode,
                "archive_ids": sess_row.archive_ids,
                "current_index": sess_row.current_index,
                "total": len(sess_row.archive_ids),
                "updated_at": sess_row.updated_at.isoformat() if sess_row.updated_at else "",
            }

        return items, stats, saved_session

    def get_enriched_items_and_stats_local(
        self, admin_id: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
        state = _load_local_admin_store()
        raw_items = sorted(
            state["archive"],
            key=lambda x: (x.get("original_generation_date", ""), int(x["id"])),
            reverse=True,
        )
        raw_prog = state.get("progress", {}).get(str(admin_id), {})
        prog_map = {int(k): v for k, v in raw_prog.items()}
        quizzes = state.get("quiz_history", {}).get(str(admin_id), [])

        now_iso = datetime.now(timezone.utc).isoformat()
        items = _merge_items_with_progress(raw_items, prog_map, now_iso)
        stats = compute_admin_statistics(items, quizzes)

        sess = state.get("sessions", {}).get(str(admin_id))
        saved_session = (
            sess
            if sess and not sess.get("is_completed") and sess.get("archive_ids")
            else None
        )
        return items, stats, saved_session

    async def update_flashcard_progress_pg(
        self,
        session: Any,
        admin_id: int,
        archive_id: int,
        action: str,
        session_index: int | None = None,
    ) -> dict[str, Any]:
        from sqlalchemy import select
        from database.models import AdminLearningSession, AdminVocabProgress

        now = datetime.now(timezone.utc)
        stmt = select(AdminVocabProgress).where(
            AdminVocabProgress.admin_id == admin_id,
            AdminVocabProgress.archive_id == archive_id,
        )
        prog = (await session.execute(stmt)).scalar_one_or_none()
        cur_stage = prog.srs_stage if prog else 0
        new_status, next_stage, interval, next_rev = compute_next_srs(
            cur_stage, action, now
        )

        if prog is None:
            prog = AdminVocabProgress(
                admin_id=admin_id,
                archive_id=archive_id,
                status=new_status,
                srs_stage=next_stage,
                interval_days=interval,
                next_review_at=next_rev,
                last_reviewed_at=now,
                memorized_at=now if new_status == "memorized" else None,
                review_count=1,
                last_quiz_wrong=False if new_status == "memorized" else False,
            )
            session.add(prog)
        else:
            prog.status = new_status
            prog.srs_stage = next_stage
            prog.interval_days = interval
            prog.next_review_at = next_rev
            prog.last_reviewed_at = now
            prog.review_count = (prog.review_count or 0) + 1
            if new_status == "memorized":
                prog.memorized_at = now
                prog.last_quiz_wrong = False

        if session_index is not None:
            l_sess = (
                await session.execute(
                    select(AdminLearningSession).where(
                        AdminLearningSession.admin_id == admin_id
                    )
                )
            ).scalar_one_or_none()
            if l_sess and l_sess.archive_ids:
                if session_index >= len(l_sess.archive_ids) - 1:
                    l_sess.is_completed = True
                else:
                    l_sess.current_index = session_index + 1

        await session.commit()
        return {
            "ok": True,
            "archive_id": archive_id,
            "status": new_status,
            "srs_stage": next_stage,
            "interval_days": interval,
            "next_review_at": next_rev.isoformat(),
        }

    def update_flashcard_progress_local(
        self,
        admin_id: int,
        archive_id: int,
        action: str,
        session_index: int | None = None,
    ) -> dict[str, Any]:
        state = _load_local_admin_store()
        admin_prog = state.setdefault("progress", {}).setdefault(str(admin_id), {})
        prev = admin_prog.get(str(archive_id), {})
        now = datetime.now(timezone.utc)
        new_status, next_stage, interval, next_rev = compute_next_srs(
            int(prev.get("srs_stage", 0)), action, now
        )
        admin_prog[str(archive_id)] = {
            "status": new_status,
            "srs_stage": next_stage,
            "interval_days": interval,
            "next_review_at": next_rev.isoformat(),
            "last_reviewed_at": now.isoformat(),
            "review_count": int(prev.get("review_count", 0)) + 1,
            "correct_count": int(prev.get("correct_count", 0)),
            "wrong_count": int(prev.get("wrong_count", 0)),
            "last_quiz_wrong": False if new_status == "memorized" else bool(prev.get("last_quiz_wrong", False)),
        }

        if session_index is not None:
            sess = state.setdefault("sessions", {}).get(str(admin_id))
            if sess and sess.get("archive_ids"):
                if session_index >= len(sess["archive_ids"]) - 1:
                    sess["is_completed"] = True
                else:
                    sess["current_index"] = session_index + 1
                sess["updated_at"] = now.isoformat()

        _save_local_admin_store(state)
        return {
            "ok": True,
            "archive_id": archive_id,
            "status": new_status,
            "srs_stage": next_stage,
            "interval_days": interval,
            "next_review_at": next_rev.isoformat(),
        }

    async def save_learning_session_pg(
        self,
        session: Any,
        admin_id: int,
        mode: str,
        archive_ids: list[int],
        current_index: int = 0,
        filter_meta: dict | None = None,
    ) -> dict[str, Any]:
        from sqlalchemy import select
        from database.models import AdminLearningSession

        stmt = select(AdminLearningSession).where(
            AdminLearningSession.admin_id == admin_id
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = AdminLearningSession(
                admin_id=admin_id,
                mode=mode,
                filter_meta=filter_meta,
                archive_ids=archive_ids,
                current_index=current_index,
                is_completed=False,
            )
            session.add(row)
        else:
            row.mode = mode
            row.filter_meta = filter_meta
            row.archive_ids = archive_ids
            row.current_index = current_index
            row.is_completed = False

        await session.commit()
        return {
            "mode": mode,
            "archive_ids": archive_ids,
            "current_index": current_index,
            "total": len(archive_ids),
        }

    def save_learning_session_local(
        self,
        admin_id: int,
        mode: str,
        archive_ids: list[int],
        current_index: int = 0,
        filter_meta: dict | None = None,
    ) -> dict[str, Any]:
        state = _load_local_admin_store()
        sess_obj = {
            "mode": mode,
            "filter_meta": filter_meta or {},
            "archive_ids": archive_ids,
            "current_index": current_index,
            "total": len(archive_ids),
            "is_completed": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        state.setdefault("sessions", {})[str(admin_id)] = sess_obj
        _save_local_admin_store(state)
        return sess_obj

    async def submit_admin_quiz_pg(
        self,
        session: Any,
        admin_id: int,
        filter_mode: str,
        submissions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from sqlalchemy import select
        from database.models import (
            AdminQuizHistory,
            AdminVocabProgress,
            VocabularyArchive,
        )

        now = datetime.now(timezone.utc)
        aids = [int(s["archive_id"]) for s in submissions]
        arch_rows = list(
            (
                await session.execute(
                    select(VocabularyArchive).where(VocabularyArchive.id.in_(aids))
                )
            )
            .scalars()
            .all()
        )
        arch_map = {a.id: a for a in arch_rows}

        correct_cnt = 0
        wrong_ids: list[int] = []
        review_details: list[dict[str, Any]] = []

        for sub in submissions:
            aid = int(sub["archive_id"])
            chosen_text = str(sub.get("selected_text", "")).strip()
            arch = arch_map.get(aid)
            if not arch:
                continue
            is_correct = normalize_expression(chosen_text) == normalize_expression(
                arch.advanced_expression
            )
            if is_correct:
                correct_cnt += 1
            else:
                wrong_ids.append(aid)

            prog = (
                await session.execute(
                    select(AdminVocabProgress).where(
                        AdminVocabProgress.admin_id == admin_id,
                        AdminVocabProgress.archive_id == aid,
                    )
                )
            ).scalar_one_or_none()
            cur_stage = prog.srs_stage if prog else 0
            action = "quiz_correct" if is_correct else "quiz_wrong"
            new_status, next_stage, interval, next_rev = compute_next_srs(
                cur_stage, action, now
            )

            if prog is None:
                prog = AdminVocabProgress(
                    admin_id=admin_id,
                    archive_id=aid,
                    status=new_status,
                    srs_stage=next_stage,
                    interval_days=interval,
                    next_review_at=next_rev,
                    last_reviewed_at=now,
                    review_count=1,
                    correct_count=1 if is_correct else 0,
                    wrong_count=0 if is_correct else 1,
                    last_quiz_wrong=not is_correct,
                )
                session.add(prog)
            else:
                prog.last_reviewed_at = now
                prog.review_count = (prog.review_count or 0) + 1
                if is_correct:
                    prog.correct_count = (prog.correct_count or 0) + 1
                    prog.last_quiz_wrong = False
                    prog.srs_stage = next_stage
                    prog.interval_days = interval
                    prog.next_review_at = next_rev
                else:
                    prog.wrong_count = (prog.wrong_count or 0) + 1
                    prog.last_quiz_wrong = True
                    prog.status = "difficult"
                    prog.srs_stage = 0
                    prog.interval_days = 1
                    prog.next_review_at = next_rev

            review_details.append(
                {
                    "archive_id": aid,
                    "basic_expression": arch.basic_expression,
                    "advanced_expression": arch.advanced_expression,
                    "selected_text": chosen_text,
                    "is_correct": is_correct,
                    "translation_uz": arch.translation_uz,
                    "translation_ru": arch.translation_ru or "",
                    "definition_en": arch.definition_en,
                    "example_en": arch.example_en,
                }
            )

        total_q = max(1, len(review_details))
        accuracy = round((correct_cnt / total_q) * 100)
        session.add(
            AdminQuizHistory(
                admin_id=admin_id,
                question_count=total_q,
                correct_count=correct_cnt,
                accuracy=accuracy,
                wrong_archive_ids=wrong_ids,
                filter_mode=filter_mode,
            )
        )
        await session.commit()

        return {
            "ok": True,
            "question_count": total_q,
            "correct_count": correct_cnt,
            "accuracy": accuracy,
            "wrong_archive_ids": wrong_ids,
            "details": review_details,
        }

    def submit_admin_quiz_local(
        self,
        admin_id: int,
        filter_mode: str,
        submissions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        state = _load_local_admin_store()
        arch_map = {int(a["id"]): a for a in state["archive"]}
        admin_prog = state.setdefault("progress", {}).setdefault(str(admin_id), {})
        now = datetime.now(timezone.utc)

        correct_cnt = 0
        wrong_ids: list[int] = []
        review_details: list[dict[str, Any]] = []

        for sub in submissions:
            aid = int(sub["archive_id"])
            chosen_text = str(sub.get("selected_text", "")).strip()
            arch = arch_map.get(aid)
            if not arch:
                continue
            is_correct = normalize_expression(chosen_text) == normalize_expression(
                arch["advanced_expression"]
            )
            if is_correct:
                correct_cnt += 1
            else:
                wrong_ids.append(aid)

            prev = admin_prog.get(str(aid), {})
            action = "quiz_correct" if is_correct else "quiz_wrong"
            new_status, next_stage, interval, next_rev = compute_next_srs(
                int(prev.get("srs_stage", 0)), action, now
            )
            admin_prog[str(aid)] = {
                "status": new_status if not is_correct else prev.get("status", "memorized"),
                "srs_stage": next_stage,
                "interval_days": interval,
                "next_review_at": next_rev.isoformat(),
                "last_reviewed_at": now.isoformat(),
                "review_count": int(prev.get("review_count", 0)) + 1,
                "correct_count": int(prev.get("correct_count", 0)) + (1 if is_correct else 0),
                "wrong_count": int(prev.get("wrong_count", 0)) + (0 if is_correct else 1),
                "last_quiz_wrong": not is_correct,
            }

            review_details.append(
                {
                    "archive_id": aid,
                    "basic_expression": arch["basic_expression"],
                    "advanced_expression": arch["advanced_expression"],
                    "selected_text": chosen_text,
                    "is_correct": is_correct,
                    "translation_uz": arch["translation_uz"],
                    "translation_ru": arch.get("translation_ru", ""),
                    "definition_en": arch["definition_en"],
                    "example_en": arch["example_en"],
                }
            )

        total_q = max(1, len(review_details))
        accuracy = round((correct_cnt / total_q) * 100)
        q_hist = state.setdefault("quiz_history", {}).setdefault(str(admin_id), [])
        q_hist.insert(
            0,
            {
                "id": len(q_hist) + 1,
                "question_count": total_q,
                "correct_count": correct_cnt,
                "accuracy": accuracy,
                "wrong_archive_ids": wrong_ids,
                "filter_mode": filter_mode,
                "created_at": now.isoformat(),
            },
        )
        _save_local_admin_store(state)

        return {
            "ok": True,
            "question_count": total_q,
            "correct_count": correct_cnt,
            "accuracy": accuracy,
            "wrong_archive_ids": wrong_ids,
            "details": review_details,
        }

    @staticmethod
    def build_export_bytes(
        items: list[dict[str, Any]], fmt: str = "csv"
    ) -> tuple[bytes, str, str]:
        f = fmt.lower().strip()
        today_tag = str(settings.today())
        if f == "xlsx":
            return (
                export_vocabulary_xlsx(items),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"shoxrux_ai_vocabulary_{today_tag}.xlsx",
            )
        if f == "pdf":
            return (
                export_vocabulary_pdf(items),
                "application/pdf",
                f"shoxrux_ai_vocabulary_{today_tag}.pdf",
            )
        return (
            export_vocabulary_csv(items),
            "text/csv; charset=utf-8",
            f"shoxrux_ai_vocabulary_{today_tag}.csv",
        )


admin_library_manager = AdminLibraryManager()
