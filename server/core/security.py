"""Password and access-token primitives (FUNCTIONAL_SPEC 5.8).

Passwords are compared by plain string equality — no hashing (SPEC.md 7.1 keeps
the reference behaviour). Tokens are standard HS256 JWTs with an `exp`; they are
signed with a hardcoded key and decoded to `None` on any failure, so a caller
turns a bad token into 401 rather than an exception.

Only the standard library is used: the reference implementation signed tokens
with a third-party lib, but this repo's dependency list does not carry one, and
an HS256 token is a handful of lines of `hmac` + `base64`.
"""

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from typing import Any

from core.config import Settings, get_settings


def verify_password(plain: str, stored: str) -> bool:
    """直接字符串相等比较，不做任何变换（FUNCTIONAL_SPEC 5.8）。"""
    return plain == stored


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _sign(signing_input: bytes, settings: Settings) -> str:
    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    return _b64url_encode(digest)


def create_access_token(
    data: Mapping[str, Any], *, settings: Settings | None = None
) -> str:
    """Sign `data` plus `iat`/`exp` into a JWT (FUNCTIONAL_SPEC 5.8「令牌规则」)."""
    active = settings or get_settings()
    issued_at = int(time.time())
    claims = {
        **data,
        "iat": issued_at,
        "exp": issued_at + active.jwt_expire_minutes * 60,
    }
    header = _b64url_encode(
        json.dumps({"alg": active.jwt_algorithm, "typ": "JWT"}).encode("utf-8")
    )
    payload = _b64url_encode(
        json.dumps(claims, ensure_ascii=False).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    return f"{header}.{payload}.{_sign(signing_input, active)}"


def decode_access_token(
    token: str, *, settings: Settings | None = None
) -> dict[str, Any] | None:
    """Return the claims, or `None` for any invalid/expired/tampered token."""
    active = settings or get_settings()
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode("ascii")
        if not hmac.compare_digest(_sign(signing_input, active), signature):
            return None
        claims = json.loads(_b64url_decode(payload))
        if claims.get("exp") is not None and int(claims["exp"]) < int(time.time()):
            return None
        return claims
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
