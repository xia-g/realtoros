"""Document processing pipeline — end-to-end orchestration.

Flow: Document -> OCR -> Classify -> Extract -> Resolve -> Graph -> Embed

Every step shares a correlation_id for traceability across the entire pipeline.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import UUID

from backend.ai.ocr import OCRService, OCRProvider
from backend.ai.classifier import DocumentClassifier
from backend.ai.extraction import EntityExtractionService
from backend.ai.resolution import EntityResolutionService
from backend.ai.graph import KnowledgeGraphBuilder
from backend.ai.embeddings import EmbeddingPipeline
from backend.core.context import get_request_context
from backend.core.logging import get_logger

logger = get_logger("knowledge")


class DocumentPipeline:
    """Orchestrate end-to-end document processing with full traceability."""

    def __init__(self, session):
        self.session = session
        self.ocr = OCRService()
        self.classifier = DocumentClassifier()
        self.extractor = EntityExtractionService()
        self.resolver = EntityResolutionService(session)
        self.graph = KnowledgeGraphBuilder(session)
        self.embeddings = EmbeddingPipeline(session)

    async def process(
        self,
        document_id: UUID,
        file_path: str,
        filename: str = "",
        correlation_id: str | None = None,
    ) -> dict:
        """Process a document through the full pipeline.

        Args:
            document_id: UUID of the document record
            file_path: absolute path to the file on disk
            filename: original filename for classification hints
            correlation_id: trace ID shared across all pipeline steps.
                If None, reads from request context or generates a new one.
        """
        # Resolve correlation_id: explicit > request context > new
        if correlation_id is None:
            ctx = get_request_context()
            if ctx and ctx.correlation_id:
                correlation_id = ctx.correlation_id
            else:
                correlation_id = uuid.uuid4().hex[:16]

        from backend.repositories import DocumentRepository
        doc_repo = DocumentRepository(self.session)
        doc = await doc_repo.get(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        metadata = {
            "steps": {},
            "document_id": str(document_id),
            "correlation_id": correlation_id,
        }

        try:
            # Step 1: OCR
            logger.info(
                "ocr_started",
                document_id=str(document_id),
                correlation_id=correlation_id,
            )
            ocr_result = await self.ocr.extract(file_path)
            metadata["steps"]["ocr"] = {
                "pages": ocr_result.page_count,
                "confidence": round(ocr_result.confidence, 3),
                "provider": ocr_result.provider,
                "correlation_id": correlation_id,
            }
            logger.info(
                "ocr_completed",
                document_id=str(document_id),
                pages=ocr_result.page_count,
                confidence=round(ocr_result.confidence, 3),
                correlation_id=correlation_id,
            )

            if not ocr_result.text:
                metadata["error"] = "No text extracted"
                logger.warning("ocr_empty_result", document_id=str(document_id), correlation_id=correlation_id)
                return metadata

            # Step 2: Chunk
            from backend.models.document_chunk import DocumentChunk
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content=ocr_result.text[:50000],
                metadata={"pages": ocr_result.page_count, "correlation_id": correlation_id},
            )
            self.session.add(chunk)
            await self.session.flush()

            # Step 3: Classify
            logger.info("classification_started", document_id=str(document_id), correlation_id=correlation_id)
            classification = await self.classifier.classify(ocr_result.text, filename)
            await doc_repo.update(document_id, doc_type=classification.document_type)
            metadata["steps"]["classification"] = {
                "type": classification.document_type,
                "confidence": classification.confidence,
                "needs_review": classification.needs_review,
                "correlation_id": correlation_id,
            }
            logger.info(
                "classification_completed",
                document_id=str(document_id),
                doc_type=classification.document_type,
                correlation_id=correlation_id,
            )

            # Step 4: Extract entities
            logger.info("extraction_started", document_id=str(document_id), correlation_id=correlation_id)
            entities = await self.extractor.extract(ocr_result.text, classification.document_type)
            metadata["steps"]["extraction"] = {
                "persons": len(entities.persons),
                "properties": len(entities.properties),
                "deals": len(entities.deals),
                "correlation_id": correlation_id,
            }
            logger.info(
                "extraction_completed",
                document_id=str(document_id),
                entities=len(entities.persons) + len(entities.properties),
                correlation_id=correlation_id,
            )

            # Step 5: Resolve
            logger.info("resolution_started", document_id=str(document_id), correlation_id=correlation_id)
            resolved = []
            for person in entities.persons:
                match = await self.resolver.resolve_person(
                    person.get("full_name", ""),
                    person.get("phone", ""),
                    person.get("email", ""),
                )
                resolved.append({
                    "entity_type": "person",
                    "target_id": str(match.target_id) if match.target_id else None,
                    "confidence": match.confidence,
                    "auto_link": match.auto_link,
                    "correlation_id": correlation_id,
                })
            metadata["steps"]["resolution"] = {"resolved": resolved, "correlation_id": correlation_id}
            logger.info(
                "resolution_completed",
                document_id=str(document_id),
                resolved=len(resolved),
                correlation_id=correlation_id,
            )

            # Step 6: Graph
            logger.info("graph_step_started", document_id=str(document_id), correlation_id=correlation_id)
            await self.graph._upsert_node("document", document_id, filename or f"Doc #{document_id}")
            for person in entities.persons:
                if person.get("full_name"):
                    cl = await self.resolver.resolve_person(person["full_name"])
                    if cl.target_id:
                        await self.graph._upsert_node("client", cl.target_id, person["full_name"])
                        await self.graph._upsert_edge(
                            document_id, cl.target_id, "refers_to",
                            source_type="document", target_type="client",
                        )
            metadata["steps"]["graph"] = {"nodes_updated": len(entities.persons) + 1, "correlation_id": correlation_id}
            logger.info(
                "graph_step_completed",
                document_id=str(document_id),
                correlation_id=correlation_id,
            )

            # Step 7: Embed
            logger.info("embedding_started", document_id=str(document_id), correlation_id=correlation_id)
            embedded = await self.embeddings.embed_chunks(document_id)
            metadata["steps"]["embedding"] = {"chunks_embedded": embedded, "correlation_id": correlation_id}
            logger.info(
                "embedding_completed",
                document_id=str(document_id),
                embedded=embedded,
                correlation_id=correlation_id,
            )

            metadata["status"] = "completed"
            metadata["correlation_id"] = correlation_id
            return metadata

        except Exception as e:
            metadata["status"] = "failed"
            metadata["error"] = str(e)
            metadata["correlation_id"] = correlation_id
            logger.exception(
                "pipeline_failed",
                document_id=str(document_id),
                error=str(e),
                correlation_id=correlation_id,
            )
            return metadata
