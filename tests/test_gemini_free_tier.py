import asyncio
from datetime import date
from types import SimpleNamespace
from typing import Any

from config import settings
from services.ai_vocabulary_generator import (
    AIVocabularyGenerator,
    DAILY_CATEGORY_QUOTAS,
    ai_generator,
)
from services.gemini_free_tier_policy import (
    FreeTierQuotaExhaustedError,
    NoVerifiedFreeModelAvailableError,
    PaidApiForbiddenError,
    enforce_free_tier_provider_and_model,
    gemini_quota_tracker,
    is_verified_free_tier_model,
    sanitize_free_tier_whitelist,
)


def test_strict_free_tier_whitelist_and_deprecated_preview_removal() -> None:
    # 1. Official Free Tier Gemini models must pass
    for official_free in (
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ):
        assert is_verified_free_tier_model(official_free) is True
        assert is_verified_free_tier_model(f"models/{official_free}") is True

    # 2. Deprecated, preview, experimental, and paid models must be rejected
    for forbidden_model in (
        "gemini-2.5-flash-preview-05-20",
        "gemini-2.0-flash-exp",
        "gemini-1.0-pro",
        "gemini-pro",
        "gemini-ultra",
        "gpt-4o",
        "gpt-4o-mini",
        "claude-3-5-sonnet",
        "deepseek-chat",
        "o1-preview",
    ):
        assert is_verified_free_tier_model(forbidden_model) is False

    # 3. Configurable whitelist strips out preview and paid models
    cleaned_wl = sanitize_free_tier_whitelist(
        "gemini-2.5-flash-preview-05-20,gpt-4o-mini,gemini-2.5-flash,gemini-2.0-flash,claude-3"
    )
    assert cleaned_wl == ["gemini-2.5-flash", "gemini-2.0-flash"]

    # 4. Paid provider or paid model in config is forced to 'gemini' Free Tier
    prov, mod = enforce_free_tier_provider_and_model("openai", "gpt-4o-mini")
    assert prov == "gemini"
    assert mod == "gemini-2.5-flash"
    assert settings.AI_PROVIDER == "gemini"
    assert settings.GEMINI_FREE_TIER_ONLY is True
    assert settings.GEMINI_BILLING_DISABLED is True


def test_zero_paid_api_guardrail_blocks_tampering() -> None:
    gen = AIVocabularyGenerator()
    # Tampering provider to openai or anthropic must raise PaidApiForbiddenError
    gen.provider = "openai"
    try:
        gen._assert_zero_cost_free_tier_policy("gemini-2.5-flash")
        raise AssertionError("Expected PaidApiForbiddenError for non-gemini provider")
    except PaidApiForbiddenError:
        pass

    gen.provider = "gemini"
    try:
        gen._assert_zero_cost_free_tier_policy("gemini-2.5-flash-preview-05-20")
        raise AssertionError("Expected PaidApiForbiddenError for preview model")
    except PaidApiForbiddenError:
        pass


def test_rpm_tpm_rpd_quota_limits_and_404_429_switching() -> None:
    gemini_quota_tracker.reset_for_testing()
    wl = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]

    # Initially gemini-2.5-flash is selected
    eligible = gemini_quota_tracker.select_eligible_free_models(
        "gemini-2.5-flash", wl
    )
    assert eligible[0] == "gemini-2.5-flash"

    # Requirement 9: If 404 occurs on gemini-2.5-flash, switch ONLY to next verified Free Tier model
    gemini_quota_tracker.record_404_unavailable("gemini-2.5-flash", "Not Found")
    eligible_after_404 = gemini_quota_tracker.select_eligible_free_models(
        "gemini-2.5-flash", wl
    )
    assert "gemini-2.5-flash" not in eligible_after_404
    assert eligible_after_404[0] == "gemini-2.5-flash-lite"

    # Requirement 8: Respect RPM limit (15 RPM on gemini-2.5-flash-lite)
    for _ in range(15):
        gemini_quota_tracker.record_request_start("gemini-2.5-flash-lite", 500)
    ok_rpm, reason_rpm = gemini_quota_tracker.can_use_model("gemini-2.5-flash-lite", 500)
    assert ok_rpm is False and reason_rpm == "RPM_LIMIT_REACHED"

    # Switch moves to gemini-2.0-flash (still verified Free Tier!)
    eligible_after_rpm = gemini_quota_tracker.select_eligible_free_models(
        "gemini-2.5-flash", wl
    )
    assert eligible_after_rpm == ["gemini-2.0-flash"]

    # Verify Admin API Monitoring Dashboard snapshot (Requirement 15)
    snap = gemini_quota_tracker.get_dashboard_snapshot(
        whitelist=wl, reserve_unused_count=106
    )
    assert snap["paid_apis_blocked"] is True
    assert snap["total_requests_today"] == 15
    assert snap["errors"]["errors_404"] == 1
    assert snap["reserve"]["unused_count"] == 106
    assert snap["reserve"]["healthy"] is True
    gemini_quota_tracker.reset_for_testing()


def test_429_stops_retries_immediately_and_missing_only_retry() -> None:
    gemini_quota_tracker.reset_for_testing()
    seed_reserve = ai_generator.load_all_validated_seed_reserve_items()
    assert 100 <= len(seed_reserve) <= 300

    # --- Case A: 429 Quota Error on attempt 1 MUST stop retries immediately (1 call total) ---
    gen_429 = AIVocabularyGenerator()
    gen_429.api_key = "AIzaSy_FAKE_TEST_FREE_TIER_KEY"
    call_count_429 = 0

    async def _mock_call_429(
        needed_by_category: dict[str, int], excluded_expressions: list[str]
    ) -> dict[str, Any]:
        nonlocal call_count_429
        call_count_429 += 1
        gemini_quota_tracker.record_429_quota_error("gemini-2.5-flash", "Quota exceeded")
        raise FreeTierQuotaExhaustedError("429 RESOURCE_EXHAUSTED")

    gen_429._call_ai_api = _mock_call_429  # type: ignore[method-assign]

    async def _mock_reserve_loader(
        session: Any,
        needed_by_category: dict[str, int],
        known_normalized: set[str],
        very_count_so_far: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        return gen_429._load_unused_from_reserve_by_quotas(
            needed_by_category, known_normalized, very_count_so_far
        )

    gen_429._load_unused_from_postgres_and_file_reserve = _mock_reserve_loader  # type: ignore[method-assign]

    async def _noop_seed(session: Any) -> int:
        return len(seed_reserve)

    gen_429.ensure_postgres_reserve_seeded = _noop_seed  # type: ignore[method-assign]

    # Stub crud methods for offline async test
    import sys
    import types
    try:
        from database import crud
    except ImportError:
        db_pkg = types.ModuleType("database")
        crud = types.ModuleType("database.crud")  # type: ignore[assignment]
        db_pkg.crud = crud  # type: ignore[attr-defined]
        sys.modules["database"] = db_pkg
        sys.modules["database.crud"] = crud

    orig_get_lesson = getattr(crud, "get_daily_lesson_by_date", None)
    orig_get_norms = getattr(crud, "get_all_normalized_expressions", None)
    orig_save_lesson = getattr(crud, "save_generated_daily_lesson", None)
    orig_create_log = getattr(crud, "create_generation_log", None)

    async def _fake_get_lesson(session: Any, target_date: date) -> Any:
        return None

    async def _fake_get_norms(session: Any) -> set[str]:
        return set()

    async def _fake_save_lesson(
        session: Any, target_date: date, candidates: list[dict[str, Any]]
    ) -> Any:
        return SimpleNamespace(
            lesson_date=target_date,
            vocabulary_ids=list(range(1, len(candidates) + 1)),
        )

    async def _fake_create_log(**kwargs: Any) -> Any:
        return None

    crud.get_daily_lesson_by_date = _fake_get_lesson  # type: ignore[assignment]
    crud.get_all_normalized_expressions = _fake_get_norms  # type: ignore[assignment]
    crud.save_generated_daily_lesson = _fake_save_lesson  # type: ignore[assignment]
    crud.create_generation_log = _fake_create_log  # type: ignore[assignment]

    try:
        res_429 = asyncio.run(
            gen_429.generate_daily_lesson(session=None, target_date=date(2026, 11, 27))
        )
        # MUST NOT retry after 429: call_count_429 == 1, retry_count == 0, fulfilled from reserve!
        assert call_count_429 == 1
        assert res_429.retry_count == 0
        assert res_429.success is True
        assert res_429.status == "FALLBACK_RESERVE"
        assert res_429.generated_count == 10

        # --- Case B: Requirement 12 — Generate ONLY missing items during retry attempts ---
        gen_partial = AIVocabularyGenerator()
        gen_partial.api_key = "AIzaSy_FAKE_TEST_FREE_TIER_KEY"
        gen_partial.ensure_postgres_reserve_seeded = _noop_seed  # type: ignore[method-assign]
        gen_partial._load_unused_from_postgres_and_file_reserve = _mock_reserve_loader  # type: ignore[method-assign]

        requested_counts: list[int] = []

        # Pick 7 valid items (3 everyday, 2 academic, 2 collocation, 0 phrasal_verb -> 3 missing!)
        ev_items = [x for x in seed_reserve if x["category"] == "everyday_upgrade"]
        ac_items = [x for x in seed_reserve if x["category"] == "academic_upgrade"]
        co_items = [x for x in seed_reserve if x["category"] == "collocation"]
        pv_items = [x for x in seed_reserve if x["category"] == "phrasal_verb"]

        batch_1 = ev_items[:3] + ac_items[:2] + co_items[:2]
        batch_2 = [ev_items[3]] + pv_items[:2]

        async def _mock_call_partial(
            needed_by_category: dict[str, int], excluded_expressions: list[str]
        ) -> dict[str, Any]:
            requested_counts.append(sum(needed_by_category.values()))
            if len(requested_counts) == 1:
                return {"items": batch_1}
            return {"items": batch_2}

        gen_partial._call_ai_api = _mock_call_partial  # type: ignore[method-assign]

        res_partial = asyncio.run(
            gen_partial.generate_daily_lesson(
                session=None, target_date=date(2026, 11, 28)
            )
        )
        # Attempt 1 asked for 10 items; 7 succeeded, so Attempt 2 asked ONLY for the 3 missing items!
        assert requested_counts == [10, 3]
        assert res_partial.success is True
        assert res_partial.status == "SUCCESS"
        assert res_partial.generated_count == 10
    finally:
        crud.get_daily_lesson_by_date = orig_get_lesson  # type: ignore[assignment]
        crud.get_all_normalized_expressions = orig_get_norms  # type: ignore[assignment]
        crud.save_generated_daily_lesson = orig_save_lesson  # type: ignore[assignment]
        crud.create_generation_log = orig_create_log  # type: ignore[assignment]
        gemini_quota_tracker.reset_for_testing()
