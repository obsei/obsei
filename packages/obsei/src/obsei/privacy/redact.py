"""Checksum-validated PII redaction applied at ingest, grouped into region packs.

Digits are matched in any script (Arabic-Indic, Devanagari, full-width, ...). Best-effort:
it does not detect personal names.
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias

from obsei.core.record import Record

Region: TypeAlias = Literal[
    "global", "north_america", "uk", "eu", "latam", "apac", "india", "africa"
]
ALL_REGIONS: tuple[Region, ...] = (
    "global",
    "north_america",
    "uk",
    "eu",
    "latam",
    "apac",
    "india",
    "africa",
)

_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_CF_ODD = {
    **dict(zip("0123456789", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21), strict=True)),
    **dict(
        zip(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            (
                1,
                0,
                5,
                7,
                9,
                13,
                15,
                17,
                19,
                21,
                2,
                4,
                18,
                20,
                11,
                3,
                6,
                8,
                12,
                14,
                16,
                10,
                22,
                25,
                24,
                23,
            ),
            strict=True,
        )
    ),
}
_NRIC_ST = "JZIHGFEDCBA"
_NRIC_FG = "XWUTRQPNMLK"
_MIN_PHONE_DIGITS = 9
_MAX_PHONE_DIGITS = 15


def ascii_digits(value: str) -> str:
    """Digits of ``value`` in ASCII, whatever script they were written in."""
    return "".join(str(unicodedata.digit(c)) for c in value if c.isdigit())


def _ints(value: str) -> list[int]:
    return [int(d) for d in ascii_digits(value)]


def _weighted(digits: Sequence[int], weights: Sequence[int]) -> int:
    return sum(d * w for d, w in zip(digits, weights, strict=False))


def luhn_valid(value: str) -> bool:
    digits = _ints(value)
    total = 0
    for i, d in enumerate(reversed(digits)):
        doubled = d * 2 if i % 2 else d
        total += doubled - 9 if doubled > 9 else doubled  # noqa: PLR2004
    return bool(digits) and total % 10 == 0


def verhoeff_valid(value: str) -> bool:
    check = 0
    for i, d in enumerate(reversed(_ints(value))):
        check = _VERHOEFF_D[check][_VERHOEFF_P[i % 8][d]]
    return check == 0


def iban_valid(value: str) -> bool:
    compact = re.sub(r"\s", "", value).upper()
    numeric = "".join(str(int(c, 36)) for c in compact[4:] + compact[:4])
    return int(numeric) % 97 == 1


def aadhaar_valid(value: str) -> bool:
    digits = ascii_digits(value)
    return digits[0] not in "01" and verhoeff_valid(digits)


def us_ssn_valid(value: str) -> bool:
    area, group, serial = value.split("-")
    return area not in {"000", "666"} and area[0] != "9" and group != "00" and serial != "0000"


def nhs_valid(value: str) -> bool:
    d = _ints(value)
    check = 11 - _weighted(d[:9], range(10, 1, -1)) % 11
    return check != 10 and (check % 11) == d[9]  # noqa: PLR2004


def fr_nir_valid(value: str) -> bool:
    d = ascii_digits(value)
    return 97 - int(d[:13]) % 97 == int(d[13:])


def es_dni_valid(value: str) -> bool:
    v = value.upper()
    number = {"X": "0", "Y": "1", "Z": "2"}.get(v[0], v[0]) + v[1:-1]
    return _DNI_LETTERS[int(number) % 23] == v[-1]


def it_cf_valid(value: str) -> bool:
    v = value.upper()
    total = sum(
        _CF_ODD[c] if i % 2 == 0 else (int(c) if c.isdigit() else ord(c) - ord("A"))
        for i, c in enumerate(v[:15])
    )
    return chr(ord("A") + total % 26) == v[15]


def nl_bsn_valid(value: str) -> bool:
    d = _ints(value)
    return (_weighted(d[:8], range(9, 1, -1)) - d[8]) % 11 == 0


def pl_pesel_valid(value: str) -> bool:
    d = _ints(value)
    return (10 - _weighted(d[:10], (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)) % 10) % 10 == d[10]


def br_cpf_valid(value: str) -> bool:
    d = _ints(value)
    if len(set(d)) == 1:
        return False
    first = _weighted(d[:9], range(10, 1, -1)) * 10 % 11 % 10
    second = _weighted(d[:10], range(11, 1, -1)) * 10 % 11 % 10
    return d[9] == first and d[10] == second


def cn_id_valid(value: str) -> bool:
    d = _ints(value[:17])
    check = "10X98765432"[_weighted(d, (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)) % 11]
    return value[17].upper() == check


def sg_nric_valid(value: str) -> bool:
    v = value.upper()
    total = _weighted(_ints(v[1:8]), (2, 7, 6, 5, 4, 3, 2)) + (4 if v[0] in "TG" else 0)
    table = _NRIC_ST if v[0] in "ST" else _NRIC_FG
    return table[total % 11] == v[8]


def jp_my_number_valid(value: str) -> bool:
    d = _ints(value)
    weights = (6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    remainder = _weighted(d[:11], weights) % 11
    return d[11] == (0 if remainder <= 1 else 11 - remainder)


def au_tfn_valid(value: str) -> bool:
    return _weighted(_ints(value), (1, 4, 3, 7, 5, 8, 6, 9, 10)) % 11 == 0


def _phone_valid(value: str) -> bool:
    return _MIN_PHONE_DIGITS <= len(ascii_digits(value)) <= _MAX_PHONE_DIGITS


def _ip_valid(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class PiiPattern:
    label: str
    region: Region
    regex: re.Pattern[str]
    validate: Callable[[str], bool] | None = None


_START = r"(?<![\dA-Za-z])(?<!\d[ .\-])"
_END = r"(?![\dA-Za-z])(?![ .\-]\d)"


def _p(
    label: str, region: Region, regex: str, validate: Callable[[str], bool] | None = None
) -> PiiPattern:
    # \b treats CJK and other scripts as word characters; bound on ASCII alphanumerics instead.
    regex = re.sub(r"^\\b", lambda _: _START, regex)
    regex = re.sub(r"\\b$", lambda _: _END, regex)
    return PiiPattern(label, region, re.compile(regex), validate)


_SEP = r"[ \-.]?"
_DASHES = "\\-\u2010\u2011\u2012\u2013\u2014\u2212\uff0d"

# Order matters: specific checksum-validated identifiers run before the generic phone pattern.
PATTERNS: tuple[PiiPattern, ...] = (
    _p("EMAIL", "global", r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    _p(
        "IBAN", "global", r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b", iban_valid
    ),
    _p("CARD", "global", r"\b(?:\d[ -]?){12,18}\d\b", luhn_valid),
    _p("US_SSN", "north_america", r"\b\d{3}-\d{2}-\d{4}\b", us_ssn_valid),
    _p("CA_SIN", "north_america", r"\b\d{3}[ -]\d{3}[ -]\d{3}\b", luhn_valid),
    _p(
        "UK_NINO",
        "uk",
        r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]"
        r" ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b",
    ),
    _p("UK_NHS", "uk", rf"\b\d{{3}}{_SEP}\d{{3}}{_SEP}\d{{4}}\b", nhs_valid),
    _p("FR_NIR", "eu", r"\b[12] ?\d{2} ?\d{2} ?\d{2} ?\d{3} ?\d{3} ?\d{2}\b", fr_nir_valid),
    _p("ES_DNI", "eu", r"\b[XYZ]?\d{7,8}-?[A-Z]\b", lambda v: es_dni_valid(v.replace("-", ""))),
    _p("IT_CF", "eu", r"\b[A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z]\b", it_cf_valid),
    _p("PL_PESEL", "eu", r"\b\d{11}\b", pl_pesel_valid),
    _p("NL_BSN", "eu", r"\b\d{9}\b", nl_bsn_valid),
    _p("BR_CPF", "latam", r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", br_cpf_valid),
    _p("MX_CURP", "latam", r"\b[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d\b"),
    _p("CN_ID", "apac", r"\b\d{17}[\dXx]\b", cn_id_valid),
    _p("SG_NRIC", "apac", r"\b[STFG]\d{7}[A-Z]\b", sg_nric_valid),
    _p("JP_MY_NUMBER", "apac", rf"\b\d{{4}}{_SEP}\d{{4}}{_SEP}\d{{4}}\b", jp_my_number_valid),
    _p("AU_TFN", "apac", rf"\b\d{{3}}{_SEP}\d{{3}}{_SEP}\d{{3}}\b", au_tfn_valid),
    _p("IN_AADHAAR", "india", r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b", aadhaar_valid),
    _p("IN_PAN", "india", r"\b[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]\b"),
    _p("ZA_ID", "africa", r"\b\d{13}\b", luhn_valid),
    _p("IPV4", "global", r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", _ip_valid),
    _p("IPV6", "global", r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b", _ip_valid),
    _p("PHONE", "global", rf"{_START}[+＋]?\d[\d\s().{_DASHES}]{{7,}}\d{_END}", _phone_valid),
)


def patterns_for(regions: Iterable[Region] = ALL_REGIONS) -> tuple[PiiPattern, ...]:
    wanted = set(regions)
    return tuple(p for p in PATTERNS if p.region in wanted)


def redact_text(text: str, patterns: Sequence[PiiPattern] = PATTERNS) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for pattern in patterns:

        def replace(match: re.Match[str], p: PiiPattern = pattern) -> str:
            if p.validate is not None and not p.validate(match.group()):
                return match.group()
            counts[p.label] = counts.get(p.label, 0) + 1
            return f"<{p.label}>"

        text = pattern.regex.sub(replace, text)
    return text, counts


class RegexRedactor:
    def __init__(self, regions: Iterable[Region] = ALL_REGIONS) -> None:
        self.patterns = patterns_for(regions)

    def redact(self, batch: Sequence[Record]) -> list[Record]:
        return [
            record.model_copy(
                update={
                    "text": redact_text(record.text, self.patterns)[0],
                    "context": {
                        k: redact_text(v, self.patterns)[0] for k, v in record.context.items()
                    },
                }
            )
            for record in batch
        ]
