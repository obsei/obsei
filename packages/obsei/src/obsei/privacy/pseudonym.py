"""Salted, keyed pseudonyms for author identities.

Handles are replaced with an HMAC-SHA256 pseudonym at ingest. The salt is
per-install and secret, so pseudonyms can't be reversed by hashing guessed
handles. Pseudonymised data is still personal data under GDPR; this reduces
risk, it does not anonymise.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import unicodedata

SALT_ENV_VAR = "OBSEI_PSEUDONYM_SALT"
MIN_SALT_BYTES = 16


class PseudonymSaltError(ValueError):
    """The pseudonym salt is missing or too short."""


def load_salt(env_var: str = SALT_ENV_VAR) -> bytes:
    """Read the per-install salt from the environment."""
    value = os.environ.get(env_var, "")
    salt = value.encode("utf-8")
    if len(salt) < MIN_SALT_BYTES:
        raise PseudonymSaltError(
            f"{env_var} must be set to a secret of at least {MIN_SALT_BYTES} bytes"
        )
    return salt


def pseudonymize(handle: str, salt: bytes) -> str:
    """Return a stable pseudonym for ``handle``, e.g. ``psn_3f1a...`` (32 hex chars)."""
    if len(salt) < MIN_SALT_BYTES:
        raise PseudonymSaltError(f"salt must be at least {MIN_SALT_BYTES} bytes")
    normalized = unicodedata.normalize("NFKC", handle).strip().casefold()
    if not normalized:
        raise ValueError("handle must not be empty")
    digest = hmac.new(salt, normalized.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"psn_{digest[:32]}"
