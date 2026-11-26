import hashlib
import hmac
import secrets


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str):
    salt = secrets.token_bytes(16)
    result = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${result.hex()}"


def verify_password(password: str, encoded: str):
    _, salt, expected = encoded.split("$")
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return hmac.compare_digest(actual.hex(), expected)


_FALLBACK_CSRF_KEY = secrets.token_hex(32)


def hmac_digest(value: str, secret: str):
    """HMAC-SHA-256 摘要：用于一次性凭据（如密码重置码），库里只存摘要。"""
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def csrf_token(raw_session: str, secret: str | None = None):
    key = (secret or _FALLBACK_CSRF_KEY).encode()
    return hmac.new(key, f"model-platform:csrf:v2:{raw_session}".encode(), hashlib.sha256).hexdigest()
