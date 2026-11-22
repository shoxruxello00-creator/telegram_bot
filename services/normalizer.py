import re
import unicodedata
from difflib import SequenceMatcher

# Common placeholder tokens often appended/inserted in dictionary entries
_PLACEHOLDER_PATTERNS = [
    (re.compile(r"\b(somebody's|someone's|one's|sb's)\b"), "ones"),
    (re.compile(r"\b(somebody|someone|sb)\b"), "someone"),
    (re.compile(r"\b(something|sth)\b"), "something"),
    (re.compile(r"\b( oneself| yourself| himself| herself| themselves)\b"), " oneself"),
]

# Leading prefixes that should not distinguish two identical expressions
_LEADING_PREFIX_RE = re.compile(r"^(to|a|an|the)\s+")
# Trailing generic object placeholders
_TRAILING_PLACEHOLDER_RE = re.compile(r"\s+(someone|something|ones)$")


def normalize_expression(raw: str) -> str:
    """
    Produce a deterministic, canonical representation of an English word or expression
    for uniqueness checking and database UNIQUE constraint on `normalized_expression`.

    Steps:
    1. Unicode NFKC normalization & lowercase conversion
    2. Normalize curly apostrophes/quotes and dashes/hyphens
    3. Remove parenthetical notes e.g. "take (something) for granted" -> "take something for granted"
    4. Standardize pronoun placeholders (sb/somebody/someone, sth/something, one's)
    5. Strip non-alphanumeric punctuation
    6. Strip leading "to " / "a " / "an " / "the " if remaining phrase is non-empty
    7. Collapse whitespace
    """
    if not raw or not isinstance(raw, str):
        return ""

    text = unicodedata.normalize("NFKC", raw).strip().lower()

    # Standardize apostrophes
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")

    # Replace slashes and dashes with spaces
    text = re.sub(r"[-–—/]+", " ", text)

    # Remove possessives "'s" for canonical comparison or normalize placeholders first
    for pattern, repl in _PLACEHOLDER_PATTERNS:
        text = pattern.sub(repl, text)

    # Remove remaining punctuation except alphanumeric and spaces
    text = re.sub(r"[^a-z0-9\s]", "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Strip leading "to ", "a ", "an ", "the " when there are other words
    stripped_prefix = _LEADING_PREFIX_RE.sub("", text).strip()
    if stripped_prefix:
        text = stripped_prefix

    # Strip trailing generic placeholders ("get to grips with something" == "get to grips with")
    stripped_trailing = _TRAILING_PLACEHOLDER_RE.sub("", text).strip()
    if stripped_trailing:
        text = stripped_trailing

    return text


def _simple_stem_token(token: str) -> str:
    """Lightweight inflection normalizer for English tokens."""
    if len(token) > 4:
        if token.endswith("ies"):
            return token[:-3] + "y"
        if token.endswith("ing"):
            return token[:-3]
        if token.endswith("ed"):
            return token[:-2]
        if token.endswith("es") and not token.endswith(("ses", "xes", "zes")):
            return token[:-1]
        if token.endswith("s") and not token.endswith("ss"):
            return token[:-1]
    return token


def stem_signature(normalized_expr: str) -> str:
    """Return a stemmed, placeholder-free signature to detect minor inflectional variations."""
    stop_placeholders = {"someone", "something", "ones", "oneself", "be", "get", "have"}
    tokens = [
        _simple_stem_token(tok)
        for tok in normalized_expr.split()
        if tok not in stop_placeholders
    ]
    if not tokens:
        tokens = [_simple_stem_token(tok) for tok in normalized_expr.split()]
    return " ".join(tokens)


def is_duplicate_or_near_duplicate(
    candidate_raw: str,
    existing_normalized: set[str],
    similarity_threshold: float = 0.88,
) -> tuple[bool, str]:
    """
    Check if `candidate_raw` matches or is a near-duplicate of any expression
    in `existing_normalized`.

    Returns:
        (is_duplicate: bool, normalized_candidate: str)
    """
    norm_cand = normalize_expression(candidate_raw)
    if not norm_cand:
        return True, ""

    if norm_cand in existing_normalized:
        return True, norm_cand

    cand_sig = stem_signature(norm_cand)

    for existing in existing_normalized:
        if not existing:
            continue
        if cand_sig and cand_sig == stem_signature(existing):
            return True, norm_cand
        # Fast length filter before SequenceMatcher
        if abs(len(norm_cand) - len(existing)) <= 4:
            ratio = SequenceMatcher(None, norm_cand, existing).ratio()
            if ratio >= similarity_threshold:
                return True, norm_cand

    return False, norm_cand
