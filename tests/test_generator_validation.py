from collections import Counter
import json
from services.ai_vocabulary_generator import (
    DAILY_CATEGORY_QUOTAS,
    RESERVE_FILE_PATH,
    ai_generator,
    is_very_adjective_pattern,
    sanitize_untrusted_text,
)


def test_reserve_vocabulary_schema_uniqueness_and_no_very_spam() -> None:
    assert RESERVE_FILE_PATH.exists()
    raw_items = json.loads(RESERVE_FILE_PATH.read_text(encoding="utf-8"))
    assert len(raw_items) == 40

    seen_normalized: set[str] = set()
    very_count = 0
    for item in raw_items:
        validated = ai_generator.validate_and_sanitize_item(
            item, for_daily_distribution=True
        )
        norm = validated["normalized_expression"]
        assert norm not in seen_normalized, f"Duplicate in reserve pool: {norm}"
        seen_normalized.add(norm)
        assert (
            validated["options"][validated["correct_option"]]
            == validated["advanced_word"]
        )
        assert validated["basic_example_en"]
        assert validated["ielts_usage"]
        if is_very_adjective_pattern(validated["simple_word"]):
            very_count += 1

    assert very_count == 0


def test_multi_day_4_2_2_2_distribution_and_non_repeating() -> None:
    known: set[str] = set()

    for day in range(1, 5):
        day_items, _ = ai_generator._load_unused_from_reserve(10, known)
        assert len(day_items) == 10
        counts = Counter(x["category"] for x in day_items)
        assert dict(counts) == DAILY_CATEGORY_QUOTAS, (
            f"Day {day} failed 4+2+2+2 distribution: {dict(counts)}"
        )


def test_sanitize_untrusted_ai_text() -> None:
    malicious = "<script>alert('xss')</script>Address an\x00 issue   <b>now</b>"
    cleaned = sanitize_untrusted_text(malicious)
    assert "<script>" not in cleaned
    assert "<b>" not in cleaned
    assert "\x00" not in cleaned
    assert cleaned == "alert('xss')Address an issue now"
