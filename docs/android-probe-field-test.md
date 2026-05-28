# Android Probe Field Test

## Receiver

Start a receiver reachable from the Android phone:

```bash
wifiops probe receive --pair --host 0.0.0.0 --advertise-host <wifiops-machine-ip> --log walktest.csv
```

Use this only on trusted test networks. Binding to `0.0.0.0` exposes the local receiver on the LAN; the receiver prints a warning when it binds outside loopback.

For local receiver-only smoke tests, keep the bind host on loopback:

```bash
wifiops probe receive --pair --host 127.0.0.1 --port 8765 --log /tmp/android-probe-smoke.csv
```

## Phone

1. Install the debug APK on the Android phone.
2. Open `wifiops probe`.
3. Enter the receiver URL, session ID, and token shown by the `wifiops probe receive --pair` command, or paste the pairing JSON if available.
4. Confirm the phone is on the same network as the advertised receiver address.
5. Tap `Start`.
6. Grant the requested Wi-Fi and notification permissions.
7. Walk through the test area.
8. Roam, briefly disable Wi-Fi, or move out of coverage to verify local buffering.
9. Return to coverage and confirm pending records sync.
10. Tap `Stop`.

## Expected Results

- The receiver terminal shows Android local client state.
- BSSID changes appear as events.
- Upload failures do not stop local collection.
- Pending records are retried after connectivity returns.
- `walktest.csv` contains accepted records with sequence numbers.

## Troubleshooting

- If the phone cannot reach the receiver, verify that `--advertise-host` is the wifiops machine IP address reachable from the phone's Wi-Fi network.
- If records stay pending after reconnecting, restart pairing and confirm the token was copied exactly.
- If SSID or BSSID fields are unavailable, confirm the requested Android Wi-Fi permissions were granted. The app does not collect GPS coordinates.
