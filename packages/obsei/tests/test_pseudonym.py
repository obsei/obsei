import pytest

from obsei import Author
from obsei.privacy import PseudonymSaltError, load_salt, pseudonymize

SALT = b"0123456789abcdef-test-salt"


def test_stable_and_normalized() -> None:
    assert pseudonymize("@Alice", SALT) == pseudonymize("  @alice ", SALT)


def test_salt_changes_output() -> None:
    assert pseudonymize("alice", SALT) != pseudonymize("alice", SALT + b"x")


def test_output_fits_author_model() -> None:
    Author(pseudonym=pseudonymize("alice", SALT))


def test_rejects_short_salt_and_empty_handle() -> None:
    with pytest.raises(PseudonymSaltError):
        pseudonymize("alice", b"short")
    with pytest.raises(ValueError, match="empty"):
        pseudonymize("   ", SALT)


def test_load_salt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OBSEI_PSEUDONYM_SALT", raising=False)
    with pytest.raises(PseudonymSaltError):
        load_salt()
    monkeypatch.setenv("OBSEI_PSEUDONYM_SALT", SALT.decode())
    assert load_salt() == SALT
