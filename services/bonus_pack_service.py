import json
import logging
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BonusPack, BonusPackWord, Vocabulary
from services.ai_vocabulary_generator import ai_generator
from services.normalizer import normalize_expression

logger = logging.getLogger(__name__)

BONUS_PACKS_SEED_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "bonus_packs_seed.json"
)


async def ensure_bonus_packs_seeded(session: AsyncSession) -> None:
    """
    Pre-seed shared Bonus Packs into PostgreSQL from `data/bonus_packs_seed.json`.
    - Shared across all users (zero per-user Gemini API load, 100% Gemini Free Tier safe).
    - Deduplicated against global `vocabulary.normalized_expression`.
    - Ready immediately when a user reaches 1, 3, 5, 10, or 20 confirmed referrals.
    """
    if not BONUS_PACKS_SEED_PATH.exists():
        logger.warning("Bonus packs seed file not found: %s", BONUS_PACKS_SEED_PATH)
        return

    try:
        payload = json.loads(BONUS_PACKS_SEED_PATH.read_text(encoding="utf-8"))
        packs_data = payload.get("packs", [])
    except Exception as exc:
        logger.error("Failed to read bonus_packs_seed.json: %s", exc)
        return

    for pack_entry in packs_data:
        pack_type = pack_entry["pack_type"]
        title = pack_entry["title"]
        required_refs = int(pack_entry["required_referrals"])
        raw_items = pack_entry.get("items", [])

        stmt = select(BonusPack).where(BonusPack.pack_type == pack_type)
        pack = (await session.execute(stmt)).scalar_one_or_none()
        if pack is None:
            pack = BonusPack(
                pack_type=pack_type,
                title=title,
                required_referrals=required_refs,
                status="ready",
            )
            session.add(pack)
            await session.flush()

        # Check existing words linked to this pack
        existing_bw_stmt = select(BonusPackWord).where(
            BonusPackWord.pack_id == pack.id
        )
        existing_bw = list((await session.execute(existing_bw_stmt)).scalars().all())
        if len(existing_bw) >= len(raw_items):
            continue

        existing_positions = {bw.position for bw in existing_bw}
        existing_vocab_ids = {bw.vocabulary_id for bw in existing_bw}

        for idx, raw_item in enumerate(raw_items, start=1):
            if idx in existing_positions:
                continue
            try:
                validated = ai_generator.validate_and_sanitize_item(raw_item)
            except Exception as val_err:
                logger.warning("Invalid bonus pack seed item in %s: %s", pack_type, val_err)
                continue

            norm_expr = normalize_expression(validated["advanced_word"])
            v_stmt = select(Vocabulary).where(
                Vocabulary.normalized_expression == norm_expr
            )
            vocab = (await session.execute(v_stmt)).scalar_one_or_none()

            if vocab is None:
                vocab = Vocabulary(
                    simple_word=validated["simple_word"],
                    advanced_word=validated["advanced_word"],
                    normalized_expression=norm_expr,
                    translation_uz=validated["translation_uz"],
                    translation_ru=validated["translation_ru"],
                    definition_en=validated["definition_en"],
                    basic_example_en=validated.get("basic_example_en"),
                    example_en=validated["example_en"],
                    example_uz=validated["example_uz"],
                    example_ru=validated["example_ru"],
                    cefr_level=validated["cefr_level"],
                    category=validated["category"],
                    ielts_usage=validated.get("ielts_usage", "Writing Task 2 & Speaking Part 3"),
                    source_name=validated.get("source_name", "Cambridge Dictionary"),
                    source_url=validated.get("source_url"),
                    quiz_question_uz=validated.get("quiz_question_uz"),
                    quiz_question_ru=validated.get("quiz_question_ru"),
                    quiz_question_en=validated.get("quiz_question_en"),
                    option_a=validated["options"][0],
                    option_b=validated["options"][1],
                    option_c=validated["options"][2],
                    option_d=validated["options"][3],
                    correct_option=validated["correct_option"],
                )
                session.add(vocab)
                await session.flush()

            if vocab.id not in existing_vocab_ids:
                session.add(
                    BonusPackWord(
                        pack_id=pack.id,
                        vocabulary_id=vocab.id,
                        position=idx,
                    )
                )
                existing_vocab_ids.add(vocab.id)

    await session.commit()
    logger.info("Shared Bonus Packs verified and seeded in PostgreSQL.")
