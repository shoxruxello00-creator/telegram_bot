import hashlib
import hmac
import json
from urllib.parse import urlencode

from services.miniapp_api import (
    build_bootstrap_payload,
    build_game_session_payload,
    build_leaderboard_payload,
    build_referrals_payload,
    handle_flashcard_action,
    handle_quiz_submit,
    handle_settings_update,
    verify_telegram_init_data,
)


def test_telegram_init_data_hmac_verification() -> None:
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    user_json = json.dumps({"id": 777888, "first_name": "Shoxrux", "username": "shoxrux"})
    params = {"auth_date": "1730000000", "query_id": "AAHdF6IQAAAAAN0XohDhrOrc", "user": user_json}

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    valid_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    init_data = urlencode({**params, "hash": valid_hash})
    verified_user = verify_telegram_init_data(init_data, bot_token)
    assert verified_user is not None
    assert verified_user["id"] == 777888

    # Tampered hash must be rejected
    tampered_data = urlencode({**params, "hash": "00" * 32})
    assert verify_telegram_init_data(tampered_data, bot_token) is None


def test_bootstrap_and_journey_and_game_modes() -> None:
    uid = 999111222
    boot = build_bootstrap_payload(uid, "test_learner", "Test Learner")
    assert boot["user"]["user_id"] == uid
    assert len(boot["daily_lesson"]["words"]) == 10
    assert len(boot["journey"]) == 6
    assert [w["cefr"] for w in boot["journey"]] == ["A1", "A2", "B1", "B2", "C1", "C2"]
    assert len(boot["heatmap_28"]) == 28
    assert len(boot["category_mastery"]) == 4

    # Flashcard action
    first_word_id = boot["daily_lesson"]["words"][0]["id"]
    fc_res = handle_flashcard_action(
        uid, {"vocabulary_id": first_word_id, "action": "memorized"}
    )
    assert fc_res["ok"] is True

    # Quiz submission validation
    quiz_answers = [
        {
            "vocab_id": w["id"],
            "selected_option": w["correct_option"],
            "time_ms": 1200,
        }
        for w in boot["daily_lesson"]["words"]
    ]
    q_res = handle_quiz_submit(uid, {"mode": "daily", "answers": quiz_answers})
    assert q_res["ok"] is True
    assert q_res["score"] == 10
    assert q_res["accuracy"] == 100
    assert q_res["earned_xp"] >= 100

    # All 8 game modes
    for mode in (
        "word_battle",
        "brain_rush",
        "word_match",
        "missing_word",
        "synonym_master",
        "ielts_arena",
        "memory_challenge",
        "daily_challenge",
    ):
        gs = build_game_session_payload(mode)
        assert gs["mode"] == mode
        assert len(gs["items"]) >= 5
        assert gs["items"][0]["sentence_with_blank"]

    # Leaderboard & Referrals & Settings
    lb = build_leaderboard_payload(uid)
    assert len(lb["all_time"]["entries"]) >= 5
    refs = build_referrals_payload(uid)
    assert len(refs["milestones"]) == 5

    s_res = handle_settings_update(uid, {"language_code": "en", "daily_goal": 15})
    assert s_res["language_code"] == "en"
    assert s_res["daily_goal"] == 15
