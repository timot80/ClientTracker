# WifiOps Keyring Credentials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add profile-based OS credential-store support to WifiOps while preserving current config and environment-variable behavior.

**Architecture:** Add a shared `wifiops.credentials` module that resolves WLC/AP credentials from environment variables, literal YAML values, device keyring refs, and credential profiles. Update both existing config loaders to use it, then add `wifiops credentials` commands for profile setup, listing, and deletion.

**Tech Stack:** Python 3.10+, PyYAML, Python `keyring`, argparse, pytest with mocked keyring calls.

---

## File Structure

- Create `wifiops/credentials.py`: shared profile parsing, keyring reference parsing, credential resolution, config-file mutation helpers, and typed errors.
- Modify `wifiops/cli.py`: add `wifiops credentials set-profile/show-profiles/delete-profile` commands.
- Modify `client_tracker/config.py`: call the shared resolver while preserving existing dataclasses and env override semantics.
- Modify `ap_radio_monitor/config.py`: call the shared resolver for WLC credentials while preserving AP balance parsing.
- Modify `pyproject.toml` and `requirements.txt`: add `keyring`.
- Modify `config.example.yaml`: show credential profile usage without plaintext secrets.
- Modify `README.md`: document the profile workflow and sudo/keyring caveat.
- Modify `tests/test_config.py`: add resolver coverage through both config loaders.
- Modify `tests/test_wifiops_cli.py`: add credential command coverage.

## Task 1: Shared Credential Resolver

**Files:**
- Create: `wifiops/credentials.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add failing config-loader tests for profile resolution**

Add tests that monkeypatch `wifiops.credentials.keyring.get_password` and load YAML like:

```yaml
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
      enable_keyring: "wifiops:profile:c9800-admin:enable"
wlc:
  host: "192.0.2.10"
  credential_profile: "c9800-admin"
ap:
  credential_profile: "c9800-admin"
```

Expected assertions:

```python
assert cfg.wlc.username == "netops-admin"
assert cfg.wlc.password == "profile-password"
assert cfg.wlc.enable == "profile-enable"
assert cfg.ap.username == "netops-admin"
assert cfg.ap.password == "profile-password"
```

- [ ] **Step 2: Run the targeted failing tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: new profile-resolution tests fail because the resolver does not exist yet.

- [ ] **Step 3: Implement `wifiops.credentials`**

Implement:

```python
SERVICE_NAME = "wifiops"
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

class CredentialConfigError(ValueError):
    pass

@dataclass(frozen=True)
class ResolvedCredentials:
    username: str = ""
    password: str = ""
    enable: str = ""

def profile_key(profile: str, field: str) -> str
def keyring_ref_to_key(ref: str) -> str
def resolve_credentials(raw: dict[str, Any], section: str, env: Mapping[str, str], env_names: Mapping[str, str]) -> ResolvedCredentials
```

Resolution order per field must be:

```text
environment variable > section literal > section keyring ref > credential profile > empty
```

Use `keyring.get_password(SERVICE_NAME, key)` only when a keyring ref is needed. Import `keyring` at module scope so tests can patch `wifiops.credentials.keyring`.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: profile tests still fail until config loaders call the resolver.

## Task 2: Config Loader Integration

**Files:**
- Modify: `client_tracker/config.py`
- Modify: `ap_radio_monitor/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Update `client_tracker.config`**

Replace direct WLC/AP username/password/enable extraction with calls to `resolve_credentials`. Preserve:

- `CLIENT_TRACKER_*` env var override names.
- `sys.exit(...)` behavior for invalid config and missing required infra values.
- `require_infra=False` allowing missing config and empty credentials.

Catch `CredentialConfigError` and exit with its message.

- [ ] **Step 2: Update `ap_radio_monitor.config`**

Resolve WLC credentials through the shared resolver. Preserve:

- `ValueError` exception behavior.
- `wlc.host` and `wlc.read_timeout` parsing.
- AP balance parsing.

Catch `CredentialConfigError` and re-raise as `ValueError(str(exc))`.

- [ ] **Step 3: Add remaining config tests**

Cover:

- Environment variables override profile/keyring values.
- Device-specific `password_keyring` overrides profile password.
- Missing `credential_profile` name raises a useful error.
- Invalid profile name raises a useful error.
- Radio config resolves profile-backed WLC credentials.

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: all config tests pass.

## Task 3: Credential CLI Commands

**Files:**
- Modify: `wifiops/credentials.py`
- Modify: `wifiops/cli.py`
- Test: `tests/test_wifiops_cli.py`

- [ ] **Step 1: Add failing CLI tests**

In `tests/test_wifiops_cli.py`, add tests for:

- `wifiops credentials set-profile c9800-admin --username netops-admin --config <tmp>`
- `wifiops credentials show-profiles --config <tmp>`
- `wifiops credentials delete-profile c9800-admin --config <tmp>`
- invalid profile name exits before writing config

Patch:

```python
patch("wifiops.credentials.keyring.set_password")
patch("wifiops.credentials.keyring.delete_password")
patch("getpass.getpass", side_effect=["profile-password", "profile-enable"])
```

Assert `set-profile` writes:

```yaml
credentials:
  profiles:
    c9800-admin:
      username: netops-admin
      password_keyring: wifiops:profile:c9800-admin:password
      enable_keyring: wifiops:profile:c9800-admin:enable
```

- [ ] **Step 2: Add config mutation helpers**

In `wifiops.credentials`, implement:

```python
def load_yaml_config(path: str | Path) -> dict[str, Any]
def save_yaml_config(path: str | Path, data: Mapping[str, Any]) -> None
def set_profile(path: str | Path, profile: str, username: str, password: str, enable: str = "") -> None
def list_profiles(path: str | Path) -> list[tuple[str, str]]
def delete_profile(path: str | Path, profile: str) -> bool
```

`set_profile` must preserve unrelated config keys and create parent directories when needed.

- [ ] **Step 3: Add `wifiops credentials` argparse routing**

Add a top-level `credentials` command with subcommands:

```bash
wifiops credentials set-profile PROFILE --username USER [--config PATH]
wifiops credentials show-profiles [--config PATH]
wifiops credentials delete-profile PROFILE [--config PATH]
```

Use hidden prompts for password and enable. Print profile names/usernames only, never secrets.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_wifiops_cli.py -v
```

Expected: all WifiOps CLI tests pass.

## Task 4: Dependencies And Docs

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `config.example.yaml`
- Modify: `README.md`

- [ ] **Step 1: Add dependency**

Add:

```text
keyring>=25.0.0
```

to both `pyproject.toml` dependencies and `requirements.txt`.

- [ ] **Step 2: Update example config**

Show credential profile usage as the preferred path. Keep a short comment that plaintext `password` and `enable` still work for local-only compatibility.

- [ ] **Step 3: Update README**

Document:

```bash
wifiops credentials set-profile c9800-admin --username netops-admin
```

Then show `wlc.credential_profile` and `ap.credential_profile`.

State that macOS local telemetry should use:

```bash
sudo -v
wifiops client local
```

Do not recommend running all infrastructure commands under sudo because keyring lookup may use root's keyring.

## Task 5: Full Verification

**Files:**
- No planned source edits unless tests reveal an issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest tests/test_config.py tests/test_wifiops_cli.py -v
```

Expected: pass.

- [ ] **Step 2: Run broader test suite**

Run:

```bash
pytest -q
```

Expected: pass, or report any unrelated existing failures with exact failing tests.

- [ ] **Step 3: Manual CLI smoke checks**

Run:

```bash
python -m wifiops.cli --help
python -m wifiops.cli credentials --help
python -m wifiops.cli credentials show-profiles --config config.example.yaml
```

Expected: commands exit cleanly and print no secrets.
