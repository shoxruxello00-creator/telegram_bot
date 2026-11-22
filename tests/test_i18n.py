from types import SimpleNamespace
from services.i18n import i18n


def test_all_three_locales_have_identical_keys() -> None:
    uz_keys = set(i18n._translations["uz"].keys())
    ru_keys = set(i18n._translations["ru"].keys())
    en_keys = set(i18n._translations["en"].keys())

    assert len(uz_keys) > 25
    assert uz_keys == ru_keys == en_keys


def test_required_prompt_strings_match_specification() -> None:
    # 08:00 morning notifications
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

    # Memorized buttons
    assert i18n.t("btn_memorized", lang="uz") == "✅ YODLADIM"
    assert i18n.t("btn_memorized", lang="ru") == "✅ Я ВЫУЧИЛ(А)"
    assert i18n.t("btn_memorized", lang="en") == "✅ I'VE MEMORIZED THEM"


def test_word_card_formatting_in_three_languages() -> None:
    vocab = SimpleNamespace(
        simple_word="Give up",
        advanced_word="Throw in the towel",
        cefr_level="C2",
        category="idiom",
        translation_uz="Taslim bo‘lmoq.",
        translation_ru="Сдаться, признать поражение.",
        definition_en="To stop trying because something is too difficult.",
        example_en="After months of negotiations, they threw in the towel.",
        example_uz="Oylar davom etgan muzokaralardan so‘ng ular taslim bo‘lishdi.",
        example_ru="После месяцев переговоров они сдались.",
        source_name="Cambridge Dictionary",
    )

    card_uz = i18n.format_word_card(vocab, lang="uz", index=1, total=10, lesson_date="2026-11-22")
    assert "Give up" in card_uz
    assert "Throw in the towel" in card_uz
    assert "Taslim bo‘lmoq." in card_uz

    card_ru = i18n.format_word_card(vocab, lang="ru", index=1, total=10, lesson_date="2026-11-22")
    assert "Give up" in card_ru
    assert "Throw in the towel" in card_ru
    assert "Сдаться, признать поражение." in card_ru

    card_en = i18n.format_word_card(vocab, lang="en", index=1, total=10, lesson_date="2026-11-22")
    assert "Give up" in card_en
    assert "Throw in the towel" in card_en
    assert "To stop trying because something is too difficult." in card_en
