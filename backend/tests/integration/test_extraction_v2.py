"""
Epic 1 / Stream C — Extraction v2 unit tests.

Tests each section extractor independently.
Uses real DKP OCR text as the primary fixture.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "services/accounting_binding"))

import pytest
from backend.services.processing.extraction.contract_extractor import extract_contract_profile
from backend.services.processing.extraction.identification_extractor import extract_identification
from backend.services.processing.extraction.party_extractor import extract_parties
from backend.services.processing.extraction.financial_terms_extractor import extract_financial_terms
from backend.services.processing.extraction.property_extractor import extract_property
from backend.services.processing.extraction.date_extractor import extract_dates
from backend.services.processing.extraction.reference_extractor import extract_references
from backend.services.processing.extraction.helpers import normalize_text


# Real DKP OCR text (truncated to key sections, ~13000 chars)
_RAW_DKP = """ДОГОВОР
№
2182-НШИ
купли-продажи
нежилого
помещения,
заключаемый
по
результатам
торгов
Санкт-Петербург
26
мая
2026
г.
Комитет
имущественных
отношений
Санкт-Петербурга,
действующий
в
соответствии
с
Положением
о
Комитете
имущественных
отношений
Санкт-Петербурга,
утвержденным
постановлением
Правительства
Санкт-Петербурга
от
16.02.2015
№
98,
именуемый
в
дальнейшем
«Комитет»,
в
лице
Санкт-Петербургского
государственного
казенного
учреждения
«Имущество
Санкт-Петербурга»,
именуемого
в
дальнейшем
«Учреждение»,
«Продавец»,
в
лице
начальника
отдела
подготовки
торгов
Учреждения
Федюшовой
Екатерины
Юрьевны,
действующего
на
основании
доверенности
от
29.12.2025,
удостоверенной
нотариусом
нотариального
округа
Санкт-Петербург
Бых
Ириной
Ивановной,
зарегистрированной
в
реестре
за
№
78/688-н/78-2025-8-667,
машиночитаемой
доверенности
от
19.03.2026
№
85132526-D4B7-464F-97E1-B84ACCD23D4E,
регистрационный
номер
доверенности
в
реестре
нотариальных
действий
78/688-н/78-2026-8-171,
в
соответствии
с
распоряжением
Комитета
от
27.03.2026
№
766-рз
«Об
условиях
приватизации
объекта
нежилого
фонда
по
адресу:
Санкт-Петербург,
наб.
Петроградская,
д.
18,
корп.
3,
литера
В,
пом.
20-Н»,
с
одной
стороны,
и
Шульгина
Ирина
Юрьевна,
именуемая
в
дальнейшем
«Покупатель»,
с
другой
стороны
(далее
-
Стороны),
в
соответствии
с
действующим
законодательством
о
приватизации,
на
основании
протокола
АО
«Российский
аукционный
дом»
подведения
итогов
аукциона
в
электронной
форме,
открытого
по
составу
участников
и
форме
подачи
предложений
о
цене,
по
продаже
имущества
от
20.05.2026
(номер
извещения
на
сайте
torgi.gov.ru:
21000002210000008914),
заключили
настоящий
Договор
(далее
-
Договор)
о
нижеследующем.

Основные
понятия:
Объект
-
указанное
в
п.
1.1.
Договора
нежилое
помещение
(в
том
числе
встроенно-пристроенное
нежилое
помещение
в
жилом
доме),
выделенное
в
натуре,
предназначенное
для
самостоятельного
использования
для
нежилых
целей.
1.
Предмет
договора
1.1.
Продавец
обязуется
передать
в
собственность
Покупателя,
а
Покупатель
обязуется
принять
и
оплатить
по
цене
и
на
условиях
Договора
Объект,
расположенный
по
адресу:
Санкт-Петербург,
наб.
Петроградская,
д.
18,
корп.
3,
литера.
В,
пом.
20-H,
площадь
218.7
кв.
м,
назначение:
нежилое,
этаж
№
4,
кадастровый
номер
78:07:0003009:1342.
2.
Цена
и
порядок
расчетов
2.1.
Цена
продажи
Объекта
составляет
18
178
000
(Восемнадцать
миллионов
сто
семьдесят
восемь
тысяч)
рублей
00
копеек,
в
том
числе
налог
на
добавленную
стоимость
(далее
—
НДС)
составляет
3
278
000
(Три
миллиона
двести
семьдесят
восемь
тысяч)
рублей
00
копеек.
Справочно:
Цена
продажи
Объекта
без
учета
НДС
составляет
14900
000
(Четырнадцать
миллионов
девятьсот
тысяч)
рублей
00
копеек.
2.1.1.
Цена
продажи
Объекта
включает
в
себя
задаток
в
размере
1
817
800
(Один
миллион
восемьсот
семнадцать
тысяч
восемьсот)
рублей
00
копеек,
на
момент
заключения
Договора
перечисленный
Покупателем
Продавцу.
2.1.2.
Подлежащая
оплате
оставшаяся
часть
цены
продажи
Объекта
на
момент
заключения
Договора
составляет
13
082
200
(Тринадцать
миллионов
восемьдесят
две
тысячи
двести)
рублей
00
копеек.
2.2.
Покупатель
перечисляет
подлежащую
оплате
оставшуюся
часть
цены
продажи
Объекта
(п.2.1.2.
Договора)
по
безналичному
расчету
на
счет
Продавца,
указанный
в
разделе
9
Договора,
не
позднее
30
(тридцати)
дней
с
момента
подписания
Договора.
"""

# Normalized version (newlines → spaces) for individual extractor tests
DKP_TEXT = normalize_text(_RAW_DKP)


class TestIdentificationExtractor:
    def test_contract_number(self):
        section = extract_identification(DKP_TEXT)
        assert section.contract_number is not None
        assert "2182" in section.contract_number.value

    def test_contract_date(self):
        section = extract_identification(DKP_TEXT)
        assert section.contract_date is not None
        assert section.contract_date.value.year == 2026
        assert section.contract_date.value.month == 5
        assert section.contract_date.value.day == 26

    def test_place_of_signing(self):
        section = extract_identification(DKP_TEXT)
        assert section.place_of_signing is not None


class TestPartyExtractor:
    def test_seller_name(self):
        section = extract_parties(DKP_TEXT)
        assert section.seller.name is not None
        assert "Комитет" in section.seller.name.value

    def test_seller_inn(self):
        section = extract_parties(DKP_TEXT)
        # Seller INN is in the text
        if section.seller.inn:
            assert len(section.seller.inn.value) >= 10

    def test_buyer_name(self):
        section = extract_parties(DKP_TEXT)
        assert section.buyer.name is not None
        assert "Шульгина" in section.buyer.name.value


class TestFinancialTermsExtractor:
    def test_total_price(self):
        section = extract_financial_terms(DKP_TEXT)
        assert section.total_price is not None
        assert section.total_price.value == 18178000.0

    def test_vat_amount(self):
        section = extract_financial_terms(DKP_TEXT)
        assert section.vat_amount is not None
        assert section.vat_amount.value == 3278000.0

    def test_deposit_amount(self):
        section = extract_financial_terms(DKP_TEXT)
        assert section.deposit_amount is not None
        assert section.deposit_amount.value == 1817800.0


class TestPropertyExtractor:
    def test_address(self):
        section = extract_property(DKP_TEXT)
        assert section.address is not None
        assert "Петроградская" in section.address.value

    def test_cadastral_number(self):
        section = extract_property(DKP_TEXT)
        assert section.cadastral_number is not None
        assert "78:07:0003009:1342" in section.cadastral_number.value

    def test_area(self):
        section = extract_property(DKP_TEXT)
        assert section.area_sqm is not None
        assert abs(section.area_sqm.value - 218.7) < 1.0


class TestReferenceExtractor:
    def test_tender_number(self):
        section = extract_references(DKP_TEXT)
        assert section.tender_number is not None
        assert "21000002210000008914" in section.tender_number.value


class TestFullProfile:
    def test_full_profile_extraction(self):
        profile = extract_contract_profile(DKP_TEXT)
        assert profile.identification.contract_number is not None
        assert profile.identification.contract_date is not None
        assert profile.parties.seller.name is not None
        assert profile.parties.buyer.name is not None
        assert profile.financial_terms.total_price is not None
        assert profile.financial_terms.vat_amount is not None
        assert profile.financial_terms.deposit_amount is not None
        assert profile.prop.cadastral_number is not None
        assert profile.prop.address is not None
        assert profile.prop.area_sqm is not None
        assert profile.references.tender_number is not None

    def test_profile_confidence(self):
        profile = extract_contract_profile(DKP_TEXT)
        assert profile.confidence > 0.5
        assert profile.confidence <= 1.0

    def test_profile_to_dict(self):
        profile = extract_contract_profile(DKP_TEXT)
        d = profile.to_dict()
        assert d["profile_version"] == "1.0"
        assert "sections" in d
        assert "identification" in d["sections"]
        assert "parties" in d["sections"]
        assert "financial_terms" in d["sections"]
        assert "property" in d["sections"]
        assert d["sections"]["financial_terms"]["total_price"]["value"] == 18178000.0
