"""Untrusted obsei.yaml must fail with a validation error, never crash."""

import sys

import atheris

with atheris.instrument_imports():
    import yaml
    from pydantic import ValidationError

    from obsei.config import ObseiConfig


def test_one_input(data: bytes) -> None:
    text = atheris.FuzzedDataProvider(data).ConsumeUnicodeNoSurrogates(8192)
    try:
        raw = yaml.safe_load(text)
        ObseiConfig.model_validate(raw)
    except (yaml.YAMLError, ValidationError):
        return


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
