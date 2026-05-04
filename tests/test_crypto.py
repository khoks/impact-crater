"""Tests for the Fernet crypto helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from impact_crater import crypto, paths


def test_key_generated_on_first_use(isolated_home: Path) -> None:
    key_path = paths.fernet_key_path()
    assert not key_path.exists()
    key = crypto.get_or_create_key()
    assert key_path.is_file()
    assert key == key_path.read_bytes().strip()
    assert len(key) > 0


def test_key_reused_on_subsequent_calls(isolated_home: Path) -> None:
    k1 = crypto.get_or_create_key()
    k2 = crypto.get_or_create_key()
    assert k1 == k2


def test_encrypt_decrypt_round_trip(isolated_home: Path) -> None:
    plaintext = "sk-ant-some-secret-token-001"
    cipher = crypto.encrypt(plaintext)
    assert cipher != plaintext
    assert crypto.decrypt(cipher) == plaintext


def test_empty_string_passthrough(isolated_home: Path) -> None:
    assert crypto.encrypt("") == ""
    assert crypto.decrypt("") == ""


def test_corrupted_key_raises(isolated_home: Path) -> None:
    # Create a deliberately invalid key file.
    paths.db_dir()
    paths.fernet_key_path().write_bytes(b"not-a-valid-fernet-key")
    with pytest.raises(crypto.FernetUnavailable):
        crypto.get_or_create_key()


def test_decrypt_wrong_ciphertext_raises(isolated_home: Path) -> None:
    crypto.get_or_create_key()  # ensure a valid key exists
    with pytest.raises(crypto.FernetUnavailable):
        crypto.decrypt("definitely-not-fernet-output")
