from datetime import date, datetime, timedelta, timezone
from typing import Any
from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import SUPPORTED_LANGUAGES, settings
from database.models import (
    AdminRecord,
    BonusPack,
    BonusPackWord,
    Broadcast,
    BroadcastRecipient,
    DailyLesson,
    DailyLessonItem,
    GenerationLog,
    Referral,
    ReferralReward,
    User,
    UserBonusProgress,
    UserDailyProgress,
    UserLearnedWord,
    UserSettings,
    Vocabulary,
    VocabularyReserve,
)

DEFAULT_MILESTONES: list[tuple[int, str, str]] = [
    (1, "bonus_10_vocab", "🎁 +10 Bonus IELTS Vocabulary"),
    (3, "speaking_advanced_pack", "💎 IELTS Speaking Advanced Pack"),
    (5, "writing_academic_pack", "📚 IELTS Writing Academic Pack"),
    (10, "vip_30day_challenge", "👑 VIP IELTS 30-Day Challenge"),
    (20, "ielts_master_status", "🏆 IELTS Master Exclusive Pack"),
]


# ==============================================================================
# USER & SETTINGS CRUD
# ==============================================================================


async def get_user_by_telegram_id(
    session: AsyncSession, user_id: int
) -> User | None:
    stmt = (
        select(User)
        .options(selectinload(User.settings))
        .where(User.user_id == user_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: str | None = None,
    full_name: str = "Learner",
    default_lang: str | None = None,
) -> tuple[User, UserSettings, bool]:
    """
    Fetch or create User and UserSettings.
    Returns (user, user_settings, is_new_user).
    """
    user = await get_user_by_telegram_id(session, user_id)
    is_new = False

    lang = (
        default_lang
        if default_lang in SUPPORTED_LANGUAGES
        else settings.DEFAULT_LANGUAGE
    )

    if user is None:
        is_new = True
        user = User(
            user_id=user_id,
            username=username,
            full_name=full_name or "Learner",
            xp=0,
            streak=0,
            best_streak=0,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        user_settings = UserSettings(
            user_id=user_id,
            language_code=lang,
            reminders_enabled=True,
            broadcast_enabled=True,
        )
        session.add(user_settings)
        await session.commit()
        await session.refresh(user)
        await session.refresh(user_settings)
        return user, user_settings, is_new

    changed = False
    if username and user.username != username:
        user.username = username
        changed = True
    if full_name and user.full_name != full_name:
        user.full_name = full_name
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True

    user_settings = user.settings
    if user_settings is None:
        user_settings = UserSettings(
            user_id=user_id,
            language_code=lang,
            reminders_enabled=True,
            broadcast_enabled=True,
        )
        session.add(user_settings)
        changed = True

    if changed:
        await session.commit()
        await session.refresh(user)
        await session.refresh(user_settings)

    return user, user_settings, is_new


async def get_user_language(session: AsyncSession, user_id: int) -> str:
    stmt = select(UserSettings.language_code).where(UserSettings.user_id == user_id)
    result = await session.execute(stmt)
    lang = result.scalar_one_or_none()
    if lang in SUPPORTED_LANGUAGES:
        return lang
    return settings.DEFAULT_LANGUAGE


async def set_user_language(
    session: AsyncSession, user_id: int, language_code: str
) -> UserSettings:
    lang = (
        language_code.lower()
        if language_code.lower() in SUPPORTED_LANGUAGES
        else settings.DEFAULT_LANGUAGE
    )
    stmt = select(UserSettings).where(UserSettings.user_id == user_id)
    result = await session.execute(stmt)
    user_settings = result.scalar_one_or_none()

    if user_settings is None:
        user_settings = UserSettings(
            user_id=user_id,
            language_code=lang,
            reminders_enabled=True,
            broadcast_enabled=True,
        )
        session.add(user_settings)
    else:
        user_settings.language_code = lang

    await session.commit()
    await session.refresh(user_settings)
    return user_settings


async def toggle_user_reminders(session: AsyncSession, user_id: int) -> UserSettings:
    stmt = select(UserSettings).where(UserSettings.user_id == user_id)
    result = await session.execute(stmt)
    user_settings = result.scalar_one_or_none()

    if user_settings is None:
        user_settings = UserSettings(
            user_id=user_id,
            language_code=settings.DEFAULT_LANGUAGE,
            reminders_enabled=False,
            broadcast_enabled=True,
        )
        session.add(user_settings)
    else:
        user_settings.reminders_enabled = not user_settings.reminders_enabled

    await session.commit()
    await session.refresh(user_settings)
    return user_settings


async def toggle_user_broadcast(session: AsyncSession, user_id: int) -> UserSettings:
    stmt = select(UserSettings).where(UserSettings.user_id == user_id)
    result = await session.execute(stmt)
    user_settings = result.scalar_one_or_none()

    if user_settings is None:
        user_settings = UserSettings(
            user_id=user_id,
            language_code=settings.DEFAULT_LANGUAGE,
            reminders_enabled=True,
            broadcast_enabled=False,
        )
        session.add(user_settings)
    else:
        user_settings.broadcast_enabled = not user_settings.broadcast_enabled

    await session.commit()
    await session.refresh(user_settings)
    return user_settings


async def set_user_active_status(
    session: AsyncSession, user_id: int, is_active: bool
) -> None:
    stmt = update(User).where(User.user_id == user_id).values(is_active=is_active)
    await session.execute(stmt)
    await session.commit()


async def get_all_active_users_with_settings(
    session: AsyncSession,
) -> list[tuple[User, UserSettings]]:
    stmt = (
        select(User, UserSettings)
        .outerjoin(UserSettings, User.user_id == UserSettings.user_id)
        .where(User.is_active.is_(True))
    )
    result = await session.execute(stmt)
    rows: list[tuple[User, UserSettings]] = []
    for user, us in result.all():
        if us is None:
            us = UserSettings(
                user_id=user.user_id,
                language_code=settings.DEFAULT_LANGUAGE,
                reminders_enabled=True,
                broadcast_enabled=True,
            )
        rows.append((user, us))
    return rows


# ==============================================================================
# VOCABULARY & DAILY LESSONS CRUD
# ==============================================================================


async def get_all_normalized_expressions(session: AsyncSession) -> set[str]:
    stmt = select(Vocabulary.normalized_expression)
    result = await session.execute(stmt)
    return {row[0] for row in result.all() if row[0]}


async def get_daily_lesson_by_date(
    session: AsyncSession, target_date: date
) -> DailyLesson | None:
    stmt = (
        select(DailyLesson)
        .options(
            selectinload(DailyLesson.items).selectinload(DailyLessonItem.vocabulary)
        )
        .where(DailyLesson.lesson_date == target_date)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_daily_lesson_words(
    session: AsyncSession, target_date: date
) -> list[Vocabulary]:
    lesson = await get_daily_lesson_by_date(session, target_date)
    if not lesson:
        return []
    if lesson.items:
        sorted_items = sorted(lesson.items, key=lambda x: x.position)
        return [item.vocabulary for item in sorted_items if item.vocabulary is not None]

    if not lesson.vocabulary_ids:
        return []
    stmt = select(Vocabulary).where(Vocabulary.id.in_(lesson.vocabulary_ids))
    result = await session.execute(stmt)
    vocab_map = {v.id: v for v in result.scalars().all()}
    return [vocab_map[vid] for vid in lesson.vocabulary_ids if vid in vocab_map]


async def save_generated_daily_lesson(
    session: AsyncSession,
    target_date: date,
    candidates: list[dict[str, Any]],
) -> DailyLesson:
    existing_lesson = await get_daily_lesson_by_date(session, target_date)
    if existing_lesson is not None:
        return existing_lesson

    vocab_objects: list[Vocabulary] = []
    for item in candidates:
        vocab = Vocabulary(
            simple_word=item["simple_word"],
            advanced_word=item["advanced_word"],
            normalized_expression=item["normalized_expression"],
            translation_uz=item["translation_uz"],
            translation_ru=item["translation_ru"],
            definition_en=item["definition_en"],
            basic_example_en=item.get("basic_example_en"),
            example_en=item["example_en"],
            example_uz=item["example_uz"],
            example_ru=item["example_ru"],
            cefr_level=item["cefr_level"],
            category=item["category"],
            ielts_usage=item.get("ielts_usage", "Writing Task 2 & Speaking Part 3"),
            source_name=item.get("source_name", "Cambridge Dictionary"),
            source_url=item.get("source_url"),
            quiz_question_uz=item.get("quiz_question_uz"),
            quiz_question_ru=item.get("quiz_question_ru"),
            quiz_question_en=item.get("quiz_question_en"),
            option_a=item["options"][0],
            option_b=item["options"][1],
            option_c=item["options"][2],
            option_d=item["options"][3],
            correct_option=item["correct_option"],
        )
        session.add(vocab)
        vocab_objects.append(vocab)

    await session.flush()

    vocab_ids = [v.id for v in vocab_objects]
    daily_lesson = DailyLesson(
        lesson_date=target_date,
        vocabulary_ids=vocab_ids,
    )
    session.add(daily_lesson)
    await session.flush()

    for idx, vocab in enumerate(vocab_objects, start=1):
        lesson_item = DailyLessonItem(
            lesson_id=daily_lesson.id,
            vocabulary_id=vocab.id,
            position=idx,
        )
        session.add(lesson_item)

    from services.admin_library_service import sync_daily_vocab_objects_to_archive_in_tx

    await sync_daily_vocab_objects_to_archive_in_tx(session, vocab_objects, target_date)

    # Mark any matching items in vocabulary_reserve as used
    norms_used = [v.normalized_expression for v in vocab_objects if v.normalized_expression]
    if norms_used:
        await session.execute(
            update(VocabularyReserve)
            .where(VocabularyReserve.normalized_expression.in_(norms_used))
            .values(is_used=True, used_at=func.now())
        )

    await session.commit()
    return await get_daily_lesson_by_date(session, target_date)  # type: ignore[return-value]


async def ensure_vocabulary_reserve_seeded(
    session: AsyncSession, seed_items: list[dict[str, Any]]
) -> int:
    """
    Idempotently seed PostgreSQL `vocabulary_reserve` from validated seed items.
    Marks items already present in `vocabulary` as `is_used=True`.
    Returns current count of unused reserve items in PostgreSQL.
    """
    used_norms = await get_all_normalized_expressions(session)
    existing_res_stmt = select(VocabularyReserve.normalized_expression)
    existing_res_norms = {
        row[0] for row in (await session.execute(existing_res_stmt)).all() if row[0]
    }

    inserted = 0
    for item in seed_items:
        norm = item.get("normalized_expression", "").strip()
        if not norm or norm in existing_res_norms:
            continue
        is_already_used = norm in used_norms
        session.add(
            VocabularyReserve(
                simple_word=item["simple_word"],
                advanced_word=item["advanced_word"],
                normalized_expression=norm,
                translation_uz=item["translation_uz"],
                translation_ru=item["translation_ru"],
                definition_en=item["definition_en"],
                basic_example_en=item.get("basic_example_en"),
                example_en=item["example_en"],
                example_uz=item["example_uz"],
                example_ru=item["example_ru"],
                cefr_level=item.get("cefr_level", "B2–C1"),
                category=item.get("category", "everyday_upgrade"),
                ielts_usage=item.get("ielts_usage", "Writing Task 2 & Speaking Part 3"),
                source_name=item.get("source_name", "Cambridge Dictionary"),
                source_url=item.get("source_url"),
                quiz_question_uz=item.get("quiz_question_uz"),
                quiz_question_ru=item.get("quiz_question_ru"),
                quiz_question_en=item.get("quiz_question_en"),
                option_a=item["options"][0],
                option_b=item["options"][1],
                option_c=item["options"][2],
                option_d=item["options"][3],
                correct_option=item["correct_option"],
                is_used=is_already_used,
            )
        )
        existing_res_norms.add(norm)
        inserted += 1

    # Sync is_used flag for any reserve items that were used in vocabulary
    if used_norms:
        await session.execute(
            update(VocabularyReserve)
            .where(
                VocabularyReserve.normalized_expression.in_(used_norms),
                VocabularyReserve.is_used.is_(False),
            )
            .values(is_used=True, used_at=func.now())
        )

    if inserted > 0 or used_norms:
        await session.commit()

    return await get_unused_reserve_count(session)


async def get_unused_reserve_count(session: AsyncSession) -> int:
    stmt = select(func.count(VocabularyReserve.id)).where(
        VocabularyReserve.is_used.is_(False)
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def get_all_known_and_reserve_normalized_expressions(
    session: AsyncSession,
) -> set[str]:
    used_norms = await get_all_normalized_expressions(session)
    res_stmt = select(VocabularyReserve.normalized_expression)
    res_norms = {row[0] for row in (await session.execute(res_stmt)).all() if row[0]}
    return used_norms | res_norms


async def save_items_to_postgres_reserve(
    session: AsyncSession, items: list[dict[str, Any]]
) -> int:
    """Save newly generated Free Tier reserve items into PostgreSQL `vocabulary_reserve`."""
    known = await get_all_known_and_reserve_normalized_expressions(session)
    added = 0
    for item in items:
        norm = item.get("normalized_expression", "").strip()
        if not norm or norm in known:
            continue
        session.add(
            VocabularyReserve(
                simple_word=item["simple_word"],
                advanced_word=item["advanced_word"],
                normalized_expression=norm,
                translation_uz=item["translation_uz"],
                translation_ru=item["translation_ru"],
                definition_en=item["definition_en"],
                basic_example_en=item.get("basic_example_en"),
                example_en=item["example_en"],
                example_uz=item["example_uz"],
                example_ru=item["example_ru"],
                cefr_level=item.get("cefr_level", "B2–C1"),
                category=item.get("category", "everyday_upgrade"),
                ielts_usage=item.get("ielts_usage", "Writing Task 2 & Speaking Part 3"),
                source_name=item.get("source_name", "Cambridge Dictionary"),
                source_url=item.get("source_url"),
                quiz_question_uz=item.get("quiz_question_uz"),
                quiz_question_ru=item.get("quiz_question_ru"),
                quiz_question_en=item.get("quiz_question_en"),
                option_a=item["options"][0],
                option_b=item["options"][1],
                option_c=item["options"][2],
                option_d=item["options"][3],
                correct_option=item["correct_option"],
                is_used=False,
            )
        )
        known.add(norm)
        added += 1
    if added > 0:
        await session.commit()
    return added


async def fetch_unused_from_postgres_reserve(
    session: AsyncSession,
) -> list[VocabularyReserve]:
    stmt = (
        select(VocabularyReserve)
        .where(VocabularyReserve.is_used.is_(False))
        .order_by(VocabularyReserve.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_vocabulary_paginated(
    session: AsyncSession, page: int = 1, page_size: int = 10
) -> tuple[list[Vocabulary], int]:
    count_stmt = select(func.count(Vocabulary.id))
    total = (await session.execute(count_stmt)).scalar_one() or 0

    offset = max(0, (page - 1) * page_size)
    stmt = (
        select(Vocabulary)
        .order_by(desc(Vocabulary.id))
        .offset(offset)
        .limit(page_size)
    )
    items = list((await session.execute(stmt)).scalars().all())
    return items, total


# ==============================================================================
# USER PROGRESS & QUIZ COMPLETION CRUD
# ==============================================================================


async def get_or_create_daily_progress(
    session: AsyncSession, user_id: int, target_date: date
) -> UserDailyProgress:
    stmt = select(UserDailyProgress).where(
        UserDailyProgress.user_id == user_id,
        UserDailyProgress.lesson_date == target_date,
    )
    result = await session.execute(stmt)
    progress = result.scalar_one_or_none()
    if progress is None:
        progress = UserDailyProgress(
            user_id=user_id,
            lesson_date=target_date,
            is_memorized=False,
            is_completed=False,
            score=0,
            earned_xp=0,
        )
        session.add(progress)
        await session.commit()
        await session.refresh(progress)
    return progress


async def mark_lesson_memorized(
    session: AsyncSession, user_id: int, target_date: date
) -> UserDailyProgress:
    progress = await get_or_create_daily_progress(session, user_id, target_date)
    if not progress.is_memorized:
        progress.is_memorized = True
        progress.memorized_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(progress)
    return progress


async def complete_daily_quiz(
    session: AsyncSession,
    user_id: int,
    target_date: date,
    score: int,
    total_questions: int,
    word_results: list[tuple[int, bool]],
) -> tuple[User, UserDailyProgress, int]:
    """
    Record daily quiz completion, award XP, update streak, and insert learned words.
    Returns (user, progress, earned_xp).
    """
    user, _, _ = await get_or_create_user(session, user_id)
    progress = await get_or_create_daily_progress(session, user_id, target_date)

    if progress.is_completed:
        return user, progress, 0

    earned_xp = score * settings.POINTS_PER_CORRECT_ANSWER
    progress.is_memorized = True
    progress.is_completed = True
    progress.score = score
    progress.earned_xp = earned_xp
    progress.completed_at = datetime.now(timezone.utc)

    user.xp += earned_xp
    user.total_quizzes += 1
    user.total_correct += score
    user.total_questions += total_questions

    if user.last_quiz_date == target_date:
        pass
    elif user.last_quiz_date == (target_date - timedelta(days=1)):
        user.streak += 1
    else:
        user.streak = 1

    if user.streak > user.best_streak:
        user.best_streak = user.streak
    user.last_quiz_date = target_date

    for vocab_id, is_correct in word_results:
        existing_lw_stmt = select(UserLearnedWord).where(
            UserLearnedWord.user_id == user_id,
            UserLearnedWord.vocabulary_id == vocab_id,
        )
        existing_lw = (await session.execute(existing_lw_stmt)).scalar_one_or_none()
        if existing_lw is None:
            session.add(
                UserLearnedWord(
                    user_id=user_id,
                    vocabulary_id=vocab_id,
                    learned_date=target_date,
                    is_correct_in_quiz=is_correct,
                )
            )
        elif is_correct and not existing_lw.is_correct_in_quiz:
            existing_lw.is_correct_in_quiz = True

    await session.commit()
    await session.refresh(user)
    await session.refresh(progress)
    return user, progress, earned_xp


async def get_user_learned_count(session: AsyncSession, user_id: int) -> int:
    stmt = select(func.count(UserLearnedWord.id)).where(
        UserLearnedWord.user_id == user_id
    )
    return (await session.execute(stmt)).scalar_one() or 0


async def get_user_learned_words_paginated(
    session: AsyncSession, user_id: int, page: int = 1, page_size: int = 10
) -> tuple[list[Vocabulary], int]:
    total = await get_user_learned_count(session, user_id)
    offset = max(0, (page - 1) * page_size)
    stmt = (
        select(Vocabulary)
        .join(UserLearnedWord, UserLearnedWord.vocabulary_id == Vocabulary.id)
        .where(UserLearnedWord.user_id == user_id)
        .order_by(desc(UserLearnedWord.created_at), desc(Vocabulary.id))
        .offset(offset)
        .limit(page_size)
    )
    words = list((await session.execute(stmt)).scalars().all())
    return words, total


# ==============================================================================
# LEADERBOARD & BOT STATISTICS CRUD
# ==============================================================================


async def get_top_users(session: AsyncSession, limit: int = 10) -> list[User]:
    stmt = (
        select(User)
        .order_by(desc(User.xp), desc(User.streak), User.id)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_user_rank(session: AsyncSession, user_id: int) -> int:
    user_stmt = select(User).where(User.user_id == user_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if user is None:
        return 1
    higher_stmt = select(func.count(User.id)).where(User.xp > user.xp)
    higher_count = (await session.execute(higher_stmt)).scalar_one() or 0
    return higher_count + 1


async def get_bot_statistics(session: AsyncSession, today_date: date) -> dict[str, Any]:
    total_users = (await session.execute(select(func.count(User.id)))).scalar_one() or 0
    active_users = (
        await session.execute(
            select(func.count(User.id)).where(User.is_active.is_(True))
        )
    ).scalar_one() or 0
    total_vocab = (
        await session.execute(select(func.count(Vocabulary.id)))
    ).scalar_one() or 0
    total_lessons = (
        await session.execute(select(func.count(DailyLesson.id)))
    ).scalar_one() or 0
    today_completed = (
        await session.execute(
            select(func.count(UserDailyProgress.id)).where(
                UserDailyProgress.lesson_date == today_date,
                UserDailyProgress.is_completed.is_(True),
            )
        )
    ).scalar_one() or 0
    today_memorized = (
        await session.execute(
            select(func.count(UserDailyProgress.id)).where(
                UserDailyProgress.lesson_date == today_date,
                UserDailyProgress.is_memorized.is_(True),
            )
        )
    ).scalar_one() or 0

    lang_counts: dict[str, int] = {"uz": 0, "ru": 0, "en": 0}
    lang_stmt = select(
        UserSettings.language_code, func.count(UserSettings.id)
    ).group_by(UserSettings.language_code)
    for l_code, cnt in (await session.execute(lang_stmt)).all():
        if l_code in lang_counts:
            lang_counts[l_code] = cnt

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_vocab": total_vocab,
        "total_lessons": total_lessons,
        "today_completed": today_completed,
        "today_memorized": today_memorized,
        "lang_counts": lang_counts,
    }


# ==============================================================================
# GENERATION LOGS CRUD
# ==============================================================================


async def create_generation_log(
    session: AsyncSession,
    lesson_date: date,
    generation_status: str,
    generated_count: int = 0,
    rejected_duplicates: int = 0,
    retry_count: int = 0,
    error_message: str | None = None,
) -> GenerationLog:
    log_entry = GenerationLog(
        lesson_date=lesson_date,
        generation_status=generation_status,
        generated_count=generated_count,
        rejected_duplicates=rejected_duplicates,
        retry_count=retry_count,
        error_message=error_message,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    return log_entry


async def get_recent_generation_logs(
    session: AsyncSession, limit: int = 10
) -> list[GenerationLog]:
    stmt = (
        select(GenerationLog)
        .order_by(desc(GenerationLog.created_at), desc(GenerationLog.id))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_generation_summary(session: AsyncSession) -> dict[str, int]:
    total_runs = (
        await session.execute(select(func.count(GenerationLog.id)))
    ).scalar_one() or 0
    total_generated = (
        await session.execute(
            select(func.coalesce(func.sum(GenerationLog.generated_count), 0))
        )
    ).scalar_one() or 0
    total_rejected = (
        await session.execute(
            select(func.coalesce(func.sum(GenerationLog.rejected_duplicates), 0))
        )
    ).scalar_one() or 0
    failed_runs = (
        await session.execute(
            select(func.count(GenerationLog.id)).where(
                GenerationLog.generation_status == "FAILED"
            )
        )
    ).scalar_one() or 0
    return {
        "total_runs": total_runs,
        "total_generated": total_generated,
        "total_rejected": total_rejected,
        "failed_runs": failed_runs,
    }


# ==============================================================================
# REFERRAL & REWARDS SYSTEM CRUD (Sections 1-10)
# ==============================================================================


async def register_pending_referral(
    session: AsyncSession,
    referrer_user_id: int,
    referred_user_id: int,
    is_new_user: bool,
) -> tuple[Referral | None, str]:
    """
    Create a pending referral for a brand-new user.
    Anti-fraud protections:
    - Blocks self-referral (`referrer_user_id == referred_user_id`)
    - Blocks existing users (`is_new_user == False`)
    - Blocks duplicate referrals (`referred_user_id` UNIQUE)
    - Verifies `referrer_user_id` exists in `users`
    - Flags suspicious velocity bursts (>10 referrals in 10 minutes)
    """
    if not is_new_user:
        return None, "EXISTING_USER"

    if referrer_user_id == referred_user_id:
        return None, "SELF_REFERRAL"

    referrer = await get_user_by_telegram_id(session, referrer_user_id)
    if referrer is None:
        return None, "REFERRER_NOT_FOUND"

    existing_ref = (
        await session.execute(
            select(Referral).where(Referral.referred_user_id == referred_user_id)
        )
    ).scalar_one_or_none()
    if existing_ref is not None:
        return None, "ALREADY_REFERRED"

    ten_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
    recent_burst_count = (
        await session.execute(
            select(func.count(Referral.id)).where(
                Referral.referrer_user_id == referrer_user_id,
                Referral.created_at >= ten_mins_ago,
            )
        )
    ).scalar_one() or 0

    is_suspicious = recent_burst_count >= 12
    suspicion_reason = (
        f"Velocity alert: {recent_burst_count + 1} referrals in 10 minutes"
        if is_suspicious
        else None
    )

    try:
        new_ref = Referral(
            referrer_user_id=referrer_user_id,
            referred_user_id=referred_user_id,
            status="pending",
            is_suspicious=is_suspicious,
            suspicion_reason=suspicion_reason,
        )
        session.add(new_ref)
        await session.commit()
        await session.refresh(new_ref)
        return new_ref, "CREATED"
    except IntegrityError:
        await session.rollback()
        return None, "ALREADY_REFERRED"


async def confirm_referral_and_unlock_rewards(
    session: AsyncSession,
    referred_user_id: int,
) -> tuple[int | None, int, list[BonusPack]]:
    """
    Atomically confirm a pending referral when `referred_user_id` completes their first quiz.
    Uses row-level locking (`with_for_update()`) to prevent concurrent duplicate rewards.
    Returns (referrer_user_id, total_confirmed_referrals, newly_unlocked_packs).
    """
    stmt = (
        select(Referral)
        .where(Referral.referred_user_id == referred_user_id)
        .with_for_update()
    )
    referral = (await session.execute(stmt)).scalar_one_or_none()
    if referral is None or referral.status != "pending":
        return None, 0, []

    if referral.is_suspicious:
        return None, 0, []

    referral.status = "confirmed"
    referral.confirmed_at = datetime.now(timezone.utc)
    await session.flush()

    referrer_id = referral.referrer_user_id

    # Lock referrer user row to serialize milestone reward evaluation
    await session.execute(
        select(User).where(User.user_id == referrer_id).with_for_update()
    )

    confirmed_count = (
        await session.execute(
            select(func.count(Referral.id)).where(
                Referral.referrer_user_id == referrer_id,
                Referral.status == "confirmed",
            )
        )
    ).scalar_one() or 0

    packs = list(
        (
            await session.execute(
                select(BonusPack).order_by(BonusPack.required_referrals)
            )
        )
        .scalars()
        .all()
    )

    existing_rewards_stmt = select(ReferralReward.milestone).where(
        ReferralReward.user_id == referrer_id
    )
    unlocked_milestones = {
        row[0] for row in (await session.execute(existing_rewards_stmt)).all()
    }

    newly_unlocked: list[BonusPack] = []
    for pack in packs:
        if (
            confirmed_count >= pack.required_referrals
            and pack.required_referrals not in unlocked_milestones
        ):
            reward = ReferralReward(
                user_id=referrer_id,
                reward_type=pack.pack_type,
                milestone=pack.required_referrals,
                unlocked_at=datetime.now(timezone.utc),
            )
            session.add(reward)
            unlocked_milestones.add(pack.required_referrals)

            prog_stmt = select(UserBonusProgress).where(
                UserBonusProgress.user_id == referrer_id,
                UserBonusProgress.pack_id == pack.id,
            )
            prog = (await session.execute(prog_stmt)).scalar_one_or_none()
            if prog is None:
                session.add(
                    UserBonusProgress(
                        user_id=referrer_id,
                        pack_id=pack.id,
                        completed_words=0,
                        completed_quizzes=0,
                    )
                )
            newly_unlocked.append(pack)

    await session.commit()
    return referrer_id, confirmed_count, newly_unlocked


async def get_user_badge(session: AsyncSession, user_id: int) -> str:
    """Return user's highest referral status badge (🏆 IELTS Master or 👑 VIP)."""
    rewards_stmt = select(ReferralReward.reward_type).where(
        ReferralReward.user_id == user_id
    )
    reward_types = {row[0] for row in (await session.execute(rewards_stmt)).all()}
    if "ielts_master_status" in reward_types:
        return "🏆 IELTS Master"
    if "vip_30day_challenge" in reward_types:
        return "👑 VIP"
    return ""


async def get_user_referral_summary(
    session: AsyncSession, user_id: int
) -> dict[str, Any]:
    invited = (
        await session.execute(
            select(func.count(Referral.id)).where(
                Referral.referrer_user_id == user_id,
                Referral.status != "rejected",
            )
        )
    ).scalar_one() or 0

    confirmed = (
        await session.execute(
            select(func.count(Referral.id)).where(
                Referral.referrer_user_id == user_id,
                Referral.status == "confirmed",
            )
        )
    ).scalar_one() or 0

    pending = (
        await session.execute(
            select(func.count(Referral.id)).where(
                Referral.referrer_user_id == user_id,
                Referral.status == "pending",
            )
        )
    ).scalar_one() or 0

    packs = list(
        (
            await session.execute(
                select(BonusPack).order_by(BonusPack.required_referrals)
            )
        )
        .scalars()
        .all()
    )

    rewards = list(
        (
            await session.execute(
                select(ReferralReward).where(ReferralReward.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    unlocked_types = {r.reward_type for r in rewards}
    unlocked_milestones = {r.milestone for r in rewards}

    # Ensure any pack where confirmed >= required_referrals is counted
    for p in packs:
        if confirmed >= p.required_referrals:
            unlocked_types.add(p.pack_type)
            unlocked_milestones.add(p.required_referrals)

    next_pack: BonusPack | None = None
    for p in packs:
        if p.pack_type not in unlocked_types:
            next_pack = p
            break

    badge = await get_user_badge(session, user_id)
    if not badge:
        if confirmed >= 20:
            badge = "🏆 IELTS Master"
        elif confirmed >= 10:
            badge = "👑 VIP"

    return {
        "invited": invited,
        "confirmed": confirmed,
        "pending": pending,
        "unlocked_count": len(unlocked_types),
        "unlocked_types": unlocked_types,
        "packs": packs,
        "next_pack": next_pack,
        "badge": badge,
    }


async def get_top_referrers(
    session: AsyncSession, limit: int = 10
) -> list[tuple[User, int]]:
    stmt = (
        select(User, func.count(Referral.id).label("ref_count"))
        .join(Referral, Referral.referrer_user_id == User.user_id)
        .where(Referral.status == "confirmed")
        .group_by(User.id)
        .order_by(desc("ref_count"), desc(User.xp))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [(row[0], int(row[1])) for row in result.all()]


async def get_user_referral_rank(
    session: AsyncSession, user_id: int
) -> tuple[int, int]:
    user_confirmed = (
        await session.execute(
            select(func.count(Referral.id)).where(
                Referral.referrer_user_id == user_id,
                Referral.status == "confirmed",
            )
        )
    ).scalar_one() or 0

    subq = (
        select(
            Referral.referrer_user_id,
            func.count(Referral.id).label("cnt"),
        )
        .where(Referral.status == "confirmed")
        .group_by(Referral.referrer_user_id)
        .subquery()
    )
    higher_stmt = select(func.count()).select_from(subq).where(subq.c.cnt > user_confirmed)
    higher = (await session.execute(higher_stmt)).scalar_one() or 0
    return higher + 1, user_confirmed


async def get_bonus_pack_with_words(
    session: AsyncSession, pack_id: int
) -> tuple[BonusPack | None, list[Vocabulary]]:
    stmt = (
        select(BonusPack)
        .options(
            selectinload(BonusPack.words).selectinload(BonusPackWord.vocabulary)
        )
        .where(BonusPack.id == pack_id)
    )
    pack = (await session.execute(stmt)).scalar_one_or_none()
    if pack is None:
        return None, []
    sorted_bw = sorted(pack.words, key=lambda x: x.position)
    words = [bw.vocabulary for bw in sorted_bw if bw.vocabulary is not None]
    return pack, words


async def is_pack_unlocked_for_user(
    session: AsyncSession, user_id: int, pack: BonusPack
) -> bool:
    summary = await get_user_referral_summary(session, user_id)
    return (
        pack.pack_type in summary["unlocked_types"]
        or summary["confirmed"] >= pack.required_referrals
    )


async def get_or_create_user_bonus_progress(
    session: AsyncSession, user_id: int, pack_id: int
) -> UserBonusProgress:
    stmt = select(UserBonusProgress).where(
        UserBonusProgress.user_id == user_id,
        UserBonusProgress.pack_id == pack_id,
    )
    prog = (await session.execute(stmt)).scalar_one_or_none()
    if prog is None:
        prog = UserBonusProgress(
            user_id=user_id,
            pack_id=pack_id,
            completed_words=1,
            completed_quizzes=0,
        )
        session.add(prog)
        await session.commit()
        await session.refresh(prog)
    return prog


async def update_user_bonus_word_progress(
    session: AsyncSession, user_id: int, pack_id: int, viewed_count: int, total_words: int
) -> UserBonusProgress:
    prog = await get_or_create_user_bonus_progress(session, user_id, pack_id)
    if viewed_count > prog.completed_words:
        prog.completed_words = min(viewed_count, total_words)
        if prog.completed_words >= total_words and prog.completed_at is None:
            prog.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(prog)
    return prog


async def record_bonus_pack_quiz_completion(
    session: AsyncSession, user_id: int, pack_id: int, score: int
) -> tuple[UserBonusProgress, int]:
    prog = await get_or_create_user_bonus_progress(session, user_id, pack_id)
    user, _, _ = await get_or_create_user(session, user_id)

    earned_xp = score * settings.POINTS_PER_CORRECT_ANSWER if prog.completed_quizzes == 0 else 0
    prog.completed_quizzes += 1
    if prog.completed_at is None:
        prog.completed_at = datetime.now(timezone.utc)

    if earned_xp > 0:
        user.xp += earned_xp

    await session.commit()
    await session.refresh(prog)
    return prog, earned_xp


async def get_admin_referral_overview(session: AsyncSession) -> dict[str, int]:
    total = (await session.execute(select(func.count(Referral.id)))).scalar_one() or 0
    confirmed = (
        await session.execute(
            select(func.count(Referral.id)).where(Referral.status == "confirmed")
        )
    ).scalar_one() or 0
    pending = (
        await session.execute(
            select(func.count(Referral.id)).where(Referral.status == "pending")
        )
    ).scalar_one() or 0
    rejected = (
        await session.execute(
            select(func.count(Referral.id)).where(Referral.status == "rejected")
        )
    ).scalar_one() or 0
    suspicious = (
        await session.execute(
            select(func.count(Referral.id)).where(Referral.is_suspicious.is_(True))
        )
    ).scalar_one() or 0
    rewards_given = (
        await session.execute(select(func.count(ReferralReward.id)))
    ).scalar_one() or 0
    return {
        "total": total,
        "confirmed": confirmed,
        "pending": pending,
        "rejected": rejected,
        "suspicious": suspicious,
        "rewards_given": rewards_given,
    }


async def get_referrals_list_for_admin(
    session: AsyncSession, suspicious_only: bool = False, limit: int = 12
) -> list[Referral]:
    stmt = select(Referral).order_by(desc(Referral.created_at)).limit(limit)
    if suspicious_only:
        stmt = (
            select(Referral)
            .where(Referral.is_suspicious.is_(True))
            .order_by(desc(Referral.created_at))
            .limit(limit)
        )
    return list((await session.execute(stmt)).scalars().all())


async def reject_referral_by_id(
    session: AsyncSession, referral_id: int
) -> Referral | None:
    stmt = select(Referral).where(Referral.id == referral_id)
    ref = (await session.execute(stmt)).scalar_one_or_none()
    if ref is None:
        return None
    ref.status = "rejected"
    await session.commit()
    await session.refresh(ref)
    return ref


async def get_recent_referral_rewards_for_admin(
    session: AsyncSession, limit: int = 12
) -> list[ReferralReward]:
    stmt = (
        select(ReferralReward)
        .order_by(desc(ReferralReward.unlocked_at))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def update_bonus_pack_milestone(
    session: AsyncSession, pack_id: int, new_required: int
) -> BonusPack | None:
    if new_required < 1:
        return None
    stmt = select(BonusPack).where(BonusPack.id == pack_id)
    pack = (await session.execute(stmt)).scalar_one_or_none()
    if pack is None:
        return None
    pack.required_referrals = new_required
    await session.commit()
    await session.refresh(pack)
    return pack


# ==============================================================================
# MULTI-ADMIN SYSTEM CRUD (Section 15 & 17)
# ==============================================================================


def is_super_admin_id(telegram_id: int) -> bool:
    return settings.is_admin(telegram_id)


async def get_admin_role(
    session: AsyncSession, telegram_id: int
) -> str | None:
    """
    Server-side role verification:
    - Returns 'super_admin' if `telegram_id` matches `.env` `ADMIN_ID`.
    - Returns 'moderator' if active in PostgreSQL `admins` table.
    - Returns None otherwise.
    """
    if is_super_admin_id(telegram_id):
        return "super_admin"

    stmt = select(AdminRecord).where(
        AdminRecord.telegram_id == telegram_id,
        AdminRecord.is_active.is_(True),
    )
    record = (await session.execute(stmt)).scalar_one_or_none()
    if record is not None:
        return record.role
    return None


async def is_any_admin(session: AsyncSession, telegram_id: int) -> bool:
    role = await get_admin_role(session, telegram_id)
    return role in {"super_admin", "moderator"}


async def get_active_moderators(session: AsyncSession) -> list[AdminRecord]:
    stmt = (
        select(AdminRecord)
        .where(
            AdminRecord.is_active.is_(True),
            AdminRecord.role == "moderator",
        )
        .order_by(AdminRecord.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())


async def validate_new_moderator_candidate(
    session: AsyncSession, candidate_telegram_id: int
) -> tuple[bool, str, User | None]:
    """
    Check all 5 requirements from Section 15 before appointing a Moderator:
    1. Valid numeric ID
    2. Not Super Admin
    3. Not already an active admin
    4. Max 1 additional moderator allowed
    5. Must exist in `users` table (already started bot via /start)
    """
    if is_super_admin_id(candidate_telegram_id):
        return False, "IS_SUPER_ADMIN", None

    existing_role = await get_admin_role(session, candidate_telegram_id)
    if existing_role is not None:
        return False, "ALREADY_ADMIN", None

    active_mods = await get_active_moderators(session)
    if len(active_mods) >= 1:
        return False, "MAX_ADMIN_LIMIT_REACHED", None

    target_user = await get_user_by_telegram_id(session, candidate_telegram_id)
    if target_user is None:
        return False, "USER_NOT_FOUND", None

    return True, "OK", target_user


async def appoint_moderator_admin(
    session: AsyncSession,
    candidate_telegram_id: int,
    added_by_super_admin_id: int,
) -> tuple[AdminRecord | None, str]:
    if not is_super_admin_id(added_by_super_admin_id):
        return None, "FORBIDDEN_NOT_SUPER_ADMIN"

    ok, reason, _ = await validate_new_moderator_candidate(
        session, candidate_telegram_id
    )
    if not ok:
        return None, reason

    stmt = select(AdminRecord).where(
        AdminRecord.telegram_id == candidate_telegram_id
    )
    record = (await session.execute(stmt)).scalar_one_or_none()
    if record is None:
        record = AdminRecord(
            telegram_id=candidate_telegram_id,
            role="moderator",
            added_by=added_by_super_admin_id,
            is_active=True,
        )
        session.add(record)
    else:
        record.role = "moderator"
        record.added_by = added_by_super_admin_id
        record.is_active = True

    await session.commit()
    await session.refresh(record)
    return record, "APPOINTED"


async def remove_moderator_admin(
    session: AsyncSession,
    moderator_telegram_id: int,
    removed_by_super_admin_id: int,
) -> tuple[bool, str]:
    """
    Remove moderator privileges while preserving the user's normal IELTS account,
    XP, streak, quiz history, and referral records.
    """
    if not is_super_admin_id(removed_by_super_admin_id):
        return False, "FORBIDDEN_NOT_SUPER_ADMIN"

    if is_super_admin_id(moderator_telegram_id):
        return False, "CANNOT_REMOVE_SUPER_ADMIN"

    stmt = select(AdminRecord).where(
        AdminRecord.telegram_id == moderator_telegram_id,
        AdminRecord.is_active.is_(True),
    )
    record = (await session.execute(stmt)).scalar_one_or_none()
    if record is None:
        return False, "ADMIN_NOT_FOUND"

    record.is_active = False
    await session.commit()
    return True, "REMOVED"


# ==============================================================================
# ADMIN BROADCAST SYSTEM CRUD (Section 14 & 16)
# ==============================================================================


async def get_broadcast_audience_counts(
    session: AsyncSession,
) -> dict[str, int]:
    total_users = (
        await session.execute(select(func.count(User.id)))
    ).scalar_one() or 0

    sendable_stmt = (
        select(func.count(User.id))
        .outerjoin(UserSettings, User.user_id == UserSettings.user_id)
        .where(
            User.is_active.is_(True),
            and_(
                (UserSettings.broadcast_enabled.is_(True))
                | (UserSettings.broadcast_enabled.is_(None))
            ),
        )
    )
    sendable_users = (await session.execute(sendable_stmt)).scalar_one() or 0
    blocked_or_disabled = max(0, total_users - sendable_users)

    return {
        "total_users": total_users,
        "sendable_users": sendable_users,
        "blocked_or_disabled": blocked_or_disabled,
    }


async def get_running_broadcast(session: AsyncSession) -> Broadcast | None:
    stmt = (
        select(Broadcast)
        .where(Broadcast.status == "running")
        .order_by(Broadcast.id)
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_broadcast_job(
    session: AsyncSession,
    created_by: int,
    source_chat_id: int,
    source_message_id: int,
    message_type: str,
) -> Broadcast:
    """
    Create a Broadcast job and populate unique BroadcastRecipient rows
    for all active users who have not disabled broadcasts.
    """
    user_stmt = (
        select(User.user_id)
        .outerjoin(UserSettings, User.user_id == UserSettings.user_id)
        .where(
            User.is_active.is_(True),
            and_(
                (UserSettings.broadcast_enabled.is_(True))
                | (UserSettings.broadcast_enabled.is_(None))
            ),
        )
    )
    recipient_user_ids = [
        row[0] for row in (await session.execute(user_stmt)).all()
    ]

    bcast = Broadcast(
        created_by=created_by,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
        message_type=message_type,
        status="running",
        total_recipients=len(recipient_user_ids),
        success_count=0,
        failed_count=0,
        started_at=datetime.now(timezone.utc),
    )
    session.add(bcast)
    await session.flush()

    for uid in recipient_user_ids:
        session.add(
            BroadcastRecipient(
                broadcast_id=bcast.id,
                user_id=uid,
                status="pending",
                attempts=0,
            )
        )

    await session.commit()
    await session.refresh(bcast)
    return bcast


async def get_pending_broadcast_recipients(
    session: AsyncSession, broadcast_id: int, limit: int = 50
) -> list[BroadcastRecipient]:
    stmt = (
        select(BroadcastRecipient)
        .where(
            BroadcastRecipient.broadcast_id == broadcast_id,
            BroadcastRecipient.status == "pending",
        )
        .order_by(BroadcastRecipient.id)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def mark_broadcast_recipient_sent(
    session: AsyncSession, recipient_id: int, broadcast_id: int
) -> None:
    await session.execute(
        update(BroadcastRecipient)
        .where(BroadcastRecipient.id == recipient_id)
        .values(
            status="sent",
            attempts=BroadcastRecipient.attempts + 1,
            sent_at=datetime.now(timezone.utc),
        )
    )
    await session.execute(
        update(Broadcast)
        .where(Broadcast.id == broadcast_id)
        .values(success_count=Broadcast.success_count + 1)
    )
    await session.commit()


async def mark_broadcast_recipient_failed(
    session: AsyncSession,
    recipient_id: int,
    broadcast_id: int,
    user_id: int,
    error_message: str,
    mark_user_inactive: bool = False,
) -> None:
    await session.execute(
        update(BroadcastRecipient)
        .where(BroadcastRecipient.id == recipient_id)
        .values(
            status="failed",
            attempts=BroadcastRecipient.attempts + 1,
            last_error=error_message[:300],
        )
    )
    await session.execute(
        update(Broadcast)
        .where(Broadcast.id == broadcast_id)
        .values(failed_count=Broadcast.failed_count + 1)
    )
    if mark_user_inactive:
        await session.execute(
            update(User).where(User.user_id == user_id).values(is_active=False)
        )
    await session.commit()


async def finalize_broadcast_job(
    session: AsyncSession, broadcast_id: int, status: str = "completed"
) -> Broadcast | None:
    stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
    bcast = (await session.execute(stmt)).scalar_one_or_none()
    if bcast is None:
        return None
    bcast.status = status
    bcast.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(bcast)
    return bcast


async def get_broadcast_by_id(
    session: AsyncSession, broadcast_id: int
) -> Broadcast | None:
    stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_recent_broadcasts(
    session: AsyncSession, limit: int = 10
) -> list[Broadcast]:
    stmt = select(Broadcast).order_by(desc(Broadcast.id)).limit(limit)
    return list((await session.execute(stmt)).scalars().all())
