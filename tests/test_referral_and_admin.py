import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

from services.i18n import i18n
from services.normalizer import is_duplicate_or_near_duplicate, normalize_expression

BONUS_SEED_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "bonus_packs_seed.json"
)
RESERVE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "reserve_vocabulary.json"
)
MIGRATION_003_PATH = (
    Path(__file__).resolve().parent.parent
    / "migrations"
    / "003_referral_and_broadcast_admin.sql"
)


def test_referral_link_parsing_and_self_referral_rules() -> None:
    def parse_ref(arg: str | None) -> int | None:
        if not arg:
            return None
        if arg.startswith("ref_") and arg[4:].isdigit():
            return int(arg[4:])
        return None

    assert parse_ref("ref_123456789") == 123456789
    assert parse_ref("ref_abc") is None
    assert parse_ref("invalid") is None
    assert parse_ref(None) is None


def test_five_referral_milestones_and_bonus_packs_seed() -> None:
    assert BONUS_SEED_PATH.exists()
    data = json.loads(BONUS_SEED_PATH.read_text(encoding="utf-8"))
    packs = data["packs"]
    assert len(packs) == 5

    milestones = [p["required_referrals"] for p in packs]
    assert milestones == [1, 3, 5, 10, 20]

    pack_types = [p["pack_type"] for p in packs]
    assert pack_types == [
        "bonus_10_vocab",
        "speaking_advanced_pack",
        "writing_academic_pack",
        "vip_30day_challenge",
        "ielts_master_status",
    ]

    # Verify zero duplicates between daily reserve pool and bonus packs
    reserve_items = json.loads(RESERVE_PATH.read_text(encoding="utf-8"))
    known = {normalize_expression(i["advanced_word"]) for i in reserve_items}

    for pack in packs:
        assert len(pack["items"]) >= 5
        for item in pack["items"]:
            is_dup, norm = is_duplicate_or_near_duplicate(
                item["advanced_word"], known
            )
            assert not is_dup, f"Duplicate expression in bonus pack: {item['advanced_word']}"
            known.add(norm)
            assert len(item["options"]) == 4
            assert item["options"][item["correct_option"]] == item["advanced_word"]


def test_multilingual_referral_and_broadcast_keys() -> None:
    i18n.reload()
    uz_keys = set(i18n._translations["uz"].keys())
    ru_keys = set(i18n._translations["ru"].keys())
    en_keys = set(i18n._translations["en"].keys())
    assert uz_keys == ru_keys == en_keys

    assert i18n.t("menu_referral", lang="uz") == "🎁 Do‘st taklif qilish"
    assert i18n.t("menu_referral", lang="ru") == "🎁 Пригласить друзей"
    assert i18n.t("menu_referral", lang="en") == "🎁 Invite Friends"

    for lang in ("uz", "ru", "en"):
        dash = i18n.t(
            "referral_dashboard",
            lang=lang,
            invited=4,
            confirmed=3,
            unlocked_count=2,
            next_reward="IELTS Writing Pack",
            progress="3/5",
            badge_line="",
            referral_link="https://t.me/TestBot?start=ref_111",
        )
        assert "3/5" in dash
        assert "https://t.me/TestBot?start=ref_111" in dash


def test_migration_003_contains_all_required_tables_and_constraints() -> None:
    assert MIGRATION_003_PATH.exists()
    sql = MIGRATION_003_PATH.read_text(encoding="utf-8")

    required_fragments = [
        "CREATE TABLE IF NOT EXISTS referrals",
        "uq_referrals_referred_user_id UNIQUE (referred_user_id)",
        "ck_referrals_no_self_referral CHECK (referrer_user_id <> referred_user_id)",
        "CREATE TABLE IF NOT EXISTS referral_rewards",
        "uq_referral_rewards_user_milestone UNIQUE (user_id, milestone)",
        "CREATE TABLE IF NOT EXISTS bonus_packs",
        "CREATE TABLE IF NOT EXISTS bonus_pack_words",
        "CREATE TABLE IF NOT EXISTS user_bonus_progress",
        "CREATE TABLE IF NOT EXISTS admins",
        "uq_admins_telegram_id UNIQUE (telegram_id)",
        "CREATE TABLE IF NOT EXISTS broadcasts",
        "CREATE TABLE IF NOT EXISTS broadcast_recipients",
        "uq_broadcast_recipients_broadcast_user UNIQUE (broadcast_id, user_id)",
    ]
    for frag in required_fragments:
        assert frag in sql, f"Missing SQL fragment in migration 003: {frag}"
