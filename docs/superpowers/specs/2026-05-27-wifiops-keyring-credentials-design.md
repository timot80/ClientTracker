# WifiOps Keyring Credentials Design

## Summary

`wifiops` should support OS-backed credential storage for infrastructure secrets while keeping the current file and environment-variable workflows working. The cross-platform implementation should use Python `keyring`, which maps to macOS Keychain on macOS and Windows Credential Manager on Windows.

The preferred operator model is credential profiles. A single centralized login can be stored once and reused by all WLCs and AP SSH sessions that share the same identity.

## Goals

- Add cross-platform OS credential-store support for `wifiops`.
- Support centralized credential profiles for environments where the same login works across WLCs and APs.
- Keep existing plaintext `config.yaml` values working for compatibility.
- Keep environment variables as the highest-precedence override for automation and emergency use.
- Make `wifiops` the preferred operator entrypoint for credential setup.
- Let legacy root shims benefit from shared credential resolution without making them the preferred interface.
- Avoid requiring sudo for infrastructure-only credential access.

## Non-Goals

- Do not remove `client_tracker.py` or `ap_radio_monitor.py` in this change.
- Do not migrate AP image inventory or rollout dashboard scripts in this change.
- Do not require every operator to use keyring immediately.
- Do not introduce global config profiles beyond credential profiles.
- Do not add Meraki credential behavior before Meraki commands exist.

## Current Baseline

- `wifiops` routes to `client_tracker.cli` and `ap_radio_monitor.cli`.
- `client_tracker.config` loads WLC and AP credentials from `config.yaml` and `CLIENT_TRACKER_*` environment variables.
- `ap_radio_monitor.config` loads WLC credentials only from YAML.
- Root scripts are compatibility shims:
  - `python client_tracker.py ...`
  - `python ap_radio_monitor.py ...`
- Some operational scripts under `scripts/` still have independent config handling and should be migrated later.

## Credential Model

Credential profiles are named shared logins. A profile can include:

- `username`
- `password`
- optional `enable` secret

Example:

```yaml
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
      enable_keyring: "wifiops:profile:c9800-admin:enable"

wlc:
  host: "wlc-a.example.com"
  credential_profile: "c9800-admin"

ap:
  credential_profile: "c9800-admin"
```

Future multi-WLC config can reuse the same model:

```yaml
wlcs:
  - name: campus-a
    host: "wlc-a.example.com"
    credential_profile: "c9800-admin"
  - name: campus-b
    host: "wlc-b.example.com"
    credential_profile: "c9800-admin"
```

Device-specific credentials remain supported for exceptions:

```yaml
wlc:
  host: "lab-wlc.example.com"
  username: "lab-admin"
  password_keyring: "wifiops:wlc:lab-wlc:lab-admin:password"
```

Plaintext values remain valid:

```yaml
wlc:
  host: "192.0.2.10"
  username: "admin"
  password: "changeme"
  enable: "changeme"
```

## Resolution Precedence

For each credential field, resolve in this order:

```text
environment variable > device literal value > device keyring reference > credential profile > missing
```

Environment variables keep their current names for client tracking:

- `CLIENT_TRACKER_WLC_HOST`
- `CLIENT_TRACKER_WLC_USERNAME`
- `CLIENT_TRACKER_WLC_PASSWORD`
- `CLIENT_TRACKER_WLC_ENABLE`
- `CLIENT_TRACKER_AP_USERNAME`
- `CLIENT_TRACKER_AP_PASSWORD`
- `CLIENT_TRACKER_AP_ENABLE`

`ap_radio_monitor` should use the same shared resolver so `wifiops c9800 radio` and `wifiops c9800 client` behave consistently.

## Keyring Storage

Use Python `keyring` as the credential-store API.

Default service name:

```text
wifiops
```

Profile-backed key names:

```text
profile:<profile-name>:password
profile:<profile-name>:enable
```

Device-specific key names:

```text
wlc:<host>:<username>:password
wlc:<host>:<username>:enable
ap:<username>:password
ap:<username>:enable
```

The explicit keyring reference string in YAML should map to the key name. The implementation may accept either a full `wifiops:<key>` string or just the key name, but documentation should prefer the explicit `wifiops:<key>` form.

## WifiOps Commands

Add credential commands under `wifiops credentials`.

Initial commands:

```bash
wifiops credentials set-profile c9800-admin
wifiops credentials show-profiles
wifiops credentials delete-profile c9800-admin
```

`set-profile` prompts for:

- username
- password, hidden input
- enable secret, hidden input and optional

The command should print where the profile was stored without echoing secrets.

Later optional commands:

```bash
wifiops credentials set-device wlc lab-wlc
wifiops credentials delete-device wlc lab-wlc
```

These are not required for the first implementation because centralized credential profiles cover the main operator workflow.

## Config Loader Design

Create a shared credential-resolution module, likely under `wifiops.credentials` or another importable package module that does not create circular imports.

Responsibilities:

- Parse credential profiles from loaded YAML data.
- Resolve `wlc` and `ap` credential sections.
- Read secrets from keyring only when a literal secret is not already present.
- Preserve environment-variable override behavior.
- Return plain dataclass values to the existing WLC and AP connection code.

`client_tracker.config` and `ap_radio_monitor.config` should both call the shared resolver.

Legacy root shims should work automatically because they delegate to package CLIs. They should not grow separate credential behavior.

## Script Migration Boundary

Keep these root scripts as compatibility shims for now:

```text
client_tracker.py
ap_radio_monitor.py
```

Keep build and install helpers in `scripts/`:

```text
scripts/build-macos-wifi-identity-helper.sh
```

Do not migrate these scripts in the first keyring implementation:

```text
scripts/ap-image-inventory.py
scripts/build-ap-rollout-dashboard.py
```

They should eventually become `wifiops c9800 ap ...` commands backed by importable modules, but that is separate from credential-store support.

## Error Handling

Missing required infrastructure credentials should produce a clear message naming the missing field and, when applicable, the missing credential profile.

If `keyring` is not installed, commands that need it should explain how to install project dependencies. Configs using literal secrets or environment variables should continue to work.

If no usable OS keyring backend is available, credential setup and lookup should fail with a clear message. The message should suggest either fixing the OS keyring backend or using environment variables/plaintext local config as a temporary fallback.

Credential commands must never print password or enable secret values.

## Testing

Tests should mock the keyring backend and avoid touching the real OS credential store.

Coverage should include:

- Plaintext config still resolves.
- Environment variables override config and keyring.
- Device-specific keyring references resolve.
- Credential profiles resolve WLC and AP credentials.
- Missing profile produces a useful error.
- `wifiops credentials set-profile` stores expected key names without echoing secrets.
- `ap_radio_monitor.config` and `client_tracker.config` both use shared resolution semantics.

## Documentation

Update README configuration guidance to make this the preferred workflow:

```bash
wifiops credentials set-profile c9800-admin
```

Then configure:

```yaml
credentials:
  profiles:
    c9800-admin:
      username: "netops-admin"
      password_keyring: "wifiops:profile:c9800-admin:password"
      enable_keyring: "wifiops:profile:c9800-admin:enable"

wlc:
  host: "wlc-a.example.com"
  credential_profile: "c9800-admin"

ap:
  credential_profile: "c9800-admin"
```

Docs should state that `wifiops` is the preferred operator entrypoint, while `client_tracker.py` and `ap_radio_monitor.py` remain supported compatibility shims.
