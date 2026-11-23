from types import SimpleNamespace
from services.i18n import i18n


def test_all_three_locales_have_identical_keys() -> None:
    i18n.reload()
    uz_keys = set(i18n._translations["uz"].keys())
    ru_keys = set(i18n._translations["ru"].keys())
    en_keys = set(i18n._translations["en"].keys())

    assert len(uz_keys) > 35
    assert uz_keys == ru_keys == en_keys


def test_required_prompt_strings_match_specification() -> None:
    assert (
        i18n.t("morning_notification", lang="uz")
        == "☀️ Xayrli tong! Bugungi 10 ta yangi advanced English ibora tayyor. O‘rganishni boshlang!"
    )
    assert (
        i18n.t("morning_notification", lang="ru")
        == "☀️ Доброе утро! Ваши 10 новых продвинутых английских выражений готовы. Начните обучение!"
    )
    assert (
        i18n.t("morning_notification", lang="en")
        == "☀️ Good morning! Your 10 new advanced English expressions are ready. Start learning!"
    )

    assert i18n.t("btn_memorized", lang="uz") == "✅ YODLADIM"
    assert i18n.t("btn_memorized", lang="ru") == "✅ Я ВЫУЧИЛ(А)"
    assert i18n.t("btn_memorized", lang="en") == "✅ I'VE MEMORIZED THEM"


def test_everyday_to_advanced_word_card_formatting_in_three_languages() -> None:
    vocab = SimpleNamespace(
        simple_word="Deal with a problem",
        advanced_word="Address an issue",
        cefr_level="B2–C1",
        category="everyday_upgrade",
        translation_uz="Muammoni hal qilish bilan shug‘ullanmoq",
        translation_ru="Заниматься решением проблемы",
        definition_en="More formal and precise than 'deal with a problem'; ideal for IELTS Writing Task 2.",
        basic_example_en="Governments should deal with this problem.",
        example_en="Governments should address this issue.",
        example_uz="Hukumatlar ushbu masalani hal qilishlari kerak.",
        example_ru="Правительствам следует заняться решением этого вопроса.",
        ielts_usage="Writing Task 2",
        source_name="Cambridge Dictionary",
    )

    for lang in ("uz", "ru", "en"):
        card = i18n.format_word_card(
            vocab, lang=lang, index=1, total=10, lesson_date="2026-11-23"
        )
        assert "BASIC:" in card
        assert "Deal with a problem" in card
        assert "ADVANCED:" in card
        assert "Address an issue" in card
        assert "Muammoni hal qilish bilan shug‘ullanmoq" in card
        assert "Заниматься решением проблемы" in card
        assert "B2–C1" in card
        assert "Governments should deal with this problem." in card
        assert "Governments should address this issue." in card
        assert "Writing Task 2" in card
