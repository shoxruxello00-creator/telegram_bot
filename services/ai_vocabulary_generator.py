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

# Exact 4 + 2 + 2 + 2 daily distribution for 10 items
DAILY_CATEGORY_QUOTAS: dict[str, int] = {
    "everyday_upgrade": 4,
    "academic_upgrade": 2,
    "collocation": 2,
    "phrasal_verb": 2,
}

ALLOWED_CEFR_LEVELS = {"B2", "B2–C1", "C1", "C1–C2", "C2"}
ALLOWED_CATEGORIES = {
    "everyday_upgrade",
    "academic_upgrade",
    "collocation",
    "phrasal_verb",
    "idiom",
    "advanced_word",
}
LEGACY_CATEGORY_MAP: dict[str, str] = {
    "idiom": "collocation",
    "advanced_word": "academic_upgrade",
    "everyday": "everyday_upgrade",
    "academic": "academic_upgrade",
}
DEFAULT_IELTS_USAGE_BY_CATEGORY: dict[str, str] = {
    "everyday_upgrade": "Writing Task 2 & Speaking Part 3",
    "academic_upgrade": "Writing Task 2 (Formal Essays)",
    "collocation": "Writing Task 2 & Speaking Part 3",
    "phrasal_verb": "Speaking Part 1–3",
    "idiom": "Speaking Part 2–3",
    "advanced_word": "Writing Task 2",
}
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
        "basic_example_en",
        "example_en",
        "example_uz",
        "example_ru",
        "cefr_level",
        "category",
        "ielts_usage",
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
        "basic_example_en": {"type": "string", "minLength": 5, "maxLength": 400},
        "example_en": {"type": "string", "minLength": 10, "maxLength": 400},
        "example_uz": {"type": "string", "minLength": 5, "maxLength": 400},
        "example_ru": {"type": "string", "minLength": 5, "maxLength": 400},
        "cefr_level": {
            "type": "string",
            "enum": ["B2", "B2–C1", "C1", "C1–C2", "C2"],
        },
        "category": {
            "type": "string",
            "enum": [
                "everyday_upgrade",
                "academic_upgrade",
                "collocation",
                "phrasal_verb",
                "idiom",
                "advanced_word",
            ],
        },
        "ielts_usage": {"type": "string", "minLength": 2, "maxLength": 120},
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
_VERY_ADJECTIVE_RE = re.compile(r"^very\s+[a-z]+(?:\s+[a-z]+)?$", re.IGNORECASE)


def is_very_adjective_pattern(simple_word: str) -> bool:
    """Detect 'very + adjective' basic expressions so we never overuse them."""
    return bool(_VERY_ADJECTIVE_RE.match((simple_word or "").strip()))


def normalize_cefr_level(raw_level: str) -> str:
    cleaned = sanitize_untrusted_text(raw_level, 20).upper()
    cleaned = cleaned.replace("-", "–").replace(" ", "")
    if "B2" in cleaned and "C1" in cleaned:
        return "B2–C1"
    if "C1" in cleaned and "C2" in cleaned:
        return "C1–C2"
    if cleaned in ALLOWED_CEFR_LEVELS:
        return cleaned
    return "B2–C1"


def normalize_category(raw_cat: str, for_daily_distribution: bool = False) -> str:
    cleaned = (
        sanitize_untrusted_text(raw_cat, 64)
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    if cleaned in LEGACY_CATEGORY_MAP and for_daily_distribution:
        return LEGACY_CATEGORY_MAP[cleaned]
    if cleaned in ALLOWED_CATEGORIES:
        if for_daily_distribution and cleaned in LEGACY_CATEGORY_MAP:
            return LEGACY_CATEGORY_MAP[cleaned]
        return cleaned
    if "everyday" in cleaned or "basic" in cleaned:
        return "everyday_upgrade"
    if "academic" in cleaned:
        return "academic_upgrade"
    if "collocation" in cleaned:
        return "collocation"
    if "phrasal" in cleaned:
        return "phrasal_verb"
    return "everyday_upgrade"


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
    basic_example_en: str = Field(..., min_length=5, max_length=400)
    example_en: str = Field(..., min_length=10, max_length=400)
    example_uz: str = Field(..., min_length=5, max_length=400)
    example_ru: str = Field(..., min_length=5, max_length=400)
    cefr_level: str = Field(default="B2–C1")
    category: str = Field(default="everyday_upgrade")
    ielts_usage: str = Field(default="Writing Task 2 & Speaking Part 3")
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
        if word_count > 12:
            raise ValueError("Advanced expression is too long (max 12 words).")
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
    Autonomous Everyday -> Advanced IELTS Vocabulary & Quiz Generator
    enforcing the exact 4 + 2 + 2 + 2 daily category distribution,
    anti-'very + adjective' filtering, formality nuance notes, and deduplication.
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
            "You are a senior Cambridge IELTS Examiner and lexicographer designing daily "
            "Everyday English -> Advanced IELTS English upgrades for Uzbek, Russian, and English learners.\n"
            "CRITICAL PEDAGOGICAL RULES:\n"
            "1. Do NOT focus on 'very + adjective' expressions.\n"
            "2. Do NOT generate only phrasal verbs or obscure idioms.\n"
            "3. Transform ALL types of everyday English (common verbs, nouns, adjectives, adverbs, "
            "quantifier phrases, collocations, and everyday sentence starters like 'I think -> I would argue', "
            "'Deal with a problem -> Address an issue', 'Bad effect -> Detrimental impact') into natural, "
            "context-appropriate IELTS Speaking & Writing English.\n"
            "4. Never force an unnatural word replacement; explain differences in formality, register, and meaning.\n"
            "5. Do not assume every upgrade is C2 — assign realistic levels ('B2–C1', 'C1', 'C1–C2', or 'C2').\n"
            "Return ONLY valid JSON matching the requested schema."
        )

    def _build_user_prompt(
        self,
        needed_by_category: dict[str, int],
        excluded_expressions: list[str],
    ) -> str:
        total_count = sum(needed_by_category.values())
        excl_sample = excluded_expressions[-400:] if excluded_expressions else []
        excl_text = ", ".join(excl_sample) if excl_sample else "None yet"

        quota_lines = []
        if needed_by_category.get("everyday_upgrade", 0) > 0:
            quota_lines.append(
                f"- {needed_by_category['everyday_upgrade']} items with `category: \"everyday_upgrade\"` "
                "(Common verbs e.g. help -> facilitate; common nouns e.g. problem -> challenge; "
                "common adjectives e.g. important -> crucial; common phrases e.g. a lot of -> a considerable amount of; "
                "everyday sentences e.g. I think -> I would argue; simple expressions e.g. bad effect -> detrimental impact)"
            )
        if needed_by_category.get("academic_upgrade", 0) > 0:
            quota_lines.append(
                f"- {needed_by_category['academic_upgrade']} items with `category: \"academic_upgrade\"` "
                "(Academic vocabulary upgrades e.g. make worse -> exacerbate; reduce negative effects -> mitigate)"
            )
        if needed_by_category.get("collocation", 0) > 0:
            quota_lines.append(
                f"- {needed_by_category['collocation']} items with `category: \"collocation\"` "
                "(Advanced collocations / natural expressions e.g. play an important role -> play a pivotal role; "
                "a serious problem -> a pressing issue; deal with a problem -> address an issue)"
            )
        if needed_by_category.get("phrasal_verb", 0) > 0:
            quota_lines.append(
                f"- {needed_by_category['phrasal_verb']} items with `category: \"phrasal_verb\"` "
                "(Natural IELTS phrasal verbs e.g. postpone -> put off; encounter -> come across)"
            )
        quota_str = "\n".join(quota_lines)

        return (
            f"Generate exactly {total_count} NEW Everyday English -> Advanced IELTS English items "
            f"following this exact category distribution:\n{quota_str}\n\n"
            "STRICT RULES:\n"
            "- Do NOT use 'very + adjective' for `simple_word`.\n"
            "- NEVER use any of these previously used `advanced_word` expressions (or minor variants):\n"
            f"[{excl_text}]\n\n"
            "For each item, return an object inside `{\"items\": [...]}` with the exact fields:\n"
            "- `simple_word`: Everyday / Basic English word, phrase, or clause (e.g., \"Deal with a problem\")\n"
            "- `advanced_word`: Natural, precise IELTS upgrade (e.g., \"Address an issue\")\n"
            "- `translation_uz`: Accurate Uzbek translation\n"
            "- `translation_ru`: Accurate Russian translation\n"
            "- `definition_en`: Clear English explanation of meaning AND difference in formality/register\n"
            "- `basic_example_en`: Everyday English sentence using the basic expression (e.g., \"Governments should deal with this problem.\")\n"
            "- `example_en`: Upgraded IELTS sentence using `advanced_word` naturally (e.g., \"Governments should address this issue.\")\n"
            "- `example_uz`: Uzbek translation of the upgraded sentence\n"
            "- `example_ru`: Russian translation of the upgraded sentence\n"
            "- `cefr_level`: Realistic CEFR level: \"B2–C1\", \"C1\", \"C1–C2\", or \"C2\"\n"
            "- `category`: One of \"everyday_upgrade\", \"academic_upgrade\", \"collocation\", \"phrasal_verb\"\n"
            "- `ielts_usage`: Specific IELTS context (e.g., \"Writing Task 2\", \"Speaking Part 3\", \"Writing Task 2 & Formal Essays\", \"Speaking Part 1–3\")\n"
            "- `source_name`: \"Cambridge Dictionary\", \"Oxford Learner's Dictionaries\", or \"Merriam-Webster\"\n"
            "- `source_url`: Dictionary URL\n"
            "- `quiz_question_uz`: Multiple-choice question in Uzbek asking for the best IELTS upgrade for `simple_word`\n"
            "- `quiz_question_ru`: Multiple-choice question in Russian asking for the best IELTS upgrade for `simple_word`\n"
            "- `quiz_question_en`: Multiple-choice question in English asking for the best IELTS upgrade for `simple_word`\n"
            "- `options`: Array of 4 distinct choices [A, B, C, D] (each under 90 chars), one matching `advanced_word` and three plausible distractors\n"
            "- `correct_option`: Integer index (0, 1, 2, or 3) of the correct choice."
        )

    async def _call_ai_api(
        self,
        needed_by_category: dict[str, int],
        excluded_expressions: list[str],
    ) -> dict[str, Any]:
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            needed_by_category, excluded_expressions
        )

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
            for fallback_m in (
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-2.5-flash-preview-05-20",
            ):
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
        self,
        raw_item: dict[str, Any],
        for_daily_distribution: bool = False,
    ) -> dict[str, Any]:
        """
        Sanitize untrusted fields, derive fallback basic_example_en / ielts_usage
        if omitted on legacy items, and validate against JSON Schema and Pydantic.
        """
        adv = sanitize_untrusted_text(raw_item.get("advanced_word", ""), 120)
        simple = sanitize_untrusted_text(raw_item.get("simple_word", ""), 120)
        cefr = normalize_cefr_level(raw_item.get("cefr_level", "B2–C1"))
        category = normalize_category(
            raw_item.get("category", "everyday_upgrade"),
            for_daily_distribution=for_daily_distribution,
        )

        ielts_usage = sanitize_untrusted_text(
            raw_item.get("ielts_usage")
            or DEFAULT_IELTS_USAGE_BY_CATEGORY.get(
                category, "Writing Task 2 & Speaking Part 3"
            ),
            120,
        )

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

        if len(options) != 4:
            raise ValueError("Quiz options must contain exactly 4 choices.")

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

        norm_opts = {normalize_expression(o) for o in options}
        if len(norm_opts) != 4:
            raise ValueError("Quiz options contain duplicate choices.")

        translation_uz = sanitize_untrusted_text(raw_item.get("translation_uz", ""), 280)
        translation_ru = sanitize_untrusted_text(raw_item.get("translation_ru", ""), 280)
        definition_en = sanitize_untrusted_text(raw_item.get("definition_en", ""), 350)
        example_en = sanitize_untrusted_text(raw_item.get("example_en", ""), 350)
        example_uz = sanitize_untrusted_text(raw_item.get("example_uz", ""), 350)
        example_ru = sanitize_untrusted_text(raw_item.get("example_ru", ""), 350)

        raw_basic_ex = raw_item.get("basic_example_en")
        if raw_basic_ex and str(raw_basic_ex).strip():
            basic_example_en = sanitize_untrusted_text(raw_basic_ex, 350)
        else:
            pattern = re.compile(re.escape(adv), flags=re.IGNORECASE)
            if pattern.search(example_en):
                rep = pattern.sub(simple.lower(), example_en, count=1)
                basic_example_en = sanitize_untrusted_text(
                    rep[0].upper() + rep[1:] if rep else example_en, 350
                )
            else:
                basic_example_en = sanitize_untrusted_text(
                    f"In everyday English: \"{simple}\".", 350
                )

        q_uz = sanitize_untrusted_text(
            raw_item.get("quiz_question_uz")
            or f"«{simple}» ({translation_uz}) ifodasining tabiiy va yuqori darajadagi IELTS muqobilini toping:",
            250,
        )
        q_ru = sanitize_untrusted_text(
            raw_item.get("quiz_question_ru")
            or f"Выберите продвинутый вариант IELTS для повседневного выражения «{simple}» ({translation_ru}):",
            250,
        )
        q_en = sanitize_untrusted_text(
            raw_item.get("quiz_question_en")
            or f"Which advanced IELTS expression best upgrades \"{simple}\" ({ielts_usage})?",
            250,
        )

        sanitized_dict: dict[str, Any] = {
            "simple_word": simple,
            "advanced_word": adv,
            "translation_uz": translation_uz,
            "translation_ru": translation_ru,
            "definition_en": definition_en,
            "basic_example_en": basic_example_en,
            "example_en": example_en,
            "example_uz": example_uz,
            "example_ru": example_ru,
            "cefr_level": cefr,
            "category": category,
            "ielts_usage": ielts_usage,
            "source_name": source_name,
            "source_url": source_url,
            "quiz_question_uz": q_uz,
            "quiz_question_ru": q_ru,
            "quiz_question_en": q_en,
            "options": options,
            "correct_option": correct_idx,
        }

        jsonschema.validate(instance=sanitized_dict, schema=VOCABULARY_ITEM_SCHEMA)
        model = VocabularyCandidateModel(**sanitized_dict)
        norm_expr = normalize_expression(model.advanced_word)
        if not norm_expr:
            raise ValueError("Normalized expression cannot be empty.")

        result = model.model_dump()
        result["normalized_expression"] = norm_expr
        return result

    @staticmethod
    def _compute_target_quotas(required_count: int) -> dict[str, int]:
        if required_count == 10:
            return dict(DAILY_CATEGORY_QUOTAS)
        # Proportional fallback if custom DAILY_WORD_COUNT is used
        quotas = {
            "everyday_upgrade": max(1, round(required_count * 0.4)),
            "academic_upgrade": max(0, round(required_count * 0.2)),
            "collocation": max(0, round(required_count * 0.2)),
            "phrasal_verb": 0,
        }
        quotas["phrasal_verb"] = max(
            0, required_count - sum(quotas.values())
        )
        return quotas

    def _load_unused_from_reserve_by_quotas(
        self,
        needed_by_category: dict[str, int],
        known_normalized: set[str],
        very_count_so_far: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Load unused items from `data/reserve_vocabulary.json` respecting the
        4 + 2 + 2 + 2 category quotas (`everyday_upgrade`, `academic_upgrade`,
        `collocation`, `phrasal_verb`) and the anti-'very + adjective' filter.
        """
        if not RESERVE_FILE_PATH.exists():
            return [], 0

        try:
            raw_list = json.loads(RESERVE_FILE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to read reserve vocabulary file: %s", exc)
            return [], 0

        remaining = dict(needed_by_category)
        total_needed = sum(remaining.values())
        selected: list[dict[str, Any]] = []
        rejected_dups = 0
        very_count = very_count_so_far

        # First pass: strictly match needed category quotas
        unmatched_valid: list[dict[str, Any]] = []
        for raw_item in raw_list:
            if len(selected) >= total_needed:
                break
            try:
                validated = self.validate_and_sanitize_item(
                    raw_item, for_daily_distribution=True
                )
            except Exception as exc:
                logger.warning("Skipping invalid reserve item: %s", exc)
                continue

            if is_very_adjective_pattern(validated["simple_word"]):
                if very_count >= 1:
                    continue

            is_dup, norm_expr = is_duplicate_or_near_duplicate(
                validated["advanced_word"], known_normalized
            )
            if is_dup:
                rejected_dups += 1
                continue

            cat = validated["category"]
            if remaining.get(cat, 0) > 0:
                validated["normalized_expression"] = norm_expr
                known_normalized.add(norm_expr)
                if is_very_adjective_pattern(validated["simple_word"]):
                    very_count += 1
                remaining[cat] -= 1
                selected.append(validated)
            else:
                unmatched_valid.append(validated)

        # Second pass: if a category in reserve was exhausted, fill remaining slots from other unused valid items
        for cand in unmatched_valid:
            if len(selected) >= total_needed:
                break
            is_dup, norm_expr = is_duplicate_or_near_duplicate(
                cand["advanced_word"], known_normalized
            )
            if is_dup:
                continue
            cand["normalized_expression"] = norm_expr
            known_normalized.add(norm_expr)
            selected.append(cand)

        return selected, rejected_dups

    def _load_unused_from_reserve(
        self,
        needed_count: int,
        known_normalized: set[str],
    ) -> tuple[list[dict[str, Any]], int]:
        quotas = self._compute_target_quotas(needed_count)
        return self._load_unused_from_reserve_by_quotas(
            needed_by_category=quotas,
            known_normalized=known_normalized,
        )

    async def generate_daily_lesson(
        self,
        session: AsyncSession,
        target_date: date | None = None,
        word_count: int | None = None,
        max_retries: int = 4,
    ) -> GenerationResult:
        """
        Generate and save a daily lesson of 10 unique Everyday -> Advanced IELTS upgrades
        with the exact 4 + 2 + 2 + 2 category distribution:
        - 4 everyday_upgrade
        - 2 academic_upgrade
        - 2 collocation
        - 2 phrasal_verb
        Idempotent for `target_date`.
        """
        lesson_date = target_date or settings.today()
        required_count = word_count or settings.DAILY_WORD_COUNT

        # 1. Check idempotency
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
            "Starting 4+2+2+2 IELTS generation for %s. Historical vocabulary count in DB: %d",
            lesson_date,
            len(known_normalized),
        )

        target_quotas = self._compute_target_quotas(required_count)
        remaining_quotas = dict(target_quotas)

        accepted_items: list[dict[str, Any]] = []
        rejected_duplicates = 0
        retry_count = 0
        very_pattern_count = 0
        last_error: str | None = None
        used_fallback = False

        # 3. Try AI API generation with automatic retry mechanism
        if self._has_valid_api_key():
            for attempt in range(1, max_retries + 1):
                needed = sum(remaining_quotas.values())
                if needed <= 0:
                    break

                if attempt > 1:
                    retry_count += 1

                try:
                    raw_payload = await self._call_ai_api(
                        needed_by_category=remaining_quotas,
                        excluded_expressions=sorted(known_normalized),
                    )
                    jsonschema.validate(
                        instance=raw_payload, schema=VOCABULARY_BATCH_SCHEMA
                    )
                    raw_items = raw_payload.get("items", [])

                    for raw_item in raw_items:
                        if sum(remaining_quotas.values()) <= 0:
                            break
                        try:
                            validated = self.validate_and_sanitize_item(
                                raw_item, for_daily_distribution=True
                            )
                        except Exception as val_err:
                            logger.warning(
                                "AI item failed schema/content validation: %s", val_err
                            )
                            continue

                        # Reject excessive 'very + adjective' patterns
                        if is_very_adjective_pattern(validated["simple_word"]):
                            if very_pattern_count >= 1:
                                logger.info(
                                    "Rejected 'very + adjective' item '%s' to maintain variety.",
                                    validated["simple_word"],
                                )
                                continue

                        cat = validated["category"]
                        if remaining_quotas.get(cat, 0) <= 0:
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
                        if is_very_adjective_pattern(validated["simple_word"]):
                            very_pattern_count += 1
                        remaining_quotas[cat] -= 1
                        accepted_items.append(validated)

                except Exception as api_err:
                    last_error = f"AI API error on attempt {attempt}: {api_err}"
                    logger.warning(last_error)
        else:
            last_error = "AI_API_KEY not configured; using unused reserve vocabulary pool."
            logger.info(last_error)

        # 4. Fallback to unused reserve vocabulary respecting remaining 4+2+2+2 category quotas
        if len(accepted_items) < required_count:
            reserve_items, reserve_dups = self._load_unused_from_reserve_by_quotas(
                needed_by_category=remaining_quotas,
                known_normalized=known_normalized,
                very_count_so_far=very_pattern_count,
            )
            rejected_duplicates += reserve_dups
            if reserve_items:
                used_fallback = True
                accepted_items.extend(reserve_items)

        # 5. NEVER repeat old words if we still couldn't find 10 unique words
        if len(accepted_items) < required_count:
            err_msg = (
                f"Could only obtain {len(accepted_items)}/{required_count} unique IELTS "
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

        # Order the final 10 items cleanly: 4 everyday_upgrade, 2 academic_upgrade, 2 collocation, 2 phrasal_verb
        category_order = {
            "everyday_upgrade": 0,
            "academic_upgrade": 1,
            "collocation": 2,
            "phrasal_verb": 3,
        }
        final_items = sorted(
            accepted_items[:required_count],
            key=lambda x: category_order.get(x["category"], 99),
        )
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
                "Successfully saved %d unique IELTS expressions (4+2+2+2) for %s (status=%s, rejected_dups=%d)",
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
