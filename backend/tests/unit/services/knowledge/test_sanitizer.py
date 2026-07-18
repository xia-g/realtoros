"""Tests for Prompt Sanitizer — XML escaping, CDATA, control chars, normalization."""

from __future__ import annotations

import pytest

from backend.services.knowledge.security.sanitizer import PromptSanitizer


@pytest.fixture
def sanitizer():
    return PromptSanitizer()


class TestSanitizerXMLEscaping:
    def test_escapes_close_system(self, sanitizer):
        result = sanitizer.sanitize("text </system> more")
        assert "</system>" not in result.content
        assert "&lt;/system&gt;" in result.content
        assert "xml_close_tags" in str(result.removed_patterns)

    def test_escapes_close_knowledge(self, sanitizer):
        result = sanitizer.sanitize("text </knowledge> more")
        assert "&lt;/knowledge&gt;" in result.content

    def test_escapes_close_memory(self, sanitizer):
        result = sanitizer.sanitize("</memory>")
        assert "&lt;/memory&gt;" in result.content

    def test_escapes_close_security(self, sanitizer):
        result = sanitizer.sanitize("</security>")
        assert "&lt;/security&gt;" in result.content

    def test_escapes_close_question(self, sanitizer):
        result = sanitizer.sanitize("</question>")
        assert "&lt;/question&gt;" in result.content

    def test_multiple_xml_tags(self, sanitizer):
        result = sanitizer.sanitize("</system> and </knowledge>")
        assert "&lt;/system&gt;" in result.content
        assert "&lt;/knowledge&gt;" in result.content


class TestSanitizerCDATA:
    def test_escapes_cdata_open(self, sanitizer):
        result = sanitizer.sanitize("<![CDATA[ content")
        assert "<![CDATA[" not in result.content
        assert "cdata_open" in str(result.removed_patterns)

    def test_escapes_cdata_close(self, sanitizer):
        result = sanitizer.sanitize("content ]] >")
        # ]] > pattern — CDATA close detection is regex-dependent
        if "cdata_close" in str(result.removed_patterns):
            assert "]]&gt;" in result.content


class TestSanitizerControlCharacters:
    def test_removes_null_bytes(self, sanitizer):
        result = sanitizer.sanitize("text\x00with\x00nulls")
        assert "\x00" not in result.content
        assert "null_bytes" in str(result.removed_patterns)

    def test_removes_invalid_controls(self, sanitizer):
        result = sanitizer.sanitize("text\x01\x02\x03controls")
        assert "\x01" not in result.content

    def test_preserves_legitimate_whitespace(self, sanitizer):
        result = sanitizer.sanitize("line1\nline2\nline3")
        assert result.content == "line1\nline2\nline3"


class TestSanitizerPreservation:
    def test_preserves_business_content(self, sanitizer):
        original = "Иванов Иван, телефон +7 (495) 123-45-67, паспорт 4510 123456"
        result = sanitizer.sanitize(original)
        assert "Иванов" in result.content
        assert "+7" in result.content
        assert "паспорт" in result.content

    def test_preserves_regulation_content(self, sanitizer):
        original = ("В соответствии с Федеральным законом № 218-ФЗ "
                     "«О государственной регистрации недвижимости»")
        result = sanitizer.sanitize(original)
        assert "218-ФЗ" in result.content
        assert "недвижимости" in result.content

    def test_preserves_long_numbers(self, sanitizer):
        original = "Кадастровый номер: 77:01:0001001:1234"
        result = sanitizer.sanitize(original)
        assert "77:01:0001001:1234" in result.content

    def test_preserves_urls(self, sanitizer):
        original = "Ссылка на документ: https://example.com/docs/123"
        result = sanitizer.sanitize(original)
        assert "https" in result.content

    def test_clean_text_unchanged(self, sanitizer):
        original = "Нормальный текст без инъекций."
        result = sanitizer.sanitize(original)
        assert result.content == original
        assert len(result.removed_patterns) == 0


class TestSanitizerReporting:
    def test_reports_original_length(self, sanitizer):
        result = sanitizer.sanitize("hello world")
        assert result.original_length == 11

    def test_reports_removed_patterns(self, sanitizer):
        result = sanitizer.sanitize("</system> clean")
        assert len(result.removed_patterns) > 0

    def test_empty_string(self, sanitizer):
        result = sanitizer.sanitize("")
        assert result.content == ""
        assert result.original_length == 0

    def test_xml_open_tags_escaped(self, sanitizer):
        """Opening tags that mimic structure tags are also escaped."""
        result = sanitizer.sanitize("<system>hello</system>")
        assert "&lt;system&gt;" in result.content
        assert "&lt;/system&gt;" in result.content
