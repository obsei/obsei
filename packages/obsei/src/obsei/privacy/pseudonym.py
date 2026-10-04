"""Salted HMAC pseudonyms for author handles. Pseudonymised data is still personal data."""

from __future__ import annotations

import hashlib
import hmac
import os
import unicodedata

SALT_ENV_VAR = "OBSEI_PSEUDONYM_SALT"
MIN_SALT_BYTES = 16


class PseudonymSaltError(ValueError):
    pass


def load_salt(env_var: str = SALT_ENV_VAR) -> bytes:
    salt = os.environ.get(env_var, "").encode("utf-8")
    if len(salt) < MIN_SALT_BYTES:
        raise PseudonymSaltError(
            f"{env_var} must be set to a secret of at least {MIN_SALT_BYTES} bytes"
        )
    return salt


def pseudonymize(handle: str, salt: bytes) -> str:
    if len(salt) < MIN_SALT_BYTES:
        raise PseudonymSaltError(f"salt must be at least {MIN_SALT_BYTES} bytes")
    normalized = unicodedata.normalize("NFKC", handle).strip().casefold()
    if not normalized:
        raise ValueError("handle must not be empty")
    digest = hmac.new(salt, normalized.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"psn_{digest[:32]}"
