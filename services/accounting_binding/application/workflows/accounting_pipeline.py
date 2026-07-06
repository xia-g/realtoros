"""
Application — Accounting Pipeline (orchestration).

Pipeline декларативный:
1. enrich → validate → map (всегда синхронно)
2. policy.evaluate → approval (решение: approve/review/reject)
3. optionally → execute_posting() (может быть async/queue/batch)

Domain остаётся чистым — вся координация здесь.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from contracts import (
    AccountingDocument,
    DocumentStatus,
    EnrichedDocument,
    JournalEntry,
    NormalizedDocument,
    PostingResult,
)
from domain.approval.policy import ApprovalDecision, ApprovalPolicy
from domain.approval.workflow import ApprovalAction, ApprovalWorkflow
from domain.enrichment.enricher import DocumentEnricher
from domain.mapping.mapper import AccountingMapper
from domain.posting.poster import PostingResult2, PostingService
from domain.reporting.service import ReportingService
from domain.validation.validators import (
    AccountingDocumentValidator,
    EnrichedDocumentValidator,
    ValidationResult,
)


@dataclass
class PipelineResult:
    """Результат полного цикла обработки."""
    success: bool
    enriched: EnrichedDocument | None = None
    validation: ValidationResult | None = None
    accounting: AccountingDocument | None = None
    journal_entry: JournalEntry | None = None
    decision: ApprovalDecision = ApprovalDecision.REVIEW
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AccountingPipeline:
    """Оркестратор полного цикла.

    run() — enrich → validate → map → evaluate (подготовка)
    execute_posting() — approve → post (может быть async/queue)

    Такой split позволяет:
    - synchronous ingestion + async posting
    - batch approval + posting
    - ручное approve + pipeline post
    """

    def __init__(
        self,
        enricher: DocumentEnricher,
        enriched_validator: EnrichedDocumentValidator,
        mapper: AccountingMapper,
        accounting_validator: AccountingDocumentValidator,
        approval_policy: ApprovalPolicy,
        approval_workflow: ApprovalWorkflow,
        posting: PostingService,
        reporting: ReportingService | None = None,
    ):
        self._enricher = enricher
        self._enriched_validator = enriched_validator
        self._mapper = mapper
        self._accounting_validator = accounting_validator
        self._policy = approval_policy
        self._approval = approval_workflow
        self._posting = posting
        self._reporting = reporting

    async def run(self, doc: NormalizedDocument) -> PipelineResult:
        """Pipeline: enrich → validate → map → policy.evaluate.
        
        НЕ выполняет posting. Для posting вызвать execute_posting().
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Enrichment
        enrich_result = await self._enricher.enrich(doc)
        enriched = enrich_result.enriched
        warnings.extend(enrich_result.warnings)

        # 2. Validation (enriched)
        validation = self._enriched_validator.validate(enriched)
        if not validation.is_valid:
            return PipelineResult(
                success=False, enriched=enriched,
                validation=validation,
                errors=[v.message for v in validation.errors],
                warnings=warnings,
            )

        # 3. Mapping
        map_result = await self._mapper.map(enriched)
        accounting = map_result.accounting_document
        warnings.extend(map_result.warnings)

        # 4. Validation (accounting)
        acc_validation = self._accounting_validator.validate(accounting)
        if not acc_validation.is_valid:
            return PipelineResult(
                success=False, enriched=enriched,
                validation=validation, accounting=accounting,
                errors=[v.message for v in acc_validation.errors],
                warnings=warnings,
            )

        # 5. Approval policy (declarative, без transition)
        decision = self._policy.evaluate(validation, enriched, accounting)
        warnings.append(f"Approval decision: {decision.value}")

        return PipelineResult(
            success=True,
            enriched=enriched,
            validation=validation,
            accounting=accounting,
            decision=decision,
            errors=errors,
            warnings=warnings,
        )

    async def execute_posting(
        self,
        accounting: AccountingDocument,
        by_user: str = "pipeline",
    ) -> PipelineResult:
        """Approval → Posting.

        Может вызываться:
        - сразу после run() для auto-approve
        - отдельно после ручного approve (через UI)
        - из очереди / batch / scheduler
        """
        warnings: list[str] = []

        # 1. SUBMIT + REVIEW + APPROVE
        try:
            submitted, _ = self._approval.apply(
                accounting, ApprovalAction.SUBMIT, by_user=by_user,
            )
            reviewed, _ = self._approval.apply(
                submitted, ApprovalAction.REQUEST_REVIEW, by_user=by_user,
            )
            approved, _ = self._approval.apply(
                reviewed, ApprovalAction.APPROVE, by_user=by_user,
            )
        except Exception as e:
            return PipelineResult(
                success=False, accounting=accounting,
                errors=[str(e)], warnings=warnings,
            )

        # 2. Posting
        if approved.status == DocumentStatus.APPROVED:
            post_result = await self._posting.post(approved)
            if post_result.result in (PostingResult.POSTED, PostingResult.DUPLICATE):
                return PipelineResult(
                    success=True,
                    accounting=approved,
                    journal_entry=post_result.entry,
                    errors=[],
                    warnings=warnings + post_result.warnings,
                )
            else:
                return PipelineResult(
                    success=False, accounting=approved,
                    errors=post_result.warnings, warnings=warnings,
                )

        return PipelineResult(
            success=False, accounting=approved,
            errors=["Не удалось перевести документ в APPROVED"],
            warnings=warnings,
        )
