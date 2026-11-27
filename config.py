import os
import re
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone, tzinfo
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

SUPPORTED_LANGUAGES = ("uz", "ru", "en")


def _clean_env(key: str, default: str = "") -> str:
    val = os.getenv(key, default).strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        val = val[1:-1].strip()
    return val


def normalize_database_url(raw_url: str) -> str:
    """
    Normalize any PostgreSQL URL (from Render, Railway, Heroku, Neon, Supabase, etc.)
    to SQLAlchemy's asyncpg format: `postgresql+asyncpg://...`
    Also converts `sslmode=...` query parameters to `ssl=...` for asyncpg compatibility.
    """
    url = raw_url.strip()
    if len(url) >= 2 and url[0] == url[-1] and url[0] in ("'", '"'):
        url = url[1:-1].strip()

    if not url:
        return "postgresql+asyncpg://postgres:password@localhost:5432/english_c2_bot"

    # Replace scheme prefix with postgresql+asyncpg://
    url = re.sub(
        r"^(?:postgres(?:ql)?(?:\+[a-z0-9_]+)?)://",
        "postgresql+asyncpg://",
        url,
        flags=re.IGNORECASE,
    )

    # Convert ?sslmode=... to ?ssl=... and drop libpq-only params unsupported by asyncpg
    unsupported_asyncpg_params = {
        "channel_binding",
        "gssencmode",
        "target_session_attrs",
        "sslnegotiation",
        "application_name",
    }
    try:
        parts = urlsplit(url)
        if parts.query:
            query_pairs = parse_qsl(parts.query, keep_blank_values=True)
            normalized_pairs: list[tuple[str, str]] = []
            for k, v in query_pairs:
                k_low = k.lower()
                if k_low == "sslmode":
                    normalized_pairs.append(("ssl", v))
                elif k_low in unsupported_asyncpg_params:
                    continue
                else:
                    normalized_pairs.append((k, v))
            new_query = urlencode(normalized_pairs)
            url = urlunsplit(
                (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
            )
    except Exception:
        pass

    return url


def _parse_admin_ids(raw_admin_id: str) -> set[int]:
    ids: set[int] = set()
    for part in raw_admin_id.split(","):
        part = part.strip().strip("'\"")
        if part.isdigit():
            ids.add(int(part))
    return ids


def _parse_first_admin_id(raw_admin_id: str) -> int:
    for part in raw_admin_id.split(","):
        part = part.strip().strip("'\"")
        if part.isdigit():
            return int(part)
    return 0


@dataclass(frozen=True)
class Config:
    BOT_TOKEN: str = field(default_factory=lambda: _clean_env("BOT_TOKEN", ""))
    ADMIN_ID: int = field(
        default_factory=lambda: _parse_first_admin_id(_clean_env("ADMIN_ID", "0"))
    )
    ADMIN_IDS: set[int] = field(
        default_factory=lambda: _parse_admin_ids(_clean_env("ADMIN_ID", "0"))
    )

    DATABASE_URL: str = field(
        default_factory=lambda: normalize_database_url(
            _clean_env(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:password@localhost:5432/english_c2_bot",
            )
        )
    )

    AI_PROVIDER: str = field(
        default_factory=lambda: "gemini"
    )
    AI_API_KEY: str = field(
        default_factory=lambda: _clean_env("GEMINI_API_KEY", "")
        or _clean_env("AI_API_KEY", "")
    )
    GEMINI_FREE_TIER_MODELS: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            __import__(
                "services.gemini_free_tier_policy",
                fromlist=["sanitize_free_tier_whitelist"],
            ).sanitize_free_tier_whitelist(
                _clean_env(
                    "GEMINI_FREE_TIER_MODELS",
                    "gemini-2.5-flash,gemini-2.5-flash-lite,gemini-2.0-flash,gemini-2.0-flash-lite,gemini-1.5-flash",
                )
            )
        )
    )
    AI_MODEL: str = field(
        default_factory=lambda: __import__(
            "services.gemini_free_tier_policy",
            fromlist=["enforce_free_tier_provider_and_model"],
        ).enforce_free_tier_provider_and_model(
            _clean_env("AI_PROVIDER", "gemini"),
            _clean_env("AI_MODEL", "gemini-2.5-flash"),
        )[1]
    )
    AI_BASE_URL: str = field(default_factory=lambda: "")
    GEMINI_FREE_TIER_ONLY: bool = True
    GEMINI_BILLING_DISABLED: bool = True
    RESERVE_MIN_WORDS: int = field(
        default_factory=lambda: max(100, int(_clean_env("RESERVE_MIN_WORDS", "100") or "100"))
    )
    RESERVE_MAX_WORDS: int = field(
        default_factory=lambda: min(300, max(100, int(_clean_env("RESERVE_MAX_WORDS", "300") or "300")))
    )

    TIMEZONE: str = field(
        default_factory=lambda: _clean_env("TIMEZONE", "Asia/Tashkent")
    )

    DAILY_GENERATION_HOUR: int = field(
        default_factory=lambda: int(_clean_env("DAILY_GENERATION_HOUR", "0") or "0")
    )
    DAILY_GENERATION_MINUTE: int = field(
        default_factory=lambda: int(_clean_env("DAILY_GENERATION_MINUTE", "5") or "5")
    )

    DAILY_SEND_HOUR: int = field(
        default_factory=lambda: int(_clean_env("DAILY_SEND_HOUR", "8") or "8")
    )
    DAILY_SEND_MINUTE: int = field(
        default_factory=lambda: int(_clean_env("DAILY_SEND_MINUTE", "0") or "0")
    )

    REMINDER_HOUR: int = field(
        default_factory=lambda: int(_clean_env("REMINDER_HOUR", "20") or "20")
    )
    REMINDER_MINUTE: int = field(
        default_factory=lambda: int(_clean_env("REMINDER_MINUTE", "0") or "0")
    )

    DAILY_WORD_COUNT: int = field(
        default_factory=lambda: int(_clean_env("DAILY_WORD_COUNT", "10") or "10")
    )
    QUIZ_TIME_LIMIT: int = field(
        default_factory=lambda: int(_clean_env("QUIZ_TIME_LIMIT", "20") or "20")
    )
    POINTS_PER_CORRECT_ANSWER: int = field(
        default_factory=lambda: int(_clean_env("POINTS_PER_CORRECT_ANSWER", "10") or "10")
    )

    DEFAULT_LANGUAGE: str = field(
        default_factory=lambda: (
            _clean_env("DEFAULT_LANGUAGE", "uz").lower()
            if _clean_env("DEFAULT_LANGUAGE", "uz").lower() in SUPPORTED_LANGUAGES
            else "uz"
        )
    )
    LOG_LEVEL: str = field(
        default_factory=lambda: _clean_env("LOG_LEVEL", "INFO").upper()
    )

    @property
    def tz(self) -> tzinfo:
        try:
            return ZoneInfo(self.TIMEZONE)
        except ZoneInfoNotFoundError:
            return timezone(timedelta(hours=5), name="Asia/Tashkent")

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def today(self) -> date:
        return self.now().date()

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.ADMIN_IDS or (self.ADMIN_ID != 0 and user_id == self.ADMIN_ID)


settings = Config()
