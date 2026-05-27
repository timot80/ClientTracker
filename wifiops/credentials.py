from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    import keyring
    from keyring.errors import KeyringError, PasswordDeleteError
except ImportError:
    class KeyringError(Exception):
        pass

    class PasswordDeleteError(KeyringError):
        pass

    class _MissingKeyring:
        def get_password(self, service: str, key: str) -> str:
            raise KeyringError("Python package 'keyring' is not installed")

        def set_password(self, service: str, key: str, value: str) -> None:
            raise KeyringError("Python package 'keyring' is not installed")

        def delete_password(self, service: str, key: str) -> None:
            raise KeyringError("Python package 'keyring' is not installed")

    keyring = _MissingKeyring()


SERVICE_NAME = "wifiops"
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class CredentialConfigError(ValueError):
    """Raised when credential configuration cannot be resolved."""


class InvalidCredentialProfileError(CredentialConfigError):
    pass


class UnknownCredentialProfileError(CredentialConfigError):
    pass


class KeyringCredentialError(CredentialConfigError):
    pass


@dataclass(frozen=True)
class ResolvedCredentials:
    username: str = ""
    password: str = ""
    enable: str = ""


def validate_profile_name(profile: str) -> None:
    if not PROFILE_NAME_RE.fullmatch(profile):
        raise InvalidCredentialProfileError(f"Invalid credential profile name '{profile}'")


def profile_key(profile: str, field: str) -> str:
    validate_profile_name(profile)
    if field not in {"password", "enable"}:
        raise CredentialConfigError(f"Unsupported profile secret field '{field}'")
    return f"profile:{profile}:{field}"


def keyring_ref_to_key(ref: str) -> str:
    if not isinstance(ref, str) or not ref.strip():
        raise CredentialConfigError("Keyring reference must be a non-empty string")
    ref = ref.strip()
    if ref.startswith(f"{SERVICE_NAME}:"):
        key = ref[len(SERVICE_NAME) + 1 :]
        if not key:
            raise CredentialConfigError("Keyring reference must include a key name")
        return key
    return ref


def resolve_credentials(
    raw: dict[str, Any],
    section: str,
    env: Mapping[str, str],
    env_names: Mapping[str, str],
) -> ResolvedCredentials:
    section_data = _section_mapping(raw, section)
    profile_name = _optional_str(section_data.get("credential_profile"))
    profile_data: Mapping[str, Any] = {}
    if profile_name:
        required_needs_profile = any(
            _field_needs_profile(field, section_data, env, env_names)
            for field in ("username", "password")
        )
        try:
            if required_needs_profile or _field_needs_profile(
                "enable", section_data, env, env_names
            ):
                profile_data = _profile_mapping(raw, profile_name)
        except UnknownCredentialProfileError:
            if required_needs_profile:
                raise

    return ResolvedCredentials(
        username=_resolve_field("username", section_data, profile_data, env, env_names),
        password=_resolve_field("password", section_data, profile_data, env, env_names),
        enable=_resolve_field("enable", section_data, profile_data, env, env_names),
    )


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        return {}
    with cfg_path.open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    if not isinstance(loaded, dict):
        raise CredentialConfigError(f"Config file must contain a YAML mapping: {cfg_path}")
    return loaded


def save_yaml_config(path: str | Path, data: Mapping[str, Any]) -> None:
    cfg_path = Path(path)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(dict(data), fh, sort_keys=False)


def set_profile(path: str | Path, profile: str, username: str, password: str, enable: str = "") -> None:
    validate_profile_name(profile)
    if not username:
        raise CredentialConfigError("Profile username is required")
    if not password:
        raise CredentialConfigError("Profile password is required")

    data = load_yaml_config(path)
    credentials = data.setdefault("credentials", {})
    if not isinstance(credentials, dict):
        raise CredentialConfigError("credentials must be a mapping")
    profiles = credentials.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        raise CredentialConfigError("credentials.profiles must be a mapping")
    previous_entry = profiles.get(profile)
    if not isinstance(previous_entry, dict):
        previous_entry = {}

    password_key = profile_key(profile, "password")
    enable_key = profile_key(profile, "enable")
    _set_keyring_secret(password_key, password)
    if enable:
        _set_keyring_secret(enable_key, enable)

    _delete_replaced_secret(previous_entry.get("password_keyring"), password_key)
    _delete_replaced_secret(previous_entry.get("enable_keyring"), enable_key if enable else None)

    entry = {
        "username": username,
        "password_keyring": f"{SERVICE_NAME}:{password_key}",
    }
    if enable:
        entry["enable_keyring"] = f"{SERVICE_NAME}:{enable_key}"
    profiles[profile] = entry
    save_yaml_config(path, data)


def list_profiles(path: str | Path) -> list[tuple[str, str]]:
    data = load_yaml_config(path)
    profiles = _profiles_mapping(data)
    return sorted((name, str(profile.get("username", "") or "")) for name, profile in profiles.items())


def delete_profile(path: str | Path, profile: str) -> bool:
    validate_profile_name(profile)
    data = load_yaml_config(path)
    credentials = data.get("credentials") or {}
    if not isinstance(credentials, dict):
        raise CredentialConfigError("credentials must be a mapping")
    profiles = credentials.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise CredentialConfigError("credentials.profiles must be a mapping")
    profile_data = profiles.pop(profile, None)
    if profile_data is None:
        return False
    if not isinstance(profile_data, dict):
        profile_data = {}

    for field in ("password", "enable"):
        ref = profile_data.get(f"{field}_keyring") or f"{SERVICE_NAME}:{profile_key(profile, field)}"
        _delete_keyring_secret(keyring_ref_to_key(str(ref)))

    save_yaml_config(path, data)
    return True


def _section_mapping(raw: dict[str, Any], section: str) -> Mapping[str, Any]:
    section_data = raw.get(section) or {}
    if not isinstance(section_data, dict):
        raise CredentialConfigError(f"{section} must be a mapping")
    return section_data


def _profiles_mapping(raw: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    credentials = raw.get("credentials") or {}
    if not isinstance(credentials, dict):
        raise CredentialConfigError("credentials must be a mapping")
    profiles = credentials.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise CredentialConfigError("credentials.profiles must be a mapping")
    for name, profile in profiles.items():
        validate_profile_name(str(name))
        if not isinstance(profile, dict):
            raise CredentialConfigError(f"credentials.profiles.{name} must be a mapping")
    return profiles


def _profile_mapping(raw: Mapping[str, Any], profile: str) -> Mapping[str, Any]:
    validate_profile_name(profile)
    profiles = _profiles_mapping(raw)
    profile_data = profiles.get(profile)
    if profile_data is None:
        raise UnknownCredentialProfileError(f"Unknown credential profile '{profile}'")
    return profile_data


def _resolve_field(
    field: str,
    section_data: Mapping[str, Any],
    profile_data: Mapping[str, Any],
    env: Mapping[str, str],
    env_names: Mapping[str, str],
) -> str:
    env_name = env_names.get(field)
    if env_name and env_name in env:
        return env[env_name]

    section_literal = _optional_str(section_data.get(field))
    if section_literal:
        return section_literal

    section_ref = _optional_str(section_data.get(f"{field}_keyring"))
    if section_ref:
        return _get_keyring_secret(section_ref)

    if profile_data:
        profile_literal = _optional_str(profile_data.get(field))
        if profile_literal:
            return profile_literal
        profile_ref = _optional_str(profile_data.get(f"{field}_keyring"))
        if profile_ref:
            return _get_keyring_secret(profile_ref)

    return ""


def _field_needs_profile(
    field: str,
    section_data: Mapping[str, Any],
    env: Mapping[str, str],
    env_names: Mapping[str, str],
) -> bool:
    env_name = env_names.get(field)
    if env_name and env_name in env:
        return False
    if _optional_str(section_data.get(field)):
        return False
    if _optional_str(section_data.get(f"{field}_keyring")):
        return False
    return True


def _optional_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _get_keyring_secret(ref: str) -> str:
    key = keyring_ref_to_key(ref)
    try:
        value = keyring.get_password(SERVICE_NAME, key)
    except KeyringError as exc:
        raise KeyringCredentialError(f"Could not read keyring secret '{SERVICE_NAME}:{key}': {exc}") from exc
    if value is None:
        raise KeyringCredentialError(f"Missing keyring secret '{SERVICE_NAME}:{key}'")
    return value


def _set_keyring_secret(key: str, value: str) -> None:
    try:
        keyring.set_password(SERVICE_NAME, key, value)
    except KeyringError as exc:
        raise KeyringCredentialError(f"Could not write keyring secret '{SERVICE_NAME}:{key}': {exc}") from exc


def _delete_keyring_secret(key: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, key)
    except PasswordDeleteError:
        return
    except KeyringError as exc:
        raise KeyringCredentialError(f"Could not delete keyring secret '{SERVICE_NAME}:{key}': {exc}") from exc


def _delete_replaced_secret(previous_ref: Any, replacement_key: str | None) -> None:
    previous = _optional_str(previous_ref)
    if not previous:
        return
    previous_key = keyring_ref_to_key(previous)
    if previous_key == replacement_key:
        return
    _delete_keyring_secret(previous_key)
