from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from obsei import Record, SourceRef
from obsei.privacy import redact as r
from obsei.privacy.redact import RegexRedactor, ascii_digits, patterns_for, redact_text


@pytest.mark.parametrize(
    ("validator", "valid", "invalid"),
    [
        (r.us_ssn_valid, "123-45-6789", "000-12-3456"),
        (r.luhn_valid, "046 454 286", "046 454 287"),
        (r.nhs_valid, "943 476 5919", "943 476 5918"),
        (r.fr_nir_valid, "1 84 12 76 451 089 46", "184127645108947"),
        (r.es_dni_valid, "12345678Z", "12345678A"),
        (r.es_dni_valid, "X1234567L", "X1234567A"),
        (r.it_cf_valid, "RSSMRA85T10A562S", "RSSMRA85T10A562T"),
        (r.nl_bsn_valid, "111222333", "123456789"),
        (r.pl_pesel_valid, "44051401359", "44051401358"),
        (r.br_cpf_valid, "529.982.247-25", "111.111.111-11"),
        (r.cn_id_valid, "11010519491231002X", "110105194912310021"),
        (r.sg_nric_valid, "S1234567D", "S1234567A"),
        (r.jp_my_number_valid, "123456789018", "123456789010"),
        (r.au_tfn_valid, "123 456 782", "123 456 789"),
        (r.aadhaar_valid, "234123412346", "134123412346"),
        (r.iban_valid, "DE89 3704 0044 0532 0130 00", "DE88 3704 0044 0532 0130 00"),
    ],
)
def test_checksums(validator: Callable[[str], bool], valid: str, invalid: str) -> None:
    assert validator(valid)
    assert not validator(invalid)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail jane.doe+x@example.co.uk", "mail <EMAIL>"),
        ("card 4111 1111 1111 1111", "card <CARD>"),
        ("SSN 123-45-6789, SIN 046 454 286", "SSN <US_SSN>, SIN <CA_SIN>"),
        ("NHS 943 476 5919, NINO AB123456C", "NHS <UK_NHS>, NINO <UK_NINO>"),
        ("Meine IBAN: DE89 3704 0044 0532 0130 00", "Meine IBAN: <IBAN>"),
        ("Mi DNI es 12345678Z y mi CPF 529.982.247-25", "Mi DNI es <ES_DNI> y mi CPF <BR_CPF>"),
        ("codice fiscale RSSMRA85T10A562S", "codice fiscale <IT_CF>"),
        ("身份证11010519491231002X和NRIC S1234567D", "身份证<CN_ID>和NRIC <SG_NRIC>"),
        ("電話は０９０−１２３４−５６７８", "電話は<PHONE>"),
        ("اتصل بي على +٩٧١ ٥٠ ١٢٣ ٤٥٦٧", "اتصل بي على <PHONE>"),
        ("मेरा आधार २३४१ २३४१ २३४६", "मेरा आधार <IN_AADHAAR>"),
        ("PAN ABCPE1234F", "PAN <IN_PAN>"),
        ("from 192.168.1.10", "from <IPV4>"),
    ],
)
def test_redacts_across_regions_and_scripts(text: str, expected: str) -> None:
    assert redact_text(text)[0] == expected


@pytest.mark.parametrize(
    "text",
    [
        "Rated 4.5 on 2026-09-01, version 2.3.1.4.5, price 1,299.00",
        "SKU AB1234567890123, order #A1234, invoice 2024-001",
        "Card-like but invalid 4111 1111 1111 1112",
    ],
)
def test_leaves_ordinary_numbers_alone(text: str) -> None:
    assert redact_text(text) == (text, {})


def test_ascii_digits_any_script() -> None:
    assert ascii_digits("٣٤ ३४ ３４") == "343434"


def test_region_selection() -> None:
    eu_only = patterns_for(["eu"])
    assert {p.region for p in eu_only} == {"eu"}
    assert redact_text("SSN 123-45-6789", eu_only)[0] == "SSN 123-45-6789"


def test_record_redactor_covers_text_and_context() -> None:
    record = Record(
        source=SourceRef(type="csv", native_id="1"),
        text="reach me at a@b.co",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        context={"subject": "refund for 4111 1111 1111 1111"},
    )
    (redacted,) = RegexRedactor().redact([record])
    assert redacted.text == "reach me at <EMAIL>"
    assert redacted.context == {"subject": "refund for <CARD>"}
    assert redacted.id == record.id
