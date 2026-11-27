import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

from config import settings
from services.gemini_free_tier_policy import (
    FreeTierQuotaExhaustedError,
    NoVerifiedFreeModelAvailableError,
    PaidApiForbiddenError,
    enforce_free_tier_provider_and_model,
    gemini_quota_tracker,
    is_verified_free_tier_model,
    normalize_gemini_model_name,
    sanitize_free_tier_whitelist,
)
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


def _validate_dict_schema(instance: dict[str, Any], is_batch: bool = False) -> None:
    if jsonschema is not None:
        jsonschema.validate(
            instance=instance,
            schema=VOCABULARY_BATCH_SCHEMA if is_batch else VOCABULARY_ITEM_SCHEMA,
        )
        return
    if is_batch:
        if not isinstance(instance, dict) or not isinstance(instance.get("items"), list) or not instance["items"]:
            raise ValueError("Batch payload must contain a non-empty 'items' list.")
        return
    for req_key in VOCABULARY_ITEM_SCHEMA["required"]:
        if req_key not in instance:
            raise ValueError(f"Missing required field '{req_key}'")


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


@dataclass
class GenerationResult:
    success: bool
    status: str  # "SUCCESS", "FALLBACK_RESERVE", "ALREADY_EXISTS", "FAILED"
    lesson_date: date
    generated_count: int = 0
    rejected_duplicates: int = 0
    retry_count: int = 0
    error_message: str | None = None
    lesson: Any = None
    items: list[dict[str, Any]] = field(default_factory=list)


class AIVocabularyGenerator:
    """
    STRICT GEMINI FREE TIER — ZERO COST POLICY Vocabulary & Quiz Generator.
    - Exclusively uses verified Google AI Studio Free Tier Gemini models.
    - Never calls paid models or paid providers (OpenAI, Anthropic, etc.).
    - Respects Free Tier RPM, TPM, and RPD limits via `gemini_quota_tracker`.
    - On 404: switches ONLY to another verified Free Tier model.
    - On 429: immediately stops retries and uses the PostgreSQL vocabulary reserve (100–300 items).
    - On retry: requests ONLY the missing vocabulary items by category.
    """

    def __init__(self) -> None:
        self.whitelist: list[str] = sanitize_free_tier_whitelist(
            list(getattr(settings, "GEMINI_FREE_TIER_MODELS", ()))
        )
        self.provider, self.model = enforce_free_tier_provider_and_model(
            settings.AI_PROVIDER,
            settings.AI_MODEL,
            self.whitelist,
        )
        self.api_key = settings.AI_API_KEY

    def _has_valid_api_key(self) -> bool:
        if not self.api_key:
            return False
        placeholder_tokens = {
            "YOUR_AI_API_KEY",
            "YOUR_GOOGLE_AI_STUDIO_FREE_TIER_KEY",
            "YOUR_API_KEY",
            "NONE",
            "NULL",
            "",
        }
        return self.api_key.upper() not in placeholder_tokens

    def _assert_zero_cost_free_tier_policy(self, model_name: str) -> str:
        """
        Requirements 1, 2, 3, 4, 6:
        Block any non-Gemini provider or any model not in the verified Free Tier whitelist.
        """
        if self.provider != "gemini":
            raise PaidApiForbiddenError(
                f"ZERO COST POLICY VIOLATION: Provider '{self.provider}' is forbidden. "
                "Only Google Gemini Free Tier is permitted."
            )
        norm = normalize_gemini_model_name(model_name)
        if not is_verified_free_tier_model(norm) or norm not in self.whitelist:
            raise PaidApiForbiddenError(
                f"ZERO COST POLICY VIOLATION: Model '{model_name}' is not a verified Free Tier Gemini model."
            )
        return norm

    async def verify_remote_free_models_if_needed(self) -> list[str]:
        """
        Requirement 3: Verify model availability and Free Tier eligibility against
        Google AI Studio `/v1beta/models` before selecting a model (cached for 6h).
        """
        if not self._has_valid_api_key() or httpx is None:
            return list(self.whitelist)
        if not gemini_quota_tracker.needs_remote_model_verification():
            return gemini_quota_tracker.select_eligible_free_models(
                self.model, self.whitelist
            )

        url = "https://generativelanguage.googleapis.com/v1beta/models"
        headers = {"x-goog-api-key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    payload = resp.json()
                    remote_free: set[str] = set()
                    for m_obj in payload.get("models", []):
                        raw_name = str(m_obj.get("name", ""))
                        methods = m_obj.get("supportedGenerationMethods", []) or []
                        norm = normalize_gemini_model_name(raw_name)
                        if (
                            "generateContent" in methods
                            and norm in self.whitelist
                            and is_verified_free_tier_model(norm)
                        ):
                            remote_free.add(norm)
                    if remote_free:
                        gemini_quota_tracker.set_remote_verified_models(remote_free)
                        logger.info(
                            "Verified %d available Gemini Free Tier models on Google AI Studio: %s",
                            len(remote_free),
                            sorted(remote_free),
                        )
        except Exception as exc:
            logger.debug("Remote ListModels check skipped (using local Free Tier whitelist): %s", exc)

        return gemini_quota_tracker.select_eligible_free_models(
            self.model, self.whitelist
        )

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
        excl_sample = excluded_expressions[-350:] if excluded_expressions else []
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
        """
        Call Google AI Studio Gemini Free Tier API exclusively.
        - Verifies Free Tier eligibility and RPM/TPM/RPD quota before requesting.
        - On 404: switches ONLY to another verified Free Tier model in `self.whitelist`.
        - On 429: records quota exhaustion and raises `FreeTierQuotaExhaustedError` immediately (no retries).
        """
        if self.provider != "gemini":
            raise PaidApiForbiddenError(
                f"Paid or non-Gemini provider '{self.provider}' is strictly prohibited."
            )
        if httpx is None:
            raise RuntimeError("httpx client is not available in this environment.")

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            needed_by_category, excluded_expressions
        )
        est_tokens = max(800, (len(system_prompt) + len(user_prompt)) // 4 + 1200)

        await self.verify_remote_free_models_if_needed()
        candidate_models = gemini_quota_tracker.select_eligible_free_models(
            preferred_model=self.model,
            whitelist=self.whitelist,
            estimated_tokens=est_tokens,
        )
        if not candidate_models:
            reason = (
                "No verified Gemini Free Tier model is currently available within RPM/TPM/RPD quota."
            )
            gemini_quota_tracker.mark_ai_temporarily_disabled(reason)
            raise NoVerifiedFreeModelAvailableError(reason)

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

        async with httpx.AsyncClient(timeout=45.0) as http_client:
            for model_name in candidate_models:
                verified_model = self._assert_zero_cost_free_tier_policy(model_name)
                can_run, quota_reason = gemini_quota_tracker.can_use_model(
                    verified_model, estimated_tokens=est_tokens
                )
                if not can_run:
                    logger.info(
                        "Skipping Free Tier model '%s' due to quota guard: %s",
                        verified_model,
                        quota_reason,
                    )
                    continue

                gemini_quota_tracker.record_request_start(
                    verified_model, estimated_tokens=est_tokens
                )
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{verified_model}:generateContent"
                )
                resp = await http_client.post(url, headers=headers, json=payload)

                # Requirement 9: On 404, switch ONLY to another verified Free Tier model
                if resp.status_code == 404:
                    gemini_quota_tracker.record_404_unavailable(
                        verified_model, f"HTTP 404 on {verified_model}"
                    )
                    logger.warning(
                        "Gemini Free Tier model '%s' returned 404. Switching to next verified Free Tier model.",
                        verified_model,
                    )
                    continue

                # Requirement 10: On 429 quota error, stop excessive retries immediately and use reserve
                if resp.status_code == 429:
                    gemini_quota_tracker.record_429_quota_error(
                        verified_model, resp.text[:160]
                    )
                    logger.warning(
                        "Gemini Free Tier model '%s' returned 429 (Quota Exhausted). "
                        "Stopping retries immediately and switching to PostgreSQL vocabulary reserve.",
                        verified_model,
                    )
                    raise FreeTierQuotaExhaustedError(
                        f"Gemini Free Tier 429 Quota Reached on '{verified_model}'."
                    )

                if resp.status_code >= 400:
                    err_txt = f"HTTP {resp.status_code} on {verified_model}: {resp.text[:160]}"
                    gemini_quota_tracker.record_other_error(verified_model, err_txt)
                    resp.raise_for_status()

                data = resp.json()
                usage_meta = data.get("usageMetadata", {}) or {}
                actual_tokens = int(
                    usage_meta.get("totalTokenCount") or est_tokens
                )
                gemini_quota_tracker.record_request_success(
                    verified_model, actual_tokens=actual_tokens
                )
                self.model = verified_model

                text_out = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "{}")
                )
                return self._extract_json_dict(text_out)

        reason = "All verified Gemini Free Tier models in whitelist returned 404 or are unavailable."
        gemini_quota_tracker.mark_ai_temporarily_disabled(reason)
        raise NoVerifiedFreeModelAvailableError(reason)

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
        if omitted on legacy items, and validate against JSON Schema.
        """
        adv = sanitize_untrusted_text(raw_item.get("advanced_word", ""), 120)
        simple = sanitize_untrusted_text(raw_item.get("simple_word", ""), 120)
        if not _ENGLISH_EXPRESSION_RE.match(adv):
            raise ValueError(f"Expression '{adv}' does not look like natural English.")
        if len(adv.split()) > 12:
            raise ValueError("Advanced expression is too long (max 12 words).")

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
                    f'In everyday English: "{simple}".', 350
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
            or f'Which advanced IELTS expression best upgrades "{simple}" ({ielts_usage})?',
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

        _validate_dict_schema(sanitized_dict, is_batch=False)
        if not norm_adv:
            raise ValueError("Normalized expression cannot be empty.")

        sanitized_dict["normalized_expression"] = norm_adv
        return sanitized_dict

    @staticmethod
    def _compute_target_quotas(required_count: int) -> dict[str, int]:
        if required_count == 10:
            return dict(DAILY_CATEGORY_QUOTAS)
        quotas = {
            "everyday_upgrade": max(1, round(required_count * 0.4)),
            "academic_upgrade": max(0, round(required_count * 0.2)),
            "collocation": max(0, round(required_count * 0.2)),
            "phrasal_verb": 0,
        }
        quotas["phrasal_verb"] = max(0, required_count - sum(quotas.values()))
        return quotas

    def load_all_validated_seed_reserve_items(self) -> list[dict[str, Any]]:
        if not RESERVE_FILE_PATH.exists():
            return []
        try:
            raw_list = json.loads(RESERVE_FILE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to read reserve vocabulary file: %s", exc)
            return []

        validated_list: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw_item in raw_list:
            try:
                v = self.validate_and_sanitize_item(
                    raw_item, for_daily_distribution=True
                )
                norm = v["normalized_expression"]
                if norm not in seen:
                    seen.add(norm)
                    validated_list.append(v)
            except Exception:
                continue
        return validated_list

    def _select_from_candidate_list_by_quotas(
        self,
        raw_candidates: list[dict[str, Any]],
        needed_by_category: dict[str, int],
        known_normalized: set[str],
        very_count_so_far: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        remaining = dict(needed_by_category)
        total_needed = sum(remaining.values())
        selected: list[dict[str, Any]] = []
        rejected_dups = 0
        very_count = very_count_so_far
        unmatched_valid: list[dict[str, Any]] = []

        for raw_item in raw_candidates:
            if len(selected) >= total_needed:
                break
            try:
                validated = self.validate_and_sanitize_item(
                    raw_item, for_daily_distribution=True
                )
            except Exception:
                continue

            if is_very_adjective_pattern(validated["simple_word"]) and very_count >= 1:
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

    def _load_unused_from_reserve_by_quotas(
        self,
        needed_by_category: dict[str, int],
        known_normalized: set[str],
        very_count_so_far: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if not RESERVE_FILE_PATH.exists():
            return [], 0
        try:
            raw_list = json.loads(RESERVE_FILE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to read reserve vocabulary file: %s", exc)
            return [], 0
        return self._select_from_candidate_list_by_quotas(
            raw_candidates=raw_list,
            needed_by_category=needed_by_category,
            known_normalized=known_normalized,
            very_count_so_far=very_count_so_far,
        )

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

    async def ensure_postgres_reserve_seeded(self, session: Any) -> int:
        """
        Requirement 11: Seed the 146 curated 4+2+2+2 reserve items into PostgreSQL
        `vocabulary_reserve` so at least 100+ unused reserve items are always ready in DB.
        """
        from database import crud

        seed_items = self.load_all_validated_seed_reserve_items()
        return await crud.ensure_vocabulary_reserve_seeded(session, seed_items)

    async def _load_unused_from_postgres_and_file_reserve(
        self,
        session: Any,
        needed_by_category: dict[str, int],
        known_normalized: set[str],
        very_count_so_far: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Pull unused items from PostgreSQL `vocabulary_reserve` first, then file reserve if needed.
        """
        from database import crud

        await self.ensure_postgres_reserve_seeded(session)
        pg_rows = await crud.fetch_unused_from_postgres_reserve(session)
        pg_dicts = [
            {
                "simple_word": r.simple_word,
                "advanced_word": r.advanced_word,
                "translation_uz": r.translation_uz,
                "translation_ru": r.translation_ru,
                "definition_en": r.definition_en,
                "basic_example_en": r.basic_example_en,
                "example_en": r.example_en,
                "example_uz": r.example_uz,
                "example_ru": r.example_ru,
                "cefr_level": r.cefr_level,
                "category": r.category,
                "ielts_usage": r.ielts_usage,
                "source_name": r.source_name,
                "source_url": r.source_url,
                "quiz_question_uz": r.quiz_question_uz,
                "quiz_question_ru": r.quiz_question_ru,
                "quiz_question_en": r.quiz_question_en,
                "options": r.get_options(),
                "correct_option": r.correct_option,
            }
            for r in pg_rows
        ]
        selected, rejected_dups = self._select_from_candidate_list_by_quotas(
            raw_candidates=pg_dicts,
            needed_by_category=needed_by_category,
            known_normalized=known_normalized,
            very_count_so_far=very_count_so_far,
        )
        gemini_quota_tracker.record_reserve_fallback()
        return selected, rejected_dups

    async def gradually_replenish_vocabulary_reserve(
        self,
        session: Any,
        batch_size: int = 10,
    ) -> dict[str, Any]:
        """
        Requirement 11: Maintain a reserve of 100–300 unique, unused vocabulary items,
        generated gradually within free quotas.
        Generates at most 1 batch (10 items) per invocation when Free Tier quota has headroom.
        Never retries on error and never incurs paid API usage.
        """
        from database import crud

        unused_count = await self.ensure_postgres_reserve_seeded(session)
        min_target = getattr(settings, "RESERVE_MIN_WORDS", 100)
        max_target = getattr(settings, "RESERVE_MAX_WORDS", 300)

        if unused_count >= max_target:
            return {
                "replenished": 0,
                "unused_count": unused_count,
                "status": "RESERVE_FULL",
            }

        if not self._has_valid_api_key():
            return {
                "replenished": 0,
                "unused_count": unused_count,
                "status": "NO_API_KEY_SEED_ACTIVE",
            }

        if not gemini_quota_tracker.has_comfortable_quota_for_gradual_reserve(
            self.whitelist
        ):
            return {
                "replenished": 0,
                "unused_count": unused_count,
                "status": "SKIPPED_TO_CONSERVE_FREE_QUOTA",
            }

        all_known = await crud.get_all_known_and_reserve_normalized_expressions(session)
        quotas = self._compute_target_quotas(batch_size)
        try:
            raw_payload = await self._call_ai_api(
                needed_by_category=quotas,
                excluded_expressions=sorted(all_known),
            )
            _validate_dict_schema(raw_payload, is_batch=True)
            valid_new: list[dict[str, Any]] = []
            for raw_item in raw_payload.get("items", []):
                try:
                    v = self.validate_and_sanitize_item(
                        raw_item, for_daily_distribution=True
                    )
                    is_dup, norm_expr = is_duplicate_or_near_duplicate(
                        v["advanced_word"], all_known
                    )
                    if not is_dup:
                        v["normalized_expression"] = norm_expr
                        all_known.add(norm_expr)
                        valid_new.append(v)
                except Exception:
                    continue

            added = await crud.save_items_to_postgres_reserve(session, valid_new)
            new_unused = await crud.get_unused_reserve_count(session)
            logger.info(
                "Gradual Free Tier reserve replenishment added %d items (unused reserve=%d, target=%d..%d)",
                added,
                new_unused,
                min_target,
                max_target,
            )
            return {
                "replenished": added,
                "unused_count": new_unused,
                "status": "REPLENISHED",
            }
        except Exception as exc:
            logger.info("Gradual reserve replenishment paused to respect Free Tier: %s", exc)
            return {
                "replenished": 0,
                "unused_count": unused_count,
                "status": f"PAUSED: {exc}",
            }

    async def generate_daily_lesson(
        self,
        session: Any,
        target_date: date | None = None,
        word_count: int | None = None,
        max_retries: int = 3,
        bot: Any = None,
    ) -> GenerationResult:
        """
        Generate and save a daily lesson of 10 unique Everyday -> Advanced IELTS upgrades
        with the exact 4 + 2 + 2 + 2 category distribution:
        - 4 everyday_upgrade
        - 2 academic_upgrade
        - 2 collocation
        - 2 phrasal_verb
        Enforces Strict Gemini Free Tier Zero-Cost Policy:
        - Missing-only retries (Requirement 12)
        - Immediate stop on 429 & fallback to PostgreSQL reserve (Requirement 10)
        - Temporary disable & admin notification if no verified free model is available (Requirement 16)
        """
        from database import crud
        try:
            from sqlalchemy.exc import IntegrityError
        except ImportError:
            class IntegrityError(Exception):  # type: ignore[no-redef]
                pass

        lesson_date = target_date or settings.today()
        required_count = word_count or settings.DAILY_WORD_COUNT

        # 1. Check idempotency (Requirement 14: prevent unnecessary API calls)
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

        # Ensure PostgreSQL vocabulary reserve (100-300 items) is seeded
        await self.ensure_postgres_reserve_seeded(session)

        # 2. Load ALL historical normalized expressions from PostgreSQL
        known_normalized = await crud.get_all_normalized_expressions(session)
        logger.info(
            "Starting Strict Free Tier 4+2+2+2 IELTS generation for %s. Historical DB count: %d",
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

        # 3. Try Gemini Free Tier API generation with missing-items-only retry
        if self._has_valid_api_key():
            for attempt in range(1, max_retries + 1):
                # Requirement 12: Generate ONLY the missing vocabulary items during retry attempts
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
                    _validate_dict_schema(raw_payload, is_batch=True)
                    raw_items = raw_payload.get("items", [])

                    for raw_item in raw_items:
                        if sum(remaining_quotas.values()) <= 0:
                            break
                        try:
                            validated = self.validate_and_sanitize_item(
                                raw_item, for_daily_distribution=True
                            )
                        except Exception as val_err:
                            gemini_quota_tracker.record_other_error(
                                self.model, str(val_err), is_validation=True
                            )
                            logger.warning(
                                "AI item failed schema/content validation: %s", val_err
                            )
                            continue

                        if is_very_adjective_pattern(validated["simple_word"]):
                            if very_pattern_count >= 1:
                                continue

                        cat = validated["category"]
                        if remaining_quotas.get(cat, 0) <= 0:
                            continue

                        is_dup, norm_expr = is_duplicate_or_near_duplicate(
                            validated["advanced_word"], known_normalized
                        )
                        if is_dup:
                            rejected_duplicates += 1
                            continue

                        validated["normalized_expression"] = norm_expr
                        known_normalized.add(norm_expr)
                        if is_very_adjective_pattern(validated["simple_word"]):
                            very_pattern_count += 1
                        remaining_quotas[cat] -= 1
                        accepted_items.append(validated)

                except FreeTierQuotaExhaustedError as quota_err:
                    # Requirement 10: Stop excessive retries immediately on 429 and use PostgreSQL reserve
                    last_error = str(quota_err)
                    logger.warning(
                        "Free Tier 429 quota reached on attempt %d. Stopping retries immediately and using PostgreSQL reserve.",
                        attempt,
                    )
                    break
                except (NoVerifiedFreeModelAvailableError, PaidApiForbiddenError) as model_err:
                    # Requirement 16: Disable AI generation temporarily and notify admin
                    last_error = str(model_err)
                    logger.error("No verified Free Tier model available: %s", last_error)
                    if bot is not None:
                        try:
                            from services.lesson_service import notify_admins

                            await notify_admins(
                                bot,
                                f"⚠️ <b>STRICT GEMINI FREE TIER ALERT</b>\n\n"
                                f"Hech bir tasdiqlangan Free Tier Gemini modeli hozircha mavjud emas:\n"
                                f"<code>{last_error}</code>\n\n"
                                f"✅ AI generatsiya vaqtincha to‘xtatildi ($0.00 xarajat) va kunlik dars PostgreSQL zaxira bazasidan (100–300 so‘z) olindi.",
                            )
                        except Exception:
                            pass
                    break
                except Exception as api_err:
                    last_error = f"Gemini Free Tier API error on attempt {attempt}: {api_err}"
                    logger.warning(last_error)
        else:
            last_error = "GEMINI_API_KEY / AI_API_KEY not configured; using PostgreSQL vocabulary reserve."
            logger.info(last_error)

        # 4. Fallback to PostgreSQL vocabulary reserve (100-300 unused items) respecting remaining 4+2+2+2 quotas
        if len(accepted_items) < required_count:
            reserve_items, reserve_dups = (
                await self._load_unused_from_postgres_and_file_reserve(
                    session=session,
                    needed_by_category=remaining_quotas,
                    known_normalized=known_normalized,
                    very_count_so_far=very_pattern_count,
                )
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
