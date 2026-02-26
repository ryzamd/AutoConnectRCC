"""
RCC License Decrypt Utility
Decrypts an AES-256-GCM encrypted license.dat file locally using the
activation password.

Crypto implementation is IDENTICAL to rcc-engine/tools/license_tool.py.
Any change to the encryption scheme MUST be mirrored here.
"""

import base64
import json
import logging
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# ── Constants (must match rcc-engine) ─────────────────────────
PBKDF2_ITERATIONS = 200_000


class DecryptionError(Exception):
    """Raised when license decryption fails (wrong password or tampered data)."""


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES key from password using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def _decrypt_data(encrypted_blob: bytes, password: str, salt: bytes) -> str:
    """
    AES-256-GCM decrypt an encrypted blob.

    Args:
        encrypted_blob: nonce(12B) || ciphertext+tag
        password: activation password
        salt: PBKDF2 salt stored in license.dat

    Returns:
        Decrypted JSON string.

    Raises:
        DecryptionError: if the password is wrong or data was tampered.
    """
    key   = _derive_key(password, salt)
    nonce = encrypted_blob[:12]
    ct    = encrypted_blob[12:]
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
    except Exception as e:
        raise DecryptionError(f"Decryption failed — wrong password or corrupted data: {e}")


def decrypt_license(license_path: str, password: str) -> dict:
    """
    Read and decrypt an encrypted license.dat file.

    Args:
        license_path: path to the license.dat file
        password: activation password

    Returns:
        Decrypted license data dict containing:
        - hwid, tier, max_devices, issued_at, can_active_before,
          password_hash, transfer_token, transfer_count_remaining, issuer

    Raises:
        FileNotFoundError: if license.dat does not exist
        DecryptionError: if decryption fails
        ValueError: if the file format is invalid
    """
    path = Path(license_path)
    if not path.exists():
        raise FileNotFoundError(f"License file not found: {license_path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid license file format: {e}")

    # Check for v2 encrypted format
    if "encrypted_data" not in raw or "pbkdf2_salt" not in raw:
        raise ValueError(
            "License file is not v2 encrypted format. "
            "Expected keys: pbkdf2_salt, encrypted_data, signature"
        )

    try:
        salt           = base64.b64decode(raw["pbkdf2_salt"])
        encrypted_blob = base64.b64decode(raw["encrypted_data"])
    except Exception as e:
        raise ValueError(f"Failed to decode base64 fields: {e}")

    logger.info("Decrypting license (PBKDF2 %d iterations)...", PBKDF2_ITERATIONS)
    decrypted_json = _decrypt_data(encrypted_blob, password, salt)

    try:
        data = json.loads(decrypted_json)
    except json.JSONDecodeError as e:
        raise DecryptionError(f"Decrypted data is not valid JSON: {e}")

    logger.info("License decrypted: tier=%s, hwid=%s...",
                data.get("tier"), str(data.get("hwid", ""))[:16])
    return data
