"""Redaction must handle any text quickly: catches crashes and catastrophic regex backtracking."""

import sys

import atheris

with atheris.instrument_imports():
    from obsei.privacy.redact import PATTERNS, redact_text


def test_one_input(data: bytes) -> None:
    text = atheris.FuzzedDataProvider(data).ConsumeUnicodeNoSurrogates(4096)
    redact_text(text, PATTERNS)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
