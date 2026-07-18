"""
Contract Compatibility Gate — CI guard для frozen contracts.

Правила:
- ADD optional field → OK
- REMOVE field → FAIL
- TYPE change → FAIL
- RENAME → FAIL
- ADD required field → FAIL (breaking change)

Запуск: python -m tests.contract_compatibility [--check]
"""
from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_type_hints

from pydantic import BaseModel


@dataclass
class SchemaEntry:
    """Описание одного поля контракта."""
    name: str
    type_hint: str
    has_default: bool
    is_optional: bool


@dataclass
class SchemaSnapshot:
    """Слепок схемы контракта."""
    module: str
    class_name: str
    fields: list[SchemaEntry] = field(default_factory=list)


def extract_schema(cls: type) -> list[SchemaEntry]:
    """Извлечь схему из Pydantic модели."""
    fields = []
    for name, field_info in cls.model_fields.items():
        type_hint = str(field_info.annotation) if field_info.annotation else "Any"
        has_default = field_info.default is not None or field_info.default_factory is not None
        is_optional = "None" in type_hint or "Optional" in type_hint
        fields.append(SchemaEntry(
            name=name, type_hint=type_hint,
            has_default=has_default, is_optional=is_optional,
        ))
    return fields


def check_compatibility(
    old: SchemaSnapshot,
    new: SchemaSnapshot,
) -> list[str]:
    """Проверить совместимость двух версий контракта."""
    errors: list[str] = []
    old_fields = {f.name: f for f in old.fields}
    new_fields = {f.name: f for f in new.fields}

    for name, old_field in old_fields.items():
        if name not in new_fields:
            errors.append(
                f"FAIL [{old.module}.{old.class_name}] REMOVE field: {name}"
            )
            continue

        new_field = new_fields[name]

        # Type change
        if old_field.type_hint != new_field.type_hint:
            errors.append(
                f"FAIL [{old.module}.{old.class_name}] TYPE CHANGE: "
                f"{name}: {old_field.type_hint} → {new_field.type_hint}"
            )

        # Required → optional is OK
        # Optional → required is breaking
        if not old_field.is_optional and new_field.is_optional:
            pass  # OK: required → optional
        if old_field.is_optional and not new_field.is_optional:
            errors.append(
                f"FAIL [{old.module}.{old.class_name}] "
                f"OPTIONAL → REQUIRED: {name}"
            )

    # ADD optional is OK
    for name, new_field in new_fields.items():
        if name not in old_fields:
            if not new_field.has_default and not new_field.is_optional:
                errors.append(
                    f"FAIL [{new.module}.{new.class_name}] "
                    f"ADD REQUIRED field: {name}"
                )

    return errors


def run_compatibility_check(
    contracts_package: str = "contracts",
) -> list[str]:
    """Запустить проверку совместимости контрактов.

    Сравнивает текущую схему с сохранённой (schema_snapshot.json).
    """
    snapshot_path = Path("tests/schema_snapshot.json")
    all_errors: list[str] = []

    # 1. Извлечь текущую схему
    current: dict[str, SchemaSnapshot] = {}
    for name, obj in inspect.getmembers(
        importlib.import_module(contracts_package),
        predicate=lambda x: isinstance(x, type) and issubclass(x, BaseModel) and x is not BaseModel,
    ):
        snapshot = SchemaSnapshot(
            module=contracts_package,
            class_name=name,
            fields=extract_schema(obj),
        )
        current[name] = snapshot

    # 2. Если нет сохранённой схемы — сохранить и выйти
    if not snapshot_path.exists():
        import json
        data = {
            name: [f.__dict__ for f in snap.fields]
            for name, snap in current.items()
        }
        snapshot_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"Schema snapshot saved: {snapshot_path}")
        return []

    # 3. Загрузить сохранённую схему
    import json
    saved_data = json.loads(snapshot_path.read_text())
    saved: dict[str, SchemaSnapshot] = {}
    for name, fields_data in saved_data.items():
        saved[name] = SchemaSnapshot(
            module=contracts_package,
            class_name=name,
            fields=[SchemaEntry(**f) for f in fields_data],
        )

    # 4. Сравнить
    for name in saved:
        if name not in current:
            all_errors.append(f"FAIL: Contract {name} was removed")
            continue
        errors = check_compatibility(saved[name], current[name])
        all_errors.extend(errors)

    return all_errors


if __name__ == "__main__":
    errors = run_compatibility_check()
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("Contract compatibility: OK")
