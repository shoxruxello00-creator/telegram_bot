import html
import json
import re
from pathlib import Path
from typing import Any
from config import SUPPORTED_LANGUAGES, settings

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"

CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "everyday_upgrade": {
        "uz": "Everyday → Advanced",
        "ru": "Everyday → Advanced",
        "en": "Everyday → Advanced",
    },
    "academic_upgrade": {
        "uz": "Academic Vocabulary",
        "ru": "Academic Vocabulary",
        "en": "Academic Vocabulary",
    },
    "collocation": {
        "uz": "Advanced Collocation",
        "ru": "Advanced Collocation",
        "en": "Advanced Collocation",
    },
    "phrasal_verb": {
        "uz": "Phrasal Verb",
        "ru": "Phrasal Verb",
        "en": "Phrasal Verb",
    },
    "idiom": {
        "uz": "Natural Expression / Idiom",
        "ru": "Natural Expression / Idiom",
        "en": "Natural Expression / Idiom",
    },
    "advanced_word": {
        "uz": "Academic / Advanced Word",
        "ru": "Academic / Advanced Word",
        "en": "Academic / Advanced Word",
    },
}

DEFAULT_IELTS_USAGE_BY_CATEGORY: dict[str, str] = {
    "everyday_upgrade": "Writing Task 2 & Speaking Part 3",
    "academic_upgrade": "Writing Task 2 (Formal Essays)",
    "collocation": "Writing Task 2 & Speaking Part 3",
    "phrasal_verb": "Speaking Part 1–3",
    "idiom": "Speaking Part 2–3",
    "advanced_word": "Writing Task 2 & Reading",
}


def _derive_basic_example(vocab: Any) -> str:
    explicit_basic = getattr(vocab, "basic_example_en", None)
    if explicit_basic and str(explicit_basic).strip():
        return str(explicit_basic).strip()

    adv_example = str(getattr(vocab, "example_en", "") or "").strip()
    adv_word = str(getattr(vocab, "advanced_word", "") or "").strip()
    simple_word = str(getattr(vocab, "simple_word", "") or "").strip()

    if adv_example and adv_word and simple_word:
        pattern = re.compile(re.escape(adv_word), flags=re.IGNORECASE)
        if pattern.search(adv_example):
            replaced = pattern.sub(simple_word.lower(), adv_example, count=1)
            return replaced[0].upper() + replaced[1:] if replaced else adv_example

    if simple_word:
        return f"People often use \"{simple_word}\" in everyday conversation."
    return adv_example


class I18nService:
    def __init__(self) -> None:
        self._translations: dict[str, dict[str, str]] = {}
        self.reload()

    def reload(self) -> None:
        for lang in SUPPORTED_LANGUAGES:
            file_path = LOCALES_DIR / f"{lang}.json"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    self._translations[lang] = json.load(f)
            else:
                self._translations[lang] = {}

    def normalize_lang(self, lang: str | None) -> str:
        if lang and lang.lower() in SUPPORTED_LANGUAGES:
            return lang.lower()
        return settings.DEFAULT_LANGUAGE

    def t(self, key: str, lang: str | None = None, **kwargs: Any) -> str:
        lang_code = self.normalize_lang(lang)
        lang_dict = self._translations.get(lang_code, {})
        fallback_dict = self._translations.get(settings.DEFAULT_LANGUAGE, {})
        template = lang_dict.get(key) or fallback_dict.get(key) or key
        if kwargs:
            kwargs.setdefault("badge", "")
            try:
                return template.format(**kwargs)
            except KeyError:
                return template
        return template

    def all_values_for_key(self, key: str) -> set[str]:
        """Return all localized strings for a given key across uz, ru, en."""
        values: set[str] = set()
        for lang in SUPPORTED_LANGUAGES:
            val = self._translations.get(lang, {}).get(key)
            if val:
                values.add(val)
        return values

    def format_word_card(
        self,
        vocab: Any,
        lang: str | None = None,
        index: int | None = None,
        total: int | None = None,
        lesson_date: str | None = None,
    ) -> str:
        lang_code = self.normalize_lang(lang)
        translation_uz = str(getattr(vocab, "translation_uz", "") or "")
        translation_ru = str(getattr(vocab, "translation_ru", "") or "")
        definition_en = str(getattr(vocab, "definition_en", "") or "")

        if lang_code == "uz":
            translation = translation_uz
            example_translation = str(getattr(vocab, "example_uz", "") or "")
        elif lang_code == "ru":
            translation = translation_ru
            example_translation = str(getattr(vocab, "example_ru", "") or "")
        else:
            translation = definition_en
            example_translation = definition_en

        raw_cat = str(getattr(vocab, "category", "everyday_upgrade") or "everyday_upgrade").lower()
        category_display = CATEGORY_LABELS.get(raw_cat, {}).get(
            lang_code, raw_cat.replace("_", " ").title()
        )

        raw_usage = getattr(vocab, "ielts_usage", None)
        ielts_usage = (
            str(raw_usage).strip()
            if raw_usage and str(raw_usage).strip()
            else DEFAULT_IELTS_USAGE_BY_CATEGORY.get(
                raw_cat, "Writing Task 2 & Speaking Part 3"
            )
        )

        basic_example_en = _derive_basic_example(vocab)

        header = ""
        if index is not None and total is not None and lesson_date is not None:
            header = (
                self.t(
                    "lesson_header",
                    lang=lang_code,
                    date=html.escape(str(lesson_date)),
                    index=index,
                    total=total,
                )
                + "\n\n"
            )

        body = self.t(
            "word_card",
            lang=lang_code,
            simple_word=html.escape(str(getattr(vocab, "simple_word", ""))),
            advanced_word=html.escape(str(getattr(vocab, "advanced_word", ""))),
            cefr_level=html.escape(str(getattr(vocab, "cefr_level", "B2–C1"))),
            category=html.escape(category_display),
            translation=html.escape(translation),
            translation_uz=html.escape(translation_uz),
            translation_ru=html.escape(translation_ru),
            definition_en=html.escape(definition_en),
            basic_example_en=html.escape(basic_example_en),
            example_en=html.escape(str(getattr(vocab, "example_en", ""))),
            example_translation=html.escape(example_translation),
            ielts_usage=html.escape(ielts_usage),
            source_name=html.escape(
                str(getattr(vocab, "source_name", "Cambridge Dictionary"))
            ),
        )
        return header + body


i18n = I18nService()
