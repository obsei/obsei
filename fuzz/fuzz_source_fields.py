"""Field mapping over untrusted JSON from webhooks and REST APIs must never crash."""

import json
import sys

import atheris

with atheris.instrument_imports():
    from obsei.sources._common import as_float, as_text, html_to_text, lookup, parse_time


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    path = fdp.ConsumeUnicodeNoSurrogates(64)
    raw = fdp.ConsumeUnicodeNoSurrogates(4096)
    try:
        item = json.loads(raw)
    except (ValueError, RecursionError):
        item = raw
    value = lookup(item, path) if path else item
    parse_time(value)
    as_text(value)
    as_float(value)
    if isinstance(value, str):
        html_to_text(value)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
