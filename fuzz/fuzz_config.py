"""Untrusted obsei.yaml must fail with a config error, never crash."""

import sys

import atheris

with atheris.instrument_imports():
    from obsei.config import ConfigError, parse_config


def test_one_input(data: bytes) -> None:
    text = atheris.FuzzedDataProvider(data).ConsumeUnicodeNoSurrogates(8192)
    try:
        parse_config(text)
    except ConfigError:
        return


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
