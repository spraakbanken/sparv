"""Unit tests for LanguageRegistry."""

from __future__ import annotations

import pytest

from sparv.core.registry import LanguageRegistry


@pytest.fixture
def language_registry() -> LanguageRegistry:
    """Fixture for LanguageRegistry."""  # noqa: DOC201
    return LanguageRegistry()


class TestLanguageRegistry:
    """Test class for LanguageRegistry."""

    @staticmethod
    def check(tested: str | None, expected: str) -> None:
        """Check if the tested value is equal to the expected value."""
        assert tested == expected

    @pytest.mark.parametrize(("lang", "expected"), [("swe", "Swedish"), ("xxx", "xxx")])
    @pytest.mark.unit
    @pytest.mark.noexternal
    def test_add_language_succeeds(self, language_registry: LanguageRegistry, lang: str, expected: str) -> None:
        """Test that adding a language succeeds."""
        res = language_registry.add_language(lang)
        self.check(res, expected)
        self.check(language_registry[lang], expected)
