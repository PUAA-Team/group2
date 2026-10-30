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


def csrf_token(raw_session: str):
    return hmac.new(raw_session.encode(), b"model-platform:csrf:v1", hashlib.sha256).hexdigest()
