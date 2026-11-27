import json
import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
LOCAL_MOCK_STATE_PATH = ROOT_DIR / "data" / ".local_mock_tests.json"

ADMIN_SUPPORT_USERNAME = "@n0omg"
ADMIN_SUPPORT_URL = "https://t.me/n0omg"

MOCK_TEST_CATEGORIES: tuple[str, ...] = (
    "Reading",
    "Listening",
    "Writing",
    "Speaking",
    "Full Mock Test",
)

# ==============================================================================
# CURATED SEED MOCK TESTS (ORIGINAL LICENSED EDUCATIONAL CONTENT)
# ==============================================================================

DEFAULT_MOCK_TESTS_SEED: list[dict[str, Any]] = [
    {
        "title": "IELTS Academic Reading — Full Mock Exam #1",
        "category": "Reading",
        "description": (
            "3 ta akademik matn (Urban Biodiversity, Cognitive Neuroplasticity, "
            "Renewable Grid Economics), 40 ta savol (True/False/Not Given, Matching Headings, "
            "Summary Completion), javoblar varaqasi va batafsil Band 9.0 Answer Key tahlili."
        ),
        "price_uzs": 35000,
        "duration_minutes": 60,
        "questions_count": 40,
        "instructions": (
            "⏱ Vaqt: 60 daqiqa (qo‘shimcha ko‘chirish vaqti berilmaydi).\n"
            "📄 Barcha 3 ta Passage savollarini ketma-ket ishlang va yakunda Answer Key bilan tekshiring."
        ),
        "is_published": True,
        "is_active": True,
        "materials": [
            {
                "file_type": "text",
                "material_role": "reading_passage",
                "title": "Passage 1–3: Academic Reading Booklet & 40 Questions",
                "text_content": (
                    "📘 PASSAGE 1: THE ARCHITECTURE OF URBAN BIODIVERSITY\n"
                    "Modern metropolitan planning has undergone a profound transformation over the past two decades. "
                    "Rather than treating concrete infrastructure and natural ecosystems as mutually exclusive domains, "
                    "contemporary architects increasingly integrate vertical forests, permeable pavements, and pollinator corridors...\n\n"
                    "Questions 1–5 (TRUE / FALSE / NOT GIVEN):\n"
                    "1. Early twentieth-century planners prioritized pollinator corridors in industrial zones.\n"
                    "2. Permeable pavements help mitigate urban flash-flooding during seasonal storms.\n"
                    "3. Vertical forests are more cost-effective in arid climates than in temperate zones.\n"
                    "4. Municipal tax incentives have accelerated green-roof adoption in European capitals.\n"
                    "5. Biodiversity metrics directly correlate with residents' self-reported mental well-being."
                ),
            },
            {
                "file_type": "text",
                "material_role": "answer_sheet",
                "title": "IELTS Reading Official Answer Sheet Template (1–40)",
                "text_content": (
                    "📝 IELTS ACADEMIC READING ANSWER SHEET\n"
                    "Write your answers in CAPITAL LETTERS (TRUE / FALSE / NOT GIVEN or A–G):\n"
                    "1. [      ]   2. [      ]   3. [      ]   4. [      ]   5. [      ]"
                ),
            },
            {
                "file_type": "text",
                "material_role": "answer_key",
                "title": "Answer Key & Examiner Explanations (Band Score Conversion)",
                "text_content": (
                    "🔑 OFFICIAL ANSWER KEY & BAND CONVERSION\n"
                    "1. FALSE (Paragraph 1 notes concrete and nature were treated as separate)\n"
                    "2. TRUE (Explicitly linked to storm runoff mitigation)\n"
                    "3. NOT GIVEN (No climate cost comparison is mentioned)\n"
                    "4. TRUE\n"
                    "5. TRUE\n"
                    "📊 Band Score Conversion: 39–40 = Band 9.0 | 37–38 = Band 8.5 | 35–36 = Band 8.0 | 30–32 = Band 7.0"
                ),
            },
        ],
    },
    {
        "title": "IELTS Listening Master — 4-Section Audio Mock #1",
        "category": "Listening",
        "description": (
            "4 bo‘limdan iborat to‘liq IELTS Listening sinovi (Part 1: Dialog, Part 2: Monolog, "
            "Part 3: Academic Discussion, Part 4: University Lecture), transkript va javoblar kaliti."
        ),
        "price_uzs": 35000,
        "duration_minutes": 40,
        "questions_count": 40,
        "instructions": (
            "🎧 Audioni faqat BIR marta eshiting.\n"
            "⏱ 30 daqiqa audio + 10 daqiqa javoblarni Answer Sheet'ga ko‘chirish uchun."
        ),
        "is_published": True,
        "is_active": True,
        "materials": [
            {
                "file_type": "text",
                "material_role": "question_paper",
                "title": "Listening Sections 1–4 Question Booklet (40 Questions)",
                "text_content": (
                    "🎧 SECTION 4: UNIVERSITY LECTURE ON MARINE BIOACOUSTICS (Questions 31–35)\n"
                    "Complete the notes below. Write ONE WORD ONLY for each answer.\n"
                    "• Low-frequency shipping noise interferes with whale __________ (31).\n"
                    "• Acoustic sensors were deployed along the continental __________ (32).\n"
                    "• Vessel speed reductions reduced underwater decibel levels by nearly __________ (33) percent.\n"
                    "• Harbor porpoises rely on high-frequency __________ (34) to locate prey.\n"
                    "• International maritime guidelines remain largely __________ (35) rather than mandatory."
                ),
            },
            {
                "file_type": "text",
                "material_role": "answer_key",
                "title": "Listening Transcript & Band 9.0 Answer Key",
                "text_content": (
                    "🔑 LISTENING ANSWER KEY (Section 4):\n"
                    "31. migration\n"
                    "32. shelf\n"
                    "33. forty / 40\n"
                    "34. clicks\n"
                    "35. voluntary\n"
                    "⚠️ Spelling must be 100% accurate for Listening credit."
                ),
            },
        ],
    },
    {
        "title": "IELTS Academic Writing Task 1 & Task 2 — Band 8.5+ Mock",
        "category": "Writing",
        "description": (
            "Haqiqiy imtihon darajasidagi Task 1 (Dynamic Line Graph & Table) va Task 2 "
            "(Opinion & Discussion Essay), baholash mezonlari (TR, CC, LR, GRA) va Band 9.0 namuna insholar."
        ),
        "price_uzs": 45000,
        "duration_minutes": 60,
        "questions_count": 2,
        "instructions": (
            "✍️ Task 1 uchun 20 daqiqa (kamida 150 so‘z), Task 2 uchun 40 daqiqa (kamida 250 so‘z) ajrating."
        ),
        "is_published": True,
        "is_active": True,
        "materials": [
            {
                "file_type": "text",
                "material_role": "question_paper",
                "title": "Writing Task 1 & Task 2 Official Prompts",
                "text_content": (
                    "✍️ WRITING TASK 1 (20 Minutes, 150+ words):\n"
                    "The table below compares the percentage of national energy generated from renewable sources "
                    "in four countries between 2005 and 2025. Summarize the information by selecting and reporting "
                    "the main features, and make comparisons where relevant.\n\n"
                    "✍️ WRITING TASK 2 (40 Minutes, 250+ words):\n"
                    "Some people argue that governments should allocate funding primarily to public transportation, "
                    "while others believe building wider roads is a more viable solution to urban congestion.\n"
                    "Discuss both these views and give your own opinion."
                ),
            },
            {
                "file_type": "text",
                "material_role": "answer_key",
                "title": "Band 9.0 Examiner Model Essays & Lexical Breakdown",
                "text_content": (
                    "🏆 BAND 9.0 MODEL ESSAY EXCERPT (Task 2):\n"
                    "\"Urban traffic congestion has evolved into a pressing issue across metropolitan regions worldwide. "
                    "While proponents of highway expansion contend that wider arterial roads alleviate immediate bottlenecks, "
                    "I would argue that investing in high-capacity mass transit represents a far more sustainable long-term solution...\"\n\n"
                    "💎 Key C1–C2 Lexical Upgrades Used:\n"
                    "• pressing issue • alleviate bottlenecks • high-capacity mass transit • sustainable long-term solution"
                ),
            },
        ],
    },
    {
        "title": "IELTS Speaking Part 1, 2 & 3 — Examiner Cue Card Mock",
        "category": "Speaking",
        "description": (
            "Yangilangan Speaking Part 1 savollari, Part 2 Cue Card (1 daqiqa tayyorgarlik + 2 daqiqa nutq), "
            "Part 3 chuqurlashtirilgan savollar va Band 8.5+ C1–C2 javob namunasi."
        ),
        "price_uzs": 40000,
        "duration_minutes": 15,
        "questions_count": 12,
        "instructions": (
            "🎙 Har bir savolga ovoz chiqarib javob bering, nutqingizni yozib oling va Band 9.0 javob bilan solishtiring."
        ),
        "is_published": True,
        "is_active": True,
        "materials": [
            {
                "file_type": "text",
                "material_role": "question_paper",
                "title": "Speaking Part 1, Part 2 Cue Card & Part 3 Questions",
                "text_content": (
                    "🎙 PART 1: WORK, STUDY & TECHNOLOGY (4–5 mins)\n"
                    "1. Do you prefer working early in the morning or late in the evening?\n"
                    "2. How has digital technology changed the way you study?\n\n"
                    "🗂 PART 2 CUE CARD (2 mins speaking):\n"
                    "Describe a problem in your city that you think should be solved.\n"
                    "You should say:\n"
                    "• what the problem is and how long it has existed\n"
                    "• how it affects local residents\n"
                    "• what measures could be taken to resolve it\n\n"
                    "🧠 PART 3: URBAN PLANNING & CIVIC RESPONSIBILITY (4–5 mins)\n"
                    "1. Should municipal governments prioritize economic growth or environmental protection?"
                ),
            },
            {
                "file_type": "text",
                "material_role": "answer_key",
                "title": "Band 9.0 Speaking Sample Script & Idiomatic Collocations",
                "text_content": (
                    "🌟 BAND 9.0 SAMPLE RESPONSE (Part 2 & 3):\n"
                    "\"One pressing issue that has plagued my hometown over the past few years is severe rush-hour congestion. "
                    "To mitigate this, municipal authorities ought to roll out dedicated bus lanes and incentivize cycling...\""
                ),
            },
        ],
    },
    {
        "title": "IELTS Full 4-Skills Complete Mock Exam (Band 7.0–9.0)",
        "category": "Full Mock Test",
        "description": (
            "To‘liq 4 ta ko‘nikma (Listening + Reading + Writing + Speaking) jamlangan kompleks IELTS Mock imtihoni. "
            "Haqiqiy imtihon vaqti, barcha bo‘limlar materiallari, javoblar varaqasi va to‘liq kalitlar."
        ),
        "price_uzs": 85000,
        "duration_minutes": 165,
        "questions_count": 84,
        "instructions": (
            "🏛 To‘liq imtihon tartibi: Listening (40 daq) -> Reading (60 daq) -> Writing (60 daq) -> Speaking (15 daq)."
        ),
        "is_published": True,
        "is_active": True,
        "materials": [
            {
                "file_type": "text",
                "material_role": "question_paper",
                "title": "Complete 4-Skills Exam Booklet (Listening, Reading, Writing, Speaking)",
                "text_content": (
                    "🏛 IELTS FULL 4-SKILLS MOCK EXAM BOOKLET\n"
                    "• Module 1: Listening (Sections 1–4, 40 questions)\n"
                    "• Module 2: Academic Reading (Passages 1–3, 40 questions)\n"
                    "• Module 3: Academic Writing (Task 1 Bar Chart + Task 2 Problem/Solution Essay)\n"
                    "• Module 4: Speaking Interview & Cue Card"
                ),
            },
            {
                "file_type": "text",
                "material_role": "answer_sheet",
                "title": "Official Combined Listening & Reading Answer Sheet",
                "text_content": "📄 Official 1–40 Listening & 1–40 Reading Transfer Sheet.",
            },
            {
                "file_type": "text",
                "material_role": "answer_key",
                "title": "Full 4-Skills Answer Keys & Band 9.0 Examiner Samples",
                "text_content": (
                    "🔑 COMPLETE ANSWER KEYS & BAND DESCRIPTORS\n"
                    "Includes full 1–40 Listening key, 1–40 Reading key with passage locators, "
                    "and Band 9.0 model essays for Task 1 and Task 2."
                ),
            },
        ],
    },
]


def format_price_uzs(price_uzs: int) -> str:
    if price_uzs <= 0:
        return "Bepul (0 UZS)"
    return f"{price_uzs:,} UZS".replace(",", " ")


def compute_access_expiration(
    duration_code: str, now: datetime | None = None
) -> tuple[datetime | None, str]:
    """
    Calculate expiration timestamp and human-readable label for:
    - 'permanent' -> None
    - '24h' -> +24 hours
    - '7d' -> +7 days
    - '30d' -> +30 days
    - 'custom:<days>' or integer days -> +N days
    """
    ts = now or datetime.now(timezone.utc)
    code = (duration_code or "permanent").strip().lower()
    if code in ("permanent", "forever", "0", "doimiy"):
        return None, "Doimiy (Permanent)"
    if code in ("24h", "1d"):
        return ts + timedelta(hours=24), "24 soat (24 hours)"
    if code == "7d":
        return ts + timedelta(days=7), "7 kun (7 days)"
    if code == "30d":
        return ts + timedelta(days=30), "30 kun (30 days)"
    if code.startswith("custom:"):
        raw_val = code.split(":", 1)[1].strip()
    else:
        raw_val = code.rstrip("d").strip()

    if raw_val.isdigit() and int(raw_val) > 0:
        days = int(raw_val)
        return ts + timedelta(days=days), f"{days} kun ({days} days)"
    return None, "Doimiy (Permanent)"


def is_access_currently_valid(
    is_active: bool,
    expires_at: str | datetime | None,
    now: datetime | None = None,
) -> bool:
    if not is_active:
        return False
    if expires_at is None:
        return True
    ts = now or datetime.now(timezone.utc)
    if isinstance(expires_at, str):
        if not expires_at.strip():
            return True
        try:
            exp_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            return True
    else:
        exp_dt = expires_at
    if exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    return exp_dt > ts


# ==============================================================================
# LOCAL FALLBACK STORE (FOR OFFLINE TESTS & LOCAL DEV PREVIEW)
# ==============================================================================


def _load_local_mock_store() -> dict[str, Any]:
    state: dict[str, Any] = {
        "tests": [],
        "access": [],
        "logs": [],
        "users": [
            {
                "user_id": 8838117173,
                "username": "shoxrux_admin",
                "full_name": "Shoxrux Admin",
                "xp": 1450,
                "streak": 12,
            },
            {
                "user_id": 100200300,
                "username": "azizbek_ielts",
                "full_name": "Azizbek Karimov",
                "xp": 890,
                "streak": 7,
            },
            {
                "user_id": 200300400,
                "username": "malika_band8",
                "full_name": "Malika Rahimova",
                "xp": 1240,
                "streak": 15,
            },
        ],
    }
    if LOCAL_MOCK_STATE_PATH.exists():
        try:
            state = json.loads(LOCAL_MOCK_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    if not state.get("tests") and not state.get("seeded"):
        now_iso = datetime.now(timezone.utc).isoformat()
        tests_list: list[dict[str, Any]] = []
        file_id_seq = 1
        for idx, raw in enumerate(DEFAULT_MOCK_TESTS_SEED, start=1):
            files_out: list[dict[str, Any]] = []
            for pos, mat in enumerate(raw.get("materials", []), start=1):
                files_out.append(
                    {
                        "id": file_id_seq,
                        "mock_test_id": idx,
                        "file_type": mat.get("file_type", "text"),
                        "material_role": mat.get("material_role", "question_paper"),
                        "title": mat.get("title", f"Material #{pos}"),
                        "telegram_file_id": mat.get("telegram_file_id"),
                        "file_name": mat.get("file_name"),
                        "mime_type": mat.get("mime_type"),
                        "text_content": mat.get("text_content"),
                        "position": pos,
                    }
                )
                file_id_seq += 1

            tests_list.append(
                {
                    "id": idx,
                    "title": raw["title"],
                    "category": raw["category"],
                    "description": raw["description"],
                    "price_uzs": int(raw["price_uzs"]),
                    "duration_minutes": int(raw["duration_minutes"]),
                    "questions_count": int(raw["questions_count"]),
                    "instructions": raw.get("instructions", ""),
                    "preview_image_file_id": raw.get("preview_image_file_id"),
                    "is_published": bool(raw.get("is_published", True)),
                    "is_active": bool(raw.get("is_active", True)),
                    "created_by": 0,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "files": files_out,
                }
            )
        state["tests"] = tests_list
        state["seeded"] = True
        _save_local_mock_store(state)
    return state


def _save_local_mock_store(state: dict[str, Any]) -> None:
    try:
        LOCAL_MOCK_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_MOCK_STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug("Failed to save local mock store: %s", exc)


# ==============================================================================
# POSTGRESQL SEEDING & UNIFIED MOCK TEST MANAGER
# ==============================================================================


class MockTestManager:
    """
    Unified manager for the IELTS Mock Test System (PostgreSQL + Local Fallback).
    - No Telegram Stars / No Payment Gateway.
    - Displays admin-configured informational UZS price and Contact Admin (@n0omg).
    - Protects test files, passages, and answer keys behind strict backend access checks.
    """

    async def ensure_seed_mock_tests_pg(self, session: Any) -> None:
        from sqlalchemy import func, select
        from database.models import MockTest, MockTestFile

        cnt = (
            await session.execute(select(func.count(MockTest.id)))
        ).scalar_one() or 0
        if cnt > 0:
            return

        for raw in DEFAULT_MOCK_TESTS_SEED:
            mt = MockTest(
                title=raw["title"],
                category=raw["category"],
                description=raw["description"],
                price_uzs=int(raw["price_uzs"]),
                duration_minutes=int(raw["duration_minutes"]),
                questions_count=int(raw["questions_count"]),
                instructions=raw.get("instructions", ""),
                preview_image_file_id=raw.get("preview_image_file_id"),
                is_published=True,
                is_active=True,
                created_by=0,
            )
            session.add(mt)
            await session.flush()

            for pos, mat in enumerate(raw.get("materials", []), start=1):
                session.add(
                    MockTestFile(
                        mock_test_id=mt.id,
                        file_type=mat.get("file_type", "text"),
                        material_role=mat.get("material_role", "question_paper"),
                        title=mat.get("title", f"Material #{pos}"),
                        telegram_file_id=mat.get("telegram_file_id"),
                        file_name=mat.get("file_name"),
                        mime_type=mat.get("mime_type"),
                        text_content=mat.get("text_content"),
                        position=pos,
                    )
                )
        await session.commit()

    def _serialize_public_test(
        self,
        test_dict: dict[str, Any],
        access_rec: dict[str, Any] | None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Serialize a mock test for the public catalog.
        NEVER includes protected `telegram_file_id` or `text_content` of test materials.
        """
        unlocked = False
        expires_at = None
        duration_label = None
        if access_rec and is_access_currently_valid(
            bool(access_rec.get("is_active")),
            access_rec.get("expires_at"),
            now=now,
        ):
            unlocked = True
            expires_at = access_rec.get("expires_at")
            duration_label = access_rec.get("duration_label", "Permanent")

        files = test_dict.get("files", [])
        return {
            "id": int(test_dict["id"]),
            "title": test_dict["title"],
            "category": test_dict["category"],
            "description": test_dict["description"],
            "price_uzs": int(test_dict.get("price_uzs", 0)),
            "price_formatted": format_price_uzs(int(test_dict.get("price_uzs", 0))),
            "duration_minutes": int(test_dict.get("duration_minutes", 60)),
            "questions_count": int(test_dict.get("questions_count", 40)),
            "instructions": test_dict.get("instructions") or "",
            "preview_image_file_id": test_dict.get("preview_image_file_id"),
            "is_published": bool(test_dict.get("is_published", True)),
            "is_active": bool(test_dict.get("is_active", True)),
            "materials_count": len(files),
            "material_types": sorted({f.get("file_type", "text") for f in files}),
            "is_unlocked": unlocked,
            "access_expires_at": expires_at,
            "access_duration_label": duration_label,
            "support_username": ADMIN_SUPPORT_USERNAME,
            "support_url": ADMIN_SUPPORT_URL,
        }

    # --------------------------------------------------------------------------
    # PUBLIC CATALOG & MY MOCK TESTS (POSTGRESQL + LOCAL)
    # --------------------------------------------------------------------------

    async def list_public_mock_tests_pg(
        self, session: Any, user_id: int
    ) -> list[dict[str, Any]]:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from database.models import MockTest, MockTestAccess

        await self.ensure_seed_mock_tests_pg(session)
        stmt = (
            select(MockTest)
            .options(selectinload(MockTest.files))
            .where(MockTest.is_published.is_(True), MockTest.is_active.is_(True))
            .order_by(MockTest.id)
        )
        tests = list((await session.execute(stmt)).scalars().all())
        acc_rows = list(
            (
                await session.execute(
                    select(MockTestAccess).where(MockTestAccess.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        acc_map = {
            a.mock_test_id: {
                "is_active": a.is_active,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                "duration_label": a.duration_label,
            }
            for a in acc_rows
        }

        now = datetime.now(timezone.utc)
        out: list[dict[str, Any]] = []
        for t in tests:
            t_dict = {
                "id": t.id,
                "title": t.title,
                "category": t.category,
                "description": t.description,
                "price_uzs": t.price_uzs,
                "duration_minutes": t.duration_minutes,
                "questions_count": t.questions_count,
                "instructions": t.instructions,
                "preview_image_file_id": t.preview_image_file_id,
                "is_published": t.is_published,
                "is_active": t.is_active,
                "files": [{"file_type": f.file_type} for f in (t.files or [])],
            }
            out.append(self._serialize_public_test(t_dict, acc_map.get(t.id), now=now))
        return out

    def list_public_mock_tests_local(
        self, user_id: int, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        state = _load_local_mock_store()
        acc_map = {
            int(a["mock_test_id"]): a
            for a in state.get("access", [])
            if int(a["user_id"]) == int(user_id)
        }
        out: list[dict[str, Any]] = []
        for t in state.get("tests", []):
            if not (t.get("is_published", True) and t.get("is_active", True)):
                continue
            out.append(
                self._serialize_public_test(
                    t, acc_map.get(int(t["id"])), now=now
                )
            )
        return out

    async def list_user_unlocked_tests_pg(
        self, session: Any, user_id: int
    ) -> list[dict[str, Any]]:
        all_pub = await self.list_public_mock_tests_pg(session, user_id)
        return [t for t in all_pub if t["is_unlocked"]]

    def list_user_unlocked_tests_local(
        self, user_id: int, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        all_pub = self.list_public_mock_tests_local(user_id, now=now)
        return [t for t in all_pub if t["is_unlocked"]]

    # --------------------------------------------------------------------------
    # PROTECTED MATERIALS DELIVERY (STRICT BACKEND ACCESS CHECK)
    # --------------------------------------------------------------------------

    async def get_protected_materials_pg(
        self,
        session: Any,
        user_id: int,
        test_id: int,
        is_admin: bool = False,
        now: datetime | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from database.models import MockTest, MockTestAccess

        await self.ensure_seed_mock_tests_pg(session)
        mt = (
            await session.execute(
                select(MockTest)
                .options(selectinload(MockTest.files))
                .where(MockTest.id == test_id)
            )
        ).scalar_one_or_none()
        if mt is None:
            return False, "NOT_FOUND", None

        acc = (
            await session.execute(
                select(MockTestAccess).where(
                    MockTestAccess.user_id == user_id,
                    MockTestAccess.mock_test_id == test_id,
                )
            )
        ).scalar_one_or_none()

        has_access = is_admin or (
            acc is not None
            and is_access_currently_valid(acc.is_active, acc.expires_at, now=now)
        )
        if not has_access:
            return False, "ACCESS_DENIED", None

        files_out = [
            {
                "id": f.id,
                "file_type": f.file_type,
                "material_role": f.material_role,
                "title": f.title,
                "telegram_file_id": f.telegram_file_id,
                "file_name": f.file_name,
                "mime_type": f.mime_type,
                "text_content": f.text_content,
                "position": f.position,
            }
            for f in (mt.files or [])
        ]
        return (
            True,
            "OK",
            {
                "id": mt.id,
                "title": mt.title,
                "category": mt.category,
                "description": mt.description,
                "price_uzs": mt.price_uzs,
                "duration_minutes": mt.duration_minutes,
                "questions_count": mt.questions_count,
                "instructions": mt.instructions or "",
                "preview_image_file_id": mt.preview_image_file_id,
                "expires_at": acc.expires_at.isoformat() if (acc and acc.expires_at) else None,
                "duration_label": acc.duration_label if acc else "Admin Access",
                "files": files_out,
            },
        )

    def get_protected_materials_local(
        self,
        user_id: int,
        test_id: int,
        is_admin: bool = False,
        now: datetime | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        state = _load_local_mock_store()
        mt = next(
            (t for t in state.get("tests", []) if int(t["id"]) == int(test_id)),
            None,
        )
        if mt is None:
            return False, "NOT_FOUND", None

        acc = next(
            (
                a
                for a in state.get("access", [])
                if int(a["user_id"]) == int(user_id)
                and int(a["mock_test_id"]) == int(test_id)
            ),
            None,
        )
        has_access = is_admin or (
            acc is not None
            and is_access_currently_valid(
                bool(acc.get("is_active")), acc.get("expires_at"), now=now
            )
        )
        if not has_access:
            return False, "ACCESS_DENIED", None

        return (
            True,
            "OK",
            {
                "id": int(mt["id"]),
                "title": mt["title"],
                "category": mt["category"],
                "description": mt["description"],
                "price_uzs": int(mt["price_uzs"]),
                "duration_minutes": int(mt["duration_minutes"]),
                "questions_count": int(mt["questions_count"]),
                "instructions": mt.get("instructions") or "",
                "preview_image_file_id": mt.get("preview_image_file_id"),
                "expires_at": acc.get("expires_at") if acc else None,
                "duration_label": acc.get("duration_label", "Admin Access") if acc else "Admin Access",
                "files": list(mt.get("files", [])),
            },
        )

    # --------------------------------------------------------------------------
    # ADMIN CRUD FOR MOCK TESTS, PRICES & MATERIALS
    # --------------------------------------------------------------------------

    async def list_all_mock_tests_admin_pg(self, session: Any) -> list[dict[str, Any]]:
        from sqlalchemy import func, select
        from sqlalchemy.orm import selectinload
        from database.models import MockTest, MockTestAccess

        await self.ensure_seed_mock_tests_pg(session)
        tests = list(
            (
                await session.execute(
                    select(MockTest)
                    .options(selectinload(MockTest.files))
                    .order_by(MockTest.id)
                )
            )
            .scalars()
            .all()
        )
        cnt_rows = (
            await session.execute(
                select(MockTestAccess.mock_test_id, func.count(MockTestAccess.id))
                .where(MockTestAccess.is_active.is_(True))
                .group_by(MockTestAccess.mock_test_id)
            )
        ).all()
        cnt_map = {tid: int(c) for tid, c in cnt_rows}

        return [
            {
                "id": t.id,
                "title": t.title,
                "category": t.category,
                "description": t.description,
                "price_uzs": t.price_uzs,
                "price_formatted": format_price_uzs(t.price_uzs),
                "duration_minutes": t.duration_minutes,
                "questions_count": t.questions_count,
                "instructions": t.instructions or "",
                "preview_image_file_id": t.preview_image_file_id,
                "is_published": t.is_published,
                "is_active": t.is_active,
                "active_users_count": cnt_map.get(t.id, 0),
                "files": [
                    {
                        "id": f.id,
                        "file_type": f.file_type,
                        "material_role": f.material_role,
                        "title": f.title,
                        "telegram_file_id": f.telegram_file_id,
                        "file_name": f.file_name,
                        "text_content": f.text_content,
                        "position": f.position,
                    }
                    for f in (t.files or [])
                ],
            }
            for t in tests
        ]

    def list_all_mock_tests_admin_local(self) -> list[dict[str, Any]]:
        state = _load_local_mock_store()
        now = datetime.now(timezone.utc)
        access_list = state.get("access", [])
        out: list[dict[str, Any]] = []
        for t in state.get("tests", []):
            tid = int(t["id"])
            active_cnt = sum(
                1
                for a in access_list
                if int(a["mock_test_id"]) == tid
                and is_access_currently_valid(
                    bool(a.get("is_active")), a.get("expires_at"), now=now
                )
            )
            out.append(
                {
                    **t,
                    "price_formatted": format_price_uzs(int(t.get("price_uzs", 0))),
                    "active_users_count": active_cnt,
                }
            )
        return out

    async def create_mock_test_pg(
        self, session: Any, admin_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        from database.models import MockTest, MockTestAdminLog, MockTestFile

        title = str(payload.get("title", "")).strip() or "New IELTS Mock Test"
        category = str(payload.get("category", "Full Mock Test")).strip()
        if category not in MOCK_TEST_CATEGORIES:
            category = "Full Mock Test"
        description = str(payload.get("description", "")).strip() or title
        price_uzs = max(0, int(payload.get("price_uzs", 0) or 0))
        duration_minutes = max(5, int(payload.get("duration_minutes", 60) or 60))
        questions_count = max(1, int(payload.get("questions_count", 40) or 40))
        instructions = str(payload.get("instructions", "") or "")
        preview_file_id = payload.get("preview_image_file_id")
        is_published = bool(payload.get("is_published", True))

        mt = MockTest(
            title=title,
            category=category,
            description=description,
            price_uzs=price_uzs,
            duration_minutes=duration_minutes,
            questions_count=questions_count,
            instructions=instructions,
            preview_image_file_id=preview_file_id,
            is_published=is_published,
            is_active=True,
            created_by=admin_id,
        )
        session.add(mt)
        await session.flush()

        for pos, mat in enumerate(payload.get("materials", []) or [], start=1):
            session.add(
                MockTestFile(
                    mock_test_id=mt.id,
                    file_type=str(mat.get("file_type", "text")),
                    material_role=str(mat.get("material_role", "question_paper")),
                    title=str(mat.get("title", f"Material #{pos}")),
                    telegram_file_id=mat.get("telegram_file_id"),
                    file_name=mat.get("file_name"),
                    mime_type=mat.get("mime_type"),
                    text_content=mat.get("text_content"),
                    position=pos,
                )
            )

        session.add(
            MockTestAdminLog(
                admin_id=admin_id,
                mock_test_id=mt.id,
                action="CREATE_MOCK_TEST",
                details=f"Created '{title}' ({category}) — {price_uzs} UZS",
            )
        )
        await session.commit()
        all_tests = await self.list_all_mock_tests_admin_pg(session)
        return next(t for t in all_tests if t["id"] == mt.id)

    def create_mock_test_local(
        self, admin_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        state = _load_local_mock_store()
        tests = state.setdefault("tests", [])
        next_id = max((int(t["id"]) for t in tests), default=0) + 1
        now_iso = datetime.now(timezone.utc).isoformat()

        category = str(payload.get("category", "Full Mock Test")).strip()
        if category not in MOCK_TEST_CATEGORIES:
            category = "Full Mock Test"

        files_out: list[dict[str, Any]] = []
        for pos, mat in enumerate(payload.get("materials", []) or [], start=1):
            files_out.append(
                {
                    "id": next_id * 100 + pos,
                    "mock_test_id": next_id,
                    "file_type": str(mat.get("file_type", "text")),
                    "material_role": str(mat.get("material_role", "question_paper")),
                    "title": str(mat.get("title", f"Material #{pos}")),
                    "telegram_file_id": mat.get("telegram_file_id"),
                    "file_name": mat.get("file_name"),
                    "mime_type": mat.get("mime_type"),
                    "text_content": mat.get("text_content"),
                    "position": pos,
                }
            )

        new_test = {
            "id": next_id,
            "title": str(payload.get("title", "New IELTS Mock Test")).strip(),
            "category": category,
            "description": str(payload.get("description", "")).strip() or "IELTS Mock Test",
            "price_uzs": max(0, int(payload.get("price_uzs", 0) or 0)),
            "duration_minutes": max(5, int(payload.get("duration_minutes", 60) or 60)),
            "questions_count": max(1, int(payload.get("questions_count", 40) or 40)),
            "instructions": str(payload.get("instructions", "") or ""),
            "preview_image_file_id": payload.get("preview_image_file_id"),
            "is_published": bool(payload.get("is_published", True)),
            "is_active": True,
            "created_by": admin_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "files": files_out,
        }
        tests.append(new_test)
        state.setdefault("logs", []).insert(
            0,
            {
                "id": len(state["logs"]) + 1,
                "admin_id": admin_id,
                "target_user_id": None,
                "mock_test_id": next_id,
                "action": "CREATE_MOCK_TEST",
                "details": f"Created '{new_test['title']}' — {new_test['price_uzs']} UZS",
                "created_at": now_iso,
            },
        )
        _save_local_mock_store(state)
        return {
            **new_test,
            "price_formatted": format_price_uzs(new_test["price_uzs"]),
            "active_users_count": 0,
        }

    async def update_mock_test_pg(
        self,
        session: Any,
        admin_id: int,
        test_id: int,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        from sqlalchemy import select
        from database.models import MockTest, MockTestAdminLog

        mt = (
            await session.execute(select(MockTest).where(MockTest.id == test_id))
        ).scalar_one_or_none()
        if mt is None:
            return None

        changed_fields: list[str] = []
        if "title" in updates and str(updates["title"]).strip():
            mt.title = str(updates["title"]).strip()
            changed_fields.append("title")
        if "category" in updates and str(updates["category"]) in MOCK_TEST_CATEGORIES:
            mt.category = str(updates["category"])
            changed_fields.append("category")
        if "description" in updates and str(updates["description"]).strip():
            mt.description = str(updates["description"]).strip()
            changed_fields.append("description")
        if "price_uzs" in updates:
            mt.price_uzs = max(0, int(updates["price_uzs"] or 0))
            changed_fields.append(f"price_uzs={mt.price_uzs}")
        if "duration_minutes" in updates:
            mt.duration_minutes = max(5, int(updates["duration_minutes"] or 60))
            changed_fields.append(f"duration={mt.duration_minutes}")
        if "questions_count" in updates:
            mt.questions_count = max(1, int(updates["questions_count"] or 40))
            changed_fields.append(f"questions={mt.questions_count}")
        if "instructions" in updates:
            mt.instructions = str(updates["instructions"] or "")
            changed_fields.append("instructions")
        if "preview_image_file_id" in updates:
            mt.preview_image_file_id = updates["preview_image_file_id"]
            changed_fields.append("preview_image")
        if "is_published" in updates:
            mt.is_published = bool(updates["is_published"])
            changed_fields.append(f"is_published={mt.is_published}")
        if "is_active" in updates:
            mt.is_active = bool(updates["is_active"])
            changed_fields.append(f"is_active={mt.is_active}")

        session.add(
            MockTestAdminLog(
                admin_id=admin_id,
                mock_test_id=test_id,
                action="UPDATE_MOCK_TEST",
                details=f"Updated #{test_id}: {', '.join(changed_fields)}",
            )
        )
        await session.commit()
        all_tests = await self.list_all_mock_tests_admin_pg(session)
        return next((t for t in all_tests if t["id"] == test_id), None)

    def update_mock_test_local(
        self, admin_id: int, test_id: int, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        state = _load_local_mock_store()
        mt = next(
            (t for t in state.get("tests", []) if int(t["id"]) == int(test_id)),
            None,
        )
        if mt is None:
            return None

        changed: list[str] = []
        for field in ("title", "description", "instructions"):
            if field in updates and updates[field] is not None:
                mt[field] = str(updates[field]).strip()
                changed.append(field)
        if "category" in updates and str(updates["category"]) in MOCK_TEST_CATEGORIES:
            mt["category"] = str(updates["category"])
            changed.append("category")
        if "price_uzs" in updates:
            mt["price_uzs"] = max(0, int(updates["price_uzs"] or 0))
            changed.append(f"price_uzs={mt['price_uzs']}")
        if "duration_minutes" in updates:
            mt["duration_minutes"] = max(5, int(updates["duration_minutes"] or 60))
            changed.append("duration")
        if "questions_count" in updates:
            mt["questions_count"] = max(1, int(updates["questions_count"] or 40))
            changed.append("questions")
        if "preview_image_file_id" in updates:
            mt["preview_image_file_id"] = updates["preview_image_file_id"]
        if "is_published" in updates:
            mt["is_published"] = bool(updates["is_published"])
        if "is_active" in updates:
            mt["is_active"] = bool(updates["is_active"])

        now_iso = datetime.now(timezone.utc).isoformat()
        mt["updated_at"] = now_iso
        state.setdefault("logs", []).insert(
            0,
            {
                "id": len(state["logs"]) + 1,
                "admin_id": admin_id,
                "target_user_id": None,
                "mock_test_id": test_id,
                "action": "UPDATE_MOCK_TEST",
                "details": f"Updated #{test_id}: {', '.join(changed)}",
                "created_at": now_iso,
            },
        )
        _save_local_mock_store(state)
        return {
            **mt,
            "price_formatted": format_price_uzs(int(mt["price_uzs"])),
        }

    async def add_material_to_test_pg(
        self,
        session: Any,
        admin_id: int,
        test_id: int,
        material: dict[str, Any],
    ) -> dict[str, Any] | None:
        from sqlalchemy import func, select
        from database.models import MockTest, MockTestAdminLog, MockTestFile

        mt = (
            await session.execute(select(MockTest).where(MockTest.id == test_id))
        ).scalar_one_or_none()
        if mt is None:
            return None

        max_pos = (
            await session.execute(
                select(func.max(MockTestFile.position)).where(
                    MockTestFile.mock_test_id == test_id
                )
            )
        ).scalar_one() or 0
        f_obj = MockTestFile(
            mock_test_id=test_id,
            file_type=str(material.get("file_type", "pdf")),
            material_role=str(material.get("material_role", "question_paper")),
            title=str(material.get("title", f"Material #{max_pos + 1}")),
            telegram_file_id=material.get("telegram_file_id"),
            file_name=material.get("file_name"),
            mime_type=material.get("mime_type"),
            text_content=material.get("text_content"),
            position=int(max_pos) + 1,
        )
        session.add(f_obj)
        session.add(
            MockTestAdminLog(
                admin_id=admin_id,
                mock_test_id=test_id,
                action="ADD_MATERIAL",
                details=f"Added {f_obj.file_type} ({f_obj.material_role}): {f_obj.title}",
            )
        )
        await session.commit()
        all_tests = await self.list_all_mock_tests_admin_pg(session)
        return next((t for t in all_tests if t["id"] == test_id), None)

    def add_material_to_test_local(
        self, admin_id: int, test_id: int, material: dict[str, Any]
    ) -> dict[str, Any] | None:
        state = _load_local_mock_store()
        mt = next(
            (t for t in state.get("tests", []) if int(t["id"]) == int(test_id)),
            None,
        )
        if mt is None:
            return None
        files = mt.setdefault("files", [])
        pos = len(files) + 1
        f_dict = {
            "id": int(test_id) * 1000 + pos,
            "mock_test_id": int(test_id),
            "file_type": str(material.get("file_type", "pdf")),
            "material_role": str(material.get("material_role", "question_paper")),
            "title": str(material.get("title", f"Material #{pos}")),
            "telegram_file_id": material.get("telegram_file_id"),
            "file_name": material.get("file_name"),
            "mime_type": material.get("mime_type"),
            "text_content": material.get("text_content"),
            "position": pos,
        }
        files.append(f_dict)
        _save_local_mock_store(state)
        return mt

    async def delete_mock_test_pg(
        self, session: Any, admin_id: int, test_id: int
    ) -> bool:
        from sqlalchemy import select
        from database.models import MockTest, MockTestAdminLog

        mt = (
            await session.execute(select(MockTest).where(MockTest.id == test_id))
        ).scalar_one_or_none()
        if mt is None:
            return False
        title = mt.title
        await session.delete(mt)
        session.add(
            MockTestAdminLog(
                admin_id=admin_id,
                mock_test_id=test_id,
                action="DELETE_MOCK_TEST",
                details=f"Deleted Mock Test #{test_id} ('{title}')",
            )
        )
        await session.commit()
        return True

    def delete_mock_test_local(self, admin_id: int, test_id: int) -> bool:
        state = _load_local_mock_store()
        tests = state.get("tests", [])
        target = next((t for t in tests if int(t["id"]) == int(test_id)), None)
        if target is None:
            return False
        state["tests"] = [t for t in tests if int(t["id"]) != int(test_id)]
        state["access"] = [
            a for a in state.get("access", []) if int(a["mock_test_id"]) != int(test_id)
        ]
        state.setdefault("logs", []).insert(
            0,
            {
                "id": len(state["logs"]) + 1,
                "admin_id": admin_id,
                "target_user_id": None,
                "mock_test_id": test_id,
                "action": "DELETE_MOCK_TEST",
                "details": f"Deleted Mock Test #{test_id} ('{target['title']}')",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        _save_local_mock_store(state)
        return True

    # --------------------------------------------------------------------------
    # MANUAL USER ACCESS MANAGEMENT (SEARCH USERS, GRANT, REVOKE, LIST HOLDERS)
    # --------------------------------------------------------------------------

    async def search_registered_users_pg(
        self,
        session: Any,
        query_str: str = "",
        page: int = 1,
        page_size: int = 8,
    ) -> tuple[list[dict[str, Any]], int, int]:
        from sqlalchemy import desc, func, or_, select
        from database.models import User

        q = (query_str or "").strip()
        stmt = select(User)
        count_stmt = select(func.count(User.id))

        if q:
            clean_q = q.lstrip("@")
            filters = [
                User.full_name.ilike(f"%{clean_q}%"),
                User.username.ilike(f"%{clean_q}%"),
            ]
            if clean_q.isdigit():
                filters.append(User.user_id == int(clean_q))
            cond = or_(*filters)
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        total = int((await session.execute(count_stmt)).scalar_one() or 0)
        total_pages = max(1, math.ceil(total / page_size))
        page = max(1, min(page, total_pages))

        rows = list(
            (
                await session.execute(
                    stmt.order_by(desc(User.xp), desc(User.id))
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        users_out = [
            {
                "user_id": u.user_id,
                "username": u.username or "",
                "full_name": u.full_name,
                "xp": u.xp,
                "streak": u.streak,
            }
            for u in rows
        ]
        return users_out, total, total_pages

    def search_registered_users_local(
        self,
        query_str: str = "",
        page: int = 1,
        page_size: int = 8,
    ) -> tuple[list[dict[str, Any]], int, int]:
        state = _load_local_mock_store()
        users = list(state.get("users", []))
        q = (query_str or "").strip().lower().lstrip("@")
        if q:
            users = [
                u
                for u in users
                if q in str(u.get("user_id", "")).lower()
                or q in str(u.get("username", "")).lower()
                or q in str(u.get("full_name", "")).lower()
            ]
        total = len(users)
        total_pages = max(1, math.ceil(total / page_size))
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size
        return users[start : start + page_size], total, total_pages

    async def grant_access_pg(
        self,
        session: Any,
        admin_id: int,
        target_user_id: int,
        test_id: int,
        duration_code: str = "permanent",
        reason: str = "Complimentary educational access",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        from sqlalchemy import select
        from database.models import MockTest, MockTestAccess, MockTestAdminLog

        ts = now or datetime.now(timezone.utc)
        mt = (
            await session.execute(select(MockTest).where(MockTest.id == test_id))
        ).scalar_one_or_none()
        if mt is None:
            return {"ok": False, "reason": "TEST_NOT_FOUND"}

        expires_at, duration_label = compute_access_expiration(duration_code, now=ts)
        existing = (
            await session.execute(
                select(MockTestAccess).where(
                    MockTestAccess.user_id == target_user_id,
                    MockTestAccess.mock_test_id == test_id,
                )
            )
        ).scalar_one_or_none()

        # Prevent duplicate identical permanent grant
        if (
            existing is not None
            and is_access_currently_valid(existing.is_active, existing.expires_at, now=ts)
            and existing.expires_at is None
            and expires_at is None
        ):
            return {
                "ok": False,
                "reason": "ALREADY_HAS_ACTIVE_ACCESS",
                "test_title": mt.title,
                "duration_label": existing.duration_label,
            }

        if existing is None:
            existing = MockTestAccess(
                user_id=target_user_id,
                mock_test_id=test_id,
                granted_by=admin_id,
                access_type="admin_grant",
                access_reason=reason,
                duration_label=duration_label,
                is_active=True,
                granted_at=ts,
                expires_at=expires_at,
                revoked_at=None,
                revoked_by=None,
            )
            session.add(existing)
        else:
            existing.granted_by = admin_id
            existing.access_reason = reason
            existing.duration_label = duration_label
            existing.is_active = True
            existing.granted_at = ts
            existing.expires_at = expires_at
            existing.revoked_at = None
            existing.revoked_by = None

        session.add(
            MockTestAdminLog(
                admin_id=admin_id,
                target_user_id=target_user_id,
                mock_test_id=test_id,
                action="GRANT_ACCESS",
                details=f"Granted '{mt.title}' to user {target_user_id} ({duration_label}). Reason: {reason}",
            )
        )
        await session.commit()
        return {
            "ok": True,
            "user_id": target_user_id,
            "mock_test_id": test_id,
            "test_title": mt.title,
            "duration_label": duration_label,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }

    def grant_access_local(
        self,
        admin_id: int,
        target_user_id: int,
        test_id: int,
        duration_code: str = "permanent",
        reason: str = "Complimentary educational access",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        state = _load_local_mock_store()
        ts = now or datetime.now(timezone.utc)
        mt = next(
            (t for t in state.get("tests", []) if int(t["id"]) == int(test_id)),
            None,
        )
        if mt is None:
            return {"ok": False, "reason": "TEST_NOT_FOUND"}

        expires_at, duration_label = compute_access_expiration(duration_code, now=ts)
        access_list = state.setdefault("access", [])
        existing = next(
            (
                a
                for a in access_list
                if int(a["user_id"]) == int(target_user_id)
                and int(a["mock_test_id"]) == int(test_id)
            ),
            None,
        )

        if (
            existing is not None
            and is_access_currently_valid(
                bool(existing.get("is_active")), existing.get("expires_at"), now=ts
            )
            and existing.get("expires_at") is None
            and expires_at is None
        ):
            return {
                "ok": False,
                "reason": "ALREADY_HAS_ACTIVE_ACCESS",
                "test_title": mt["title"],
                "duration_label": existing.get("duration_label", "Permanent"),
            }

        exp_iso = expires_at.isoformat() if expires_at else None
        if existing is None:
            access_list.append(
                {
                    "id": len(access_list) + 1,
                    "user_id": int(target_user_id),
                    "mock_test_id": int(test_id),
                    "granted_by": int(admin_id),
                    "access_type": "admin_grant",
                    "access_reason": reason,
                    "duration_label": duration_label,
                    "is_active": True,
                    "granted_at": ts.isoformat(),
                    "expires_at": exp_iso,
                    "revoked_at": None,
                    "revoked_by": None,
                }
            )
        else:
            existing["granted_by"] = int(admin_id)
            existing["access_reason"] = reason
            existing["duration_label"] = duration_label
            existing["is_active"] = True
            existing["granted_at"] = ts.isoformat()
            existing["expires_at"] = exp_iso
            existing["revoked_at"] = None
            existing["revoked_by"] = None

        state.setdefault("logs", []).insert(
            0,
            {
                "id": len(state["logs"]) + 1,
                "admin_id": int(admin_id),
                "target_user_id": int(target_user_id),
                "mock_test_id": int(test_id),
                "action": "GRANT_ACCESS",
                "details": f"Granted '{mt['title']}' to user {target_user_id} ({duration_label}). Reason: {reason}",
                "created_at": ts.isoformat(),
            },
        )
        _save_local_mock_store(state)
        return {
            "ok": True,
            "user_id": int(target_user_id),
            "mock_test_id": int(test_id),
            "test_title": mt["title"],
            "duration_label": duration_label,
            "expires_at": exp_iso,
        }

    async def revoke_access_pg(
        self,
        session: Any,
        admin_id: int,
        target_user_id: int,
        test_id: int,
    ) -> dict[str, Any]:
        from sqlalchemy import select
        from database.models import MockTestAccess, MockTestAdminLog

        now = datetime.now(timezone.utc)
        existing = (
            await session.execute(
                select(MockTestAccess).where(
                    MockTestAccess.user_id == target_user_id,
                    MockTestAccess.mock_test_id == test_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None or not existing.is_active:
            return {"ok": False, "reason": "NO_ACTIVE_ACCESS"}

        existing.is_active = False
        existing.revoked_at = now
        existing.revoked_by = admin_id
        session.add(
            MockTestAdminLog(
                admin_id=admin_id,
                target_user_id=target_user_id,
                mock_test_id=test_id,
                action="REVOKE_ACCESS",
                details=f"Revoked access to Mock Test #{test_id} from user {target_user_id}",
            )
        )
        await session.commit()
        return {"ok": True, "user_id": target_user_id, "mock_test_id": test_id}

    def revoke_access_local(
        self, admin_id: int, target_user_id: int, test_id: int
    ) -> dict[str, Any]:
        state = _load_local_mock_store()
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = next(
            (
                a
                for a in state.get("access", [])
                if int(a["user_id"]) == int(target_user_id)
                and int(a["mock_test_id"]) == int(test_id)
            ),
            None,
        )
        if existing is None or not existing.get("is_active"):
            return {"ok": False, "reason": "NO_ACTIVE_ACCESS"}

        existing["is_active"] = False
        existing["revoked_at"] = now_iso
        existing["revoked_by"] = int(admin_id)
        state.setdefault("logs", []).insert(
            0,
            {
                "id": len(state["logs"]) + 1,
                "admin_id": int(admin_id),
                "target_user_id": int(target_user_id),
                "mock_test_id": int(test_id),
                "action": "REVOKE_ACCESS",
                "details": f"Revoked access to Mock Test #{test_id} from user {target_user_id}",
                "created_at": now_iso,
            },
        )
        _save_local_mock_store(state)
        return {"ok": True, "user_id": int(target_user_id), "mock_test_id": int(test_id)}

    async def list_access_holders_pg(
        self, session: Any, test_id: int | None = None
    ) -> list[dict[str, Any]]:
        from sqlalchemy import desc, select
        from database.models import MockTest, MockTestAccess, User

        stmt = (
            select(MockTestAccess, User, MockTest)
            .outerjoin(User, User.user_id == MockTestAccess.user_id)
            .join(MockTest, MockTest.id == MockTestAccess.mock_test_id)
            .where(MockTestAccess.is_active.is_(True))
            .order_by(desc(MockTestAccess.granted_at))
        )
        if test_id is not None:
            stmt = stmt.where(MockTestAccess.mock_test_id == test_id)

        now = datetime.now(timezone.utc)
        rows = (await session.execute(stmt)).all()
        out: list[dict[str, Any]] = []
        for acc, usr, mt in rows:
            if not is_access_currently_valid(acc.is_active, acc.expires_at, now=now):
                continue
            out.append(
                {
                    "user_id": acc.user_id,
                    "username": usr.username if usr and usr.username else "",
                    "full_name": usr.full_name if usr else f"User {acc.user_id}",
                    "mock_test_id": mt.id,
                    "test_title": mt.title,
                    "category": mt.category,
                    "duration_label": acc.duration_label,
                    "granted_by": acc.granted_by,
                    "granted_at": acc.granted_at.isoformat() if acc.granted_at else "",
                    "expires_at": acc.expires_at.isoformat() if acc.expires_at else None,
                }
            )
        return out

    def list_access_holders_local(
        self, test_id: int | None = None, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        state = _load_local_mock_store()
        ts = now or datetime.now(timezone.utc)
        tests_map = {int(t["id"]): t for t in state.get("tests", [])}
        users_map = {int(u["user_id"]): u for u in state.get("users", [])}

        out: list[dict[str, Any]] = []
        for acc in state.get("access", []):
            tid = int(acc["mock_test_id"])
            if test_id is not None and tid != int(test_id):
                continue
            if not is_access_currently_valid(
                bool(acc.get("is_active")), acc.get("expires_at"), now=ts
            ):
                continue
            mt = tests_map.get(tid)
            if not mt:
                continue
            uid = int(acc["user_id"])
            usr = users_map.get(uid, {})
            out.append(
                {
                    "user_id": uid,
                    "username": usr.get("username", ""),
                    "full_name": usr.get("full_name", f"User {uid}"),
                    "mock_test_id": tid,
                    "test_title": mt["title"],
                    "category": mt["category"],
                    "duration_label": acc.get("duration_label", "Permanent"),
                    "granted_by": acc.get("granted_by", 0),
                    "granted_at": acc.get("granted_at", ""),
                    "expires_at": acc.get("expires_at"),
                }
            )
        return out


mock_test_manager = MockTestManager()
