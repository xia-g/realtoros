"""Accounting domain enums — mirrors DB types. Single source of truth."""

from __future__ import annotations

import enum


class ProcessingState(str, enum.Enum):
    NEW = "new"
    RECOGNIZING = "recognizing"
    READY_FOR_DECISION = "ready_for_decision"
    DECIDING = "deciding"
    DONE = "done"
    FAILED = "failed"


class DecisionState(str, enum.Enum):
    PENDING = "pending"
    INCLUDED = "included"
    EXCLUDED = "excluded"
    REVIEW_REQUIRED = "review_required"


class RecognitionStatus(str, enum.Enum):
    PENDING = "pending"
    RECOGNIZED = "recognized"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class EventType(str, enum.Enum):
    BANK_INFLOW = "bank_inflow"
    BANK_OUTFLOW = "bank_outflow"
    SALE = "sale"
    PURCHASE = "purchase"
    CLIENT_PAYMENT = "client_payment"
    AGENT_COMMISSION = "agent_commission"
    REFUND = "refund"
    TRANSFER = "transfer"
    MANUAL = "manual"


class BatchStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SupersededReason(str, enum.Enum):
    OCR_CORRECTION = "ocr_correction"
    MANUAL_FIX = "manual_fix"
    RULE_CHANGE = "rule_change"
    DOCUMENT_UPDATED = "document_updated"
    BANK_REIMPORT = "bank_reimport"
    RECALCULATION = "recalculation"


class MatchType(str, enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"
    RULE = "rule"


class DocRole(str, enum.Enum):
    PRIMARY = "primary"
    CONFIRMING = "confirming"
    VAT = "vat"
    ATTACHMENT = "attachment"


# ── Phase 4: Tax Enums ────────────────────────────────────────────────


class TaxRegisterType(str, enum.Enum):
    KUDIR_INCOME = "KUDIR_INCOME"
    KUDIR_EXPENSE = "KUDIR_EXPENSE"
    VAT_SALES = "VAT_SALES"
    VAT_PURCHASE = "VAT_PURCHASE"
    GENERAL_INCOME = "GENERAL_INCOME"
    GENERAL_EXPENSE = "GENERAL_EXPENSE"
    EXCLUDED = "EXCLUDED"


class TaxTreatment(str, enum.Enum):
    TAXABLE = "taxable"
    DEDUCTIBLE = "deductible"
    EXEMPT = "exempt"
    EXCLUDED = "excluded"


class TaxRegime(str, enum.Enum):
    USN_D = "USN_D"
    USN_DR = "USN_DR"
    GENERAL = "GENERAL"
    PATENT = "PATENT"


class TaxReasonCode(str, enum.Enum):
    BALANCE_ACCOUNT = "balance_account"
    UNMAPPED_ACCOUNT = "unmapped_account"
    INTERNAL_TRANSFER = "internal_transfer"
    VAT_RECLAIM = "vat_reclaim"
    NON_TAXABLE_INCOME = "non_taxable_income"
    NON_DEDUCTIBLE_EXPENSE = "non_deductible_expense"
    MANUAL_EXCLUSION = "manual_exclusion"
    NO_ACTIVE_POLICY = "no_active_policy"


class TaxPeriodResolution(str, enum.Enum):
    MONTHLY = "month"
    QUARTERLY = "quarter"
    YEARLY = "year"


# ── Phase 5: Reporting Enums ───────────────────────────────────────────


class ReportStatus(str, enum.Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    AI_REVIEWED = "ai_reviewed"
    ACCOUNTANT_APPROVED = "accountant_approved"
    READY_TO_SUBMIT = "ready_to_submit"
    SUBMITTED = "submitted"


class TemplateStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    FETCHED = "fetched"
    VALIDATED = "validated"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class AuditSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AuditCategory(str, enum.Enum):
    FORMAL = "formal"
    LOGICAL = "logical"
    CONTEXTUAL = "contextual"
    CROSS_CHECK = "cross_check"


class AuditAction(str, enum.Enum):
    VERIFY = "verify"
    RECALCULATE = "recalculate"
    EXCLUDE = "exclude"
    NONE = "none"


class SubmissionFormat(str, enum.Enum):
    XML = "xml"
    JSON = "json"
    XLSX = "xlsx"


# ── Phase 6: Reconciliation Enums ───────────────────────────────────────


class ReconciliationStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    MATCHED_PARTIAL = "matched_partial"
    MATCHED_FULL = "matched_full"
    UNRESOLVED = "unresolved"
    CLOSED = "closed"


class MatchType(str, enum.Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    PARTIAL = "partial"
    UNMATCHED_LEDGER = "unmatched_ledger"
    UNMATCHED_BANK = "unmatched_bank"


class GapType(str, enum.Enum):
    MISSING_BANK_TRANSACTION = "missing_bank_transaction"
    MISSING_LEDGER_POSTING = "missing_ledger_posting"
    TIMING_DIFFERENCE = "timing_difference"
    DUPLICATE_BANK_IMPORT = "duplicate_bank_import"
    UNMATCHED_TAX_PROJECTION = "unmatched_tax_projection"
    AMOUNT_MISMATCH = "amount_mismatch"
    DIRECTION_MISMATCH = "direction_mismatch"
    DATE_MISMATCH = "date_mismatch"
    OTHER = "other"


class GapSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ExternalSystemType(str, enum.Enum):
    LEDGER = "ledger"
    BANK = "bank"
    ERP = "erp"
    PAYMENT_PROCESSOR = "payment_processor"
    CRM = "crm"
    EXTERNAL = "external"


class ItemType(str, enum.Enum):
    POSTING = "posting"
    BANK_TRANSACTION = "bank_transaction"
    TAX_REGISTER = "tax_register"
    SOURCE_EVENT = "source_event"
    INVOICE = "invoice"
    PAYMENT = "payment"
    OTHER = "other"
