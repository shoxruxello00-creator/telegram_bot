from datetime import datetime, timedelta, timezone

from config import settings
from services.i18n import i18n
from services.miniapp_api import (
    build_admin_mock_tests_payload,
    build_mock_test_materials_payload,
    build_mock_tests_catalog_payload,
    handle_admin_mock_test_access,
    handle_admin_mock_test_save,
)
from services.mock_test_service import (
    ADMIN_SUPPORT_URL,
    ADMIN_SUPPORT_USERNAME,
    LOCAL_MOCK_STATE_PATH,
    _load_local_mock_store,
    mock_test_manager,
)


def _reset_mock_store() -> tuple[int, int]:
    if LOCAL_MOCK_STATE_PATH.exists():
        LOCAL_MOCK_STATE_PATH.unlink()
    _load_local_mock_store()
    admin_id = settings.ADMIN_ID if settings.ADMIN_ID else 8838117173
    learner_id = 100200300
    return admin_id, learner_id


def test_public_catalog_uzs_pricing_and_support_contact() -> None:
    _, learner_id = _reset_mock_store()
    cat = build_mock_tests_catalog_payload(learner_id)
    assert cat["ok"] is True
    assert cat["support_username"] == "@n0omg" == ADMIN_SUPPORT_USERNAME
    assert cat["support_url"] == "https://t.me/n0omg" == ADMIN_SUPPORT_URL
    assert len(cat["tests"]) >= 5
    assert len(cat["my_tests"]) == 0

    # Verify required Uzbek support and grant notification strings
    assert (
        i18n.t("mock_support_message", lang="uz")
        == "Mock Test haqida batafsil ma’lumot olish uchun admin bilan bog‘laning: @n0omg"
    )
    assert (
        i18n.t("mock_grant_notification", lang="uz")
        == "🎉 Tabriklaymiz! Sizga yangi IELTS Mock Test taqdim etildi. Testni MOCK TEST → MENING TESTLARIM bo‘limidan ochishingiz mumkin."
    )

    # Verify public catalog never leaks protected file IDs or text content
    for t in cat["tests"]:
        assert "files" not in t
        assert "text_content" not in t
        assert "telegram_file_id" not in t
        assert t["price_uzs"] > 0
        assert "UZS" in t["price_formatted"]
        assert t["is_unlocked"] is False


def test_create_edit_price_upload_pdf_audio_and_publish_visibility() -> None:
    admin_id, learner_id = _reset_mock_store()

    # 1. Non-admin is strictly blocked from creating or editing mock tests (403)
    code_unauth, _ = handle_admin_mock_test_save(
        learner_id, {"action": "create", "title": "Unauthorized Test"}
    )
    assert code_unauth == 403

    # 2. Admin creates a new Mock Test with PDF, Audio, Answer Sheet, and Answer Key
    code_cr, cr_res = handle_admin_mock_test_save(
        admin_id,
        {
            "action": "create",
            "title": "IELTS Academic Reading & Listening Combo #9",
            "category": "Full Mock Test",
            "description": "Full exam with PDF booklet, audio track, and answer key.",
            "price_uzs": 50000,
            "duration_minutes": 120,
            "questions_count": 80,
            "is_published": True,
            "materials": [
                {
                    "file_type": "pdf",
                    "material_role": "question_paper",
                    "title": "Reading Booklet.pdf",
                    "telegram_file_id": "BQACAgIAAxkBAAIB_PDF_FILE_ID",
                    "file_name": "reading_booklet.pdf",
                },
                {
                    "file_type": "audio",
                    "material_role": "audio_track",
                    "title": "Listening Master Track.mp3",
                    "telegram_file_id": "CQACAgIAAxkBAAIB_AUDIO_FILE_ID",
                    "file_name": "listening_track.mp3",
                },
                {
                    "file_type": "text",
                    "material_role": "answer_key",
                    "title": "Official Answer Key 1-80",
                    "text_content": "1. TRUE | 2. FALSE | 3. C | 4. migration",
                },
            ],
        },
    )
    assert code_cr == 200 and cr_res["ok"] is True
    new_tid = int(cr_res["test"]["id"])
    assert cr_res["test"]["price_uzs"] == 50000
    assert cr_res["test"]["price_formatted"] == "50 000 UZS"
    assert len(cr_res["test"]["files"]) == 3

    # 3. Upload an additional Answer Sheet PDF to the test
    code_mat, mat_res = handle_admin_mock_test_save(
        admin_id,
        {
            "action": "add_material",
            "test_id": new_tid,
            "material": {
                "file_type": "pdf",
                "material_role": "answer_sheet",
                "title": "Official Answer Sheet.pdf",
                "telegram_file_id": "BQACAgIAAxkBAAIB_SHEET_ID",
            },
        },
    )
    assert code_mat == 200 and len(mat_res["test"]["files"]) == 4

    # 4. Edit price in UZS (50000 -> 65000)
    code_pr, pr_res = handle_admin_mock_test_save(
        admin_id,
        {
            "action": "update",
            "test_id": new_tid,
            "price_uzs": 65000,
        },
    )
    assert code_pr == 200
    assert pr_res["test"]["price_uzs"] == 65000
    assert pr_res["test"]["price_formatted"] == "65 000 UZS"

    # 5. Unpublish test -> hidden from public catalog
    handle_admin_mock_test_save(
        admin_id,
        {"action": "update", "test_id": new_tid, "is_published": False},
    )
    pub_cat = build_mock_tests_catalog_payload(learner_id)
    assert not any(int(t["id"]) == new_tid for t in pub_cat["tests"])

    # Re-publish -> visible in public catalog
    handle_admin_mock_test_save(
        admin_id,
        {"action": "update", "test_id": new_tid, "is_published": True},
    )
    pub_cat2 = build_mock_tests_catalog_payload(learner_id)
    assert any(int(t["id"]) == new_tid for t in pub_cat2["tests"])


def test_user_search_grant_duplicate_prevention_revoke_and_expiration() -> None:
    admin_id, learner_id = _reset_mock_store()
    test_id = 1

    # 1. Unauthorized learner cannot access protected materials of locked test #1 (403)
    code_locked, _ = build_mock_test_materials_payload(
        learner_id, {"test_id": str(test_id)}
    )
    assert code_locked == 403

    # 2. Search registered users by name, username, and Telegram ID
    u_by_name, tot1, _ = mock_test_manager.search_registered_users_local("Azizbek")
    assert tot1 == 1 and u_by_name[0]["user_id"] == learner_id

    u_by_uname, tot2, _ = mock_test_manager.search_registered_users_local("@malika_band8")
    assert tot2 == 1 and u_by_uname[0]["user_id"] == 200300400

    u_by_id, tot3, _ = mock_test_manager.search_registered_users_local(str(learner_id))
    assert tot3 == 1 and u_by_id[0]["user_id"] == learner_id

    # 3. Grant permanent complimentary access to learner_id
    g_code, g_res = handle_admin_mock_test_access(
        admin_id,
        {
            "action": "grant",
            "test_id": test_id,
            "target_user_id": learner_id,
            "duration_code": "permanent",
            "reason": "Complimentary gift",
        },
    )
    assert g_code == 200 and g_res["ok"] is True

    # 4. Prevent duplicate active permanent grant
    dup_code, dup_res = handle_admin_mock_test_access(
        admin_id,
        {
            "action": "grant",
            "test_id": test_id,
            "target_user_id": learner_id,
            "duration_code": "permanent",
        },
    )
    assert dup_code == 200 and dup_res["ok"] is False
    assert dup_res["reason"] == "ALREADY_HAS_ACTIVE_ACCESS"

    # 5. Now learner_id sees test #1 in My Mock Tests and can open protected materials & answer keys!
    cat_unlocked = build_mock_tests_catalog_payload(learner_id)
    assert len(cat_unlocked["my_tests"]) == 1
    assert cat_unlocked["my_tests"][0]["id"] == test_id

    mat_code, mat_payload = build_mock_test_materials_payload(
        learner_id, {"test_id": str(test_id)}
    )
    assert mat_code == 200 and mat_payload["ok"] is True
    assert len(mat_payload["test"]["files"]) >= 3
    assert any(
        f["material_role"] == "answer_key" for f in mat_payload["test"]["files"]
    )

    # 6. Revoke access -> learner_id is immediately blocked again (403)
    rev_code, rev_res = handle_admin_mock_test_access(
        admin_id,
        {
            "action": "revoke",
            "test_id": test_id,
            "target_user_id": learner_id,
        },
    )
    assert rev_code == 200 and rev_res["ok"] is True

    code_after_rev, _ = build_mock_test_materials_payload(
        learner_id, {"test_id": str(test_id)}
    )
    assert code_after_rev == 403

    # 7. Grant time-limited 24-hour access and verify automatic expiration after 25 hours
    now_t0 = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    mock_test_manager.grant_access_local(
        admin_id=admin_id,
        target_user_id=learner_id,
        test_id=2,
        duration_code="24h",
        now=now_t0,
    )
    # Valid at +12 hours
    ok_12h, _, _ = mock_test_manager.get_protected_materials_local(
        learner_id, 2, now=now_t0 + timedelta(hours=12)
    )
    assert ok_12h is True

    # Expired at +25 hours
    ok_25h, reason_25h, _ = mock_test_manager.get_protected_materials_local(
        learner_id, 2, now=now_t0 + timedelta(hours=25)
    )
    assert ok_25h is False and reason_25h == "ACCESS_DENIED"

    # 8. Verify Admin audit log entries were recorded
    st = _load_local_mock_store()
    log_actions = [entry["action"] for entry in st.get("logs", [])]
    assert "GRANT_ACCESS" in log_actions
    assert "REVOKE_ACCESS" in log_actions

    if LOCAL_MOCK_STATE_PATH.exists():
        LOCAL_MOCK_STATE_PATH.unlink()
