"""Adapter Registry — manages regulation source adapters."""

from __future__ import annotations

from backend.integrations.regulations.base_adapter import RegulationSourceAdapter
from backend.integrations.regulations.adapters import (
    RosreestrAdapter,
    FNSAdapter,
    CBRAdapter,
    GovernmentPortalAdapter,
    ConsultantAdapter,
    GarantAdapter,
)


class AdapterRegistry:
    """Реестр адаптеров источников нормативных актов."""

    _adapters: dict[str, type[RegulationSourceAdapter]] = {
        "rosreestr": RosreestrAdapter,
        "nalog": FNSAdapter,
        "cbr": CBRAdapter,
        "government_portal": GovernmentPortalAdapter,
        "consultant": ConsultantAdapter,
        "garant": GarantAdapter,
    }

    @classmethod
    def get_adapter(cls, source_type: str, **kwargs) -> RegulationSourceAdapter:
        adapter_cls = cls._adapters.get(source_type)
        if adapter_cls is None:
            raise ValueError(f"Unknown source type: {source_type}")
        return adapter_cls(**kwargs)

    @classmethod
    def list_available(cls) -> list[str]:
        return list(cls._adapters.keys())
