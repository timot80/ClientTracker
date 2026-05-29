# Android Probe Field Test

## Receiver

Start a receiver reachable from the Android phone:

```bash
wifiops probe receive --pair --host 0.0.0.0 --advertise-host <wifiops-machine-ip> --log walktest.csv
```

Use this only on trusted test networks. Binding to `0.0.0.0` exposes the local receiver on the LAN; the receiver prints a warning when it binds outside loopback.

The receiver prints a `Scan receiver QR code` block for the Android setup screen. It also keeps printing the setup JSON fallback for paste/manual setup.

For IPv6-only or dual-stack tests, bind and advertise an IPv6 literal. The pairing URL will use brackets automatically:

```bash
wifiops probe receive --pair --host :: --advertise-host <wifiops-machine-ipv6> --log walktest-ipv6.csv
```

Example pairing URL:

```text
http://[2001:db8::10]:8765
```

For local receiver-only smoke tests, keep the bind host on loopback:

```bash
wifiops probe receive --pair --host 127.0.0.1 --port 8765 --log /tmp/android-probe-smoke.csv
```

## Phone

1. Install the debug APK on the Android phone.
2. Open `wifiops probe`.
3. Tap `Scan receiver QR code` and scan the QR code printed by the receiver, or paste the setup JSON if camera access is unavailable.
4. Confirm the phone is on the same network as the advertised receiver address.
5. Tap `Start`.
6. Grant the requested Wi-Fi, notification, and precise location permissions. Android gates SSID/BSSID visibility behind location permission; the app does not collect GPS coordinates.
7. Walk through the test area.
8. Roam, briefly disable Wi-Fi, or move out of coverage to verify local buffering.
9. Return to coverage and confirm pending records sync.
10. Tap `Stop`.

## Expected Results

- The receiver terminal shows Android local client state.
- The receiver terminal prints `Probe connected` after the first accepted upload.
- BSSID changes appear as events.
- Upload failures do not stop local collection.
- Pending records are retried after connectivity returns.
- `walktest.csv` contains accepted records with sequence numbers.

## Troubleshooting

- If the phone cannot reach the receiver, verify that `--advertise-host` is the wifiops machine IP address reachable from the phone's Wi-Fi network.
- For IPv6 literals, enter or paste the bracketed URL exactly, for example `http://[2001:db8::10]:8765`.
- If records stay pending after reconnecting, restart pairing and confirm the token was copied exactly.
- If SSID or BSSID fields are unavailable, confirm the requested Android Wi-Fi and precise location permissions were granted and that Android Location is enabled. The app does not collect GPS coordinates.
