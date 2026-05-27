# CLI Command Access Requirements

This document lists the controller, AP, and local endpoint commands used by the ClientTracker tools and the access level needed for each mode.

## Summary

ClientTracker can run with a low-privilege WLC account for limited visibility, but full infrastructure mode needs access to detailed wireless client commands. AP-side validation requires separate SSH access to the APs.

Recommended production model:

- Use a dedicated service account.
- Authorize only the required show commands through TACACS+/ISE command authorization where available.
- Keep configuration commands denied.
- Keep AP credentials separate from WLC credentials.
- Configure an enable secret only if the environment requires enable mode for the allowed commands.

## WLC Commands

| Command | Used For | Current App Path | Minimum Observed Access | Recommended Authorization |
| --- | --- | --- | --- | --- |
| `show wireless client mac-address <mac> detail` | Full client state: AP name, SSID, protocol, policy state, RSSI, SNR | Infrastructure and combined mode | Requires privileged EXEC or command authorization on tested Catalyst 9800 controllers | Allow exact command pattern for the service account |
| `show ap summary` | Resolve associated AP name to AP management IP | Client tracker infrastructure and combined mode after WLC client detail identifies the AP | Works in common read-only contexts, but depends on local AAA policy | Allow exact command |
| `show ap summary load-info` | AP radio client counts and channel utilization by radio slot | AP radio distribution monitor | Works in common read-only contexts, but depends on local AAA policy | Allow exact command |
| `show run \| include hostname` | Optional controller hostname display | WLC session setup | May be denied for read-only users | Optional; app continues if hostname is unavailable |

The app currently depends on `show wireless client mac-address <mac> detail` for complete WLC-side client telemetry. If that command is denied, the app cannot currently populate full WLC client fields.

Planned fallback:

| Command | Used For | Access Goal |
| --- | --- | --- |
| `show wireless client summary` | Summary-only client lookup by MAC, AP name, protocol, state, method, and role | Support privilege-1/read-only WLC accounts |
| `show wireless client summary detail` | Broader client detail when allowed but per-MAC detail is denied | Support intermediate AAA policies |

## AP Commands

| Command | Used For | Current App Path | Minimum Observed Access | Recommended Authorization |
| --- | --- | --- | --- | --- |
| `show dot11 clients` | AP-side RSSI, channel, SSID, MCS/rate for the target client | Infrastructure and combined mode | Requires AP SSH access; enable may be required depending on AP policy | Allow exact command on APs used for validation |

AP validation is independent from WLC authorization. The WLC can identify an AP while AP SSH still fails because of routing, ACLs, AP SSH policy, credentials, or enable requirements.

## Local Endpoint Commands

### macOS

| Command | Used For | Required Access |
| --- | --- | --- |
| `wdutil info` | Local Wi-Fi interface, channel, RSSI, noise, CCA, PHY, MCS, NSS, security, IP, router | Run through `sudo -n`; start with `sudo -v` or run ClientTracker with sudo |
| Repo-owned SSID/BSSID helper | Optional unredaction of SSID and BSSID when macOS redacts `wdutil` output | Installed with `scripts/build-macos-wifi-identity-helper.sh`; Location Services permission for `client-tracker-wifi-identity.app` |
| Configured custom SSID/BSSID helper | Advanced override for SSID and BSSID lookup | Explicit absolute helper path in `config.yaml`; Location Services permission for the helper app |

ClientTracker intentionally requires the useful macOS path to use sudo because non-sudo macOS Wi-Fi commands do not provide the same RF detail.

### Windows

| Command | Used For | Required Access |
| --- | --- | --- |
| `netsh wlan show interfaces` | Local Wi-Fi SSID, BSSID, channel, rates, signal, radio type, and authentication | Normal user shell in typical Windows deployments |

## Suggested TACACS+/ISE Command Set

For a least-privilege WLC service account, allow only the operational show commands needed by the tracker:

```text
show wireless client mac-address .* detail
show ap summary
show ap summary load-info
show run | include hostname
```

When summary fallback is implemented, also allow:

```text
show wireless client summary
show wireless client summary detail
```

For AP SSH validation, allow on APs:

```text
show dot11 clients
```

Avoid granting configuration mode or broad `show running-config` access unless required by local operations policy. If the WLC AAA model cannot authorize individual commands cleanly, use a dedicated privilege-15 service account with compensating controls: limited source IPs, strong credential storage, audit logging, and command accounting.

## Verification Commands

Use these commands to confirm what a proposed service account can run before configuring ClientTracker:

```text
show privilege
show wireless client summary
show wireless client summary detail
show wireless client mac-address aaaa.bbbb.cccc detail
show ap summary
show ap summary load-info
show run | include hostname
```

On an AP:

```text
show privilege
show dot11 clients
```

Expected outcomes:

- Full WLC tracking requires successful output from `show wireless client mac-address <mac> detail`.
- Summary-only tracking requires successful output from `show wireless client summary`.
- AP-side stats require successful AP SSH plus `show dot11 clients`.
- AP radio distribution monitoring requires successful output from `show ap summary load-info`.

## References

- Cisco Catalyst 9800 Series Wireless Controller Command Reference: https://www.cisco.com/c/en/us/td/docs/wireless/controller/9800/command-reference/b_wireless_cr.html
- Cisco IOS XE Role-Based CLI Access: https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/sec_usr_cfg/configuration/xe-2/sec-usr-cfg-xe-2-book/sec-role-base-cli.html
