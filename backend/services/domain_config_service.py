"""Domain Configuration Service — multi-tenant URL generation.

AP-1: Zero Hardcode — all domains via config.
AP-3: Multi-Tenant Ready — any domain works.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass
class DomainConfig:
    primary_domain: str = "spcnn.ru"
    ssl_enabled: bool = True
    api_subdomain: str = "api"
    crm_subdomain: str = "crm"
    admin_subdomain: str = "admin"
    executive_subdomain: str = "executive"
    analytics_subdomain: str = "analytics"

    @property
    def protocol(self) -> str:
        return "https" if self.ssl_enabled else "http"

    def full_url(self, subdomain: str) -> str:
        return f"{self.protocol}://{subdomain}.{self.primary_domain}"

    @property
    def api_url(self) -> str:
        return self.full_url(self.api_subdomain)

    @property
    def crm_url(self) -> str:
        return self.full_url(self.crm_subdomain)

    @property
    def admin_url(self) -> str:
        return self.full_url(self.admin_subdomain)

    @property
    def executive_url(self) -> str:
        return self.full_url(self.executive_subdomain)

    @property
    def analytics_url(self) -> str:
        return self.full_url(self.analytics_subdomain)

    def api_path(self, path: str) -> str:
        return urljoin(f"{self.api_url}/", path.lstrip("/"))

    def crm_path(self, path: str) -> str:
        return urljoin(f"{self.crm_url}/", path.ltrim("/"))

    def admin_path(self, path: str) -> str:
        return urljoin(f"{self.admin_url}/", path.lstrip("/"))

    @classmethod
    def from_settings(cls, settings: dict[str, str]) -> DomainConfig:
        return cls(
            primary_domain=settings.get("primary_domain", "spcnn.ru"),
            ssl_enabled=settings.get("ssl_enabled", "true").lower() == "true",
            api_subdomain=settings.get("api_subdomain", "api"),
            crm_subdomain=settings.get("crm_subdomain", "crm"),
            admin_subdomain=settings.get("admin_subdomain", "admin"),
            executive_subdomain=settings.get("executive_subdomain", "executive"),
            analytics_subdomain=settings.get("analytics_subdomain", "analytics"),
        )
