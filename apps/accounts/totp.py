"""Two-step sign-in with an authenticator app (TOTP, RFC 6238) — standard
library only. Works with Google Authenticator, Microsoft Authenticator,
1Password, Aegis and the like."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30
DIGITS = 6
ISSUER = "Silai Rahm"


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode()


def code_at(secret, counter):
    key = base64.b32decode(secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10 ** DIGITS).zfill(DIGITS)


def verify(secret, code, now=None, window=1):
    """True if `code` is valid now (or one step earlier/later: clocks drift)."""
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if not secret or len(code) != DIGITS:
        return False
    counter = int((now if now is not None else time.time()) // STEP)
    return any(hmac.compare_digest(code_at(secret, counter + d), code) for d in range(-window, window + 1))


def uri(secret, account):
    label = quote(f"{ISSUER}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={ISSUER}&digits={DIGITS}&period={STEP}"


def _hash(code):
    return hashlib.sha256(code.replace("-", "").strip().lower().encode()).hexdigest()


def new_recovery_codes(count=8):
    """(codes to show once, hashes to store)."""
    codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _i in range(count)]
    return codes, [_hash(c) for c in codes]


def use_recovery_code(user, code):
    """Consume a one-time recovery code. True if it was valid."""
    hashed = _hash(str(code or ""))
    if hashed in (user.recovery_codes or []):
        user.recovery_codes = [h for h in user.recovery_codes if h != hashed]
        user.save(update_fields=["recovery_codes"])
        return True
    return False
