import json
from services.ai_vocabulary_generator import (
    RESERVE_FILE_PATH,
    ai_generator,
    sanitize_untrusted_text,
)


def test_reserve_vocabulary_schema_and_uniqueness() -> None:
    assert RESERVE_FILE_PATH.exists()
    raw_items = json.loads(RESERVE_FILE_PATH.read_text(encoding="utf-8"))
    assert len(raw_items) >= 30

    seen_normalized: set[str] = set()
    for item in raw_items:
        validated = ai_generator.validate_and_sanitize_item(item)
        norm = validated["normalized_expression"]
        assert norm not in seen_normalized, f"Duplicate in reserve pool: {norm}"
        seen_normalized.add(norm)
        assert validated["options"][validated["correct_option"]] == validated["advanced_word"]


def test_multi_day_non_repeating_selection() -> None:
    known: set[str] = set()

    # Day 1: 10 words
    day1_items, _ = ai_generator._load_unused_from_reserve(10, known)
    assert len(day1_items) == 10
    day1_norms = {x["normalized_expression"] for x in day1_items}
    assert len(day1_norms) == 10

    # Day 2: 10 completely different words
    day2_items, rejected_dups = ai_generator._load_unused_from_reserve(10, known)
    assert len(day2_items) == 10
    day2_norms = {x["normalized_expression"] for x in day2_items}
    assert len(day2_norms) == 10
    assert rejected_dups == 10  # The 10 words from Day 1 were rejected as duplicates!
    assert day1_norms.isdisjoint(day2_norms)

    # Day 3: 10 more completely different words
    day3_items, rejected_dups_day3 = ai_generator._load_unused_from_reserve(10, known)
    assert len(day3_items) == 10
    day3_norms = {x["normalized_expression"] for x in day3_items}
    assert len(day3_norms) == 10
    assert rejected_dups_day3 == 20
    assert day3_norms.isdisjoint(day1_norms | day2_norms)


def test_sanitize_untrusted_ai_text() -> None:
    malicious = "<script>alert('xss')</script>Throw in the\x00 towel   <b>now</b>"
    cleaned = sanitize_untrusted_text(malicious)
    assert "<script>" not in cleaned
    assert "<b>" not in cleaned
    assert "\x00" not in cleaned
    assert cleaned == "alert('xss')Throw in the towel now"
