# Stream B — Contract Profile Extraction Strategy

```
Epic              1 — Intelligent Document Intake
Stream            B — Extraction Strategy
Status            Architecture Design (no code)
Predecessor       Stream A — Contract Profile Architecture (APPROVED)
```

──────────────────────────────────────────────────────
## 1. Independent Extraction Sections

Каждая секция извлекается независимо.

Это позволяет:

- добавлять/удалять секции без изменения других
- тестировать каждую секцию изолированно
- иметь разный confidence для каждой секции
- переиспользовать extractor'ы для других типов документов

**Независимые секции:**

```
IdentificationExtractor   ← Номер, дата, место
PartyExtractor            ← Продавец / Покупатель
FinancialTermsExtractor   ← Цена, НДС, задаток
PropertyExtractor         ← Адрес, площадь, кадастр
DateExtractor             ← Даты подписания, оплаты, передачи
ReferenceExtractor        ← Ссылки на протоколы, торги
```

**Зависимости между секциями — нет.**

Каждый extractor получает `raw_text` и возвращает свою секцию.

Главный `ContractExtractor`:

```python
class ContractExtractor:
    def extract(self, raw_text: str) -> ContractProfile:
        return ContractProfile(
            identification=IdentificationExtractor.extract(raw_text),
            parties=PartyExtractor.extract(raw_text),
            financial_terms=FinancialTermsExtractor.extract(raw_text),
            property=PropertyExtractor.extract(raw_text),
            dates=DateExtractor.extract(raw_text),
            references=ReferenceExtractor.extract(raw_text),
            metadata=self._build_metadata(section_results),
        )
```

Никакого общего состояния. Каждый extractor — чистая функция `(raw_text) → Section`.

──────────────────────────────────────────────────────
## 2. Regex Strategy

### 2.1. Три типа паттернов

**Тип A — Section Locator (заголовки секций)**

Находит границы секций в тексте:

```
SECTION_HEADERS = [
    r"(?im)^1\.\s*Предмет\s*договора",
    r"(?im)^2\.\s*Цена\s*и\s*порядок\s*расчетов",
    r"(?im)^3\.\s*Обязанности\s*Сторон",
    r"(?im)^ПРОДАВЕЦ[:\s]",
    r"(?im)^ПОКУПАТЕЛЬ[:\s]",
]
```

Эти паттерны ищут структуру документа, а не конкретные значения.

**Тип B — Field Extractor (конкретные поля)**

Извлекает значение рядом с ключевым словом:

```
PRICE_PATTERNS = [
    r"(?im)цена\s*продажи.*?составляет\s+([\d\s]+)\s*руб",
    r"(?im)цена\s*продажи.*?(\d[\d\s]*)\s*руб",
]
```

**Тип C — Post-Processor (нормализация)**

Преобразует извлечённый текст в структурированное значение:

```
parse_money("18 178 000 (Восемнадцать миллионов...) рублей") → 18178000.00
extract_inn("ИНН 780527855675") → "780527855675"
normalize_date("26.05.2026") → date(2026, 5, 26)
```

### 2.2. Composable patterns

Паттерны компонуются в цепочки.

Пример для `FinancialTermsExtractor`:

```
raw_text
  │
  ▼
SectionLocator("Цена и порядок расчётов")
  │
  ▼  (изолированный текст секции)
FieldExtractor → total_price
  │
  ▼
FieldExtractor → vat_amount
  │
  ▼
FieldExtractor → deposit_amount
  │
  ▼
PostProcessor → parse_money()
  │
  ▼
SectionResult(confidence, fields, warnings)
```

Каждый FieldExtractor может иметь **несколько** regex-паттернов (fallback chain):

```python
FieldExtractor(
    name="total_price",
    patterns=[
        r"цена\s*продажи.*?составляет\s+([\d\s]+)\s*руб",
        r"цена\s*продажи.*?(\d[\d\s]*)\s*рублей",
        r"(\d[\d\s]*)\s*рублей.*?НДС",  # fallback: рядом с НДС
    ],
    post_process=parse_money,
    required=False,
)
```

Если первый pattern не сработал — пробует второй, третий.

──────────────────────────────────────────────────────
## 3. Required vs Optional Fields

### Обязательные (must have — profile считается неполным без них)

```
contract_number
contract_date
seller.name
buyer.name
```

Если хотя бы одно обязательное поле отсутствует → `warnings` + `confidence < 0.5`.

### Опциональные (nice to have — не влияют на полноту профиля)

```
seller.inn
seller.kpp
seller.ogrn
buyer.inn
total_price
vat_amount
property.address
property.cadastral_number
```

Профиль считается валидным и без них.

──────────────────────────────────────────────────────
## 4. Confidence Model

### Уровни confidence

```
0.0 — 0.3   → поле не найдено / низкое качество
0.3 — 0.7   → поле найдено, но с предупреждениями
0.7 — 0.9   → поле найдено, regex совпал
0.9 — 1.0   → поле найдено + cross-validation
```

### Confidence секции = среднее по полям

```
section_confidence = sum(field.confidence for field in section) / len(section)
```

### Confidence профиля = среднее по секциям

```
profile_confidence = sum(section.confidence for section in sections) / len(sections)
```

### Cross-validation (повышает confidence)

```
total_price == price_excluding_vat + vat_amount    → +0.1 к total_price
contract_date <= signing_date                       → +0.05 к обоим
seller.inn найден в секции "Продавец"               → +0.1 к seller.name
```

──────────────────────────────────────
## 5. Extraction Warnings

Каждый extractor возвращает список warnings.

```python
dataclass
class ExtractionWarning:
    field: str
    code: str              # MONEY_PARSE_FAIL, SECTION_NOT_FOUND, LOW_CONFIDENCE
    message: str
    severity: str          # "info" | "warning" | "error"
```

Типы warnings:

| Code | Severity | Meaning |
|------|----------|---------|
| `SECTION_NOT_FOUND` | warning | Секция не найдена в тексте |
| `FIELD_NOT_FOUND` | warning | Поле не найдено в секции |
| `MONEY_PARSE_FAIL` | error | Сумма найдена, но не распаршена |
| `MULTIPLE_VALUES` | info | Найдено несколько значений, взято первое |
| `LOW_CONFIDENCE` | warning | Confidence поля < 0.5 |
| `CROSS_VALIDATION_FAIL` | info | Проверка не прошла (напр. А ≠ Б+В) |

Warnings сохраняются в `metadata.warnings`.

──────────────────────────────────────
## 6. Profile Validation

Валидация запускается после извлечения всех секций.

### Типы проверок

**Structural** (всегда):

- profile содержит хотя бы identification
- обязательные поля присутствуют
- нет конфликтов типов

**Semantic** (опционально):

- `total_price >= vat_amount`
- `signing_date <= payment_deadline`
- `seller.inn` — 10 цифр (если есть)
- `buyer.inn` — 10 или 12 цифр (если есть)

**Cross-section** (опционально):

- `parties.seller.name` не равен `parties.buyer.name`
- `contract_number` из identification совпадает с номером в filename

Если структурная проверка не пройдена → `confidence *= 0.5`.

──────────────────────────────────────
## 7. Backward Compatibility

**Существующий pipeline не меняется.**

```
Pipeline API:    POST /processing/pipelines/start/{doc_id}
                 GET  /processing/pipelines/{pipeline_id}
                 POST /processing/pipelines/{pipeline_id}/retry

Вход:            тот же (file + metadata)
Выход:           тот же (pipeline_id, status, steps)
```

**Единственное изменение — внутренняя реализация extraction step.**

```
Было:
  execute_extraction_step()
    → возвращает flat dict: {"date": "...", "number": "..."}

Стало:
  ContractExtractor.extract(raw_text)
    → возвращает ContractProfile (как dict → сохраняется в result)
```

**Формат шага не меняется:**

```python
step.result = {
    "document_type": "contract",
    "fields": profile.to_dict(),  # ← теперь структурированный, не flat
    "confidence": profile.confidence,
    "warnings": profile.warnings,
}
```

**Потребители (accounting mapper, routing engine) получают тот же `step.result["fields"]`, но с richer структурой.**

Новый consumers читают `fields.sections.parties.seller.name`.
Старые consumers читают `fields.invoice_number` — продолжает работать (совместимость обеспечена ключом `invoice_number` на верхнем уровне).

──────────────────────────────────────
## 8. Implementation Plan

### T1 — Profile Model (30 мин)

Файл: `backend/services/processing/extraction/models.py`

Создать dataclass'ы:

- `ContractProfile`
- `IdentificationSection`
- `PartiesSection` (с `Party` внутри)
- `FinancialTermsSection` (с `Money` внутри)
- `PropertySection`
- `DatesSection`
- `ReferenceSection`
- `ExtractionMetadata`
- `ExtractionWarning`

### T2 — Section Extractors (2 часа)

Файлы:

```
extraction/
├── contract_extractor.py     ← ContractExtractor (агрегатор)
├── identification_extractor.py
├── party_extractor.py
├── financial_terms_extractor.py
├── property_extractor.py
├── date_extractor.py
└── reference_extractor.py
```

Каждый extractor содержит:

- section locator patterns
- field extractor patterns
- post-processor
- confidence computation

### T3 — Profile Validation (30 мин)

Файл: `extraction/validators.py`

- structural validation
- semantic validation
- cross-section validation

### T4 — Pipeline Integration (15 мин)

Обновить `execute_extraction_step` в `steps/extraction_step.py`.

Вызывать `ContractExtractor.extract()` вместо старого flat extraction.

### T5 — Tests (1 час)

- unit tests на каждый extractor
- integration test на ContractExtractor с реальным текстом ДКП
- test на backward compatibility

──────────────────────────────────────
## Architecture Summary

```
Platform changes:   0
Knowledge changes:  0
New files:          8 (model + 6 extractors + validator)
Modified files:     1 (extraction_step.py — внутренняя реализация)
Backward compat:    Да (flat fields сохранены на верхнем уровне)
```

**Ключевое решение:** extractor'ы — чистые функции, без состояния, без Platform-зависимостей.

**Stream B complete. Ready for Stream C — Implementation.**
