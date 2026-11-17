"""نسخة طبق الأصل من `backend/services/backup_crypto.py` في المنصة (R33) — أي تعديل هنا يتعمل هناك كمان.

تشفير النسخة الاحتياطية — بصيغة `openssl enc` بالظبط، فأي جهاز عليه openssl يفكّها بأمر واحد من غير كودنا.

الصيغة: `Salted__` + ملح ٨ بايت + AES-256-CBC (حشو PKCS7). المفتاح والـIV طالعين من الجملة السرّية
(`BACKUP_ENCRYPTION_KEY`) بـPBKDF2-HMAC-SHA256 بعدد لفّات ثابت (`PBKDF2_ITER`). ده نفس اللي بيعمله:

    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 \\
        -pass env:BACKUP_ENCRYPTION_KEY -in dashboard.db.gz.enc -out dashboard.db.gz

ليه CBC مش GCM؟ لأن `openssl enc` ما بيدعمش GCM، والأهم عندنا إن الفكّ يشتغل يوم الطوارئ على أي ماك أو سيرفر
من غير ما نحتاج كود المنصة نفسه. السلامة من التلف جوّه الملف نفسه: gzip فيه CRC،
وقاعدة SQLite بعد الفكّ بتتفحص بـ`PRAGMA integrity_check` (الدليل في المنصة: docs/backups/RESTORE_RUNBOOK.md).

⛔ المفتاح ما يتطبعش ولا يتسجّل في أي لوج. لو المتغيّر فاضي ⇒ النسخة بتطلع زي زمان (gzip بس) والملخص بيحذّر.
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"Salted__"
SALT_LEN = 8
HEADER_LEN = len(MAGIC) + SALT_LEN
PBKDF2_ITER = 200_000
KEY_ENV = "BACKUP_ENCRYPTION_KEY"

OPENSSL_DECRYPT_CMD = (
    "openssl enc -d -aes-256-cbc -pbkdf2 -iter %d -md sha256 "
    "-pass env:%s -in <FILE>.enc -out <FILE>" % (PBKDF2_ITER, KEY_ENV)
)


def backup_key() -> str:
    """الجملة السرّية من البيئة وقت النداء (مش وقت الاستيراد) — فتغييرها في الإعدادات + إعادة تشغيل يكفي."""
    return (os.getenv(KEY_ENV) or "").strip()


def is_encrypted(head: bytes) -> bool:
    return head[: len(MAGIC)] == MAGIC


def _derive(passphrase: str, salt: bytes, iterations: int = PBKDF2_ITER):
    raw = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=48)
    return raw[:32], raw[32:]


class StreamEncryptor:
    """تشفير متدفّق: `header()` الأول، وبعدين `update()` لكل قطعة، وفي الآخر `finalize()`."""

    def __init__(self, passphrase: str, salt: Optional[bytes] = None, iterations: int = PBKDF2_ITER):
        if not passphrase:
            raise ValueError("empty passphrase")
        self._salt = salt or os.urandom(SALT_LEN)
        key, iv = _derive(passphrase, self._salt, iterations)
        self._enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        self._pad = padding.PKCS7(128).padder()

    def header(self) -> bytes:
        return MAGIC + self._salt

    def update(self, data: bytes) -> bytes:
        return self._enc.update(self._pad.update(data)) if data else b""

    def finalize(self) -> bytes:
        return self._enc.update(self._pad.finalize()) + self._enc.finalize()


class StreamDecryptor:
    """فكّ متدفّق: أول ١٦ بايت (`Salted__` + الملح) بيتقروا لوحدهم، والباقي قطعة قطعة.
    مفتاح غلط ⇒ الحشو بيبوظ في `finalize()` ⇒ ValueError (أو gzip/sha256 بيرفض قبلها)."""

    def __init__(self, passphrase: str, iterations: int = PBKDF2_ITER):
        if not passphrase:
            raise ValueError("empty passphrase")
        self._pass = passphrase
        self._iter = iterations
        self._head = b""
        self._dec = None
        self._unpad = padding.PKCS7(128).unpadder()

    def update(self, data: bytes) -> bytes:
        if self._dec is None:
            self._head += data
            if len(self._head) < HEADER_LEN:
                return b""
            if not is_encrypted(self._head):
                raise ValueError("not an openssl-salted file")
            salt, data = self._head[len(MAGIC):HEADER_LEN], self._head[HEADER_LEN:]
            key, iv = _derive(self._pass, salt, self._iter)
            self._dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return self._unpad.update(self._dec.update(data)) if data else b""

    def finalize(self) -> bytes:
        if self._dec is None:
            raise ValueError("truncated encrypted file")
        return self._unpad.update(self._dec.finalize()) + self._unpad.finalize()


def encrypt_bytes(data: bytes, passphrase: str, salt: Optional[bytes] = None) -> bytes:
    enc = StreamEncryptor(passphrase, salt)
    return enc.header() + enc.update(data) + enc.finalize()


def decrypt_bytes(data: bytes, passphrase: str) -> bytes:
    dec = StreamDecryptor(passphrase)
    return dec.update(data) + dec.finalize()
