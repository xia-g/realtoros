# Document

Документ — любое файловое вложение в систему.

## Типы документов

- contract — договор
- passport — паспорт
- extract — выписка ЕГРН
- deed — акт приёма-передачи
- receipt — квитанция об оплате
- statement — выписка из банка
- photo — фотография объекта
- video — видео объекта
- report — отчёт (оценка, инспекция)
- other — прочее

## Статусы

- pending — ожидает получения
- received — получен
- verified — проверен
- expired — истёк
- rejected — отклонён

## Атрибуты

- id: UUID (PK)
- document_type: DocumentType
- status: DocumentStatus
- title: string (название документа)
- description: text
- file_name: string
- file_path: string (путь к файлу в хранилище)
- file_size: int (байты)
- file_hash: string (SHA-256 для проверки целостности)
- mime_type: string
- client_id: UUID (FK -> Client, nullable)
- property_id: UUID (FK -> Property, nullable)
- deal_id: UUID (FK -> Deal, nullable)
- uploaded_by: UUID (FK -> User)
- expiry_date: date (опционально — для паспортов, выписок)
- notes: text
- created_at: timestamp
- updated_at: timestamp

## Связи

- Belongs to Client (опционально)
- Belongs to Property (опционально)
- Belongs to Deal (опционально)
- Uploaded by User

Хотя бы одна из FK (client_id, property_id, deal_id) должна быть заполнена.

## Индексы

- status + document_type — поиск по типу и статусу
- client_id — все документы клиента
- property_id — все документы объекта
- deal_id — все документы сделки
- file_hash — уникальность файла
