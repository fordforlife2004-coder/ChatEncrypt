"""
crypto_util.py - All the encryption logic for Chat Encrypt, in one place.

Keeping crypto in a single shared module (instead of copy-pasting it into
the client) means there's exactly ONE implementation to reason about and
audit. The server never imports this file - it has no key and can't decrypt.
"""

import json
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# A fixed, shared salt so every client derives the SAME key from the same
# passphrase. (In a system with per-user stored passwords you'd use a random
# salt per user; here all peers must agree, so it's shared on purpose.)
SALT = b"ChatEncrypt-shared-salt-v1"

# High iteration count = slow to brute-force the passphrase. Roughly the
# OWASP guidance for PBKDF2-HMAC-SHA256. Imperceptible once at startup.
ITERATIONS = 600_000


def derive_key(passphrase: str) -> bytes:
    """Stretch a human passphrase into a strong 32-byte key for Fernet."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=ITERATIONS,
    )
    raw_key = kdf.derive(passphrase.encode())
    # Fernet expects the key as url-safe base64 text.
    return base64.urlsafe_b64encode(raw_key)


def make_cipher(passphrase: str) -> Fernet:
    """Build the cipher object everyone uses to encrypt/decrypt."""
    return Fernet(derive_key(passphrase))


def encrypt_payload(cipher: Fernet, payload: dict) -> bytes:
    """
    Encrypt a message dict and frame it for sending.

    Returns the Fernet token followed by a newline. Tokens are base64 and
    contain no newlines, so '\\n' is a safe separator between messages on
    the TCP stream (this is "message framing").
    """
    token = cipher.encrypt(json.dumps(payload).encode())
    return token + b"\n"


def decrypt_token(cipher: Fernet, token: bytes):
    """
    Decrypt one token back into a dict.

    Returns None if the token can't be decrypted - wrong passphrase, or the
    message was tampered with (Fernet verifies integrity, not just secrecy).
    """
    try:
        plaintext = cipher.decrypt(token)
    except InvalidToken:
        return None
    try:
        return json.loads(plaintext)
    except (ValueError, json.JSONDecodeError):
        return None
