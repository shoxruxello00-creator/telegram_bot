from services.normalizer import is_duplicate_or_near_duplicate, normalize_expression


def test_normalize_case_and_whitespace() -> None:
    assert normalize_expression("  Throw   In The   Towel  ") == "throw in the towel"
    assert normalize_expression("THROW IN THE TOWEL!") == "throw in the towel"


def test_normalize_punctuation_and_hyphens() -> None:
    assert normalize_expression("get-to-grips with...") == "get to grips with"
    assert normalize_expression("To get to grips with something") == "get to grips with"


def test_normalize_pronoun_placeholders() -> None:
    expr1 = normalize_expression("shirk one's responsibilities")
    expr2 = normalize_expression("Shirk someone’s responsibilities!")
    expr3 = normalize_expression("to shirk somebody's responsibilities")
    assert expr1 == expr2 == expr3


def test_near_duplicate_detection() -> None:
    existing = {
        normalize_expression("Throw in the towel"),
        normalize_expression("Get to grips with"),
        normalize_expression("Come to fruition"),
    }

    # Exact match with different casing
    is_dup, _ = is_duplicate_or_near_duplicate("throw in the towel", existing)
    assert is_dup is True

    # Inflectional / plural / minor variation
    is_dup_plural, _ = is_duplicate_or_near_duplicate("Throwing in the towels", existing)
    assert is_dup_plural is True

    # With trailing placeholder "something"
    is_dup_placeholder, _ = is_duplicate_or_near_duplicate(
        "Get to grips with something", existing
    )
    assert is_dup_placeholder is True

    # Completely different expression is NOT a duplicate
    is_dup_new, norm_new = is_duplicate_or_near_duplicate("Go the extra mile", existing)
    assert is_dup_new is False
    assert norm_new == "go the extra mile"
