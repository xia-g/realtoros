"""
NormalizationService — приводим разные представления к единому формату.

Каждый нормализатор независим.
Поддерживает: company names, person names, addresses,
              contract numbers, phones, emails, cadastre, bank accounts.

All in-memory. NO DB writes.
"""
from __future__ import annotations

import re


class NormalizationService:
    """Приводит идентификаторы к каноническому виду."""

    @staticmethod
    def normalize_company(name: str) -> str:
        """ООО Ромашка / ООО «Ромашка» / "Ромашка", ООО → одинаково."""
        if not name:
            return ""
        v = name.strip()
        v = v.replace('"', '').replace("«", "").replace("»", "").replace("'", "")
        v = re.sub(r"\s+", " ", v)
        v = v.strip(' "«»')
        v_lower = v.lower()

        # Извлечь ООО, АО, ЗАО, ИП etc
        prefixes = []
        if any(x in v_lower for x in ["ооо", "ооо", "общество с ограниченной ответственностью"]):
            prefixes.append("ооо")
        elif any(x in v_lower for x in ["ао", "акционерное общество"]):
            prefixes.append("ао")
        elif any(x in v_lower for x in ["зао", "закрытое акционерное"]):
            prefixes.append("зао")
        elif any(x in v_lower for x in ["ип", "индивидуальный предприниматель"]):
            prefixes.append("ип")
        elif any(x in v_lower for x in ["пао", "публичное акционерное"]):
            prefixes.append("пао")

        # Body = всё кроме префикса
        body = v
        remove_words = [
            "ооо", "ооо", "общество с ограниченной ответственностью",
            "ао", "акционерное общество", "зао", "закрытое акционерное общество",
            "ип", "индивидуальный предприниматель", "пао", "публичное акционерное общество",
        ]
        for w in sorted(remove_words, key=len, reverse=True):
            body = re.sub(rf"\b{re.escape(w)}\b", "", body, flags=re.IGNORECASE)

        body = re.sub(r"\s+", " ", body).strip(' ,"«»')
        pf = f"{prefixes[0]} " if prefixes else ""
        return pf + body.lower()

    @staticmethod
    def normalize_person(name: str) -> str:
        """ФИО → единый формат."""
        if not name:
            return ""
        v = name.strip()
        v = re.sub(r"\s+", " ", v)
        return v.lower()

    @staticmethod
    def normalize_address(address: str) -> str:
        """г. Санкт-Петербург, наб. Петроградская, д.18 → единый формат."""
        if not address:
            return ""
        v = address.lower().strip()
        # Replace abbreviations
        replacements = [
            (r"г\.\s*", "город "),
            (r"ул\.\s*", "улица "),
            (r"пр\.\s*", "проспект "),
            (r"д\.\s*", "дом "),
            (r"кв\.\s*", "квартира "),
            (r"стр\.\s*", "строение "),
            (r"пом\.\s*", "помещение "),
            (r"лит\.\s*", "литера "),
            (r"наб\.\s*", "набережная "),
            (r"корп\.\s*", "корпус "),
            (r"пер\.\s*", "переулок "),
            (r"ш\.\s*", "шоссе "),
        ]
        for pat, repl in replacements:
            v = re.sub(pat, repl, v)
        v = re.sub(r"\s+", " ", v).strip()
        v = v.replace(",", "").replace(".", "")
        return v

    @staticmethod
    def normalize_contract_number(number: str) -> str:
        """№2182-НП/И → 2182-нпи."""
        if not number:
            return ""
        v = number.strip()
        v = v.replace("№", "").replace("N", "").replace("#", "")
        v = v.strip().upper()
        v = re.sub(r"\s+", "", v)
        return v

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """8(921)123-45-67 → +79211234567."""
        if not phone:
            return ""
        v = "".join(c for c in phone if c.isdigit() or c == "+")
        if v.startswith("8") and len(v) == 11:
            v = "+7" + v[1:]
        elif not v.startswith("+") and len(v) == 10:
            v = "+7" + v
        return v

    @staticmethod
    def normalize_email(email: str) -> str:
        """TESt@Example.COM → test@example.com."""
        return email.strip().lower() if email else ""

    @staticmethod
    def normalize_cadastre(cadastre: str) -> str:
        """Убрать лишние пробелы и привести к единому формату."""
        if not cadastre:
            return ""
        return re.sub(r"\s+", "", cadastre.strip())

    @staticmethod
    def normalize_bank_account(account: str) -> str:
        return "".join(c for c in account if c.isdigit()) if account else ""
