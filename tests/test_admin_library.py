import json
import zipfile
import io
from datetime import datetime, timezone

from config import settings
from services.admin_library_service import (
    LOCAL_ADMIN_STATE_PATH,
    SRS_INTERVALS_DAYS,
    _load_local_admin_store,
    _save_local_admin_store,
    admin_library_manager,
    compute_next_srs,
    filter_archive_items,
    generate_randomized_quiz_from_items,
    load_recoverable_seed_records,
)
from services.miniapp_api import (
    build_admin_library_payload,
    build_admin_quiz_payload,
    build_bootstrap_payload,
    handle_admin_export,
    handle_admin_flashcard_update,
    handle_admin_quiz_submit,
    handle_admin_session_start,
)


def _get_test_admin_ids() -> tuple[int, int, int]:
    super_admin_id = settings.ADMIN_ID if settings.ADMIN_ID else 8838117173
    moderator_id = 777000111
    unauthorized_user_id = 999888777
    state = _load_local_admin_store()
    state.setdefault("extra_admins", {})[str(moderator_id)] = "moderator"
    # Clean test progress for deterministic assertions
    state.setdefault("progress", {}).pop(str(super_admin_id), None)
    state.setdefault("progress", {}).pop(str(moderator_id), None)
    state.setdefault("sessions", {}).pop(str(super_admin_id), None)
    state.setdefault("sessions", {}).pop(str(moderator_id), None)
    state.setdefault("quiz_history", {}).pop(str(super_admin_id), None)
    _save_local_admin_store(state)
    return super_admin_id, moderator_id, unauthorized_user_id


def test_historical_recovery_and_idempotent_daily_sync() -> None:
    records = load_recoverable_seed_records()
    # 19 historical commit fa3ff96 items + 40 bonus pack items + 40 reserve 4+2+2+2 items = 99 unique
    assert len(records) == 99
    hist_items = [r for r in records if r["origin_type"] == "historical_commit_fa3ff96"]
    assert len(hist_items) == 19
    assert all(r["original_generation_date"] == "2026-11-22" for r in hist_items)

    # Idempotent sync: calling _load_local_admin_store multiple times never creates duplicates
    st1 = _load_local_admin_store()
    cnt1 = len(st1["archive"])
    st2 = _load_local_admin_store()
    cnt2 = len(st2["archive"])
    assert cnt1 == cnt2 >= 99
    norms = [x["normalized_expression"] for x in st2["archive"]]
    assert len(norms) == len(set(norms))


def test_backend_admin_only_authorization() -> None:
    admin_id, mod_id, regular_uid = _get_test_admin_ids()

    # Non-admin user MUST be blocked on the backend across every admin endpoint
    code_lib, _ = build_admin_library_payload(regular_uid, {})
    assert code_lib == 403

    code_sess, _ = handle_admin_session_start(regular_uid, {"mode": "all", "session_size": "10"})
    assert code_sess == 403

    code_fc, _ = handle_admin_flashcard_update(regular_uid, {"archive_id": 1, "action": "memorized"})
    assert code_fc == 403

    code_quiz, _ = build_admin_quiz_payload(regular_uid, {"mode": "all", "count": "10"})
    assert code_quiz == 403

    code_qsub, _ = handle_admin_quiz_submit(
        regular_uid,
        {"mode": "all", "submissions": [{"archive_id": 1, "selected_text": "test"}]},
    )
    assert code_qsub == 403

    code_exp, _, _, _ = handle_admin_export(regular_uid, {"format": "csv", "scope": "all"})
    assert code_exp == 403

    # Regular user bootstrap has is_admin == False; Admin has is_admin == True
    reg_boot = build_bootstrap_payload(regular_uid, "learner1", "Learner One")
    assert reg_boot["user"]["is_admin"] is False

    adm_boot = build_bootstrap_payload(admin_id, "shoxrux", "Shoxrux Admin")
    assert adm_boot["user"]["is_admin"] is True

    mod_code, mod_lib = build_admin_library_payload(mod_id, {})
    assert mod_code == 200
    assert mod_lib["admin_role"] == "moderator"


def test_spaced_repetition_intervals() -> None:
    assert SRS_INTERVALS_DAYS == [1, 3, 7, 14, 30]
    now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)

    stage = 0
    expected_days = [1, 3, 7, 14, 30]
    for exp_interval in expected_days:
        status, stage, interval, next_rev = compute_next_srs(stage, "memorized", now)
        assert status == "memorized"
        assert interval == exp_interval
        assert (next_rev - now).days == exp_interval

    # Difficult resets stage to 0 and schedules 1-day review
    d_status, d_stage, d_int, _ = compute_next_srs(4, "difficult", now)
    assert d_status == "difficult"
    assert d_stage == 0
    assert d_int == 1


def test_flashcards_individual_admin_progress_and_persistence() -> None:
    admin_1, admin_2, _ = _get_test_admin_ids()

    # Start a 20-word session for admin_1
    code, sess_resp = handle_admin_session_start(
        admin_1, {"mode": "unmemorized", "session_size": "20"}
    )
    assert code == 200
    assert len(sess_resp["items"]) == 20

    first_id = sess_resp["items"][0]["id"]
    second_id = sess_resp["items"][1]["id"]
    third_id = sess_resp["items"][2]["id"]

    # Mark 1st memorized (YODLADIM), 2nd difficult (QIYIN), 3rd later (KEYINROQ)
    r1_code, r1 = handle_admin_flashcard_update(
        admin_1, {"archive_id": first_id, "action": "memorized", "session_index": 0}
    )
    assert r1_code == 200 and r1["status"] == "memorized" and r1["interval_days"] == 1

    r2_code, r2 = handle_admin_flashcard_update(
        admin_1, {"archive_id": second_id, "action": "difficult", "session_index": 1}
    )
    assert r2_code == 200 and r2["status"] == "difficult"

    r3_code, r3 = handle_admin_flashcard_update(
        admin_1, {"archive_id": third_id, "action": "later", "session_index": 2}
    )
    assert r3_code == 200 and r3["status"] == "later"

    # Reload from disk (simulating restart) & verify resumable session at index 3
    _, lib_1 = build_admin_library_payload(admin_1, {"mode": "all"})
    assert lib_1["stats"]["memorized_count"] == 1
    assert lib_1["stats"]["difficult_count"] == 1
    assert lib_1["saved_session"] is not None
    assert lib_1["saved_session"]["current_index"] == 3

    # Verify admin_2 has completely independent progress (0 memorized, no saved session)
    _, lib_2 = build_admin_library_payload(admin_2, {"mode": "all"})
    assert lib_2["stats"]["memorized_count"] == 0
    assert lib_2["stats"]["difficult_count"] == 0
    assert lib_2["saved_session"] is None


def test_all_vocabulary_quiz_and_retry_incorrect() -> None:
    admin_id, _, _ = _get_test_admin_ids()

    # Request custom 15-question quiz
    q_code, q_payload = build_admin_quiz_payload(admin_id, {"mode": "all", "count": "15"})
    assert q_code == 200
    questions = q_payload["questions"]
    assert len(questions) == 15

    # Verify each question has 4 options and exactly 1 correct answer matching advanced_expression
    submissions = []
    for i, q in enumerate(questions):
        assert len(q["options"]) == 4
        assert q["options"][q["correct_option"]] == q["advanced_expression"]
        if i < 12:
            # Answer correctly
            chosen = q["advanced_expression"]
        else:
            # Answer wrongly on last 3 questions
            wrong_opt = next(o for o in q["options"] if o != q["advanced_expression"])
            chosen = wrong_opt
        submissions.append({"archive_id": q["archive_id"], "selected_text": chosen})

    sub_code, sub_res = handle_admin_quiz_submit(
        admin_id, {"mode": "all", "submissions": submissions}
    )
    assert sub_code == 200
    assert sub_res["question_count"] == 15
    assert sub_res["correct_count"] == 12
    assert sub_res["accuracy"] == 80
    assert len(sub_res["wrong_archive_ids"]) == 3

    # Retry ONLY the 3 incorrect answers
    retry_csv = ",".join(str(x) for x in sub_res["wrong_archive_ids"])
    ret_code, ret_payload = build_admin_quiz_payload(admin_id, {"retry_ids": retry_csv})
    assert ret_code == 200
    assert ret_payload["total"] == 3


def test_search_filters_and_csv_xlsx_pdf_exports() -> None:
    admin_id, _, _ = _get_test_admin_ids()

    # Search by category & date range
    _, filtered_cat = build_admin_library_payload(
        admin_id, {"category": "phrasal_verb"}
    )
    assert filtered_cat["total_filtered"] >= 8
    assert all(x["category"] == "phrasal_verb" for x in filtered_cat["items"])

    _, filtered_date = build_admin_library_payload(
        admin_id, {"date_from": "2026-11-22", "date_to": "2026-11-22"}
    )
    assert filtered_date["total_filtered"] == 19

    # Export CSV
    c_code, csv_bytes, c_type, c_name = handle_admin_export(
        admin_id, {"format": "csv", "scope": "all"}
    )
    assert c_code == 200 and isinstance(csv_bytes, bytes)
    assert c_name.endswith(".csv")
    csv_text = csv_bytes.decode("utf-8-sig")
    assert "Basic English" in csv_text
    assert len(csv_text.splitlines()) >= 100

    # Export XLSX (valid ZIP/OpenXML container)
    x_code, xlsx_bytes, _, x_name = handle_admin_export(
        admin_id, {"format": "xlsx", "scope": "filtered", "category": "phrasal_verb"}
    )
    assert x_code == 200 and isinstance(xlsx_bytes, bytes)
    assert x_name.endswith(".xlsx")
    assert xlsx_bytes[:4] == b"PK\x03\x04"
    with zipfile.ZipFile(io.BytesIO(xlsx_bytes), "r") as zf:
        assert "xl/workbook.xml" in zf.namelist()

    # Export PDF (valid PDF-1.4 document)
    p_code, pdf_bytes, _, p_name = handle_admin_export(
        admin_id, {"format": "pdf", "scope": "all"}
    )
    assert p_code == 200 and isinstance(pdf_bytes, bytes)
    assert p_name.endswith(".pdf")
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf_bytes
