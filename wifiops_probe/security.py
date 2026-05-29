from __future__ import annotations

import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(24)


def parse_bearer_token(header: str) -> str:
    if not header.startswith("Bearer "):
        return ""
    return header[len("Bearer ") :].strip()


def redact_token(token: str) -> str:
    if len(token) <= 8:
        return "<redacted>"
    return f"{token[:4]}...<redacted>"
