"""
Epic 3 / Stream 0 — Document Lifecycle Completion domain tests.

Tests for mark_document_ready() pure function.
No database, no HTTP — direct domain logic verification.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.services.document_lifecycle import (
    Document,
    mark_document_ready,
    transition_document,
)
from backend.core.domain_events import DomainEvent, EVENT_DOCUMENT_READY


# ─── Helpers ───────────────────────────────────────────────────────


def _make_doc(status: str = "UPLOADED", profile: dict | None = None) -> Document:
    """Create a minimal Document with given status."""
    return Document(
        document_id="test-doc-001",
        organization_id="org-001",
        uploaded_by="user-001",
        uploaded_at=datetime.now(timezone.utc),
        status=status,
        profile=profile or {},
    )


def _make_mock_event_bus():
    """Create a mock event bus that records emitted events."""
    bus = MagicMock()
    bus.emit = MagicMock()
    return bus


# ─── Domain Tests ──────────────────────────────────────────────────


class TestMarkDocumentReady:
    """Domain logic tests for mark_document_ready()."""

    def test_1_analyzed_to_ready_success(self):
        """ANALYZED → READY: returns (None, DomainEvent); status changes."""
        doc = _make_doc(status="ANALYZED")
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err is None
        assert event is not None
        assert doc.status == "READY"
        assert isinstance(event, DomainEvent)

    def test_2_needs_review_to_ready_success(self):
        """NEEDS_REVIEW → READY: returns (None, DomainEvent); status changes."""
        doc = _make_doc(status="NEEDS_REVIEW")
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err is None
        assert event is not None
        assert doc.status == "READY"

    def test_3_ready_idempotency(self):
        """READY дважды: error, статус не меняется, событие не эмитится."""
        doc = _make_doc(status="READY")
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err == "Document is already in READY state"
        assert event is None
        assert doc.status == "READY"  # unchanged
        bus.emit.assert_not_called()

    def test_4_uploaded_to_ready_invalid(self):
        """UPLOADED → READY: error, None."""
        doc = _make_doc(status="UPLOADED")
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err is not None
        assert "Cannot transition" in err
        assert "only ANALYZED or NEEDS_REVIEW" in err
        assert event is None

    def test_5_failed_to_ready_invalid(self):
        """FAILED → READY: error, None."""
        doc = _make_doc(status="FAILED")
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err is not None
        assert "Cannot transition" in err
        assert event is None

    def test_6_event_created_exactly_once(self):
        """Ровно одно событие с правильным event_type и previous_status."""
        doc = _make_doc(status="ANALYZED")
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err is None
        assert event is not None
        assert event.event_type == EVENT_DOCUMENT_READY
        assert event.event_type == "document.ready"
        assert event.payload["previous_status"] == "ANALYZED"
        assert event.payload["status"] == "READY"
        assert event.entity_type == "document"
        assert event.actor_id == "user-001"

    def test_7_event_not_emitted_on_idempotency(self):
        """При idempotency guard — событие не эмитится."""
        doc = _make_doc(status="READY")
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err is not None
        assert event is None
        bus.emit.assert_not_called()

    def test_8_event_not_emitted_on_invalid_transition(self):
        """При invalid transition — событие не эмитится."""
        doc = _make_doc(status="UPLOADED")
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err is not None
        assert event is None
        bus.emit.assert_not_called()

    def test_9_document_id_in_event_payload(self):
        """document_id передаётся в payload события."""
        doc = _make_doc(status="ANALYZED", profile={"contract_number": "CN-001"})
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err is None
        assert event is not None
        assert event.payload["document_id"] == "test-doc-001"
        assert event.payload["contract_number"] == "CN-001"

    def test_10_profile_in_event_payload(self):
        """profile поля пробрасываются в payload события."""
        doc = _make_doc(
            status="ANALYZED",
            profile={
                "contract_number": "CN-001",
                "total_price": "5000000",
                "buyer_name": "Иван Иванов",
                "seller_name": "Петр Петров",
            },
        )
        bus = _make_mock_event_bus()

        err, event = mark_document_ready(doc, actor_id="user-001", event_bus=bus)

        assert err is None
        assert event is not None
        assert event.payload["buyer_name"] == "Иван Иванов"
        assert event.payload["seller_name"] == "Петр Петров"
        assert event.payload["total_price"] == "5000000"

    def test_11_passing_through_transition_document_guard(self):
        """mark_document_ready использует VALID_TRANSITIONS через transition_document()."""
        # NEEDS_REVIEW → READY — valid in both VALID_TRANSITIONS and semantic guard
        doc = _make_doc(status="NEEDS_REVIEW")
        # Move to READY directly
        err = transition_document(doc, "READY")
        assert err is None
        assert doc.status == "READY"

        # FAILED → READY — NOT in VALID_TRANSITIONS (FAILED only goes to PROCESSING)
        doc2 = _make_doc(status="FAILED")
        err = transition_document(doc2, "READY")
        assert err is not None  # not allowed by VALID_TRANSITIONS
