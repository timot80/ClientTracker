from __future__ import annotations

from wifiops_probe.security import generate_token, parse_bearer_token, redact_token


def test_generate_token_returns_urlsafe_high_entropy_token():
    token = generate_token()

    assert len(token) >= 22
    assert " " not in token


def test_parse_bearer_token_accepts_bearer_scheme():
    assert parse_bearer_token("Bearer abc123") == "abc123"


def test_parse_bearer_token_strips_whitespace_after_bearer_prefix():
    assert parse_bearer_token("Bearer abc123 ") == "abc123"


def test_parse_bearer_token_rejects_empty_and_basic_scheme():
    assert parse_bearer_token("") == ""
    assert parse_bearer_token("Basic abc123") == ""


def test_redact_token_keeps_prefix_and_hides_rest_for_long_tokens():
    token = "abcd1234567890"

    redacted = redact_token(token)

    assert redacted.startswith("abcd")
    assert "1234567890" not in redacted
