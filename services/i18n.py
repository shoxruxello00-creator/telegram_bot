import html
import json
from pathlib import Path
from typing import Any
from config import SUPPORTED_LANGUAGES, settings

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


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
        if lang_code == "uz":
            translation = getattr(vocab, "translation_uz", "")
            example_translation = getattr(vocab, "example_uz", "")
        elif lang_code == "ru":
            translation = getattr(vocab, "translation_ru", "")
            example_translation = getattr(vocab, "example_ru", "")
        else:
            translation = getattr(vocab, "definition_en", "")
            example_translation = getattr(vocab, "definition_en", "")

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
            cefr_level=html.escape(str(getattr(vocab, "cefr_level", "C1"))),
            category=html.escape(str(getattr(vocab, "category", "Idiom"))),
            translation=html.escape(str(translation)),
            definition_en=html.escape(str(getattr(vocab, "definition_en", ""))),
            example_en=html.escape(str(getattr(vocab, "example_en", ""))),
            example_translation=html.escape(str(example_translation)),
            source_name=html.escape(
                str(getattr(vocab, "source_name", "Cambridge Dictionary"))
            ),
        )
        return header + body


i18n = I18nService()
