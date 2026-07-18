"""
SimilarityScorer — weighted scoring with explainable MatchingEvidence.

Получает TransactionFingerprint + CandidateTransaction.
Возвращает SimilarityResult с score, confidence и evidence.

Не занимается поиском.
"""
from __future__ import annotations

from decimal import Decimal

from domain.deal_resolution.fingerprint import (
    TransactionFingerprint,
    SimilarityResult,
    MatchingEvidence,
    ConfidenceLevel,
)
from domain.deal_resolution.candidate_finder import CandidateTransaction


class SimilarityScorer:
    """Вычисляет схожесть fingerprint'а с кандидатом."""

    # Веса конфигурируемы
    WEIGHTS: dict[str, float] = {
        "cadastral_number": 45.0,
        "normalized_address": 20.0,
        "transaction_type": 15.0,
        "transaction_direction": 10.0,
        "parties": 10.0,
        "contract_date": 5.0,
        "amount": 5.0,
    }

    CONFIDENCE_THRESHOLDS = {
        ConfidenceLevel.HIGH: 95.0,
        ConfidenceLevel.MEDIUM: 80.0,
        # below 80 = LOW
    }

    def __init__(self, weights: dict[str, float] | None = None):
        if weights:
            self.WEIGHTS = {**self.WEIGHTS, **weights}
        total = sum(self.WEIGHTS.values())
        self._normalized_weights = {k: v / total for k, v in self.WEIGHTS.items()} if total > 0 else self.WEIGHTS

    async def score(
        self,
        fp: TransactionFingerprint,
        candidate: CandidateTransaction,
    ) -> SimilarityResult:
        """Вычислить схожесть с объяснением."""
        evidence: list[MatchingEvidence] = []
        total_score = 0.0

        # 1. Cadastral number (45%)
        cadastral_field = fp.property_identity.cadastral_number if fp.property_identity else ""
        c_cadastral = candidate.cadastral_number
        matched = bool(cadastral_field) and cadastral_field == c_cadastral
        evidence.append(MatchingEvidence(
            field="cadastral_number",
            document_value=cadastral_field,
            candidate_value=c_cadastral,
            weight=self.WEIGHTS["cadastral_number"],
            matched=matched,
        ))
        if matched:
            total_score += self.WEIGHTS["cadastral_number"]

        # 2. Address (20%)
        address = fp.property_identity.normalized_address if fp.property_identity else ""
        c_addr = candidate.address
        addr_match = bool(address) and bool(c_addr)
        if addr_match:
            # Normalize both
            from domain.property.property_identity import PropertyIdentity
            n_addr = PropertyIdentity.normalize_address(address)
            n_c_addr = PropertyIdentity.normalize_address(c_addr)
            addr_match = n_addr == n_c_addr or (
                len(set(n_addr.split()) & set(n_c_addr.split())) / max(len(set(n_c_addr.split())), 1) > 0.8
            )
        evidence.append(MatchingEvidence(
            field="normalized_address",
            document_value=address,
            candidate_value=c_addr,
            weight=self.WEIGHTS["normalized_address"],
            matched=addr_match,
        ))
        if addr_match:
            total_score += self.WEIGHTS["normalized_address"]

        # 3. Transaction type (15%)
        # Map document roles to deal types for comparison
        ROLE_TO_DEAL_TYPE = {
            "sale_contract": "purchase",
            "transfer_act": "purchase",
            "egrn_extract": "registration",
            "payment_order": "payment",
            "invoice": "payment",
            "receipt": "expense",
        }
        doc_deal_type = ROLE_TO_DEAL_TYPE.get(fp.transaction_type, fp.transaction_type)
        cand_deal_type = candidate.deal_type
        type_match = bool(fp.transaction_type) and doc_deal_type == cand_deal_type
        evidence.append(MatchingEvidence(
            field="transaction_type",
            document_value=fp.transaction_type,
            candidate_value=candidate.deal_type,
            weight=self.WEIGHTS["transaction_type"],
            matched=type_match,
        ))
        if type_match:
            total_score += self.WEIGHTS["transaction_type"]

        # 4. Transaction direction (10%)
        dir_match = bool(fp.transaction_direction)
        # Для кандидата direction определяется по deal_type + parties
        c_dir = "purchase" if candidate.deal_type in ("purchase",) else candidate.deal_type
        dir_match = dir_match and fp.transaction_direction == c_dir
        evidence.append(MatchingEvidence(
            field="transaction_direction",
            document_value=fp.transaction_direction,
            candidate_value=c_dir,
            weight=self.WEIGHTS["transaction_direction"],
            matched=dir_match,
        ))
        if dir_match:
            total_score += self.WEIGHTS["transaction_direction"]

        # 5. Parties (10%)
        party_match = False
        if fp.buyer or fp.seller:
            c_buyer = candidate.buyer or ""
            c_seller = candidate.seller or ""
            if (fp.buyer and c_buyer and fp.buyer.lower() in c_buyer.lower()) or \
               (fp.seller and c_seller and fp.seller.lower() in c_seller.lower()):
                party_match = True
        evidence.append(MatchingEvidence(
            field="parties",
            document_value=f"buyer={fp.buyer}, seller={fp.seller}",
            candidate_value=f"buyer={candidate.buyer}, seller={candidate.seller}",
            weight=self.WEIGHTS["parties"],
            matched=party_match,
        ))
        if party_match:
            total_score += self.WEIGHTS["parties"]

        # 6. Date proximity (5%)
        date_match = False
        if fp.contract_date:
            c_date = candidate.contract_date
            if c_date:
                delta = abs((fp.contract_date - c_date).days)
                date_match = delta <= 30
        evidence.append(MatchingEvidence(
            field="contract_date",
            document_value=str(fp.contract_date) if fp.contract_date else "",
            candidate_value=str(candidate.contract_date) if candidate.contract_date else "",
            weight=self.WEIGHTS["contract_date"],
            matched=date_match,
        ))
        if date_match:
            total_score += self.WEIGHTS["contract_date"]

        # 7. Amount proximity (5%)
        amount_match = False
        if fp.amount > 0:
            c_amount = Decimal(str(candidate.amount))
            if c_amount > 0:
                ratio = min(fp.amount, c_amount) / max(fp.amount, c_amount)
                amount_match = ratio >= 0.8
        evidence.append(MatchingEvidence(
            field="amount",
            document_value=str(fp.amount),
            candidate_value=str(candidate.amount),
            weight=self.WEIGHTS["amount"],
            matched=amount_match,
        ))
        if amount_match:
            total_score += self.WEIGHTS["amount"]

        # Determine confidence
        if total_score >= self.CONFIDENCE_THRESHOLDS[ConfidenceLevel.HIGH]:
            confidence = ConfidenceLevel.HIGH
        elif total_score >= self.CONFIDENCE_THRESHOLDS[ConfidenceLevel.MEDIUM]:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

        return SimilarityResult(
            score=round(total_score, 2),
            confidence=confidence,
            evidence=evidence,
        )
