# Stream A — Contract Document Profile Architecture (Proposal)

```
Epic              1 — Intelligent Document Intake
Stream            A — Contract Document Profile
Architecture      v3.0 (Platform FROZEN)
Knowledge Layer   v3.0 (unchanged)
Product Layer     Epic 1 (Document + Pipeline + Routing + Accounting)
Phase             0 — Architecture Proposal Only
```

──────────────────────────────────────────────────────
## 1. Why Not Fix Regex

Текущая проблема:

```
Extraction v1 → {"date": "...", "invoice_number": "...", "contract_number": "..."}
```

Это **плоский JSON**, где нет:

- семантики полей
- структуры
- типов
- обязательности
- связей между полями

Можно "починить regex" и добавить 10 новых ключей. Но через неделю появится новый тип документа, и снова нужно будет добавлять regex.

**Правильное решение:**

Извлекать **структурированный профиль документа**, где каждое поле имеет:

- имя
- тип (string, money, date, person, address)
- секцию
- confidence
- source (какой шаг pipeline извлёк)
- обязательность

Профиль — это Product Layer объект.

Не Knowledge.

Не Platform.

──────────────────────────────────────────────────────
## 2. Contract Profile Domain Model

```
ContractProfile
│
├── profile_type: "contract"        (всегда)
├── profile_version: "1.0"          (схема версионируется)
├── document_id: UUID               (ссылка на Document)
├── confidence: float               (общая уверенность профиля)
│
├── identification                  ← Кто, что, когда
│   ├── contract_number: str
│   ├── contract_date: date
│   ├── place_of_signing: str
│   └── language: str
│
├── parties                         ← Стороны
│   ├── seller
│   │   ├── name: str
│   │   ├── type: "legal" | "individual"
│   │   ├── inn: str | None
│   │   ├── kpp: str | None
│   │   ├── ogrn: str | None
│   │   └── address: str | None
│   └── buyer
│       ├── name: str
│       ├── type: "legal" | "individual"
│       ├── inn: str | None
│       ├── kpp: str | None
│       ├── ogrn: str | None
│       └── address: str | None
│
├── financial_terms                 ← Финансовые условия
│   ├── total_price: Money
│   ├── vat_amount: Money
│   ├── price_excluding_vat: Money
│   ├── deposit_amount: Money
│   ├── payment_due_days: int | None
│   └── currency: str (RUB)
│
├── property                        ← Объект (для ДКП недвижимости)
│   ├── type: "non_residential" | "residential" | "land"
│   ├── address: str
│   ├── area_sqm: float
│   ├── floor: int | None
│   ├── cadastral_number: str | None
│   └── purpose: str | None
│
├── dates                           ← Ключевые даты
│   ├── signing_date: date
│   ├── payment_deadline: date | None
│   └── transfer_deadline: date | None
│
├── references                      ← Ссылки на связанные документы
│   ├── protocol_number: str | None
│   ├── protocol_date: date | None
│   └── tender_number: str | None
│
└── metadata                        ← Служебная информация
    ├── extracted_by: "pipeline:extraction-v2"
    ├── confidence_per_field: dict[str, float]
    ├── warnings: list[str]
    └── raw_text_excerpts: dict[str, str]
```

──────────────────────────────────────────────────────
## 3. Logical Sections — детально

### 3.1. Identification

Что это за документ?

```
contract_number:  "2182-НШИ"
contract_date:   2026-05-26
place_of_signing: "Санкт-Петербург"
```

Источник: заголовок документа (первые 200 символов OCR). Извлекается через контекстный regex + проверка позиции в тексте.

### 3.2. Parties

Кто участвует?

```
seller:
  name: "Комитет имущественных отношений Санкт-Петербурга"
  type: "legal"
  inn: "7832000076"
  kpp: "784201001"
  ogrn: "1177847189190"

buyer:
  name: "Шульгина Ирина Юрьевна"
  type: "individual"
  inn: "780527855675"
```

Источник: секции "Продавец" и "Покупатель" в теле документа. Извлекается через поиск заголовков секций + контекстные паттерны.

### 3.3. Financial Terms

Сколько и как платить?

```
total_price:       18_178_000.00
vat_amount:         3_278_000.00
price_excluding_vat: 14_900_000.00
deposit_amount:     1_817_800.00
currency:          "RUB"
```

Источник: секция "Цена и порядок расчётов". Самая сложная для извлечения — суммы прописью, НДС выделен отдельно.

### 3.4. Property

Какой объект?

```
type:              "non_residential"
address:           "Санкт-Петербург, наб. Петроградская, д. 18, корп. 3, лит. В, пом. 20-Н"
area_sqm:          218.7
floor:             4
cadastral_number:  "78:07:0003009:1342"
```

Источник: секция "Предмет договора". Кадастровый номер и площадь — ключевые поля.

### 3.5. Dates

Когда?

```
signing_date:      2026-05-26
payment_deadline:  2026-06-25
transfer_deadline: None
```

### 3.6. References

На основании чего?

```
protocol_number:   None
tender_number:     "21000002210000008914"
```

──────────────────────────────────────────────────────
## 4. Что остаётся в metadata

В metadata попадает всё, что не входит в основные секции:

```python
metadata = {
    "extracted_by": "pipeline:extraction-v2",
    "pipeline_run_id": "...",
    "confidence_per_field": {
        "contract_number": 0.95,
        "seller_name": 0.80,
        "total_price": 0.70,
        "cadastral_number": 0.90,
    },
    "warnings": [
        "Payment deadline not explicitly stated",
        "Multiple dates found, using earliest as signing date",
    ],
    "raw_text_excerpts": {
        "price_section": "Цена продажи Объекта составляет...",
        "parties_section": "Продавец: Комитет...",
    },
    "extraction_time_ms": 145,
    "fallback_fields": ["payment_deadline"],
}
```

**Не хранить в metadata:**
- полный raw_text (он уже есть в OCR step result)
- вычисляемые поля (баланс, итоги)
- Business-логику (категория сделки, тип налога)

──────────────────────────────────────────────────────
## 5. Что остаётся в OCR text

OCR text (сырой) — это **временные данные pipeline**.

Он хранится в `processing_steps.result.ocr.raw_text` и нужен только для извлечения.

**После формирования профиля OCR text НЕ нужен:**
- Document хранит profile
- Profile содержит всё необходимое для consumers
- Consumers (Accounting, Deal, Knowledge) читают profile, а не сырой текст

**Флаг:** если потребуется переизвлечение — pipeline может быть запущен заново, и OCR text возьмётся из того же источника (OCRNode или повторная обработка файла).

──────────────────────────────────────────────────────
## 6. Как Profile связывается с Document

```
Document (document_intake)
│
│   .profile: ContractProfile (JSONB)
│   .document_type: "contract"
│   .status: "ANALYZED"
│
├── Accounting Entry
│       .document_id → Document.document_id
│       .profile → читает financial_terms из doc.profile
│
├── Routing Decision
│       .document_id → Document.document_id
│       .profile → читает parties, financial_terms
│
├── Deal
│       .notes → "doc_id: {document.document_id}"
│       .profile → читает property, parties
│
└── KnowledgeRevision
        .source_document_id → Document.document_id
        .graph → строится из profile.parties, profile.property
```

**Поток:**

```
OCR Text
   ↓
Extraction Step
   ↓
ContractProfile (структурированный)
   ↓
сохраняется в document_intake.profile (JSONB)
   ↓
все consumer'ы читают document.profile
```

**Никакой синхронизации.** Profile — singleton на документ.

Profile обновляется только при повторном pipeline run.

──────────────────────────────────────────────────────
## 7. Platform Changes

**Platform: 0 изменений.**

- Domain (v3.0 frozen) — не трогаем
- Knowledge (v3.0 frozen) — не трогаем
- Query Engine — не трогаем
- Projection Layer — не трогаем

Новый extraction — это **Product Layer**:

```
backend/services/processing/extraction/
├── __init__.py
├── models.py              ← ContractProfile dataclass
├── contract_extractor.py  ← логика извлечения
└── schemas/
    └── contract.yaml      ← описание полей (опционально)
```

**Profile хранится в существующей таблице:** `document_intake.profile` (JSONB).

Новых таблиц не нужно.

──────────────────────────────────────────────────────
## 8. Product Layer Changes

| Компонент | Изменение |
|-----------|-----------|
| Extraction Step | ✅ Переписать: regex → ContractProfile |
| Classification Step | **Не меняется** (остаётся keyword-based) |
| Pipeline orchestrator | **Не меняется** |
| Processing API | **Не меняется** (тот же /start, /status) |
| Document model | **Не меняется** (profile уже JSONB) |
| Accounting mapper | **Улучшается** — читает profile.financial_terms |
| Routing engine | **Улучшается** — читает profile.parties |
| Frontend | **Улучшается** — показывает profile секциями |

**Единственное изменение в pipeline:** `execute_extraction_step` теперь возвращает `ContractProfile` вместо плоского dict.

──────────────────────────────────────────────────────
## 9. API Contract — что возвращает extraction step

```json
{
  "document_type": "contract",
  "profile_version": "1.0",
  "confidence": 0.75,
  "sections": {
    "identification": {
      "contract_number": "2182-НШИ",
      "contract_date": "2026-05-26"
    },
    "parties": {
      "seller": {
        "name": "Комитет имущественных отношений Санкт-Петербурга",
        "type": "legal",
        "inn": "7832000076"
      },
      "buyer": {
        "name": "Шульгина Ирина Юрьевна",
        "type": "individual",
        "inn": "780527855675"
      }
    },
    "financial_terms": {
      "total_price": {
        "value": 18178000.00,
        "currency": "RUB",
        "confidence": 0.9
      },
      "vat_amount": {
        "value": 3278000.00,
        "currency": "RUB",
        "confidence": 0.9
      }
    },
    "property": {
      "cadastral_number": "78:07:0003009:1342",
      "address": "наб. Петроградская, д. 18, корп. 3, лит. В, пом. 20-Н",
      "area_sqm": 218.7
    }
  },
  "metadata": {
    "warnings": [],
    "confidence_per_field": {
      "contract_number": 0.95,
      "seller_name": 0.85
    }
  }
}
```

──────────────────────────────────────────────────────
## 10. Implementation Strategy

### T1 — Profile Model

Создать `ContractProfile` dataclass с секциями.

Никакой логики извлечения.

Только модель.

### T2 — Contract Extractor

Перенести текущие regex в структурированный формат.

Добавить section-aware поиск:

```
1. Найти секцию "Цена и порядок расчётов"
2. Внутри секции искать суммы
3. Извлечь total_price, vat_amount
```

### T3 — Profile → Accounting

Обновить accounting mapper:

```
Вместо плоского fields["amount"]
Читать profile.sections.financial_terms.total_price
```

### T4 — Profile → Frontend

Показать профиль секциями на странице документа.

Вместо "Тип: contract" → секции + confidence.

### T5 — Tests

Тесты на каждую секцию:

- contract с НДС
- contract без НДС
- contract с юрлицом
- contract с физлицом
- минимальный contract (только identification)

──────────────────────────────────────────────────────
## 11. Risks

| Риск | Вероятность | Влияние | Митигация |
|------|:-----------:|:-------:|-----------|
| Слишком жёсткая схема | Средняя | Среднее | profile_version + optional поля |
| Расхождение профилей для разных типов | Высокая | Низкое | Каждый тип документа = своя схема |
| Извлечение сумм прописью | Высокая | Среднее | Два этапа: цифры → текст → нормализация |
| Overfitting на один ДКП | Средняя | Высокое | Тестировать на 3+ разных ДКП |
| Consumer coupling | Низкая | Низкое | Profile — Product Layer, не Platform |
| Размер profile JSONB | Низкая | Низкое | Документов ~100/мес |

──────────────────────────────────────────────────────
## 12. GO / NO-GO Recommendation

**STRONG GO** ✅

**Причина:**

Текущая extraction v1 — плоский JSON без структуры. Он не масштабируется на:

- реальные бухгалтерские проводки
- анализ сделок
- поиск по документам
- AI-ассистента

Profile — это **единственная точка расширения**, которая:

- не требует Platform изменений
- использует существующую `document_intake.profile` (JSONB)
- даёт структуру всем потребителям
- версионируется

**Противоположный вариант (NO-GO):**

Продолжать добавлять regex-ключи в плоский JSON.

Через 10 документов получим 100+ ключей без структуры — и каждый consumer будет парсить их по-своему.

**Итог:** GO. Stream A — необходимый фундамент перед любым следующим шагом (Deal Intelligence, Accounting v2, AI Copilot).

──────────────────────────────────────────────────────
## Architecture Summary

```
До Stream A:

  Extraction v1 → {"date": "...", "number": "..."}  (flat JSON)
                      ↓
              Accounting: "где сумма?"
              Deal:       "где продавец?"
              AI:         "где контекст?"

После Stream A:

  Extraction v2 → ContractProfile (structured sections)
                      ↓
              Accounting: profile.financial_terms.total_price
              Deal:       profile.parties.buyer
              AI:         profile.sections
              Search:     profile.property.address
```

0 Platform changes. 
0 Knowledge changes. 
0 New tables. 
1 New model. 
1 New extractor.

**GO / NO-GO?**
