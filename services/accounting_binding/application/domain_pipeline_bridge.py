"""
DomainPipelineBridge — connects v1 OCR/upload flow to v2.1 Domain pipeline.

Transforms OCR results (raw_text, entities, classification) through the full
Domain pipeline: Facts → Agreement → Identity → Evolution → Graph →
Explainability → Provenance → Revision.

All services are stateless and deterministic.
"""
from __future__ import annotations

import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Optional

# ─── A1: Facts ────────────────────────────────────────────────
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact_builder import FactBuilder
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.entity_types import EntityType as BusEntityType
from domain.business_relationship.entity_identifier import EntityIdentifier, IdentifierType

# ─── A2: Agreement ────────────────────────────────────────────
from domain.business_relationship.agreement_types import AgreementType, ParticipantRole
from domain.business_relationship.agreement_status import AgreementStatus
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_participant import AgreementParticipant
from domain.business_relationship.agreement_period import AgreementPeriod
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.agreement_resolver import AgreementResolver

# ─── A3: Identity ─────────────────────────────────────────────
from domain.business_relationship.identity_resolver import IdentityResolver

# ─── A4: Evolution ────────────────────────────────────────────
from domain.business_relationship.ke_evolution_service import KnowledgeEvolutionService

# ─── A5.1–2: Graph ────────────────────────────────────────────
from domain.business_relationship.kg_builder import GraphBuilder

# ─── A5.3: Explainability ─────────────────────────────────────
from domain.business_relationship.ke_explanation_builder import ExplanationBuilder

# ─── A5.4: Provenance ─────────────────────────────────────────
from domain.business_relationship.kg_provenance_builder import ProvenanceBuilder

# ─── A5.5: Revision ───────────────────────────────────────────
from domain.business_relationship.revision_builder import RevisionBuilder

logger = logging.getLogger(__name__)


# Maps OCR document types → Domain agreement types
DOC_TYPE_TO_AGREEMENT: dict[str, AgreementType] = {
    "contract": AgreementType.SALE,
    "sale_contract": AgreementType.SALE,
    "purchase_agreement": AgreementType.SALE,
    "dkp": AgreementType.SALE,
    "lease": AgreementType.LEASE,
    "rent": AgreementType.LEASE,
    "service": AgreementType.SERVICE,
    "act": AgreementType.SERVICE,
    "invoice": AgreementType.SERVICE,
    "payment_order": AgreementType.SERVICE,
    "municipal_contract": AgreementType.FRAMEWORK,
    "property_doc": AgreementType.UNKNOWN,
    "other": AgreementType.UNKNOWN,
}


class DomainPipelineBridge:
    """Bridge from v1 OCR/document data → v2.1 Domain Pipeline.

    Usage:
        bridge = DomainPipelineBridge()
        result = bridge.process(
            document_id="doc-xxx",
            raw_text="...",
            entities={"company": ["ООО Продавец"], ...},
            classification="contract",
            confidence=0.95,
        )
        # result.revision — KnowledgeRevision
        # result.graph — KnowledgeGraph
        # result.provenance — KnowledgeProvenance
        # result.explanation — GraphExplanation
    """

    def __init__(self) -> None:
        self._agreement_resolver = AgreementResolver()
        self._evolution_service = KnowledgeEvolutionService()
        self._graph_builder = GraphBuilder()
        self._explanation_builder = ExplanationBuilder()
        self._provenance_builder = ProvenanceBuilder()
        self._revision_builder = RevisionBuilder()

    def process(
        self,
        document_id: str,
        raw_text: str,
        entities: dict[str, Any],
        classification: str,
        confidence: float,
        semantic_type: str = "",
        document_role: str = "unknown",
    ) -> dict[str, Any]:
        """Run the full Domain pipeline on OCR results.

        Returns dict with all stage results for API serialisation.
        """
        logger.info(
            "Pipeline: doc=%s class=%s conf=%.2f role=%s",
            document_id[:8], classification, confidence, document_role,
        )

        # ── Step 1: Extract data from entities ──
        company_names: list[str] = entities.get("company", []) or entities.get("companies", []) or []
        person_names: list[str] = entities.get("persons", []) or entities.get("person", []) or []
        amounts: list[str] = entities.get("amount", []) or entities.get("amounts", []) or []
        dates_raw: list[str] = entities.get("date", []) or entities.get("dates", []) or []
        inns: list[str] = entities.get("vat_number", []) or entities.get("inn", []) or []

        # Create BusinessEntity for each party
        domain_entities: list[BusinessEntity] = []
        entity_identifiers: dict[str, list[EntityIdentifier]] = {}

        for i, name in enumerate(company_names):
            eid = f"ent-{document_id[:8]}-{i}"
            entity = BusinessEntity(
                entity_type=BusEntityType.COMPANY,
                display_name=name,
                id=eid,
                created_at=datetime.utcnow(),
            )
            domain_entities.append(entity)

            # INN if available
            idfs: list[EntityIdentifier] = []
            if i < len(inns):
                idfs.append(EntityIdentifier(
                    identifier_type=IdentifierType.INN,
                    value=inns[i],
                    entity_id=eid,
                    confidence=confidence,
                    source_document_id=document_id,
                ))
            entity_identifiers[eid] = idfs

        if not domain_entities:
            # Fallback: one generic entity
            entity = BusinessEntity(
                entity_type=BusEntityType.COMPANY,
                display_name="Неизвестная сторона",
                id=f"ent-{document_id[:8]}-0",
                created_at=datetime.utcnow(),
            )
            domain_entities.append(entity)
            entity_identifiers[entity.id] = []

        # ── Step 2: Create BusinessFacts ──
        facts = []
        for entity in domain_entities:
            facts.append(FactBuilder.document_has_party(
                document_id=document_id,
                entity_id=entity.id,
                confidence=FactConfidence.from_float(confidence),
            ))

        # Amount fact
        if amounts:
            try:
                raw = amounts[0].replace(" ", "").replace(",", ".")
                amount_val = Decimal(raw)
                facts.append(FactBuilder.build(
                    fact_type=FactType.DOCUMENT_HAS_AMOUNT,
                    subject_entity_id=domain_entities[0].id,
                    document_id=document_id,
                    value=FactValue.from_decimal(amount_val),
                    confidence=FactConfidence.from_float(confidence),
                ))
            except Exception:
                logger.warning("Cannot parse amount: %s", amounts[0])

        # Date fact
        if dates_raw:
            try:
                from dateutil import parser
                dt = parser.parse(dates_raw[0], dayfirst=True).date()
                facts.append(FactBuilder.build(
                    fact_type=FactType.DOCUMENT_HAS_DATE,
                    subject_entity_id=domain_entities[0].id,
                    document_id=document_id,
                    value=FactValue.from_date(dt),
                    confidence=FactConfidence.from_float(confidence),
                ))
            except Exception:
                logger.warning("Cannot parse date: %s", dates_raw[0])

        logger.info("Step 1–2: %d entities, %d facts", len(domain_entities), len(facts))

        # ── Step 3: Resolve Agreement ──
        agreement_type = DOC_TYPE_TO_AGREEMENT.get(classification, AgreementType.UNKNOWN)
        result_agreement = self._agreement_resolver.resolve(
            facts=facts,
            entities=domain_entities,
            document_role=document_role,
            semantic_classification=semantic_type or classification,
            existing_agreements=[],
        )

        agreement = result_agreement.agreement
        if agreement is None:
            # Create agreement manually from classified data
            agreement_id = AgreementId.from_string(f"agr-{document_id[:12]}")
            participants = []
            for entity in domain_entities:
                participants.append(AgreementParticipant(
                    agreement_id=agreement_id,
                    entity_id=entity.id,
                    participant_role=ParticipantRole.UNKNOWN,
                ))

            # Parse amount from facts
            amt = Decimal("0")
            for f in facts:
                if f.fact_type == FactType.DOCUMENT_HAS_AMOUNT and f.value and f.value.numeric:
                    amt = f.value.numeric
                    break

            agreement = Agreement(
                agreement_type=agreement_type,
                id=agreement_id,
                number=f"OCR-{document_id[:8]}",
                date=date.today(),
                amount=amt,
                currency="RUB",
                status=AgreementStatus.ACTIVE,
                period=AgreementPeriod(start_date=date.today()),
                participants=tuple(participants),
            )

        logger.info("Step 3: agreement=%s type=%s", agreement.number, agreement.agreement_type.value)

        # ── Step 4: Canonical Identity ──
        canonical_entities = []
        for entity in domain_entities:
            idfs = entity_identifiers.get(entity.id, [])
            result = IdentityResolver.resolve(
                entity=entity,
                identifiers=idfs,
                document_id=document_id,
                existing_entities=[],
            )
            if result.entity is not None:
                canonical_entities.append(result.entity)

        logger.info("Step 4: %d canonical entities resolved", len(canonical_entities))

        # ── Step 5: Knowledge Evolution ──
        evolution_results = []
        for ce in canonical_entities:
            ev = self._evolution_service.evolve(
                entity=ce,
                facts=facts,
                agreement=agreement,
            )
            evolution_results.append(ev)

        logger.info("Step 5: %d evolution results", len(evolution_results))

        # ── Step 6: Knowledge Graph ──
        graph_result = self._graph_builder.build(
            entities=canonical_entities,
            agreements=[agreement],
            facts=facts,
        )
        graph = graph_result.graph
        logger.info("Step 6: graph=%d nodes", graph.node_count)

        # ── Step 7: Explainability ──
        first_node = graph.nodes[0] if graph.nodes else None
        explanation = None
        if first_node and canonical_entities:
            exp_result = self._explanation_builder.build(
                graph_node_id=first_node.node_id,
                entity=canonical_entities[0],
                agreement=agreement,
                facts=facts,
            )
            explanation = exp_result.explanation
            logger.info("Step 7: explanation=%d steps", explanation.step_count if explanation else 0)

        # ── Step 8: Provenance ──
        provenance_result = self._provenance_builder.build(
            graph=graph,
            entity=canonical_entities[0] if canonical_entities else None,
            agreement=agreement,
            facts=facts,
        )
        provenance = provenance_result.provenance
        logger.info("Step 8: provenance=%d links", len(provenance.chain.links))

        # ── Step 9: Knowledge Revision ──
        revision_result = self._revision_builder.build(
            graph=graph,
            provenance=provenance,
            explanation=explanation,
            revision_number=1,
            created_by="document-intake",
            reason=f"OCR document: {classification}",
            document_count=1,
            entity_count=len(canonical_entities),
        )
        revision = revision_result.revision
        logger.info("Step 9: revision=#%d snapshot=%d nodes",
                     revision.revision_number.number, revision.snapshot.total_nodes)

        return {
            "document_id": document_id,
            "classification": classification,
            "confidence": confidence,
            "facts_count": len(facts),
            "entities_count": len(domain_entities),
            "canonical_entities_count": len(canonical_entities),
            "agreement": {
                "number": agreement.number,
                "type": agreement.agreement_type.value,
                "status": agreement.status.value,
            },
            "graph": {
                "node_count": graph.node_count,
                "edge_count": graph.edge_count,
            },
            "explanation_steps": explanation.step_count if explanation else 0,
            "provenance_links": len(provenance.chain.links),
            "revision": {
                "id": revision.revision_id.value,
                "number": revision.revision_number.number,
                "snapshot": revision.snapshot,
            },
            "pipeline_status": "completed",
        }
