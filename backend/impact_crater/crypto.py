"""Fernet-based at-rest encryption for sensitive settings + connector tokens.

Per ADR-0013, the encryption key lives at `~/.impact-crater/db/.fernet-key`
with restrictive file permissions. Generated on first use and reused
thereafter; loss of the key file means all encrypted values become
unreadable (the user re-authenticates connectors / re-enters API keys).
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from impact_crater import paths


class FernetUnavailableError(RuntimeError):
    """Raised when the Fernet key file is missing or corrupted."""


def get_or_create_key() -> bytes:
    """Return the Fernet key bytes, generating + persisting on first call."""
    key_path = paths.fernet_key_path()
    if key_path.is_file():
        try:
            data = key_path.read_bytes().strip()
            # Validate it's a usable Fernet key.
            Fernet(data)
            return data
        except (InvalidToken, ValueError) as exc:
            raise FernetUnavailableError(
                f"Fernet key at {key_path} is corrupted; delete it to regenerate."
            ) from exc

    key = Fernet.generate_key()
    key_path.write_bytes(key + b"\n")
    paths.harden_secret_file(key_path)
    return key


def fernet() -> Fernet:
    return Fernet(get_or_create_key())


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string and return the URL-safe base64 ciphertext."""
    if plaintext == "":
        return ""
    token = fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet ciphertext (str → str)."""
    if ciphertext == "":
        return ""
    try:
        plain = fernet().decrypt(ciphertext.encode("ascii"))
    except InvalidToken as exc:
        raise FernetUnavailableError("Ciphertext does not validate against the current key.") from exc
    return plain.decode("utf-8")
