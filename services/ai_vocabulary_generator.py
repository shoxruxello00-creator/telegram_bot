import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import jsonschema
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import crud
from database.models import DailyLesson
from services.normalizer import is_duplicate_or_near_duplicate, normalize_expression

logger = logging.getLogger(__name__)

RESERVE_FILE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "reserve_vocabulary.json"
)

ALLOWED_CEFR_LEVELS = {"C1", "C2"}
ALLOWED_CATEGORIES = {"idiom", "phrasal_verb", "collocation", "advanced_word"}
TRUSTED_SOURCES = {
    "Cambridge Dictionary": "https://dictionary.cambridge.org/dictionary/english/",
    "Oxford Learner's Dictionaries": "https://www.oxfordlearnersdictionaries.com/definition/english/",
    "Merriam-Webster": "https://www.merriam-webster.com/dictionary/",
    "Collins Dictionary": "https://www.collinsdictionary.com/dictionary/english/",
}

# JSON Schema for strict validation of AI responses
VOCABULARY_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "simple_word",
        "advanced_word",
        "translation_uz",
        "translation_ru",
        "definition_en",
        "example_en",
        "example_uz",
        "example_ru",
        "cefr_level",
        "category",
        "source_name",
        "options",
        "correct_option",
    ],
    "properties": {
        "simple_word": {"type": "string", "minLength": 2, "maxLength": 150},
        "advanced_word": {"type": "string", "minLength": 2, "maxLength": 150},
        "translation_uz": {"type": "string", "minLength": 2, "maxLength": 300},
        "translation_ru": {"type": "string", "minLength": 2, "maxLength": 300},
        "definition_en": {"type": "string", "minLength": 5, "maxLength": 400},
        "example_en": {"type": "string", "minLength": 10, "maxLength": 400},
        "example_uz": {"type": "string", "minLength": 5, "maxLength": 400},
        "example_ru": {"type": "string", "minLength": 5, "maxLength": 400},
        "cefr_level": {"type": "string", "enum": ["C1", "C2"]},
        "category": {
            "type": "string",
            "enum": ["idiom", "phrasal_verb", "collocation", "advanced_word"],
        },
        "source_name": {"type": "string", "minLength": 2, "maxLength": 120},
        "source_url": {"type": ["string", "null"]},
        "quiz_question_uz": {"type": ["string", "null"]},
        "quiz_question_ru": {"type": ["string", "null"]},
        "quiz_question_en": {"type": ["string", "null"]},
        "options": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {"type": "string", "minLength": 1, "maxLength": 100},
        },
        "correct_option": {"type": "integer", "minimum": 0, "maximum": 3},
    },
}

VOCABULARY_BATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "minItems": 1,
            "items": VOCABULARY_ITEM_SCHEMA,
        }
    },
}

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_ENGLISH_EXPRESSION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9\s\-'’/(),.]{1,120}$")


def sanitize_untrusted_text(value: Any, max_len: int = 350) -> str:
    """
    Sanitize AI output as untrusted external content:
    - Strip control characters
    - Remove raw HTML tags so AI output cannot inject markup or scripts
    - Collapse whitespace and enforce length bounds
    """
    if not isinstance(value, str):
        value = str(value or "")
    cleaned = _CONTROL_CHARS_RE.sub("", value)
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


class VocabularyCandidateModel(BaseModel):
    simple_word: str = Field(..., min_length=2, max_length=150)
    advanced_word: str = Field(..., min_length=2, max_length=150)
    normalized_expression: str = Field(default="")
    translation_uz: str = Field(..., min_length=2, max_length=300)
    translation_ru: str = Field(..., min_length=2, max_length=300)
    definition_en: str = Field(..., min_length=5, max_length=400)
    example_en: str = Field(..., min_length=10, max_length=400)
    example_uz: str = Field(..., min_length=5, max_length=400)
    example_ru: str = Field(..., min_length=5, max_length=400)
    cefr_level: str = Field(default="C1")
    category: str = Field(default="idiom")
    source_name: str = Field(default="Cambridge Dictionary")
    source_url: str | None = Field(default=None)
    quiz_question_uz: str | None = Field(default=None)
    quiz_question_ru: str | None = Field(default=None)
    quiz_question_en: str | None = Field(default=None)
    options: list[str] = Field(..., min_length=4, max_length=4)
    correct_option: int = Field(..., ge=0, le=3)

    @field_validator("advanced_word")
    @classmethod
    def validate_natural_english(cls, v: str) -> str:
        cleaned = sanitize_untrusted_text(v, 120)
        if not _ENGLISH_EXPRESSION_RE.match(cleaned):
            raise ValueError(f"Expression '{cleaned}' does not look like natural English.")
        word_count = len(cleaned.split())
        if word_count > 10:
            raise ValueError("Advanced expression is too long (max 10 words).")
        return cleaned


@dataclass
class GenerationResult:
    success: bool
    status: str  # "SUCCESS", "FALLBACK_RESERVE", "ALREADY_EXISTS", "FAILED"
    lesson_date: date
    generated_count: int = 0
    rejected_duplicates: int = 0
    retry_count: int = 0
    error_message: str | None = None
    lesson: DailyLesson | None = None
    items: list[dict[str, Any]] = field(default_factory=list)


class AIVocabularyGenerator:
    """
    Autonomous C1–C2 Vocabulary & Quiz Generator with strict deduplication,
    JSON schema validation, multi-retry recovery, and unused reserve fallback.
    """

    def __init__(self) -> None:
        self.provider = settings.AI_PROVIDER
        self.api_key = settings.AI_API_KEY
        self.model = settings.AI_MODEL
        self.base_url = settings.AI_BASE_URL

    def _has_valid_api_key(self) -> bool:
        if not self.api_key:
            return False
        placeholder_tokens = {"YOUR_AI_API_KEY", "YOUR_API_KEY", "NONE", "NULL", ""}
        return self.api_key.upper() not in placeholder_tokens

    def _build_system_prompt(self) -> str:
        return (
            "You are an expert Cambridge C1/C2 lexicographer and multilingual curriculum designer "
            "for Uzbek, Russian, and English learners.\n"
            "Your task is to generate authentic, natural C1–C2 level English expressions "
            "(idioms, phrasal verbs, collocations, or high-level academic/literary vocabulary) "
            "verified against authoritative dictionaries (Cambridge Dictionary, Oxford Learner's Dictionaries, "
            "Merriam-Webster).\n"
            "Return ONLY valid JSON matching the requested schema. Do not wrap in markdown or commentary."
        )

    def _build_user_prompt(
        self, count: int, excluded_expressions: list[str]
    ) -> str:
        excl_sample = excluded_expressions[-400:] if excluded_expressions else []
        excl_text = ", ".join(excl_sample) if excl_sample else "None yet"

        return (
            f"Generate exactly {count} NEW, distinct C1–C2 English vocabulary items.\n\n"
            f"CRITICAL RULE: NEVER use any of these previously used expressions (or minor spelling variants):\n"
            f"[{excl_text}]\n\n"
            "For each item, return an object inside `{\"items\": [...]}` with the exact fields:\n"
            "- `simple_word`: Simple B1/B2 English equivalent (e.g., \"Give up\")\n"
            "- `advanced_word`: C1 or C2 English idiom, phrasal verb, collocation, or word (e.g., \"Throw in the towel\")\n"
            "- `translation_uz`: Accurate, natural Uzbek translation\n"
            "- `translation_ru`: Accurate, natural Russian translation\n"
            "- `definition_en`: Clear English definition in one sentence\n"
            "- `example_en`: Natural C1–C2 English example sentence demonstrating usage\n"
            "- `example_uz`: Uzbek translation of the example sentence\n"
            "- `example_ru`: Russian translation of the example sentence\n"
            "- `cefr_level`: Either \"C1\" or \"C2\"\n"
            "- `category`: One of \"idiom\", \"phrasal_verb\", \"collocation\", \"advanced_word\"\n"
            "- `source_name`: Authoritative dictionary source (\"Cambridge Dictionary\", \"Oxford Learner's Dictionaries\", or \"Merriam-Webster\")\n"
            "- `source_url`: Dictionary URL for the expression\n"
            "- `quiz_question_uz`: Multiple-choice question prompt in Uzbek testing this expression\n"
            "- `quiz_question_ru`: Multiple-choice question prompt in Russian testing this expression\n"
            "- `quiz_question_en`: Multiple-choice question prompt in English testing this expression\n"
            "- `options`: Array of 4 distinct C1–C2 English expressions [A, B, C, D] (each under 90 characters), where one is the exact `advanced_word` and three are plausible distractors\n"
            "- `correct_option`: Integer index (0, 1, 2, or 3) corresponding to the correct option in `options`."
        )

    async def _call_ai_api(
        self, count: int, excluded_expressions: list[str]
    ) -> dict[str, Any]:
        """Call configured AI provider (OpenAI / Gemini / Anthropic / OpenAI-compatible) and parse JSON."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(count, excluded_expressions)

        if self.provider in {"openai", "groq", "deepseek", "openrouter", "together"}:
            client_kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            client = AsyncOpenAI(**client_kwargs)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                timeout=45.0,
            )
            raw_content = response.choices[0].message.content or "{}"
            return self._extract_json_dict(raw_content)

        if self.provider == "gemini":
            primary_model = (self.model or "gemini-2.5-flash").strip()
            if primary_model.startswith("models/"):
                primary_model = primary_model.split("models/", 1)[1]
            candidate_models = [primary_model]
            for fallback_m in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-preview-05-20"):
                if fallback_m not in candidate_models:
                    candidate_models.append(fallback_m)

            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "responseMimeType": "application/json",
                },
            }
            headers = {
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            }
            last_exc: Exception | None = None
            async with httpx.AsyncClient(timeout=45.0) as http_client:
                for model_name in candidate_models:
                    url = (
                        f"https://generativelanguage.googleapis.com/v1beta/models/"
                        f"{model_name}:generateContent"
                    )
                    resp = await http_client.post(url, headers=headers, json=payload)
                    if resp.status_code == 404:
                        last_exc = httpx.HTTPStatusError(
                            f"Gemini model '{model_name}' not found (404)",
                            request=resp.request,
                            response=resp,
                        )
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    text_out = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "{}")
                    )
                    return self._extract_json_dict(text_out)
            if last_exc:
                raise last_exc
            raise RuntimeError("Gemini API call failed across all candidate models.")

        if self.provider == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": self.model or "claude-3-5-sonnet-latest",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            async with httpx.AsyncClient(timeout=45.0) as http_client:
                resp = await http_client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text_out = data.get("content", [{}])[0].get("text", "{}")
                return self._extract_json_dict(text_out)

        raise ValueError(f"Unsupported AI_PROVIDER: {self.provider}")

    @staticmethod
    def _extract_json_dict(raw_text: str) -> dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return {"items": parsed}
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("AI response is neither a JSON object nor a JSON array.")

    def validate_and_sanitize_item(
        self, raw_item: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Sanitize untrusted fields, repair minor option indexing if needed,
        and validate against JSON Schema and Pydantic.
        """
        adv = sanitize_untrusted_text(raw_item.get("advanced_word", ""), 120)
        simple = sanitize_untrusted_text(raw_item.get("simple_word", ""), 120)
        cefr = sanitize_untrusted_text(raw_item.get("cefr_level", "C1"), 10).upper()
        if cefr not in ALLOWED_CEFR_LEVELS:
            cefr = "C1"

        category = (
            sanitize_untrusted_text(raw_item.get("category", "idiom"), 64)
            .lower()
            .replace(" ", "_")
        )
        if category not in ALLOWED_CATEGORIES:
            category = "idiom"

        source_name = sanitize_untrusted_text(
            raw_item.get("source_name", "Cambridge Dictionary"), 120
        )
        if source_name not in TRUSTED_SOURCES:
            source_name = "Cambridge Dictionary"

        slug = re.sub(r"[^a-z0-9]+", "-", adv.lower()).strip("-")
        default_url = f"{TRUSTED_SOURCES[source_name]}{slug}"
        source_url = sanitize_untrusted_text(
            raw_item.get("source_url") or default_url, 300
        )
        if not source_url.startswith(("https://", "http://")):
            source_url = default_url

        raw_options = raw_item.get("options") or []
        options = [sanitize_untrusted_text(opt, 95) for opt in raw_options if opt]

        correct_idx = raw_item.get("correct_option", 0)
        if not isinstance(correct_idx, int) or not (0 <= correct_idx < 4):
            correct_idx = 0

        # Ensure exact 4 distinct options containing `adv` at `correct_idx`
        if len(options) != 4:
            raise ValueError("Quiz options must contain exactly 4 choices.")

        # Verify `adv` is at `options[correct_idx]` or locate it
        norm_adv = normalize_expression(adv)
        matched_idx = None
        for idx, opt in enumerate(options):
            if normalize_expression(opt) == norm_adv:
                matched_idx = idx
                break

        if matched_idx is not None:
            correct_idx = matched_idx
            options[correct_idx] = adv
        else:
            options[correct_idx] = adv

        # Check all 4 options are distinct
        norm_opts = {normalize_expression(o) for o in options}
        if len(norm_opts) != 4:
            raise ValueError("Quiz options contain duplicate choices.")

        translation_uz = sanitize_untrusted_text(raw_item.get("translation_uz", ""), 280)
        translation_ru = sanitize_untrusted_text(raw_item.get("translation_ru", ""), 280)
        definition_en = sanitize_untrusted_text(raw_item.get("definition_en", ""), 350)
        example_en = sanitize_untrusted_text(raw_item.get("example_en", ""), 350)
        example_uz = sanitize_untrusted_text(raw_item.get("example_uz", ""), 350)
        example_ru = sanitize_untrusted_text(raw_item.get("example_ru", ""), 350)

        q_uz = sanitize_untrusted_text(
            raw_item.get("quiz_question_uz")
            or f"«{simple}» ({translation_uz}) ma'nosini bildiruvchi {cefr} darajadagi iborani toping:",
            250,
        )
        q_ru = sanitize_untrusted_text(
            raw_item.get("quiz_question_ru")
            or f"Выберите выражение уровня {cefr} со значением «{simple}» ({translation_ru}):",
            250,
        )
        q_en = sanitize_untrusted_text(
            raw_item.get("quiz_question_en")
            or f"Which {cefr} expression best replaces \"{simple}\" ({definition_en})?",
            250,
        )

        sanitized_dict: dict[str, Any] = {
            "simple_word": simple,
            "advanced_word": adv,
            "translation_uz": translation_uz,
            "translation_ru": translation_ru,
            "definition_en": definition_en,
            "example_en": example_en,
            "example_uz": example_uz,
            "example_ru": example_ru,
            "cefr_level": cefr,
            "category": category,
            "source_name": source_name,
            "source_url": source_url,
            "quiz_question_uz": q_uz,
            "quiz_question_ru": q_ru,
            "quiz_question_en": q_en,
            "options": options,
            "correct_option": correct_idx,
        }

        # Validate against JSON Schema
        jsonschema.validate(instance=sanitized_dict, schema=VOCABULARY_ITEM_SCHEMA)

        # Validate with Pydantic
        model = VocabularyCandidateModel(**sanitized_dict)
        norm_expr = normalize_expression(model.advanced_word)
        if not norm_expr:
            raise ValueError("Normalized expression cannot be empty.")

        result = model.model_dump()
        result["normalized_expression"] = norm_expr
        return result

    def _load_unused_from_reserve(
        self,
        needed_count: int,
        known_normalized: set[str],
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Load unused C1–C2 items from `data/reserve_vocabulary.json` that have
        NEVER been used in PostgreSQL (`known_normalized`).
        """
        if not RESERVE_FILE_PATH.exists():
            return [], 0

        try:
            raw_list = json.loads(RESERVE_FILE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to read reserve vocabulary file: %s", exc)
            return [], 0

        selected: list[dict[str, Any]] = []
        rejected_dups = 0

        for raw_item in raw_list:
            if len(selected) >= needed_count:
                break
            try:
                validated = self.validate_and_sanitize_item(raw_item)
            except Exception as exc:
                logger.warning("Skipping invalid reserve item: %s", exc)
                continue

            is_dup, norm_expr = is_duplicate_or_near_duplicate(
                validated["advanced_word"], known_normalized
            )
            if is_dup:
                rejected_dups += 1
                continue

            validated["normalized_expression"] = norm_expr
            known_normalized.add(norm_expr)
            selected.append(validated)

        return selected, rejected_dups

    async def generate_daily_lesson(
        self,
        session: AsyncSession,
        target_date: date | None = None,
        word_count: int | None = None,
        max_retries: int = 4,
    ) -> GenerationResult:
        """
        Main entry point to generate and save a daily lesson of 10 unique C1–C2 expressions.
        Idempotent for `target_date`: if the lesson already exists, returns immediately.
        """
        lesson_date = target_date or settings.today()
        required_count = word_count or settings.DAILY_WORD_COUNT

        # 1. Check idempotency: does a lesson for this date already exist?
        existing_lesson = await crud.get_daily_lesson_by_date(session, lesson_date)
        if existing_lesson is not None:
            logger.info("Daily lesson for %s already exists; skipping generation.", lesson_date)
            return GenerationResult(
                success=True,
                status="ALREADY_EXISTS",
                lesson_date=lesson_date,
                generated_count=len(existing_lesson.vocabulary_ids or []),
                lesson=existing_lesson,
            )

        # 2. Load ALL historical normalized expressions from PostgreSQL
        known_normalized = await crud.get_all_normalized_expressions(session)
        logger.info(
            "Starting generation for %s. Historical vocabulary count in DB: %d",
            lesson_date,
            len(known_normalized),
        )

        accepted_items: list[dict[str, Any]] = []
        rejected_duplicates = 0
        retry_count = 0
        last_error: str | None = None
        used_fallback = False

        # 3. Try AI API generation with automatic retry mechanism
        if self._has_valid_api_key():
            for attempt in range(1, max_retries + 1):
                needed = required_count - len(accepted_items)
                if needed <= 0:
                    break

                if attempt > 1:
                    retry_count += 1

                try:
                    # Ask AI for a few extra candidates when retrying to absorb potential duplicates
                    request_batch_size = needed if attempt == 1 else min(needed + 3, 15)
                    raw_payload = await self._call_ai_api(
                        count=request_batch_size,
                        excluded_expressions=sorted(known_normalized),
                    )
                    jsonschema.validate(
                        instance=raw_payload, schema=VOCABULARY_BATCH_SCHEMA
                    )
                    raw_items = raw_payload.get("items", [])

                    for raw_item in raw_items:
                        if len(accepted_items) >= required_count:
                            break
                        try:
                            validated = self.validate_and_sanitize_item(raw_item)
                        except Exception as val_err:
                            logger.warning(
                                "AI item failed schema/content validation: %s", val_err
                            )
                            continue

                        is_dup, norm_expr = is_duplicate_or_near_duplicate(
                            validated["advanced_word"], known_normalized
                        )
                        if is_dup:
                            rejected_duplicates += 1
                            logger.info(
                                "Rejected duplicate/near-duplicate AI expression: '%s' (%s)",
                                validated["advanced_word"],
                                norm_expr,
                            )
                            continue

                        validated["normalized_expression"] = norm_expr
                        known_normalized.add(norm_expr)
                        accepted_items.append(validated)

                except Exception as api_err:
                    last_error = f"AI API error on attempt {attempt}: {api_err}"
                    logger.warning(last_error)
        else:
            last_error = "AI_API_KEY not configured; using unused reserve vocabulary pool."
            logger.info(last_error)

        # 4. Fallback to unused reserve vocabulary if AI API failed or returned < required_count
        if len(accepted_items) < required_count:
            still_needed = required_count - len(accepted_items)
            reserve_items, reserve_dups = self._load_unused_from_reserve(
                needed_count=still_needed,
                known_normalized=known_normalized,
            )
            rejected_duplicates += reserve_dups
            if reserve_items:
                used_fallback = True
                accepted_items.extend(reserve_items)

        # 5. NEVER repeat old words if we still couldn't find 10 unique words
        if len(accepted_items) < required_count:
            err_msg = (
                f"Could only obtain {len(accepted_items)}/{required_count} unique C1-C2 "
                f"expressions. Refusing to repeat previously used words. Last error: {last_error}"
            )
            logger.error(err_msg)
            await crud.create_generation_log(
                session=session,
                lesson_date=lesson_date,
                generation_status="FAILED",
                generated_count=len(accepted_items),
                rejected_duplicates=rejected_duplicates,
                retry_count=retry_count,
                error_message=err_msg,
            )
            return GenerationResult(
                success=False,
                status="FAILED",
                lesson_date=lesson_date,
                generated_count=len(accepted_items),
                rejected_duplicates=rejected_duplicates,
                retry_count=retry_count,
                error_message=err_msg,
            )

        # 6. Atomically save the 10 unique words and daily lesson inside PostgreSQL transaction
        final_items = accepted_items[:required_count]
        status_label = "FALLBACK_RESERVE" if used_fallback else "SUCCESS"
        try:
            daily_lesson = await crud.save_generated_daily_lesson(
                session=session,
                target_date=lesson_date,
                candidates=final_items,
            )
            await crud.create_generation_log(
                session=session,
                lesson_date=lesson_date,
                generation_status=status_label,
                generated_count=len(final_items),
                rejected_duplicates=rejected_duplicates,
                retry_count=retry_count,
                error_message=last_error if used_fallback else None,
            )
            logger.info(
                "Successfully saved %d unique C1–C2 expressions for %s (status=%s, rejected_dups=%d)",
                len(final_items),
                lesson_date,
                status_label,
                rejected_duplicates,
            )
            return GenerationResult(
                success=True,
                status=status_label,
                lesson_date=lesson_date,
                generated_count=len(final_items),
                rejected_duplicates=rejected_duplicates,
                retry_count=retry_count,
                error_message=last_error if used_fallback else None,
                lesson=daily_lesson,
                items=final_items,
            )
        except IntegrityError as db_err:
            await session.rollback()
            err_msg = f"Database UNIQUE constraint prevented duplicate insert: {db_err}"
            logger.error(err_msg)
            await crud.create_generation_log(
                session=session,
                lesson_date=lesson_date,
                generation_status="FAILED",
                generated_count=0,
                rejected_duplicates=rejected_duplicates + 1,
                retry_count=retry_count,
                error_message=err_msg,
            )
            return GenerationResult(
                success=False,
                status="FAILED",
                lesson_date=lesson_date,
                generated_count=0,
                rejected_duplicates=rejected_duplicates + 1,
                retry_count=retry_count,
                error_message=err_msg,
            )


ai_generator = AIVocabularyGenerator()
