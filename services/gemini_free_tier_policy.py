import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
QUOTA_STATE_PATH = ROOT_DIR / "data" / ".gemini_free_tier_quota.json"

# ==============================================================================
# OFFICIAL GOOGLE AI STUDIO GEMINI FREE TIER MODELS & QUOTA LIMITS
# Zero Cost Policy: Only models officially supporting Google AI Studio Free Tier.
# Deprecated and preview models (e.g. gemini-2.5-flash-preview-05-20, gemini-pro,
# gemini-1.0-pro, -exp) and paid-only providers (OpenAI, Anthropic, etc.) are blocked.
# ==============================================================================

OFFICIAL_GEMINI_FREE_TIER_SPECS: dict[str, dict[str, Any]] = {
    "gemini-2.5-flash": {
        "rpm": 10,
        "tpm": 250_000,
        "rpd": 250,
        "tier": "FREE_TIER",
        "description": "Gemini 2.5 Flash (Official Free Tier Primary)",
    },
    "gemini-2.5-flash-lite": {
        "rpm": 15,
        "tpm": 250_000,
        "rpd": 1000,
        "tier": "FREE_TIER",
        "description": "Gemini 2.5 Flash-Lite (Official Free Tier High-Quota)",
    },
    "gemini-2.0-flash": {
        "rpm": 15,
        "tpm": 1_000_000,
        "rpd": 1500,
        "tier": "FREE_TIER",
        "description": "Gemini 2.0 Flash (Official Free Tier Stable)",
    },
    "gemini-2.0-flash-lite": {
        "rpm": 30,
        "tpm": 1_000_000,
        "rpd": 1500,
        "tier": "FREE_TIER",
        "description": "Gemini 2.0 Flash-Lite (Official Free Tier Lightweight)",
    },
    "gemini-1.5-flash": {
        "rpm": 15,
        "tpm": 1_000_000,
        "rpd": 1500,
        "tier": "FREE_TIER",
        "description": "Gemini 1.5 Flash (Official Free Tier Fallback)",
    },
    "gemini-1.5-flash-8b": {
        "rpm": 15,
        "tpm": 1_000_000,
        "rpd": 1500,
        "tier": "FREE_TIER",
        "description": "Gemini 1.5 Flash-8B (Official Free Tier Fallback)",
    },
}

DEFAULT_FREE_TIER_WHITELIST: tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
)

FORBIDDEN_MODEL_SUBSTRINGS: tuple[str, ...] = (
    "preview",
    "-exp",
    "experimental",
    "gemini-1.0",
    "gemini-pro",
    "ultra",
    "gpt-",
    "o1-",
    "o3-",
    "claude",
    "deepseek",
    "openai",
    "anthropic",
    "llama",
    "mixtral",
    "imagen",
    "veo",
)

FORBIDDEN_PAID_PROVIDERS: set[str] = {
    "openai",
    "anthropic",
    "groq",
    "deepseek",
    "openrouter",
    "together",
    "cohere",
    "mistral",
    "azure",
    "bedrock",
    "vertex_paid",
}


class PaidApiForbiddenError(RuntimeError):
    """Raised if any code attempts to invoke a paid model or paid API provider."""


class FreeTierQuotaExhaustedError(RuntimeError):
    """Raised when HTTP 429 or local RPM/TPM/RPD Free Tier quota is reached."""


class NoVerifiedFreeModelAvailableError(RuntimeError):
    """Raised when no verified Free Tier model is available (all 404 or disabled)."""


def normalize_gemini_model_name(raw_model: str) -> str:
    cleaned = (raw_model or "").strip().lower()
    if cleaned.startswith("models/"):
        cleaned = cleaned.split("models/", 1)[1].strip()
    return cleaned


def is_verified_free_tier_model(model_name: str) -> bool:
    """
    Strictly verify that `model_name`:
    1. Does NOT contain any deprecated, preview, experimental, or paid model substring.
    2. Is an official Google AI Studio Free Tier model in `OFFICIAL_GEMINI_FREE_TIER_SPECS`.
    """
    norm = normalize_gemini_model_name(model_name)
    if not norm:
        return False
    for forbidden in FORBIDDEN_MODEL_SUBSTRINGS:
        if forbidden in norm:
            return False
    return norm in OFFICIAL_GEMINI_FREE_TIER_SPECS


def sanitize_free_tier_whitelist(raw_csv_or_list: str | list[str] | None) -> list[str]:
    """
    Parse a configurable model whitelist from environment/config and keep ONLY
    verified Free Tier models. Never allows deprecated preview or paid models.
    """
    if isinstance(raw_csv_or_list, str):
        candidates = [x.strip() for x in raw_csv_or_list.split(",") if x.strip()]
    elif isinstance(raw_csv_or_list, (list, tuple)):
        candidates = [str(x).strip() for x in raw_csv_or_list if str(x).strip()]
    else:
        candidates = list(DEFAULT_FREE_TIER_WHITELIST)

    verified: list[str] = []
    for cand in candidates:
        norm = normalize_gemini_model_name(cand)
        if is_verified_free_tier_model(norm) and norm not in verified:
            verified.append(norm)

    if not verified:
        verified = list(DEFAULT_FREE_TIER_WHITELIST)
    return verified


def enforce_free_tier_provider_and_model(
    raw_provider: str,
    raw_model: str,
    whitelist: list[str] | None = None,
) -> tuple[str, str]:
    """
    Ensure provider is ALWAYS 'gemini' and model is ALWAYS a verified Free Tier model.
    Never switches to paid providers or unverified models.
    """
    allowed_list = whitelist or list(DEFAULT_FREE_TIER_WHITELIST)
    prov = (raw_provider or "gemini").strip().lower()
    if prov != "gemini":
        logger.warning(
            "STRICT FREE TIER POLICY: Blocked non-Gemini provider '%s'. Enforcing 'gemini' Free Tier.",
            prov,
        )
        prov = "gemini"

    norm_model = normalize_gemini_model_name(raw_model)
    if norm_model in allowed_list and is_verified_free_tier_model(norm_model):
        return prov, norm_model

    fallback_free = allowed_list[0] if allowed_list else "gemini-2.5-flash"
    if norm_model:
        logger.warning(
            "STRICT FREE TIER POLICY: Model '%s' is deprecated, preview, or not in Free Tier whitelist. "
            "Selecting verified Free Tier model '%s'.",
            raw_model,
            fallback_free,
        )
    return prov, fallback_free


@dataclass
class ModelWindowEvent:
    timestamp: float
    tokens: int


class GeminiFreeTierQuotaTracker:
    """
    Tracks RPM (Requests Per Minute), TPM (Tokens Per Minute), RPD (Requests Per Day),
    404 model unavailability, 429 quota cooldowns, and remote `/v1beta/models` verification.
    """

    def __init__(self) -> None:
        self._window_events: dict[str, list[ModelWindowEvent]] = {}
        self._unavailable_404_models: set[str] = set()
        self._cooldown_429_until: dict[str, float] = {}
        self._remote_verified_models: set[str] | None = None
        self._remote_verified_at: float = 0.0
        self._ai_temporarily_disabled: bool = False
        self._ai_disabled_reason: str | None = None
        self._active_model: str = DEFAULT_FREE_TIER_WHITELIST[0]
        self._state = self._load_daily_state()

    def _today_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_daily_state(self) -> dict[str, Any]:
        today = self._today_key()
        default_state: dict[str, Any] = {
            "date": today,
            "total_requests": 0,
            "successful_requests": 0,
            "total_tokens": 0,
            "errors_404": 0,
            "errors_429": 0,
            "errors_validation": 0,
            "errors_other": 0,
            "reserve_fallbacks": 0,
            "last_error": None,
            "last_error_at": None,
            "models": {},
        }
        if QUOTA_STATE_PATH.exists():
            try:
                loaded = json.loads(QUOTA_STATE_PATH.read_text(encoding="utf-8"))
                if loaded.get("date") == today:
                    return loaded
                # Day rolled over -> reset daily RPD counters and 429 cooldowns
                self._cooldown_429_until.clear()
                self._ai_temporarily_disabled = False
                self._ai_disabled_reason = None
            except Exception:
                pass
        return default_state

    def _ensure_today(self) -> None:
        today = self._today_key()
        if self._state.get("date") != today:
            self._state = {
                "date": today,
                "total_requests": 0,
                "successful_requests": 0,
                "total_tokens": 0,
                "errors_404": 0,
                "errors_429": 0,
                "errors_validation": 0,
                "errors_other": 0,
                "reserve_fallbacks": 0,
                "last_error": None,
                "last_error_at": None,
                "models": {},
            }
            self._cooldown_429_until.clear()
            self._ai_temporarily_disabled = False
            self._ai_disabled_reason = None
            self._save_daily_state()

    def _save_daily_state(self) -> None:
        try:
            QUOTA_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            QUOTA_STATE_PATH.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("Could not persist quota state: %s", exc)

    def _get_model_daily_dict(self, model_name: str) -> dict[str, Any]:
        self._ensure_today()
        models_map = self._state.setdefault("models", {})
        return models_map.setdefault(
            model_name,
            {
                "requests_today": 0,
                "successful_today": 0,
                "tokens_today": 0,
                "errors_404": 0,
                "errors_429": 0,
                "errors_other": 0,
            },
        )

    def _prune_minute_window(self, model_name: str, now: float | None = None) -> list[ModelWindowEvent]:
        ts = now if now is not None else time.time()
        cutoff = ts - 60.0
        events = [
            e for e in self._window_events.get(model_name, []) if e.timestamp > cutoff
        ]
        self._window_events[model_name] = events
        return events

    def get_model_window_usage(self, model_name: str, now: float | None = None) -> tuple[int, int]:
        """Return (rpm_used, tpm_used) in the trailing 60-second sliding window."""
        events = self._prune_minute_window(model_name, now)
        rpm_used = len(events)
        tpm_used = sum(e.tokens for e in events)
        return rpm_used, tpm_used

    def can_use_model(
        self,
        model_name: str,
        estimated_tokens: int = 2500,
        now: float | None = None,
    ) -> tuple[bool, str]:
        """
        Check whether `model_name`:
        1. Is a verified Free Tier model
        2. Has not returned 404
        3. Is not in 429 quota cooldown
        4. Is within Free Tier RPM, TPM, and RPD limits
        """
        norm = normalize_gemini_model_name(model_name)
        if not is_verified_free_tier_model(norm):
            return False, "NOT_IN_FREE_TIER_WHITELIST"

        if norm in self._unavailable_404_models:
            return False, "MODEL_404_UNAVAILABLE"

        if (
            self._remote_verified_models is not None
            and len(self._remote_verified_models) > 0
            and norm not in self._remote_verified_models
        ):
            return False, "NOT_AVAILABLE_IN_REMOTE_LIST"

        ts = now if now is not None else time.time()
        cooldown_until = self._cooldown_429_until.get(norm, 0.0)
        if cooldown_until > ts:
            return False, "COOLDOWN_429_QUOTA"

        specs = OFFICIAL_GEMINI_FREE_TIER_SPECS[norm]
        m_daily = self._get_model_daily_dict(norm)
        if int(m_daily["requests_today"]) >= int(specs["rpd"]):
            return False, "RPD_LIMIT_REACHED"

        rpm_used, tpm_used = self.get_model_window_usage(norm, ts)
        if rpm_used >= int(specs["rpm"]):
            return False, "RPM_LIMIT_REACHED"
        if tpm_used + estimated_tokens > int(specs["tpm"]):
            return False, "TPM_LIMIT_REACHED"

        return True, "OK"

    def select_eligible_free_models(
        self,
        preferred_model: str,
        whitelist: list[str],
        estimated_tokens: int = 2500,
    ) -> list[str]:
        """
        Return ordered list of verified Free Tier models currently eligible to serve a request.
        Preferred model comes first if verified and within quota.
        """
        ordered: list[str] = []
        pref = normalize_gemini_model_name(preferred_model)
        if pref and is_verified_free_tier_model(pref) and pref in whitelist:
            ordered.append(pref)
        for m in whitelist:
            norm = normalize_gemini_model_name(m)
            if is_verified_free_tier_model(norm) and norm not in ordered:
                ordered.append(norm)

        eligible: list[str] = []
        for m in ordered:
            ok, _ = self.can_use_model(m, estimated_tokens=estimated_tokens)
            if ok:
                eligible.append(m)

        if eligible:
            self._active_model = eligible[0]
            self._ai_temporarily_disabled = False
            self._ai_disabled_reason = None
        return eligible

    def record_request_start(self, model_name: str, estimated_tokens: int = 1200) -> None:
        norm = normalize_gemini_model_name(model_name)
        self._ensure_today()
        self._active_model = norm
        self._state["total_requests"] = int(self._state.get("total_requests", 0)) + 1
        m_daily = self._get_model_daily_dict(norm)
        m_daily["requests_today"] = int(m_daily.get("requests_today", 0)) + 1
        self._window_events.setdefault(norm, []).append(
            ModelWindowEvent(timestamp=time.time(), tokens=estimated_tokens)
        )
        self._save_daily_state()

    def record_request_success(self, model_name: str, actual_tokens: int = 2000) -> None:
        norm = normalize_gemini_model_name(model_name)
        self._ensure_today()
        self._active_model = norm
        self._state["successful_requests"] = (
            int(self._state.get("successful_requests", 0)) + 1
        )
        self._state["total_tokens"] = (
            int(self._state.get("total_tokens", 0)) + actual_tokens
        )
        m_daily = self._get_model_daily_dict(norm)
        m_daily["successful_today"] = int(m_daily.get("successful_today", 0)) + 1
        m_daily["tokens_today"] = int(m_daily.get("tokens_today", 0)) + actual_tokens
        # Update the latest sliding window event with actual tokens
        events = self._window_events.get(norm, [])
        if events:
            events[-1].tokens = actual_tokens
        self._save_daily_state()

    def record_404_unavailable(self, model_name: str, err_msg: str = "") -> None:
        norm = normalize_gemini_model_name(model_name)
        self._ensure_today()
        self._unavailable_404_models.add(norm)
        self._state["errors_404"] = int(self._state.get("errors_404", 0)) + 1
        self._state["last_error"] = f"404 Model Not Found ({norm}): {err_msg}"[:240]
        self._state["last_error_at"] = datetime.now(timezone.utc).isoformat()
        m_daily = self._get_model_daily_dict(norm)
        m_daily["errors_404"] = int(m_daily.get("errors_404", 0)) + 1
        self._save_daily_state()

    def record_429_quota_error(
        self,
        model_name: str,
        err_msg: str = "",
        cooldown_seconds: float = 900.0,
    ) -> None:
        """
        Requirement 10: When a 429 quota error occurs, mark cooldown immediately
        so excessive retries stop and the bot uses the PostgreSQL vocabulary reserve.
        """
        norm = normalize_gemini_model_name(model_name)
        self._ensure_today()
        self._cooldown_429_until[norm] = time.time() + cooldown_seconds
        self._state["errors_429"] = int(self._state.get("errors_429", 0)) + 1
        self._state["last_error"] = f"429 Free Tier Quota Reached ({norm}): {err_msg}"[:240]
        self._state["last_error_at"] = datetime.now(timezone.utc).isoformat()
        m_daily = self._get_model_daily_dict(norm)
        m_daily["errors_429"] = int(m_daily.get("errors_429", 0)) + 1
        self._save_daily_state()

    def record_other_error(self, model_name: str, err_msg: str, is_validation: bool = False) -> None:
        norm = normalize_gemini_model_name(model_name)
        self._ensure_today()
        if is_validation:
            self._state["errors_validation"] = (
                int(self._state.get("errors_validation", 0)) + 1
            )
        else:
            self._state["errors_other"] = int(self._state.get("errors_other", 0)) + 1
            m_daily = self._get_model_daily_dict(norm)
            m_daily["errors_other"] = int(m_daily.get("errors_other", 0)) + 1
        self._state["last_error"] = str(err_msg)[:240]
        self._state["last_error_at"] = datetime.now(timezone.utc).isoformat()
        self._save_daily_state()

    def record_reserve_fallback(self) -> None:
        self._ensure_today()
        self._state["reserve_fallbacks"] = (
            int(self._state.get("reserve_fallbacks", 0)) + 1
        )
        self._save_daily_state()

    def mark_ai_temporarily_disabled(self, reason: str) -> None:
        self._ai_temporarily_disabled = True
        self._ai_disabled_reason = reason
        self._state["last_error"] = reason[:240]
        self._state["last_error_at"] = datetime.now(timezone.utc).isoformat()
        self._save_daily_state()

    def set_remote_verified_models(self, available_free_models: set[str]) -> None:
        self._remote_verified_models = set(available_free_models)
        self._remote_verified_at = time.time()

    def needs_remote_model_verification(self) -> bool:
        # Verify once every 6 hours so we never waste Free Tier requests
        return (
            self._remote_verified_models is None
            or (time.time() - self._remote_verified_at) > 21600
        )

    def has_comfortable_quota_for_gradual_reserve(self, whitelist: list[str]) -> bool:
        """
        Requirement 11: Maintain a reserve of 100-300 items generated gradually
        within free quotas. Only replenish when no 429 occurred recently and
        at least 60% of daily RPD remains on an eligible Free Tier model.
        """
        if self._ai_temporarily_disabled:
            return False
        self._ensure_today()
        if int(self._state.get("errors_429", 0)) > 0:
            # Do not run background reserve refill on a day when 429 occurred
            return False

        for m in whitelist:
            norm = normalize_gemini_model_name(m)
            ok, _ = self.can_use_model(norm, estimated_tokens=3500)
            if not ok:
                continue
            specs = OFFICIAL_GEMINI_FREE_TIER_SPECS[norm]
            used_rpd = int(self._get_model_daily_dict(norm).get("requests_today", 0))
            if used_rpd < int(specs["rpd"]) * 0.4:
                return True
        return False

    def get_dashboard_snapshot(
        self,
        whitelist: list[str],
        reserve_unused_count: int = 0,
        reserve_target_min: int = 100,
        reserve_target_max: int = 300,
    ) -> dict[str, Any]:
        """
        Requirement 15: Build comprehensive Admin API Monitoring Dashboard payload
        showing active model, request count, errors, estimated remaining quota, and reserve status.
        """
        self._ensure_today()
        now = time.time()
        models_report: list[dict[str, Any]] = []
        total_rpd_limit = 0
        total_rpd_remaining = 0

        for m in whitelist:
            norm = normalize_gemini_model_name(m)
            if not is_verified_free_tier_model(norm):
                continue
            specs = OFFICIAL_GEMINI_FREE_TIER_SPECS[norm]
            m_daily = self._get_model_daily_dict(norm)
            rpm_used, tpm_used = self.get_model_window_usage(norm, now)
            rpd_used = int(m_daily.get("requests_today", 0))
            rpd_limit = int(specs["rpd"])
            rpd_rem = max(0, rpd_limit - rpd_used)

            total_rpd_limit += rpd_limit
            if norm not in self._unavailable_404_models:
                total_rpd_remaining += rpd_rem

            if norm in self._unavailable_404_models:
                status = "UNAVAILABLE_404"
            elif self._cooldown_429_until.get(norm, 0.0) > now:
                status = "COOLDOWN_429"
            elif rpd_rem == 0:
                status = "RPD_EXHAUSTED"
            else:
                status = "AVAILABLE"

            models_report.append(
                {
                    "model": norm,
                    "tier": "FREE_TIER",
                    "status": status,
                    "rpd_used": rpd_used,
                    "rpd_limit": rpd_limit,
                    "rpd_remaining": rpd_rem,
                    "rpm_used": rpm_used,
                    "rpm_limit": int(specs["rpm"]),
                    "rpm_remaining": max(0, int(specs["rpm"]) - rpm_used),
                    "tpm_used": tpm_used,
                    "tpm_limit": int(specs["tpm"]),
                    "tpm_remaining": max(0, int(specs["tpm"]) - tpm_used),
                    "errors_404": int(m_daily.get("errors_404", 0)),
                    "errors_429": int(m_daily.get("errors_429", 0)),
                    "errors_other": int(m_daily.get("errors_other", 0)),
                }
            )

        active_spec = OFFICIAL_GEMINI_FREE_TIER_SPECS.get(
            self._active_model,
            OFFICIAL_GEMINI_FREE_TIER_SPECS["gemini-2.5-flash"],
        )
        active_daily = self._get_model_daily_dict(self._active_model)
        act_rpm_used, act_tpm_used = self.get_model_window_usage(self._active_model, now)
        act_rpd_used = int(active_daily.get("requests_today", 0))
        act_rpd_limit = int(active_spec["rpd"])

        return {
            "date": self._state.get("date"),
            "billing_policy": "STRICT_FREE_TIER_ZERO_COST ($0.00 / Billing Disabled)",
            "paid_apis_blocked": True,
            "active_model": self._active_model,
            "ai_temporarily_disabled": self._ai_temporarily_disabled,
            "ai_disabled_reason": self._ai_disabled_reason,
            "total_requests_today": int(self._state.get("total_requests", 0)),
            "successful_requests_today": int(self._state.get("successful_requests", 0)),
            "total_tokens_today": int(self._state.get("total_tokens", 0)),
            "active_model_quota": {
                "rpd_used": act_rpd_used,
                "rpd_limit": act_rpd_limit,
                "rpd_remaining": max(0, act_rpd_limit - act_rpd_used),
                "rpm_used": act_rpm_used,
                "rpm_limit": int(active_spec["rpm"]),
                "rpm_remaining": max(0, int(active_spec["rpm"]) - act_rpm_used),
                "tpm_used": act_tpm_used,
                "tpm_limit": int(active_spec["tpm"]),
                "tpm_remaining": max(0, int(active_spec["tpm"]) - act_tpm_used),
            },
            "combined_free_rpd_remaining": total_rpd_remaining,
            "combined_free_rpd_limit": total_rpd_limit,
            "errors": {
                "errors_404": int(self._state.get("errors_404", 0)),
                "errors_429": int(self._state.get("errors_429", 0)),
                "errors_validation": int(self._state.get("errors_validation", 0)),
                "errors_other": int(self._state.get("errors_other", 0)),
                "last_error": self._state.get("last_error"),
                "last_error_at": self._state.get("last_error_at"),
            },
            "reserve": {
                "unused_count": reserve_unused_count,
                "target_min": reserve_target_min,
                "target_max": reserve_target_max,
                "fallbacks_today": int(self._state.get("reserve_fallbacks", 0)),
                "healthy": reserve_unused_count >= reserve_target_min,
            },
            "models": models_report,
        }

    def reset_for_testing(self) -> None:
        self._window_events.clear()
        self._unavailable_404_models.clear()
        self._cooldown_429_until.clear()
        self._remote_verified_models = None
        self._remote_verified_at = 0.0
        self._ai_temporarily_disabled = False
        self._ai_disabled_reason = None
        self._active_model = DEFAULT_FREE_TIER_WHITELIST[0]
        if QUOTA_STATE_PATH.exists():
            try:
                QUOTA_STATE_PATH.unlink()
            except Exception:
                pass
        self._state = self._load_daily_state()


gemini_quota_tracker = GeminiFreeTierQuotaTracker()
