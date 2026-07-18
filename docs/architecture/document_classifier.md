# Document Classification Subsystem

## Overview

Classifies uploaded documents into expected types after OCR extraction. The classifier sits between the OCR pipeline and the field extraction service.

```
OCR Pipeline → Document Classifier → Field Extraction → Storage
```

## Expected Document Types

| # | Type (English) | Type (Russian) | High-level Category | Estimated Frequency |
|---|----------------|----------------|---------------------|-------------------|
| 1 | Sale contract | Договор купли-продажи | contract | High |
| 2 | Agency contract | Агентский договор | contract | Medium |
| 3 | Rental contract | Договор аренды | contract | High |
| 4 | Passport | Паспорт РФ | passport | Medium |
| 5 | EGRN extract | Выписка ЕГРН | extract | High |
| 6 | Receipt | Квитанция / чек об оплате | receipt | Medium |
| 7 | Power of attorney | Доверенность | other | Low |

## Classification Strategy

### Pipeline

```
Raw Image / OCR Text
    │
    ▼
┌─────────────────────────────────────────────┐
│  Stage 1: Rule-based Classifier             │
│  (fast, no model, 0 cost)                   │
│  ├─ File extension check                    │
│  ├─ MIME type check                         │
│  ├─ File name keyword match                 │
│  ├─ Page count check                        │
│  └─ Layout structure check (tables ratio)   │
│                                             │
│  Result: direct match → return              │
│  Result: ambiguous → Stage 2                │
└─────────────────────────────────────────────┘
    │ (ambiguous)
    ▼
┌─────────────────────────────────────────────┐
│  Stage 2: ML-based Classifier               │
│  (fasttext / tf-idf + SVM, 50 ms)           │
│  ├─ TF-IDF vectorize OCR text               │
│  ├─ Match against keyword profiles          │
│  ├─ Layout feature comparison               │
│  └─ SVM or fastText classifier              │
│                                             │
│  Result: confidence > 0.85 → return         │
│  Result: confidence 0.60–0.85 → Stage 3     │
│  Result: confidence < 0.60 → Stage 3        │
└─────────────────────────────────────────────┘
    │ (low confidence)
    ▼
┌─────────────────────────────────────────────┐
│  Stage 3: LLM-based Classifier              │
│  (DeepSeek Flash, 2–5 sec)                  │
│  ├─ Prompt with full OCR text               │
│  ├─ Returns JSON: {type, confidence, reason}│
│  └─ Structured output via Pydantic schema   │
│                                             │
│  Result: confidence > 0.80 → return         │
│  Result: confidence < 0.80 → manual review  │
└─────────────────────────────────────────────┘
    │ (all failed)
    ▼
┌─────────────────────────────────────────────┐
│  Manual Review (Telegram notification)       │
│  ├─ Flagged in admin panel                  │
│  ├─ Telegram message to agent               │
│  └─ Agent selects type via inline buttons   │
└─────────────────────────────────────────────┘
```

### Stage 1: Rule-based Classifier

Fast, zero-cost checks using file metadata and OCR text heuristics.

```python
class RuleClassifier:
    """Stage 1: rule-based document classification."""

    RULES = {
        "passport": {
            "file_extensions": {".jpg", ".jpeg", ".png"},
            "page_count": (1, 2),
            "mime_types": {"image/jpeg", "image/png"},
            "keywords": {
                "паспорт", "паспорт рф", "удостоверение личности",
                "орган", "выдан", "подпись владельца",
            },
            "min_area_keyword_ratio": 0.15,
            # Passports have 2 fixed pages, no tables
            "layout_signature": "dense_text_no_tables",
        },
        "egrn_extract": {
            "file_extensions": {".pdf"},
            "page_count": (1, 10),
            "mime_types": {"application/pdf"},
            "keywords": {
                "выписка", "егрн", "единый государственный реестр",
                "кадастровый номер", "объект недвижимости",
                "правообладатель", "вид права", "обременение",
            },
            "layout_signature": "tabular_with_text",
        },
        "sale_contract": {
            "file_extensions": {".pdf"},
            "page_count": (2, 20),
            "mime_types": {"application/pdf"},
            "keywords": {
                "договор купли-продажи", "продавец", "покупатель",
                "цена договора", "переход права собственности",
                "регистрация", "росреестр",
            },
            "layout_signature": "dense_text_legal",
        },
        "agency_contract": {
            "file_extensions": {".pdf"},
            "page_count": (2, 15),
            "mime_types": {"application/pdf"},
            "keywords": {
                "агентский договор", "агент", "принципал",
                "вознаграждение", "услуги", "поручение",
            },
            "layout_signature": "dense_text_legal",
        },
        "rental_contract": {
            "file_extensions": {".pdf"},
            "page_count": (2, 15),
            "mime_types": {"application/pdf"},
            "keywords": {
                "договор аренды", "арендодатель", "арендатор",
                "арендная плата", "срок аренды", "помещение",
                "квартира", "найм",
            },
            "layout_signature": "dense_text_legal",
        },
        "receipt": {
            "file_extensions": {".jpg", ".jpeg", ".png", ".pdf"},
            "page_count": (1, 1),
            "mime_types": {"image/jpeg", "image/png", "application/pdf"},
            "keywords": {
                "квитанция", "чек", "оплата", "сумма", "получатель",
                "назначение платежа", "банк", "перевод",
            },
            "layout_signature": "half_page_text",
        },
        "power_of_attorney": {
            "file_extensions": {".pdf"},
            "page_count": (1, 5),
            "mime_types": {"application/pdf"},
            "keywords": {
                "доверенность", "представитель", "доверитель",
                "полномочия", "нотариус", "реестровый",
            },
            "layout_signature": "dense_text_legal",
        },
    }

    def classify(self, file, ocr_meta, ocr_text) -> ClassificationResult:
        """Returns result or None if ambiguous."""

        for doc_type, rule in self.RULES.items():
            score = 0.0
            checks = 0

            # Extension
            ext = Path(file.name).suffix.lower()
            if ext in rule["file_extensions"]:
                score += 1.0
            checks += 1

            # MIME type
            if file.mime_type in rule["mime_types"]:
                score += 1.0
            checks += 1

            # Page count
            pages = ocr_meta.get("page_count", 1)
            lo, hi = rule["page_count"]
            if lo <= pages <= hi:
                score += 1.0
            checks += 1

            # Keywords
            text_lower = ocr_text.lower()
            keyword_hits = sum(
                1 for kw in rule["keywords"]
                if kw in text_lower
            )
            ratio = keyword_hits / max(len(rule["keywords"]), 1)
            score += min(ratio, 1.0)
            checks += 1

            confidence = score / max(checks, 1)
            if confidence >= 0.75:
                return ClassificationResult(
                    document_type=doc_type,
                    confidence=confidence,
                    method="rule",
                )

        return None  # ambiguous, go to Stage 2
```

**Expected coverage:** 30–40% of documents classified at Stage 1. Fast, zero ML cost.

### Stage 2: ML-based Classifier

Lightweight text classifier using TF-IDF features + SVM.

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
import joblib

class MLClassifier:
    """Stage 2: TF-IDF + SVM classifier for document types.

    Training data: 200+ labelled OCR texts per document type.
    Retrained weekly as new labelled data accumulates.
    """

    # Russian keyword patterns per document type
    # Used for automatic labelling of training data
    KEYWORD_PROFILES = {
        "sale_contract": {
            "must_include": {"договор купли-продажи", "продавец", "покупатель"},
            "likely": {"цена", "недвижимость", "регистрация", "переход права"},
            "forbidden": {"агентский договор", "доверенность", "аренда"},
        },
        "agency_contract": {
            "must_include": {"агентский договор", "агент", "принципал"},
            "likely": {"вознаграждение", "услуги", "поручение"},
            "forbidden": {"купли-продажи", "аренда", "доверенность"},
        },
        "rental_contract": {
            "must_include": {"договор аренды", "арендодатель", "арендатор"},
            "likely": {"арендная плата", "срок", "помещение", "найм"},
            "forbidden": {"купли-продажи", "агентский", "доверенность"},
        },
        "passport": {
            "must_include": {"паспорт", "паспорт рф", "выдан"},
            "likely": {"орган", "серия", "номер", "дата рождения"},
            "forbidden": {"договор", "егрн", "квитанция"},
        },
        "egrn_extract": {
            "must_include": {"выписка", "егрн", "кадастровый номер"},
            "likely": {"правообладатель", "объект недвижимости", "обременение"},
            "forbidden": {"паспорт", "доверенность"},
        },
        "receipt": {
            "must_include": {"квитанция", "оплата", "сумма"},
            "likely": {"чек", "банк", "перевод", "получатель"},
            "forbidden": {"договор", "егрн"},
        },
        "power_of_attorney": {
            "must_include": {"доверенность", "представитель"},
            "likely": {"доверитель", "полномочия", "нотариус"},
            "forbidden": {"купли-продажи", "аренда", "агентский"},
        },
    }

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),     # unigrams + bigrams + trigrams
            analyzer="char_wb",       # character n-grams (handles OCR typos)
            min_df=2,
        )
        self.classifier = SVC(
            kernel="linear",
            probability=True,
            class_weight="balanced",
        )
        self.model_path = "data/models/document_classifier.joblib"

    def train(self, texts: list[str], labels: list[str]):
        X = self.vectorizer.fit_transform(texts)
        self.classifier.fit(X, labels)
        joblib.dump((self.vectorizer, self.classifier), self.model_path)

    def predict(self, text: str) -> ClassificationResult:
        if not self._model_loaded():
            return None  # model not trained, skip to Stage 3
        X = self.vectorizer.transform([text])
        probs = self.classifier.predict_proba(X)[0]
        best_idx = probs.argmax()
        return ClassificationResult(
            document_type=self.classifier.classes_[best_idx],
            confidence=float(probs[best_idx]),
            method="ml",
        )
```

**Expected coverage:** 40–50% of documents at Stage 2 (after Stage 1 fails).

**Training strategy:**
1. Initial training: synthetic data from keyword-based auto-labelling of first 1000 documents
2. Continuous: weekly retraining on human-verified classifications
3. Cold start: keyword profiles seed the initial model

### Stage 3: LLM-based Classifier

Uses DeepSeek Flash (medium reasoning) for documents that pass all ML checks but remain ambiguous.

```python
from pydantic import BaseModel, Field
from typing import Literal

class LLMClassification(BaseModel):
    """Structured output from LLM classifier."""

    document_type: Literal[
        "sale_contract",
        "agency_contract",
        "rental_contract",
        "passport",
        "egrn_extract",
        "receipt",
        "power_of_attorney",
        "unknown",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    extracted_date: str | None = None
    extracted_amount: str | None = None


class LLMClassifier:
    """Stage 3: LLM-based classifier for ambiguous documents.

    Uses DeepSeek Flash (medium complexity) per development rules.
    """

    SYSTEM_PROMPT = """
    Ты — классификатор документов агентства недвижимости.
    
    Определи тип документа по его OCR-тексту и метаданным.
    
    Возможные типы:
    - sale_contract: договор купли-продажи недвижимости
    - agency_contract: агентский договор с агентством недвижимости
    - rental_contract: договор аренды/найма жилья
    - passport: паспорт РФ (первая страница, разворот)
    - egrn_extract: выписка из ЕГРН на объект недвижимости
    - receipt: квитанция об оплате / чек
    - power_of_authority: доверенность на совершение сделок
    - unknown: не удалось определить
    
    Верни JSON с полями: document_type, confidence (0-1), reasoning.
    """

    def classify(self, ocr_text: str, file_meta: dict) -> LLMClassification:
        prompt = f"""
        Метаданные:
        - Имя файла: {file_meta.get('file_name', '')}
        - MIME тип: {file_meta.get('mime_type', '')}
        - Количество страниц: {file_meta.get('page_count', 1)}
        
        OCR-текст:
        {ocr_text[:8000]}  # truncate to fit context window
        """
        # Use DeepSeek Flash (medium reasoning)
        result = llm.extract_structured(
            system=self.SYSTEM_PROMPT,
            prompt=prompt,
            schema=LLMClassification,
            model="deepseek-flash",
        )
        return result
```

**Expected coverage:** 15–20% of all documents reach Stage 3.
**Of those:** ~70% classified, ~20% sent to manual review, ~10% still unknown.

## Confidence Thresholds

| Stage | Threshold | Action |
|-------|-----------|--------|
| Stage 1 (rule) | ≥ 0.75 | Accept, auto-classify |
| Stage 1 (rule) | < 0.75 | Pass to Stage 2 |
| Stage 2 (ML) | ≥ 0.85 | Accept, auto-classify |
| Stage 2 (ML) | 0.60 – 0.85 | Pass to Stage 3 |
| Stage 2 (ML) | < 0.60 | Pass to Stage 3 |
| Stage 3 (LLM) | ≥ 0.80 | Accept, auto-classify |
| Stage 3 (LLM) | < 0.80 | Flag for manual review |
| Manual review | — | Agent confirms or corrects |

### Threshold Justification

| Threshold | Rationale |
|-----------|-----------|
| Rule ≥ 0.75 | Simple heuristics (ext + keywords + page count) are reliable — 75% match means 3 of 4 checks passed |
| ML ≥ 0.85 | Higher bar than rules because ML can overfit on limited training data |
| LLM ≥ 0.80 | LLM has full context — it should be confident if it's right. Below 0.80 means genuine ambiguity |
| Manual < 0.80 | Last resort. Better to ask a human than misclassify a legal document |

## Fallback Strategy

| Scenario | Action |
|----------|--------|
| ML model not trained | Skip Stage 2 entirely, go direct to Stage 3 |
| LLM unavailable (network) | Use ML result even at low confidence, flag for review |
| Both ML + LLM fail | Classify as `unknown`, flag for manual review |
| OCR text too short (< 100 chars) | Skip all stages, flag as `unreadable` |
| Multi-type document (e.g., passport + contract in one file) | Classify per page, store page-level results |
| New document type not in training set | LLM returns `unknown`, added to review queue for future training |
| Rapid re-classification request | Use cached result (document_hash → classification) |

### Fallback Cascade

```
[OCR Text]
    │
    ├─ Text < 100 chars? ──────────────→ unreadable (manual)
    │
    ├─ Rule ≥ 0.75? ────────────────────→ accept
    │
    ├─ ML model exists AND ≥ 0.85? ────→ accept
    │
    ├─ LLM available AND ≥ 0.80? ──────→ accept
    │
    ├─ LLM available? ──────────────────→ accept with LLM (flag for review)
    │
    └─ Fallback ─────────────────────────→ unknown (manual review)
```

## Database Storage Model

### Table: `document_classifications`

```sql
CREATE TYPE document_category AS ENUM (
    'contract',
    'passport',
    'extract',
    'receipt',
    'other'
);

CREATE TYPE document_subtype AS ENUM (
    -- contracts
    'sale_contract',
    'agency_contract',
    'rental_contract',
    -- passports
    'passport',
    -- extracts
    'egrn_extract',
    -- receipts
    'receipt',
    -- other
    'power_of_attorney',
    'unknown'
);

CREATE TYPE classification_method AS ENUM (
    'rule',
    'ml',
    'llm',
    'manual',
    'unclassified'
);

CREATE TABLE document_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Classification result
    category document_category NOT NULL,
    subtype document_subtype NOT NULL DEFAULT 'unknown',
    subtype_original VARCHAR(50),  -- original value before normalization

    -- Confidence & method
    confidence FLOAT NOT NULL DEFAULT 0.0,
    method classification_method NOT NULL DEFAULT 'unclassified',

    -- Stage-level details
    rule_confidence FLOAT,
    ml_confidence FLOAT,
    llm_confidence FLOAT,
    llm_reasoning TEXT,       -- LLM's reasoning for the decision

    -- Manual review
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    -- Versioning
    classifier_version VARCHAR(50),  -- '2026-06-07-v1', model checkpoint
    is_active BOOLEAN NOT NULL DEFAULT TRUE,  -- supports re-classification

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_confidence CHECK (
        confidence >= 0.0 AND confidence <= 1.0
    )
);

-- Indexes
CREATE INDEX idx_doc_classifications_document
    ON document_classifications(document_id);
CREATE INDEX idx_doc_classifications_subtype
    ON document_classifications(subtype);
CREATE INDEX idx_doc_classifications_method
    ON document_classifications(method);
CREATE INDEX idx_doc_classifications_active
    ON document_classifications(is_active)
    WHERE is_active = TRUE;
```

### Integration with Existing Schema

The classification system extends the existing `documents` table without modifying it:

```
documents
├── id UUID (PK)
├── document_type VARCHAR(20)  → broad category: 'contract', 'passport', ...
├── status VARCHAR(20)         → 'pending' → 'processing' → 'completed' | 'failed'
└── ...
     │
     ▼
ocr_results
├── document_id UUID (FK)
├── raw_text TEXT              → OCR-extracted text (input to classifier)
├── confidence FLOAT
└── layout JSONB               → layout features for rule-based checks
     │
     ▼
document_classifications      ← NEW TABLE
├── document_id UUID (FK)
├── category ENUM              → mapped from document_type
├── subtype ENUM               → fine-grained: sale_contract, egrn_extract, ...
├── confidence FLOAT           0.0–1.0
├── method ENUM                → rule | ml | llm | manual
└── reviewed_by / notes        → manual verification
```

### Mapping: Expected Types → Existing document_type

| Expected Type | document_type (existing) | category (new) | subtype (new) |
|---------------|-------------------------|----------------|---------------|
| Sale contract | contract | contract | sale_contract |
| Agency contract | contract | contract | agency_contract |
| Rental contract | contract | contract | rental_contract |
| Passport | passport | passport | passport |
| EGRN extract | extract | extract | egrn_extract |
| Receipt | receipt | receipt | receipt |
| Power of attorney | other | other | power_of_attorney |

## Classification Features

### Text Features (TF-IDF input)

Extracted from OCR text after preprocessing:

```python
class TextFeatures:
    """
    Features extracted from cleaned OCR text for ML classifier.

    Preprocessing:
    1. Lowercase
    2. Remove punctuation (except hyphens in multi-word terms)
    3. Collapse whitespace
    4. Remove lines < 3 characters (likely noise)
    """

    features = [
        "ngram_char_1_3",          # character n-grams (handles OCR typos)
        "word_unigrams",           "single words"
        "word_bigrams",            # word pairs
        "keyword_density",         # hits / total words
        "cjk_ratio",               # Chinese/Japanese characters (none expected)
        "latin_ratio",             # latin characters (contracts have legal terms)
        "digit_ratio",             # numbers (passports, receipts)
        "line_length_mean",        # average line length
        "paragraph_count",         # number of paragraphs
    ]
```

### Layout Features

Extracted from PP-Structure layout analysis:

| Feature | Used for |
|---------|----------|
| Table area ratio | Table-heavy → extract/statement; text-heavy → contract |
| Text block count | Multi-column → passport; single column → contract |
| Average text block height | Headers (large) vs body (small) |
| Image-to-text ratio | High → photo document; low → scanned text |
| Signature region presence | Present → contract/deed; absent → extract |
| Stamp/seal detection | Round seal → official document (extract, contract) |

### File Metadata Features

| Feature | Used for |
|---------|----------|
| File extension | .pdf → contract/extract; .jpg → receipt/passport |
| MIME type | image/jpeg → photo; application/pdf → scan |
| File size | Small → single page; large → multi-page contract |
| Page count | 1 page → receipt; 2 pages → passport; 5+ → contract |

## Performance Targets

| Metric | Target |
|--------|--------|
| End-to-end classification latency | < 3 sec (80th percentile) |
| Stage 1 + 2 coverage (no LLM needed) | > 75% of documents |
| Stage 3 accuracy (LLM) | > 90% |
| Overall accuracy (all stages) | > 95% |
| Manual review rate | < 5% of all documents |
| False positive rate (wrong class) | < 1% |
| ML model retraining frequency | Weekly |

## Error Handling

| Error | Behaviour |
|-------|-----------|
| ML model file not found | Skip Stage 2, log warning, go to Stage 3 |
| LLM timeout (> 10 sec) | Use ML result (even low confidence), flag for review |
| LLM returns invalid JSON | Retry once with stricter prompt |
| OCR text empty | Classify as `unreadable`, flag for manual review |
| Unknown document type | Classify as `unknown`, add to training queue |
| Classification already exists | Return cached result (same document_hash) |

## Data Flow

```
1. Document Uploaded
   │
2. OCR Pipeline (see ocr_layer.md)
   │   └─ Result: raw_text, layout, confidence
   │
3. Document Classifier (this document)
   │   ├─ Stage 1: Rule → match? return
   │   ├─ Stage 2: ML → confident? return
   │   ├─ Stage 3: LLM → confident? return
   │   └─ Manual → agent corrects
   │
4. Save Classification
   │   └─ INSERT INTO document_classifications
   │
5. Update Document Status
   │   └─ UPDATE documents SET status = 'classified'
   │
6. Field Extraction (separate service)
   │   └─ LLM extracts structured data per document type
   │
7. AI Processing
   └─ Clause analysis, compliance check, data entry
```

## Training Data Collection

Every classified document generates a training sample:

```python
TRAINING_SAMPLE = {
    "ocr_text": str,               # preprocessed OCR text
    "layout_features": dict,       # table ratio, block count, etc.
    "file_features": dict,         # extension, mime, page count
    "true_label": str,             # final subtype (human-verified)
    "method": str,                 # classification method used
    "classifier_version": str,
}
```

Samples are stored in a `classification_training_log` table for weekly retraining of the Stage 2 ML model.

## Related Documentation

- `docs/architecture/ocr_layer.md` — OCR pipeline (upstream dependency)
- `docs/architecture/document_classifier.md` — this document
- `docs/domain/document.md` — Document entity definition
- `docs/domain/database_schema_v1.md` — documents + ocr_results tables
- `docs/development_rules.md` — AI model selection (Qwen/DeepSeek/ChatGPT)
- `docs/adr/0004-ocr-layer-paddleocr.md` — OCR engine decision
