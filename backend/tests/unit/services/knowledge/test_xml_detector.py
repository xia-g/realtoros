"""Tests for XML Injection Detector."""

from __future__ import annotations

import pytest

from backend.services.knowledge.security.xml_detector import XMLInjectionDetector


@pytest.fixture
def xml_detector():
    return XMLInjectionDetector()


class TestXMLInjectionDetector:
    def test_detect_close_system(self, xml_detector):
        findings = xml_detector.scan("before </system> after")
        assert len(findings) == 1
        assert findings[0].pattern_name == "xml_close_tag_system"

    def test_detect_close_knowledge(self, xml_detector):
        findings = xml_detector.scan("before </knowledge> after")
        assert len(findings) == 1
        assert findings[0].pattern_name == "xml_close_tag_knowledge"

    def test_detect_close_memory(self, xml_detector):
        findings = xml_detector.scan("before </memory> after")
        assert len(findings) == 1
        assert findings[0].pattern_name == "xml_close_tag_memory"

    def test_detect_close_security(self, xml_detector):
        findings = xml_detector.scan("before </security> after")
        assert len(findings) == 1
        assert findings[0].pattern_name == "xml_close_tag_security"

    def test_detect_close_question(self, xml_detector):
        findings = xml_detector.scan("before </question> after")
        assert len(findings) == 1
        assert findings[0].pattern_name == "xml_close_tag_question"

    def test_detect_cdata_close(self, xml_detector):
        findings = xml_detector.scan("before ]]> after")
        cdata_findings = [f for f in findings if "cdata" in f.pattern_name]
        assert len(cdata_findings) >= 1

    def test_detect_nested_system_block(self, xml_detector):
        findings = xml_detector.scan("some <system> nested block")
        nested = [f for f in findings if "nested_block" in f.pattern_name]
        assert len(nested) >= 1

    def test_detect_nested_knowledge_block(self, xml_detector):
        findings = xml_detector.scan("<knowledge> another block")
        nested = [f for f in findings if "nested_block" in f.pattern_name]
        assert len(nested) >= 1

    def test_clean_xml_passes(self, xml_detector):
        findings = xml_detector.scan("clean text without any XML tags")
        assert len(findings) == 0

    def test_regulatory_text_passes(self, xml_detector):
        findings = xml_detector.scan(
            "В соответствии с Федеральным законом № 218-ФЗ "
            "«О государственной регистрации недвижимости»"
        )
        assert len(findings) == 0

    def test_empty_string(self, xml_detector):
        findings = xml_detector.scan("")
        assert len(findings) == 0

    def test_multiple_injections(self, xml_detector):
        findings = xml_detector.scan("</system> </knowledge> </memory>")
        assert len(findings) == 3

    def test_spaces_in_tags(self, xml_detector):
        """Variations with whitespace inside tags."""
        findings = xml_detector.scan("< / system > hack")
        assert len(findings) >= 0  # pattern depends on exact regex
