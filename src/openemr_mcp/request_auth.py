"""Request-scoped auth context for streamable HTTP transport."""

from __future__ import annotations

import base64
import json
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequestAuthContext:
    access_token: str
    refresh_token: str | None = None
    claims: dict[str, Any] | None = None

    @property
    def user_id(self) -> str | None:
        claims = self.claims or {}
        for key in ("preferred_username", "username", "sub", "user_id"):
            value = claims.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None


_request_auth_context: ContextVar[RequestAuthContext | None] = ContextVar("request_auth_context", default=None)


def get_request_auth_context() -> RequestAuthContext | None:
    return _request_auth_context.get()


def set_request_auth_context(context: RequestAuthContext | None) -> Token:
    return _request_auth_context.set(context)


def reset_request_auth_context(token: Token) -> None:
    _request_auth_context.reset(token)


def parse_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    scheme, _, token = header_value.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ValueError("Authorization header must use Bearer token")
    return token.strip()


def decode_jwt_claims(token: str) -> dict[str, Any] | None:
    """Best-effort JWT payload decode without signature validation."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return claims if isinstance(claims, dict) else None


def claims_are_active(claims: dict[str, Any]) -> bool:
    now = time.time()
    exp = claims.get("exp")
    if isinstance(exp, (int, float)) and exp <= now:
        return False
    nbf = claims.get("nbf")
    if isinstance(nbf, (int, float)) and nbf > now:
        return False
    return True
