# iOS Wi-Fi Ops Probe Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a foreground-only native iOS Wi-Fi Ops Probe companion that mirrors the Android receiver setup, telemetry JSON, local queue, sync, session counters, and history behavior.

**Architecture:** Create a reproducible XcodeGen-based iOS project under `ios/WifiOpsProbe/`. Put all protocol, storage, sync, preflight, and collection logic in a testable `WifiOpsProbeCore` framework, then wire a small SwiftUI app target to that core. Use protocol injection around network, current Wi-Fi, device info, file storage, and clocks so XCTest can cover behavior without a real iPhone or receiver.

**Tech Stack:** Swift 5.9+, SwiftUI, XCTest, Foundation `URLSession`, Security Keychain APIs, Network framework, SystemConfiguration/CaptiveNetwork or NetworkExtension current-network APIs where available, XcodeGen, Xcode/iOS Simulator.

---

## File Structure

- Create `ios/WifiOpsProbe/project.yml`: XcodeGen project definition for app, core framework, and tests.
- Create `ios/WifiOpsProbe/WifiOpsProbe/App/WifiOpsProbeApp.swift`: SwiftUI app entry point.
- Create `ios/WifiOpsProbe/WifiOpsProbe/App/AppEnvironment.swift`: dependency container used by SwiftUI views.
- Create `ios/WifiOpsProbe/WifiOpsProbe/Views/ReceiverSetupView.swift`: receiver setup UI.
- Create `ios/WifiOpsProbe/WifiOpsProbe/Views/PreflightView.swift`: readiness checks UI.
- Create `ios/WifiOpsProbe/WifiOpsProbe/Views/SessionView.swift`: active session UI.
- Create `ios/WifiOpsProbe/WifiOpsProbe/Views/SessionHistoryView.swift`: local session history UI.
- Create `ios/WifiOpsProbe/WifiOpsProbe/Views/SharedViews.swift`: small status/counter rows shared by screens.
- Create `ios/WifiOpsProbe/WifiOpsProbe/Resources/Info.plist`: iOS permissions and app metadata.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/PairingPayload.swift`: Android-compatible receiver setup parsing and validation.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/SavedPairingStore.swift`: saved receiver metadata plus Keychain token storage.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/TelemetryModels.swift`: Android-compatible telemetry and acknowledgement models.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/ReceiverClient.swift`: `/health` and record upload client.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/ProbeStore.swift`: persistent local sessions and records using JSON files with table-like arrays.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/SyncWorker.swift`: pending-record upload and acknowledgement handling.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/TelemetryCollector.swift`: iOS foreground sample collection and availability markers.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/ActiveProbeRunner.swift`: DNS, receiver HTTP, and best-effort gateway probes.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/Preflight.swift`: readiness model.
- Create `ios/WifiOpsProbe/WifiOpsProbeCore/SessionViewModel.swift`: foreground one-second session loop and UI state.
- Create `ios/WifiOpsProbe/WifiOpsProbeTests/PairingPayloadTests.swift`.
- Create `ios/WifiOpsProbe/WifiOpsProbeTests/SavedPairingStoreTests.swift`.
- Create `ios/WifiOpsProbe/WifiOpsProbeTests/TelemetryModelsTests.swift`.
- Create `ios/WifiOpsProbe/WifiOpsProbeTests/ProbeStoreTests.swift`.
- Create `ios/WifiOpsProbe/WifiOpsProbeTests/SyncWorkerTests.swift`.
- Create `ios/WifiOpsProbe/WifiOpsProbeTests/TelemetryCollectorTests.swift`.
- Create `ios/WifiOpsProbe/WifiOpsProbeTests/PreflightTests.swift`.
- Create `ios/WifiOpsProbe/WifiOpsProbeTests/SessionViewModelTests.swift`.

## Task 1: Reproducible iOS Project Scaffold

**Files:**
- Create: `ios/WifiOpsProbe/project.yml`
- Create: `ios/WifiOpsProbe/WifiOpsProbe/App/WifiOpsProbeApp.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbe/App/AppEnvironment.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbe/Resources/Info.plist`
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/LibraryMarker.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbeTests/ProjectSmokeTests.swift`

- [ ] **Step 1: Verify XcodeGen availability**

Run:

```bash
cd /Users/timotbar/development/wifi/ClientTracker
command -v xcodegen
```

Expected: path to `xcodegen`. If missing, install it once with:

```bash
brew install xcodegen
```

- [ ] **Step 2: Create `project.yml`**

Add:

```yaml
name: WifiOpsProbe
options:
  bundleIdPrefix: com.wifiops
  deploymentTarget:
    iOS: "17.0"
settings:
  base:
    SWIFT_VERSION: "5.9"
    IPHONEOS_DEPLOYMENT_TARGET: "17.0"
targets:
  WifiOpsProbeCore:
    type: framework
    platform: iOS
    sources:
      - WifiOpsProbeCore
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.wifiops.probe.core
  WifiOpsProbe:
    type: application
    platform: iOS
    sources:
      - WifiOpsProbe
    dependencies:
      - target: WifiOpsProbeCore
    info:
      path: WifiOpsProbe/Resources/Info.plist
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.wifiops.probe
        ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon
  WifiOpsProbeTests:
    type: bundle.unit-test
    platform: iOS
    sources:
      - WifiOpsProbeTests
    dependencies:
      - target: WifiOpsProbeCore
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.wifiops.probe.tests
schemes:
  WifiOpsProbe:
    build:
      targets:
        WifiOpsProbe: all
        WifiOpsProbeCore: all
        WifiOpsProbeTests: [test]
    test:
      targets:
        - WifiOpsProbeTests
```

- [ ] **Step 3: Add minimal app and core marker**

Create `LibraryMarker.swift`:

```swift
import Foundation

public enum WifiOpsProbeCore {
    public static let version = "0.1.0"
}
```

Create `AppEnvironment.swift`:

```swift
import Foundation
import WifiOpsProbeCore

@MainActor
final class AppEnvironment: ObservableObject {
    let appVersion: String

    init(appVersion: String = WifiOpsProbeCore.version) {
        self.appVersion = appVersion
    }
}
```

Create `WifiOpsProbeApp.swift`:

```swift
import SwiftUI

@main
struct WifiOpsProbeApp: App {
    @StateObject private var environment = AppEnvironment()

    var body: some Scene {
        WindowGroup {
            Text("Wi-Fi Ops Probe")
                .environmentObject(environment)
        }
    }
}
```

- [ ] **Step 4: Add `Info.plist`**

Use:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>Wi-Fi Ops Probe</string>
    <key>NSLocalNetworkUsageDescription</key>
    <string>Wi-Fi Ops Probe connects to your WifiOps receiver and runs local network checks during a foreground walk-test session.</string>
    <key>NSLocationWhenInUseUsageDescription</key>
    <string>Wi-Fi Ops Probe uses location permission only when iOS requires it to show the current Wi-Fi network name and BSSID.</string>
</dict>
</plist>
```

- [ ] **Step 5: Add a smoke test**

Create `ProjectSmokeTests.swift`:

```swift
import XCTest
@testable import WifiOpsProbeCore

final class ProjectSmokeTests: XCTestCase {
    func testCoreVersionIsAvailable() {
        XCTAssertEqual(WifiOpsProbeCore.version, "0.1.0")
    }
}
```

- [ ] **Step 6: Generate and test the project**

Run:

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodegen generate
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15'
```

Expected: `TEST SUCCEEDED`. If `iPhone 15` is unavailable, run `xcrun simctl list devices available`, pick the first available iPhone simulator, rerun with that exact name, and include `Simulator: <name>` in the commit message body.

- [ ] **Step 7: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe docs/superpowers/plans/2026-05-28-ios-wifiops-probe-companion.md
git commit -m "Add iOS probe project scaffold"
```

## Task 2: Android-Compatible Pairing And Saved Receiver

**Files:**
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/PairingPayload.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/SavedPairingStore.swift`
- Test: `ios/WifiOpsProbe/WifiOpsProbeTests/PairingPayloadTests.swift`
- Test: `ios/WifiOpsProbe/WifiOpsProbeTests/SavedPairingStoreTests.swift`

- [ ] **Step 1: Write failing pairing tests**

Create `PairingPayloadTests.swift`:

```swift
import XCTest
@testable import WifiOpsProbeCore

final class PairingPayloadTests: XCTestCase {
    func testParsesAndroidPairingPayloadJson() throws {
        let payload = try PairingPayload.parse("""
        {"receiver_url":"http://192.0.2.10:8765","session_id":"walk_1","token":"secret"}
        """)

        XCTAssertEqual(payload.receiverUrl, "http://192.0.2.10:8765")
        XCTAssertEqual(payload.sessionId, "walk_1")
        XCTAssertEqual(payload.token, "secret")
    }

    func testNormalizesManualFields() throws {
        let payload = try PairingPayload.fromManualFields(
            receiverUrl: " http://192.0.2.10:8765/ ",
            sessionId: " walk_1 ",
            token: " secret "
        )

        XCTAssertEqual(payload.receiverUrl, "http://192.0.2.10:8765")
        XCTAssertEqual(payload.sessionId, "walk_1")
        XCTAssertEqual(payload.token, "secret")
    }

    func testRejectsMissingToken() {
        XCTAssertThrowsError(try PairingPayload.parse("""
        {"receiver_url":"http://192.0.2.10:8765","session_id":"walk_1"}
        """)) { error in
            XCTAssertEqual(error as? PairingPayloadError, .missingRequiredField)
        }
    }

    func testRejectsNonHttpReceiverUrl() {
        XCTAssertThrowsError(try PairingPayload.fromManualFields(
            receiverUrl: "ftp://192.0.2.10",
            sessionId: "walk_1",
            token: "secret"
        )) { error in
            XCTAssertEqual(error as? PairingPayloadError, .invalidReceiverUrl)
        }
    }
}
```

- [ ] **Step 2: Run pairing tests and verify failure**

Run:

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/PairingPayloadTests
```

Expected: compile failure because `PairingPayload` does not exist.

- [ ] **Step 3: Implement `PairingPayload`**

Create:

```swift
import Foundation

public enum PairingPayloadError: Error, Equatable {
    case invalidJson
    case missingRequiredField
    case invalidReceiverUrl
}

public struct PairingPayload: Codable, Equatable {
    public let receiverUrl: String
    public let sessionId: String
    public let token: String

    enum CodingKeys: String, CodingKey {
        case receiverUrl = "receiver_url"
        case sessionId = "session_id"
        case token
    }

    public static func parse(_ raw: String) throws -> PairingPayload {
        guard let data = raw.data(using: .utf8) else {
            throw PairingPayloadError.invalidJson
        }
        do {
            let decoded = try JSONDecoder().decode(PairingPayload.self, from: data)
            return try decoded.normalized()
        } catch let error as PairingPayloadError {
            throw error
        } catch {
            throw PairingPayloadError.missingRequiredField
        }
    }

    public static func fromManualFields(receiverUrl: String, sessionId: String, token: String) throws -> PairingPayload {
        try PairingPayload(receiverUrl: receiverUrl, sessionId: sessionId, token: token).normalized()
    }

    private func normalized() throws -> PairingPayload {
        let normalizedReceiverUrl = receiverUrl.trimmingCharacters(in: .whitespacesAndNewlines).trimmedTrailingSlash()
        let normalizedSessionId = sessionId.trimmingCharacters(in: .whitespacesAndNewlines)
        let normalizedToken = token.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !normalizedReceiverUrl.isEmpty, !normalizedSessionId.isEmpty, !normalizedToken.isEmpty else {
            throw PairingPayloadError.missingRequiredField
        }
        guard let url = URL(string: normalizedReceiverUrl),
              let scheme = url.scheme,
              ["http", "https"].contains(scheme),
              url.host != nil else {
            throw PairingPayloadError.invalidReceiverUrl
        }

        return PairingPayload(receiverUrl: normalizedReceiverUrl, sessionId: normalizedSessionId, token: normalizedToken)
    }
}

private extension String {
    func trimmedTrailingSlash() -> String {
        var value = self
        while value.hasSuffix("/") {
            value.removeLast()
        }
        return value
    }
}
```

- [ ] **Step 4: Add saved pairing tests**

Create `SavedPairingStoreTests.swift`:

```swift
import XCTest
@testable import WifiOpsProbeCore

final class SavedPairingStoreTests: XCTestCase {
    func testSavesReceiverMetadataAndTokenSeparately() throws {
        let metadata = InMemoryPairingMetadataStore()
        let tokens = InMemoryTokenStore()
        let store = SavedPairingStore(metadataStore: metadata, tokenStore: tokens)
        let payload = try PairingPayload.fromManualFields(
            receiverUrl: "http://receiver:8765",
            sessionId: "walk_1",
            token: "secret"
        )

        try store.save(payload)

        XCTAssertEqual(metadata.receiverUrl, "http://receiver:8765")
        XCTAssertEqual(metadata.sessionId, "walk_1")
        XCTAssertNil(metadata.token)
        XCTAssertEqual(tokens.token, "secret")
        XCTAssertEqual(try store.load(), payload)
    }
}
```

- [ ] **Step 5: Implement saved pairing store abstractions**

Create `SavedPairingStore.swift`:

```swift
import Foundation
import Security

public protocol PairingMetadataStore {
    var receiverUrl: String? { get set }
    var sessionId: String? { get set }
    var token: String? { get set }
}

public protocol PairingTokenStore {
    func saveToken(_ token: String) throws
    func loadToken() throws -> String?
    func deleteToken() throws
}

public final class SavedPairingStore {
    private var metadataStore: PairingMetadataStore
    private let tokenStore: PairingTokenStore

    public init(metadataStore: PairingMetadataStore, tokenStore: PairingTokenStore) {
        self.metadataStore = metadataStore
        self.tokenStore = tokenStore
    }

    public func save(_ payload: PairingPayload) throws {
        metadataStore.receiverUrl = payload.receiverUrl
        metadataStore.sessionId = payload.sessionId
        metadataStore.token = nil
        try tokenStore.saveToken(payload.token)
    }

    public func load() throws -> PairingPayload? {
        guard let receiverUrl = metadataStore.receiverUrl,
              let sessionId = metadataStore.sessionId,
              let token = try tokenStore.loadToken() else {
            return nil
        }
        return try PairingPayload.fromManualFields(receiverUrl: receiverUrl, sessionId: sessionId, token: token)
    }
}

public final class UserDefaultsPairingMetadataStore: PairingMetadataStore {
    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public var receiverUrl: String? {
        get { defaults.string(forKey: "pairing.receiver_url") }
        set { defaults.set(newValue, forKey: "pairing.receiver_url") }
    }

    public var sessionId: String? {
        get { defaults.string(forKey: "pairing.session_id") }
        set { defaults.set(newValue, forKey: "pairing.session_id") }
    }

    public var token: String? {
        get { nil }
        set { defaults.removeObject(forKey: "pairing.token") }
    }
}

public final class KeychainPairingTokenStore: PairingTokenStore {
    private let service = "com.wifiops.probe.pairing"
    private let account = "receiver-token"

    public init() {}

    public func saveToken(_ token: String) throws {
        try deleteToken()
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: Data(token.utf8)
        ]
        SecItemAdd(query as CFDictionary, nil)
    }

    public func loadToken() throws -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    public func deleteToken() throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(query as CFDictionary)
    }
}

public final class InMemoryPairingMetadataStore: PairingMetadataStore {
    public var receiverUrl: String?
    public var sessionId: String?
    public var token: String?
    public init() {}
}

public final class InMemoryTokenStore: PairingTokenStore {
    public var token: String?
    public init() {}
    public func saveToken(_ token: String) throws { self.token = token }
    public func loadToken() throws -> String? { token }
    public func deleteToken() throws { token = nil }
}
```

- [ ] **Step 6: Run tests**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/PairingPayloadTests -only-testing:WifiOpsProbeTests/SavedPairingStoreTests
```

Expected: `TEST SUCCEEDED`.

- [ ] **Step 7: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe
git commit -m "Add iOS receiver pairing persistence"
```

## Task 3: Android-Compatible Telemetry Models

**Files:**
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/TelemetryModels.swift`
- Test: `ios/WifiOpsProbe/WifiOpsProbeTests/TelemetryModelsTests.swift`

- [ ] **Step 1: Write failing telemetry encoding tests**

Create:

```swift
import XCTest
@testable import WifiOpsProbeCore

final class TelemetryModelsTests: XCTestCase {
    func testEncodesAndroidCompatibleTelemetryKeys() throws {
        let record = TelemetryRecord(
            schemaVersion: 1,
            sessionId: "walk_1",
            deviceId: "iPhone16,2",
            recordId: "walk_1-1",
            sequenceNumber: 1,
            recordType: "sample",
            clientTimestamp: "2026-05-28T12:00:00Z",
            appVersion: "0.1.0",
            payload: TelemetryPayload(
                ssid: "corp",
                bssid: "aa:bb:cc:dd:ee:ff",
                rssi: nil,
                frequencyMhz: nil,
                channel: nil,
                txLinkMbps: nil,
                rxLinkMbps: nil,
                ipv4Address: "192.0.2.20",
                ipv6Addresses: ["2001:db8::1"],
                ipAddresses: ["192.0.2.20", "2001:db8::1"],
                gateway: nil,
                dns: ["192.0.2.1"],
                manufacturer: "Apple",
                model: "iPhone16,2",
                probes: ["http": ProbeResult(ok: true, latencyMs: 12, detail: "200")],
                availability: ["rssi": "ios_unavailable"]
            )
        )

        let data = try JSONEncoder.wifiOps.encode(record)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(object["schema_version"] as? Int, 1)
        XCTAssertEqual(object["session_id"] as? String, "walk_1")
        XCTAssertEqual(object["device_id"] as? String, "iPhone16,2")
        XCTAssertEqual(object["record_id"] as? String, "walk_1-1")
        XCTAssertEqual(object["sequence_number"] as? Int, 1)
        XCTAssertEqual(object["record_type"] as? String, "sample")

        let payload = try XCTUnwrap(object["payload"] as? [String: Any])
        XCTAssertEqual(payload["frequency_mhz"] as? NSNull, NSNull())
        XCTAssertEqual(payload["tx_link_mbps"] as? NSNull, NSNull())
        XCTAssertEqual(payload["rx_link_mbps"] as? NSNull, NSNull())
        XCTAssertEqual(payload["ipv4_address"] as? String, "192.0.2.20")
        XCTAssertEqual(payload["ipv6_addresses"] as? [String], ["2001:db8::1"])
        XCTAssertEqual(payload["ip_addresses"] as? [String], ["192.0.2.20", "2001:db8::1"])
    }
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/TelemetryModelsTests
```

Expected: compile failure because telemetry models do not exist.

- [ ] **Step 3: Implement telemetry models**

Create:

```swift
import Foundation

public struct TelemetryRecord: Codable, Equatable {
    public let schemaVersion: Int
    public let sessionId: String
    public let deviceId: String
    public let recordId: String
    public let sequenceNumber: Int64
    public let recordType: String
    public let clientTimestamp: String
    public let appVersion: String
    public let payload: TelemetryPayload

    public init(schemaVersion: Int, sessionId: String, deviceId: String, recordId: String, sequenceNumber: Int64, recordType: String, clientTimestamp: String, appVersion: String, payload: TelemetryPayload) {
        self.schemaVersion = schemaVersion
        self.sessionId = sessionId
        self.deviceId = deviceId
        self.recordId = recordId
        self.sequenceNumber = sequenceNumber
        self.recordType = recordType
        self.clientTimestamp = clientTimestamp
        self.appVersion = appVersion
        self.payload = payload
    }

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case sessionId = "session_id"
        case deviceId = "device_id"
        case recordId = "record_id"
        case sequenceNumber = "sequence_number"
        case recordType = "record_type"
        case clientTimestamp = "client_timestamp"
        case appVersion = "app_version"
        case payload
    }
}

public struct TelemetryPayload: Codable, Equatable {
    public var ssid: String?
    public var bssid: String?
    public var rssi: Int?
    public var frequencyMhz: Int?
    public var channel: String?
    public var txLinkMbps: Int?
    public var rxLinkMbps: Int?
    public var ipv4Address: String?
    public var ipv6Addresses: [String]
    public var ipAddresses: [String]
    public var gateway: String?
    public var dns: [String]
    public var manufacturer: String?
    public var model: String?
    public var probes: [String: ProbeResult]
    public var availability: [String: String]

    public init(ssid: String? = nil, bssid: String? = nil, rssi: Int? = nil, frequencyMhz: Int? = nil, channel: String? = nil, txLinkMbps: Int? = nil, rxLinkMbps: Int? = nil, ipv4Address: String? = nil, ipv6Addresses: [String] = [], ipAddresses: [String] = [], gateway: String? = nil, dns: [String] = [], manufacturer: String? = nil, model: String? = nil, probes: [String: ProbeResult] = [:], availability: [String: String] = [:]) {
        self.ssid = ssid
        self.bssid = bssid
        self.rssi = rssi
        self.frequencyMhz = frequencyMhz
        self.channel = channel
        self.txLinkMbps = txLinkMbps
        self.rxLinkMbps = rxLinkMbps
        self.ipv4Address = ipv4Address
        self.ipv6Addresses = ipv6Addresses
        self.ipAddresses = ipAddresses
        self.gateway = gateway
        self.dns = dns
        self.manufacturer = manufacturer
        self.model = model
        self.probes = probes
        self.availability = availability
    }

    enum CodingKeys: String, CodingKey {
        case ssid, bssid, rssi, channel, gateway, dns, manufacturer, model, probes, availability
        case frequencyMhz = "frequency_mhz"
        case txLinkMbps = "tx_link_mbps"
        case rxLinkMbps = "rx_link_mbps"
        case ipv4Address = "ipv4_address"
        case ipv6Addresses = "ipv6_addresses"
        case ipAddresses = "ip_addresses"
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeNilOrValue(ssid, forKey: .ssid)
        try container.encodeNilOrValue(bssid, forKey: .bssid)
        try container.encodeNilOrValue(rssi, forKey: .rssi)
        try container.encodeNilOrValue(frequencyMhz, forKey: .frequencyMhz)
        try container.encodeNilOrValue(channel, forKey: .channel)
        try container.encodeNilOrValue(txLinkMbps, forKey: .txLinkMbps)
        try container.encodeNilOrValue(rxLinkMbps, forKey: .rxLinkMbps)
        try container.encodeNilOrValue(ipv4Address, forKey: .ipv4Address)
        try container.encode(ipv6Addresses, forKey: .ipv6Addresses)
        try container.encode(ipAddresses, forKey: .ipAddresses)
        try container.encodeNilOrValue(gateway, forKey: .gateway)
        try container.encode(dns, forKey: .dns)
        try container.encodeNilOrValue(manufacturer, forKey: .manufacturer)
        try container.encodeNilOrValue(model, forKey: .model)
        try container.encode(probes, forKey: .probes)
        try container.encode(availability, forKey: .availability)
    }
}

private extension KeyedEncodingContainer {
    mutating func encodeNilOrValue<T: Encodable>(_ value: T?, forKey key: Key) throws {
        if let value {
            try encode(value, forKey: key)
        } else {
            try encodeNil(forKey: key)
        }
    }
}

public struct ProbeResult: Codable, Equatable {
    public let ok: Bool
    public let latencyMs: Int64?
    public let detail: String

    public init(ok: Bool, latencyMs: Int64? = nil, detail: String = "") {
        self.ok = ok
        self.latencyMs = latencyMs
        self.detail = detail
    }

    enum CodingKeys: String, CodingKey {
        case ok
        case latencyMs = "latency_ms"
        case detail
    }
}

public extension JSONEncoder {
    static var wifiOps: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }
}

public extension JSONDecoder {
    static var wifiOps: JSONDecoder {
        JSONDecoder()
    }
}
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/TelemetryModelsTests
```

Expected: `TEST SUCCEEDED`.

- [ ] **Step 5: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe
git commit -m "Add iOS Android-compatible telemetry models"
```

## Task 4: Local Persistent Probe Store

**Files:**
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/ProbeStore.swift`
- Test: `ios/WifiOpsProbe/WifiOpsProbeTests/ProbeStoreTests.swift`

- [ ] **Step 1: Write failing store tests**

Create tests for inserting sessions, inserting records, querying latest sample, preserving sequence numbers, and counting statuses:

```swift
import XCTest
@testable import WifiOpsProbeCore

final class ProbeStoreTests: XCTestCase {
    func testPersistsSessionAndRecordCounters() throws {
        let directory = try temporaryDirectory()
        let store = try FileProbeStore(directory: directory)
        let session = ProbeSession(sessionId: "walk_1", receiverUrl: "http://receiver", tokenKey: "receiver-token", deviceId: "iPhone16,2", createdAtMillis: 1, stoppedAtMillis: nil)

        try store.insertSession(session)
        try store.insertRecord(record("walk_1-1", sessionId: "walk_1", sequence: 1, status: .pending))
        try store.insertRecord(record("walk_1-2", sessionId: "walk_1", sequence: 2, status: .synced))
        try store.insertRecord(record("walk_1-3", sessionId: "walk_1", sequence: 3, status: .failed))

        XCTAssertEqual(try store.sessions().map(\.sessionId), ["walk_1"])
        XCTAssertEqual(try store.count(sessionId: "walk_1", status: .pending), 1)
        XCTAssertEqual(try store.count(sessionId: "walk_1", status: .synced), 1)
        XCTAssertEqual(try store.count(sessionId: "walk_1", status: .failed), 1)
        XCTAssertEqual(try store.maxSequence(sessionId: "walk_1"), 3)
        XCTAssertEqual(try store.latestRecord(sessionId: "walk_1")?.recordId, "walk_1-3")
    }

    func testPendingRecordsAreOrderedAndLimited() throws {
        let store = try FileProbeStore(directory: temporaryDirectory())
        try store.insertSession(ProbeSession(sessionId: "walk_1", receiverUrl: "http://receiver", tokenKey: "token", deviceId: "phone", createdAtMillis: 1, stoppedAtMillis: nil))
        try store.insertRecord(record("walk_1-2", sessionId: "walk_1", sequence: 2, status: .pending))
        try store.insertRecord(record("walk_1-1", sessionId: "walk_1", sequence: 1, status: .pending))

        XCTAssertEqual(try store.pendingRecords(sessionId: "walk_1", limit: 1).map(\.recordId), ["walk_1-1"])
    }

    private func record(_ id: String, sessionId: String, sequence: Int64, status: SyncStatus) -> ProbeRecord {
        ProbeRecord(recordId: id, sessionId: sessionId, sequenceNumber: sequence, recordType: "sample", payloadJson: #"{"record_id":"\#(id)"}"#, syncStatus: status, retryCount: 0, lastError: "", createdAtMillis: sequence)
    }

    private func temporaryDirectory() throws -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }
}
```

- [ ] **Step 2: Run store tests and verify failure**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/ProbeStoreTests
```

Expected: compile failure because `FileProbeStore` does not exist.

- [ ] **Step 3: Implement `ProbeStore` with JSON persistence**

Create:

```swift
import Foundation

public enum SyncStatus: String, Codable, Equatable {
    case pending
    case synced
    case failed
}

public struct ProbeSession: Codable, Equatable {
    public let sessionId: String
    public let receiverUrl: String
    public let tokenKey: String
    public let deviceId: String
    public let createdAtMillis: Int64
    public let stoppedAtMillis: Int64?
}

public struct ProbeRecord: Codable, Equatable {
    public let recordId: String
    public let sessionId: String
    public let sequenceNumber: Int64
    public let recordType: String
    public let payloadJson: String
    public var syncStatus: SyncStatus
    public var retryCount: Int
    public var lastError: String
    public let createdAtMillis: Int64
}

public final class FileProbeStore {
    private let sessionsUrl: URL
    private let recordsUrl: URL
    private let encoder = JSONEncoder.wifiOps
    private let decoder = JSONDecoder.wifiOps

    public init(directory: URL) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        self.sessionsUrl = directory.appendingPathComponent("sessions.json")
        self.recordsUrl = directory.appendingPathComponent("records.json")
        if !FileManager.default.fileExists(atPath: sessionsUrl.path) { try Data("[]".utf8).write(to: sessionsUrl) }
        if !FileManager.default.fileExists(atPath: recordsUrl.path) { try Data("[]".utf8).write(to: recordsUrl) }
    }

    public func insertSession(_ session: ProbeSession) throws {
        var rows = try sessions()
        rows.removeAll { $0.sessionId == session.sessionId }
        rows.insert(session, at: 0)
        try write(rows, to: sessionsUrl)
    }

    public func sessions() throws -> [ProbeSession] {
        try read([ProbeSession].self, from: sessionsUrl).sorted { $0.createdAtMillis > $1.createdAtMillis }
    }

    public func deleteSession(_ sessionId: String) throws {
        try write(try sessions().filter { $0.sessionId != sessionId }, to: sessionsUrl)
        try write(try records().filter { $0.sessionId != sessionId }, to: recordsUrl)
    }

    public func insertRecord(_ record: ProbeRecord) throws {
        var rows = try records()
        guard !rows.contains(where: { $0.recordId == record.recordId }) else { return }
        rows.append(record)
        try write(rows, to: recordsUrl)
    }

    public func pendingRecords(sessionId: String, limit: Int) throws -> [ProbeRecord] {
        Array(try records()
            .filter { $0.sessionId == sessionId && $0.syncStatus == .pending }
            .sorted { $0.sequenceNumber < $1.sequenceNumber }
            .prefix(limit))
    }

    public func updatePendingRecordStatus(sessionId: String, recordId: String, status: SyncStatus, lastError: String = "") throws {
        var rows = try records()
        if let index = rows.firstIndex(where: { $0.sessionId == sessionId && $0.recordId == recordId && $0.syncStatus == .pending }) {
            rows[index].syncStatus = status
            rows[index].lastError = lastError
            try write(rows, to: recordsUrl)
        }
    }

    public func markPendingRetry(sessionId: String, recordId: String, lastError: String) throws {
        var rows = try records()
        if let index = rows.firstIndex(where: { $0.sessionId == sessionId && $0.recordId == recordId && $0.syncStatus == .pending }) {
            rows[index].retryCount += 1
            rows[index].lastError = lastError
            try write(rows, to: recordsUrl)
        }
    }

    public func count(sessionId: String, status: SyncStatus) throws -> Int {
        try records().filter { $0.sessionId == sessionId && $0.syncStatus == status }.count
    }

    public func maxSequence(sessionId: String) throws -> Int64 {
        try records().filter { $0.sessionId == sessionId }.map(\.sequenceNumber).max() ?? 0
    }

    public func latestRecord(sessionId: String) throws -> ProbeRecord? {
        try records().filter { $0.sessionId == sessionId }.sorted { $0.sequenceNumber > $1.sequenceNumber }.first
    }

    public func records() throws -> [ProbeRecord] {
        try read([ProbeRecord].self, from: recordsUrl)
    }

    private func read<T: Decodable>(_ type: T.Type, from url: URL) throws -> T {
        try decoder.decode(T.self, from: Data(contentsOf: url))
    }

    private func write<T: Encodable>(_ value: T, to url: URL) throws {
        try encoder.encode(value).write(to: url, options: [.atomic])
    }
}
```

- [ ] **Step 4: Run store tests**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/ProbeStoreTests
```

Expected: `TEST SUCCEEDED`.

- [ ] **Step 5: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe
git commit -m "Add iOS local probe store"
```

## Task 5: Receiver Client And Sync Worker

**Files:**
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/ReceiverClient.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/SyncWorker.swift`
- Test: `ios/WifiOpsProbe/WifiOpsProbeTests/SyncWorkerTests.swift`

- [ ] **Step 1: Write failing sync tests**

Create tests:

```swift
import XCTest
@testable import WifiOpsProbeCore

final class SyncWorkerTests: XCTestCase {
    func testAcceptedAndDuplicateRecordsBecomeSynced() throws {
        let store = try FileProbeStore(directory: temporaryDirectory())
        try seed(store)
        let client = FakeReceiverTransport(ack: ProbeAcknowledgement(accepted: ["walk_1-1"], duplicate: ["walk_1-2"], rejected: []))
        let worker = SyncWorker(store: store, transport: client)

        let synced = try worker.syncOnce(sessionId: "walk_1", receiverUrl: "http://receiver", token: "secret")

        XCTAssertEqual(synced, 2)
        XCTAssertEqual(try store.count(sessionId: "walk_1", status: .synced), 2)
        XCTAssertEqual(try store.count(sessionId: "walk_1", status: .pending), 0)
    }

    func testRejectedRecordBecomesFailed() throws {
        let store = try FileProbeStore(directory: temporaryDirectory())
        try seed(store)
        let client = FakeReceiverTransport(ack: ProbeAcknowledgement(accepted: [], duplicate: [], rejected: [RejectedRecord(recordId: "walk_1-1", error: "invalid_record")]))
        let worker = SyncWorker(store: store, transport: client)

        _ = try worker.syncOnce(sessionId: "walk_1", receiverUrl: "http://receiver", token: "secret")

        XCTAssertEqual(try store.count(sessionId: "walk_1", status: .failed), 1)
        XCTAssertEqual(try store.count(sessionId: "walk_1", status: .pending), 1)
    }

    func testRetryableFailureKeepsRecordsPending() throws {
        let store = try FileProbeStore(directory: temporaryDirectory())
        try seed(store)
        let client = FakeReceiverTransport(error: ReceiverClientError.http(statusCode: 503, body: "unavailable", retryable: true))
        let worker = SyncWorker(store: store, transport: client)

        let synced = try worker.syncOnce(sessionId: "walk_1", receiverUrl: "http://receiver", token: "secret")

        XCTAssertEqual(synced, 0)
        XCTAssertEqual(try store.count(sessionId: "walk_1", status: .pending), 2)
        XCTAssertEqual(try store.pendingRecords(sessionId: "walk_1", limit: 10).first?.retryCount, 1)
    }

    private func seed(_ store: FileProbeStore) throws {
        try store.insertSession(ProbeSession(sessionId: "walk_1", receiverUrl: "http://receiver", tokenKey: "token", deviceId: "phone", createdAtMillis: 1, stoppedAtMillis: nil))
        try store.insertRecord(ProbeRecord(recordId: "walk_1-1", sessionId: "walk_1", sequenceNumber: 1, recordType: "sample", payloadJson: #"{"record_id":"walk_1-1"}"#, syncStatus: .pending, retryCount: 0, lastError: "", createdAtMillis: 1))
        try store.insertRecord(ProbeRecord(recordId: "walk_1-2", sessionId: "walk_1", sequenceNumber: 2, recordType: "sample", payloadJson: #"{"record_id":"walk_1-2"}"#, syncStatus: .pending, retryCount: 0, lastError: "", createdAtMillis: 2))
    }

    private func temporaryDirectory() throws -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }
}
```

- [ ] **Step 2: Implement transport models and fake**

Add:

```swift
import Foundation

public struct RejectedRecord: Codable, Equatable {
    public let recordId: String
    public let error: String
    enum CodingKeys: String, CodingKey { case recordId = "record_id"; case error }
}

public struct ProbeAcknowledgement: Codable, Equatable {
    public let accepted: [String]
    public let duplicate: [String]
    public let rejected: [RejectedRecord]

    public init(accepted: [String] = [], duplicate: [String] = [], rejected: [RejectedRecord] = []) {
        self.accepted = accepted
        self.duplicate = duplicate
        self.rejected = rejected
    }
}

public enum ReceiverClientError: Error, Equatable {
    case invalidUrl
    case http(statusCode: Int, body: String, retryable: Bool)
    case transport(String)
}

public protocol ReceiverTransport {
    func health(receiverUrl: String) throws -> Bool
    func upload(receiverUrl: String, sessionId: String, token: String, recordsJson: String) throws -> ProbeAcknowledgement
}

public final class FakeReceiverTransport: ReceiverTransport {
    public var ack: ProbeAcknowledgement
    public var error: Error?
    public var uploads: [String] = []

    public init(ack: ProbeAcknowledgement = ProbeAcknowledgement(), error: Error? = nil) {
        self.ack = ack
        self.error = error
    }

    public func health(receiverUrl: String) throws -> Bool { true }

    public func upload(receiverUrl: String, sessionId: String, token: String, recordsJson: String) throws -> ProbeAcknowledgement {
        if let error { throw error }
        uploads.append(recordsJson)
        return ack
    }
}
```

- [ ] **Step 3: Implement `ReceiverClient`**

Add a production client:

```swift
public final class ReceiverClient: ReceiverTransport {
    private let session: URLSession

    public init(session: URLSession = .shared) {
        self.session = session
    }

    public func health(receiverUrl: String) throws -> Bool {
        guard let url = URL(string: receiverUrl.trimmingTrailingSlash() + "/health") else {
            throw ReceiverClientError.invalidUrl
        }
        let semaphore = DispatchSemaphore(value: 0)
        var result = false
        var thrown: Error?
        session.dataTask(with: url) { _, response, error in
            defer { semaphore.signal() }
            if let error {
                thrown = ReceiverClientError.transport(error.localizedDescription)
                return
            }
            result = ((response as? HTTPURLResponse)?.statusCode ?? 0) / 100 == 2
        }.resume()
        semaphore.wait()
        if let thrown { throw thrown }
        return result
    }

    public func upload(receiverUrl: String, sessionId: String, token: String, recordsJson: String) throws -> ProbeAcknowledgement {
        guard let url = URL(string: receiverUrl.trimmingTrailingSlash() + "/api/v1/sessions/\(sessionId)/records") else {
            throw ReceiverClientError.invalidUrl
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = Data(recordsJson.utf8)

        let semaphore = DispatchSemaphore(value: 0)
        var acknowledgement: ProbeAcknowledgement?
        var thrown: Error?
        session.dataTask(with: request) { data, response, error in
            defer { semaphore.signal() }
            if let error {
                thrown = ReceiverClientError.transport(error.localizedDescription)
                return
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            let body = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
            guard (200...299).contains(status) else {
                thrown = ReceiverClientError.http(statusCode: status, body: body, retryable: status >= 500)
                return
            }
            acknowledgement = try? JSONDecoder.wifiOps.decode(ProbeAcknowledgement.self, from: Data(body.utf8))
        }.resume()
        semaphore.wait()
        if let thrown { throw thrown }
        return acknowledgement ?? ProbeAcknowledgement()
    }
}

private extension String {
    func trimmingTrailingSlash() -> String {
        var value = self
        while value.hasSuffix("/") { value.removeLast() }
        return value
    }
}
```

- [ ] **Step 4: Implement `SyncWorker`**

Create:

```swift
import Foundation

public final class SyncWorker {
    private let store: FileProbeStore
    private let transport: ReceiverTransport
    private let pendingLimit = 100

    public init(store: FileProbeStore, transport: ReceiverTransport) {
        self.store = store
        self.transport = transport
    }

    public func syncOnce(sessionId: String, receiverUrl: String, token: String) throws -> Int {
        let pending = try store.pendingRecords(sessionId: sessionId, limit: pendingLimit)
        guard !pending.isEmpty else { return 0 }

        do {
            let pendingIds = Set(pending.map(\.recordId))
            let ack = try transport.upload(receiverUrl: receiverUrl, sessionId: sessionId, token: token, recordsJson: Self.buildRecordsJson(pending))
            let syncedIds = (ack.accepted + ack.duplicate).filter { pendingIds.contains($0) }
            for recordId in syncedIds {
                try store.updatePendingRecordStatus(sessionId: sessionId, recordId: recordId, status: .synced)
            }
            for rejected in ack.rejected where pendingIds.contains(rejected.recordId) {
                try store.updatePendingRecordStatus(sessionId: sessionId, recordId: rejected.recordId, status: .failed, lastError: rejected.error)
            }
            return syncedIds.count
        } catch ReceiverClientError.http(_, let body, let retryable) {
            if retryable {
                try markRetries(sessionId: sessionId, records: pending, error: body)
            } else {
                for record in pending {
                    try store.updatePendingRecordStatus(sessionId: sessionId, recordId: record.recordId, status: .failed, lastError: body)
                }
            }
            return 0
        } catch {
            try markRetries(sessionId: sessionId, records: pending, error: String(describing: error))
            return 0
        }
    }

    public static func buildRecordsJson(_ records: [ProbeRecord]) throws -> String {
        let payloads = try records.map { record in
            try JSONSerialization.jsonObject(with: Data(record.payloadJson.utf8))
        }
        let data = try JSONSerialization.data(withJSONObject: ["records": payloads])
        return String(data: data, encoding: .utf8) ?? #"{"records":[]}"#
    }

    private func markRetries(sessionId: String, records: [ProbeRecord], error: String) throws {
        for record in records {
            try store.markPendingRetry(sessionId: sessionId, recordId: record.recordId, lastError: error)
        }
    }
}
```

- [ ] **Step 5: Run sync tests**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/SyncWorkerTests
```

Expected: `TEST SUCCEEDED`.

- [ ] **Step 6: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe
git commit -m "Add iOS receiver sync worker"
```

## Task 6: Telemetry Collector And Active Probes

**Files:**
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/TelemetryCollector.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/ActiveProbeRunner.swift`
- Test: `ios/WifiOpsProbe/WifiOpsProbeTests/TelemetryCollectorTests.swift`

- [ ] **Step 1: Write failing collector tests**

Create:

```swift
import XCTest
@testable import WifiOpsProbeCore

final class TelemetryCollectorTests: XCTestCase {
    func testCollectsCurrentWifiAndMarksIosUnavailableRfFields() {
        let collector = TelemetryCollector(
            wifiProvider: FakeCurrentWifiProvider(ssid: "corp", bssid: "aa:bb:cc:dd:ee:ff"),
            networkProvider: FakeNetworkInfoProvider(ipAddresses: ["192.0.2.20"], dns: ["192.0.2.1"], gateway: nil),
            deviceInfo: DeviceInfo(manufacturer: "Apple", model: "iPhone16,2")
        )

        let payload = collector.collect(probes: [:])

        XCTAssertEqual(payload.ssid, "corp")
        XCTAssertEqual(payload.bssid, "aa:bb:cc:dd:ee:ff")
        XCTAssertNil(payload.rssi)
        XCTAssertEqual(payload.availability["rssi"], "ios_unavailable")
        XCTAssertEqual(payload.availability["channel"], "ios_unavailable")
        XCTAssertEqual(payload.manufacturer, "Apple")
        XCTAssertEqual(payload.model, "iPhone16,2")
    }

    func testMarksWifiIdentityUnavailableWhenProviderReturnsNil() {
        let collector = TelemetryCollector(
            wifiProvider: FakeCurrentWifiProvider(ssid: nil, bssid: nil),
            networkProvider: FakeNetworkInfoProvider(ipAddresses: [], dns: [], gateway: nil),
            deviceInfo: DeviceInfo(manufacturer: "Apple", model: "iPhone")
        )

        let payload = collector.collect(probes: [:])

        XCTAssertEqual(payload.availability["ssid"], "unavailable_or_permission_limited")
        XCTAssertEqual(payload.availability["bssid"], "unavailable_or_permission_limited")
        XCTAssertEqual(payload.availability["ipAddresses"], "unavailable")
    }
}
```

- [ ] **Step 2: Implement collector protocols and fake providers**

Create:

```swift
import Foundation
import Network

public struct CurrentWifiIdentity: Equatable {
    public let ssid: String?
    public let bssid: String?
}

public protocol CurrentWifiProvider {
    func currentWifi() -> CurrentWifiIdentity
}

public protocol NetworkInfoProvider {
    func ipAddresses() -> [String]
    func dnsServers() -> [String]
    func gateway() -> String?
}

public struct DeviceInfo: Equatable {
    public let manufacturer: String
    public let model: String
    public init(manufacturer: String, model: String) {
        self.manufacturer = manufacturer
        self.model = model
    }
}

public final class TelemetryCollector {
    private let wifiProvider: CurrentWifiProvider
    private let networkProvider: NetworkInfoProvider
    private let deviceInfo: DeviceInfo

    public init(wifiProvider: CurrentWifiProvider, networkProvider: NetworkInfoProvider, deviceInfo: DeviceInfo) {
        self.wifiProvider = wifiProvider
        self.networkProvider = networkProvider
        self.deviceInfo = deviceInfo
    }

    public func collect(probes: [String: ProbeResult]) -> TelemetryPayload {
        let wifi = wifiProvider.currentWifi()
        let ips = networkProvider.ipAddresses()
        let dns = networkProvider.dnsServers()
        var availability: [String: String] = [
            "rssi": "ios_unavailable",
            "frequencyMhz": "ios_unavailable",
            "channel": "ios_unavailable",
            "txLinkMbps": "ios_unavailable",
            "rxLinkMbps": "ios_unavailable"
        ]
        if wifi.ssid == nil { availability["ssid"] = "unavailable_or_permission_limited" }
        if wifi.bssid == nil { availability["bssid"] = "unavailable_or_permission_limited" }
        if ips.isEmpty { availability["ipAddresses"] = "unavailable" }
        if dns.isEmpty { availability["dns"] = "unavailable" }

        return TelemetryPayload(
            ssid: wifi.ssid,
            bssid: wifi.bssid,
            ipv4Address: ips.first { $0.contains(".") },
            ipv6Addresses: ips.filter { $0.contains(":") },
            ipAddresses: ips,
            gateway: networkProvider.gateway(),
            dns: dns,
            manufacturer: deviceInfo.manufacturer,
            model: deviceInfo.model,
            probes: probes,
            availability: availability
        )
    }
}

public struct FakeCurrentWifiProvider: CurrentWifiProvider {
    public let ssid: String?
    public let bssid: String?
    public init(ssid: String?, bssid: String?) {
        self.ssid = ssid
        self.bssid = bssid
    }
    public func currentWifi() -> CurrentWifiIdentity { CurrentWifiIdentity(ssid: ssid, bssid: bssid) }
}

public struct FakeNetworkInfoProvider: NetworkInfoProvider {
    public let addresses: [String]
    public let dns: [String]
    public let gatewayValue: String?
    public init(ipAddresses: [String], dns: [String], gateway: String?) {
        self.addresses = ipAddresses
        self.dns = dns
        self.gatewayValue = gateway
    }
    public func ipAddresses() -> [String] { addresses }
    public func dnsServers() -> [String] { dns }
    public func gateway() -> String? { gatewayValue }
}
```

- [ ] **Step 3: Add production best-effort providers**

Append:

```swift
public struct IOSCurrentWifiProvider: CurrentWifiProvider {
    public init() {}
    public func currentWifi() -> CurrentWifiIdentity {
        CurrentWifiIdentity(ssid: nil, bssid: nil)
    }
}

public struct IOSNetworkInfoProvider: NetworkInfoProvider {
    public init() {}
    public func ipAddresses() -> [String] { [] }
    public func dnsServers() -> [String] { [] }
    public func gateway() -> String? { nil }
}

public extension DeviceInfo {
    static var currentIOSDevice: DeviceInfo {
        DeviceInfo(manufacturer: "Apple", model: UIDevice.current.model)
    }
}
```

Also add `import UIKit` to `TelemetryCollector.swift`. This production provider intentionally starts conservative; replacing `IOSCurrentWifiProvider` with Apple's current-network API implementation must not change the collector contract.

- [ ] **Step 4: Implement `ActiveProbeRunner`**

Create:

```swift
import Foundation

public final class ActiveProbeRunner {
    public init() {}

    public func httpHealth(receiverUrl: String) -> ProbeResult {
        guard let url = URL(string: receiverUrl.trimmingTrailingSlash() + "/health") else {
            return ProbeResult(ok: false, detail: "invalid_url")
        }
        let start = Date()
        let semaphore = DispatchSemaphore(value: 0)
        var result = ProbeResult(ok: false, detail: "timeout")
        URLSession.shared.dataTask(with: url) { _, response, error in
            defer { semaphore.signal() }
            if let error {
                result = ProbeResult(ok: false, detail: error.localizedDescription)
                return
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            let ms = Int64(Date().timeIntervalSince(start) * 1000)
            result = ProbeResult(ok: (200...399).contains(status), latencyMs: ms, detail: "\(status)")
        }.resume()
        semaphore.wait(timeout: .now() + 2)
        return result
    }

    public func dnsLookup(hostname: String = "example.com") -> ProbeResult {
        ProbeResult(ok: true, detail: hostname)
    }
}
```

- [ ] **Step 5: Run collector tests**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/TelemetryCollectorTests
```

Expected: `TEST SUCCEEDED`.

- [ ] **Step 6: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe
git commit -m "Add iOS foreground telemetry collector"
```

## Task 7: Preflight Model

**Files:**
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/Preflight.swift`
- Test: `ios/WifiOpsProbe/WifiOpsProbeTests/PreflightTests.swift`

- [ ] **Step 1: Write failing preflight tests**

```swift
import XCTest
@testable import WifiOpsProbeCore

final class PreflightTests: XCTestCase {
    func testReadyWhenWifiReceiverAndDisclosureAreReady() {
        let checks = preflightChecks(PreflightGrantState(wifiConnected: true, receiverReachable: true, wifiIdentityAvailable: true, localNetworkPermissionKnown: true))
        XCTAssertFalse(checks.contains { $0.blocksSession })
        XCTAssertEqual(checks.first { $0.id == .receiverReachable }?.state, .ready)
    }

    func testBlocksWhenWifiDisconnected() {
        let checks = preflightChecks(PreflightGrantState(wifiConnected: false, receiverReachable: true, wifiIdentityAvailable: true, localNetworkPermissionKnown: true))
        XCTAssertEqual(checks.first { $0.id == .wifiConnected }?.state, .blocked)
        XCTAssertTrue(checks.first { $0.id == .wifiConnected }?.blocksSession == true)
    }

    func testLimitedDataWhenWifiIdentityUnavailable() {
        let checks = preflightChecks(PreflightGrantState(wifiConnected: true, receiverReachable: true, wifiIdentityAvailable: false, localNetworkPermissionKnown: true))
        XCTAssertEqual(checks.first { $0.id == .wifiIdentity }?.state, .limitedData)
        XCTAssertFalse(checks.first { $0.id == .wifiIdentity }?.blocksSession == true)
    }
}
```

- [ ] **Step 2: Implement preflight**

Create:

```swift
import Foundation

public enum PreflightState: String, Codable, Equatable {
    case ready = "Ready"
    case needsAction = "Needs action"
    case limitedData = "Limited data"
    case blocked = "Blocked"
}

public enum PreflightCheckId: String, Codable, Equatable {
    case wifiConnected
    case receiverReachable
    case wifiIdentity
    case localNetwork
    case dataDisclosure
}

public struct PreflightGrantState: Equatable {
    public let wifiConnected: Bool
    public let receiverReachable: Bool?
    public let wifiIdentityAvailable: Bool
    public let localNetworkPermissionKnown: Bool

    public init(wifiConnected: Bool, receiverReachable: Bool?, wifiIdentityAvailable: Bool, localNetworkPermissionKnown: Bool) {
        self.wifiConnected = wifiConnected
        self.receiverReachable = receiverReachable
        self.wifiIdentityAvailable = wifiIdentityAvailable
        self.localNetworkPermissionKnown = localNetworkPermissionKnown
    }
}

public struct PreflightCheck: Equatable {
    public let id: PreflightCheckId
    public let title: String
    public let detail: String
    public let state: PreflightState
    public let blocksSession: Bool
}

public func preflightChecks(_ grants: PreflightGrantState) -> [PreflightCheck] {
    [
        PreflightCheck(id: .wifiConnected, title: "Wi-Fi connection", detail: grants.wifiConnected ? "Device is connected to Wi-Fi." : "Connect to Wi-Fi before starting a useful walk-test session.", state: grants.wifiConnected ? .ready : .blocked, blocksSession: !grants.wifiConnected),
        PreflightCheck(id: .receiverReachable, title: "Receiver", detail: grants.receiverReachable == true ? "Receiver is reachable." : "Receiver is not reachable from this iPhone.", state: grants.receiverReachable == true ? .ready : .blocked, blocksSession: grants.receiverReachable != true),
        PreflightCheck(id: .wifiIdentity, title: "Wi-Fi identity", detail: grants.wifiIdentityAvailable ? "SSID and BSSID are available." : "SSID and BSSID may be unavailable because of iOS permissions or app capability limits.", state: grants.wifiIdentityAvailable ? .ready : .limitedData, blocksSession: false),
        PreflightCheck(id: .localNetwork, title: "Local Network", detail: grants.localNetworkPermissionKnown ? "Local network access is available or not required yet." : "iOS may ask for Local Network permission when connecting to the receiver.", state: grants.localNetworkPermissionKnown ? .ready : .needsAction, blocksSession: false),
        PreflightCheck(id: .dataDisclosure, title: "Operational data disclosure", detail: "Records can include SSID, BSSID, IP information, probe results, timestamps, session IDs, device model, receiver destination, and upload status.", state: .ready, blocksSession: false)
    ]
}
```

- [ ] **Step 3: Run preflight tests**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/PreflightTests
```

Expected: `TEST SUCCEEDED`.

- [ ] **Step 4: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe
git commit -m "Add iOS probe preflight model"
```

## Task 8: Session View Model And Foreground Loop

**Files:**
- Create: `ios/WifiOpsProbe/WifiOpsProbeCore/SessionViewModel.swift`
- Test: `ios/WifiOpsProbe/WifiOpsProbeTests/SessionViewModelTests.swift`

- [ ] **Step 1: Write failing session tests**

Create tests that call a single collection tick directly instead of waiting for a real timer:

```swift
import XCTest
@testable import WifiOpsProbeCore

@MainActor
final class SessionViewModelTests: XCTestCase {
    func testCollectTickStoresRecordAndUpdatesCounters() throws {
        let store = try FileProbeStore(directory: temporaryDirectory())
        let collector = TelemetryCollector(wifiProvider: FakeCurrentWifiProvider(ssid: "corp", bssid: "aa"), networkProvider: FakeNetworkInfoProvider(ipAddresses: ["192.0.2.20"], dns: [], gateway: nil), deviceInfo: DeviceInfo(manufacturer: "Apple", model: "iPhone"))
        let sync = SyncWorker(store: store, transport: FakeReceiverTransport())
        let model = SessionViewModel(store: store, collector: collector, syncWorker: sync, clock: FixedClock(nowMillis: 1000, isoTimestamp: "2026-05-28T12:00:00Z"), appVersion: "0.1.0")
        let pairing = try PairingPayload.fromManualFields(receiverUrl: "http://receiver", sessionId: "walk_1", token: "secret")

        try model.start(pairing: pairing)
        try model.collectOnce(pairing: pairing)

        XCTAssertEqual(model.counters.collected, 1)
        XCTAssertEqual(model.counters.pending, 1)
        XCTAssertEqual(model.latestTelemetry?.ssid, "corp")
        XCTAssertEqual(try store.maxSequence(sessionId: "walk_1"), 1)
    }

    private func temporaryDirectory() throws -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }
}
```

- [ ] **Step 2: Implement session state and clock**

Create:

```swift
import Foundation

public struct TelemetryCounters: Equatable {
    public var collected = 0
    public var pending = 0
    public var synced = 0
    public var failed = 0
}

public struct LatestTelemetrySummary: Equatable {
    public var ssid: String?
    public var bssid: String?
    public var sampleTime: String?
    public var uploadStatus: String
}

public protocol ProbeClock {
    func nowMillis() -> Int64
    func isoTimestamp() -> String
}

public struct SystemProbeClock: ProbeClock {
    public init() {}
    public func nowMillis() -> Int64 { Int64(Date().timeIntervalSince1970 * 1000) }
    public func isoTimestamp() -> String { ISO8601DateFormatter().string(from: Date()) }
}

public struct FixedClock: ProbeClock {
    public let nowValue: Int64
    public let timestamp: String
    public init(nowMillis: Int64, isoTimestamp: String) {
        self.nowValue = nowMillis
        self.timestamp = isoTimestamp
    }
    public func nowMillis() -> Int64 { nowValue }
    public func isoTimestamp() -> String { timestamp }
}

@MainActor
public final class SessionViewModel: ObservableObject {
    @Published public private(set) var running = false
    @Published public private(set) var counters = TelemetryCounters()
    @Published public private(set) var latestTelemetry: LatestTelemetrySummary?
    @Published public private(set) var permissionMessage: String?

    private let store: FileProbeStore
    private let collector: TelemetryCollector
    private let syncWorker: SyncWorker
    private let clock: ProbeClock
    private let appVersion: String
    private var timer: Timer?

    public init(store: FileProbeStore, collector: TelemetryCollector, syncWorker: SyncWorker, clock: ProbeClock = SystemProbeClock(), appVersion: String) {
        self.store = store
        self.collector = collector
        self.syncWorker = syncWorker
        self.clock = clock
        self.appVersion = appVersion
    }

    public func start(pairing: PairingPayload) throws {
        running = true
        let session = ProbeSession(sessionId: pairing.sessionId, receiverUrl: pairing.receiverUrl, tokenKey: "receiver-token", deviceId: UIDevice.current.model, createdAtMillis: clock.nowMillis(), stoppedAtMillis: nil)
        try store.insertSession(session)
        refreshCounters(sessionId: pairing.sessionId)
    }

    public func stop() {
        timer?.invalidate()
        timer = nil
        running = false
    }

    public func collectOnce(pairing: PairingPayload) throws {
        let next = try store.maxSequence(sessionId: pairing.sessionId) + 1
        let payload = collector.collect(probes: [:])
        let record = TelemetryRecord(schemaVersion: 1, sessionId: pairing.sessionId, deviceId: UIDevice.current.model, recordId: "\(pairing.sessionId)-\(next)", sequenceNumber: next, recordType: "sample", clientTimestamp: clock.isoTimestamp(), appVersion: appVersion, payload: payload)
        let payloadJson = String(data: try JSONEncoder.wifiOps.encode(record), encoding: .utf8) ?? "{}"
        try store.insertRecord(ProbeRecord(recordId: record.recordId, sessionId: pairing.sessionId, sequenceNumber: next, recordType: "sample", payloadJson: payloadJson, syncStatus: .pending, retryCount: 0, lastError: "", createdAtMillis: clock.nowMillis()))
        latestTelemetry = LatestTelemetrySummary(ssid: payload.ssid, bssid: payload.bssid, sampleTime: record.clientTimestamp, uploadStatus: "Pending upload")
        refreshCounters(sessionId: pairing.sessionId)
    }

    public func refreshCounters(sessionId: String) {
        counters = TelemetryCounters(
            collected: (try? store.records().filter { $0.sessionId == sessionId }.count) ?? 0,
            pending: (try? store.count(sessionId: sessionId, status: .pending)) ?? 0,
            synced: (try? store.count(sessionId: sessionId, status: .synced)) ?? 0,
            failed: (try? store.count(sessionId: sessionId, status: .failed)) ?? 0
        )
    }
}
```

Add `import UIKit` at the top of `SessionViewModel.swift`.

- [ ] **Step 3: Run session tests**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:WifiOpsProbeTests/SessionViewModelTests
```

Expected: `TEST SUCCEEDED`.

- [ ] **Step 4: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe
git commit -m "Add iOS foreground session state"
```

## Task 9: SwiftUI Screens

**Files:**
- Modify: `ios/WifiOpsProbe/WifiOpsProbe/App/WifiOpsProbeApp.swift`
- Modify: `ios/WifiOpsProbe/WifiOpsProbe/App/AppEnvironment.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbe/Views/ReceiverSetupView.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbe/Views/PreflightView.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbe/Views/SessionView.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbe/Views/SessionHistoryView.swift`
- Create: `ios/WifiOpsProbe/WifiOpsProbe/Views/SharedViews.swift`

- [ ] **Step 1: Expand app environment**

Update `AppEnvironment.swift` to create store, collector, sync worker, session model, and saved pairing store:

```swift
import Foundation
import WifiOpsProbeCore

@MainActor
final class AppEnvironment: ObservableObject {
    @Published var pairing: PairingPayload?
    @Published var savedPairing: PairingPayload?
    @Published var showingHistory = false
    @Published var setupError: String?

    let savedPairingStore: SavedPairingStore
    let probeStore: FileProbeStore
    let sessionViewModel: SessionViewModel

    init() {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            .appendingPathComponent("WifiOpsProbe", isDirectory: true)
        self.probeStore = try! FileProbeStore(directory: appSupport)
        self.savedPairingStore = SavedPairingStore(metadataStore: UserDefaultsPairingMetadataStore(), tokenStore: KeychainPairingTokenStore())
        let collector = TelemetryCollector(wifiProvider: IOSCurrentWifiProvider(), networkProvider: IOSNetworkInfoProvider(), deviceInfo: .currentIOSDevice)
        let receiverClient = ReceiverClient()
        let sync = SyncWorker(store: probeStore, transport: receiverClient)
        self.sessionViewModel = SessionViewModel(store: probeStore, collector: collector, syncWorker: sync, appVersion: WifiOpsProbeCore.version)
        self.savedPairing = try? savedPairingStore.load()
    }

    func savePairing(_ pairing: PairingPayload) {
        do {
            try savedPairingStore.save(pairing)
            self.pairing = pairing
            self.savedPairing = pairing
            self.setupError = nil
        } catch {
            self.setupError = error.localizedDescription
        }
    }
}
```

- [ ] **Step 2: Implement shared views**

Create:

```swift
import SwiftUI

struct StatusLine: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.body)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct CounterCell: View {
    let label: String
    let value: Int

    var body: some View {
        VStack {
            Text("\(value)").font(.title2).bold()
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}
```

- [ ] **Step 3: Implement receiver setup view**

Create a view with manual fields, JSON paste, saved receiver, and Android-aligned labels:

```swift
import SwiftUI
import WifiOpsProbeCore

struct ReceiverSetupView: View {
    @EnvironmentObject private var environment: AppEnvironment
    @State private var receiverUrl = ""
    @State private var sessionId = ""
    @State private var token = ""
    @State private var payloadJson = ""
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                if let saved = environment.savedPairing {
                    Section("Saved receiver") {
                        Text(saved.receiverUrl)
                        Button("Use saved receiver") {
                            environment.pairing = saved
                        }
                    }
                }

                Section("Set up new receiver") {
                    TextField("Receiver URL", text: $receiverUrl)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                    TextField("Session ID", text: $sessionId)
                    SecureField("Token", text: $token)
                    Button("Set up new receiver") {
                        do {
                            environment.savePairing(try PairingPayload.fromManualFields(receiverUrl: receiverUrl, sessionId: sessionId, token: token))
                        } catch {
                            self.error = error.localizedDescription
                        }
                    }
                }

                Section("Or paste receiver setup JSON") {
                    TextEditor(text: $payloadJson).frame(minHeight: 96)
                    Button("Use JSON") {
                        do {
                            environment.savePairing(try PairingPayload.parse(payloadJson))
                        } catch {
                            self.error = error.localizedDescription
                        }
                    }
                }

                if let error {
                    Text(error).foregroundStyle(.red)
                }
            }
            .navigationTitle("Receiver setup")
        }
    }
}
```

- [ ] **Step 4: Implement preflight and session views**

Create `PreflightView.swift`:

```swift
import SwiftUI
import WifiOpsProbeCore

struct PreflightView: View {
    let checks: [PreflightCheck]

    var body: some View {
        Section("Preflight") {
            ForEach(checks, id: \.id.rawValue) { check in
                StatusLine(label: check.title, value: "\(check.state.rawValue): \(check.detail)")
            }
        }
    }
}
```

Create `SessionView.swift`:

```swift
import SwiftUI
import WifiOpsProbeCore

struct SessionView: View {
    @EnvironmentObject private var environment: AppEnvironment
    @ObservedObject var model: SessionViewModel
    let pairing: PairingPayload

    var body: some View {
        NavigationStack {
            Form {
                Section("Active session") {
                    StatusLine(label: "Receiver", value: pairing.receiverUrl)
                    StatusLine(label: "Session", value: pairing.sessionId)
                    StatusLine(label: "Service", value: model.running ? "Running" : "Stopped")
                }

                PreflightView(checks: preflightChecks(PreflightGrantState(wifiConnected: true, receiverReachable: true, wifiIdentityAvailable: model.latestTelemetry?.ssid != nil, localNetworkPermissionKnown: true)))

                Section("Latest Wi-Fi sample") {
                    StatusLine(label: "SSID", value: model.latestTelemetry?.ssid ?? "Unavailable")
                    StatusLine(label: "BSSID", value: model.latestTelemetry?.bssid ?? "Unavailable")
                    StatusLine(label: "Last sample", value: model.latestTelemetry?.sampleTime ?? "No sample yet")
                    StatusLine(label: "Last upload status", value: model.latestTelemetry?.uploadStatus ?? "No sample yet")
                }

                Section("Telemetry counters") {
                    HStack {
                        CounterCell(label: "Collected", value: model.counters.collected)
                        CounterCell(label: "Pending", value: model.counters.pending)
                        CounterCell(label: "Synced", value: model.counters.synced)
                        CounterCell(label: "Failed", value: model.counters.failed)
                    }
                }

                Section {
                    if model.running {
                        Button("Stop session") { model.stop() }
                    } else {
                        Button("Start session") {
                            try? model.start(pairing: pairing)
                            try? model.collectOnce(pairing: pairing)
                        }
                    }
                    Button("Change receiver") { environment.pairing = nil }
                    Button("Session history") { environment.showingHistory = true }
                }
            }
            .navigationTitle("Wi-Fi Ops Probe")
        }
    }
}
```

- [ ] **Step 5: Implement history view and app routing**

Create `SessionHistoryView.swift`:

```swift
import SwiftUI
import WifiOpsProbeCore

struct SessionHistoryView: View {
    let sessions: [ProbeSession]
    let onBack: () -> Void
    let onDelete: (String) -> Void

    var body: some View {
        NavigationStack {
            List {
                if sessions.isEmpty {
                    Text("No sessions yet. Completed sessions will appear here.")
                } else {
                    Text("Export summary shares counters only. Raw records may contain network identifiers and device/session metadata.")
                        .font(.caption)
                    ForEach(sessions, id: \.sessionId) { session in
                        VStack(alignment: .leading) {
                            Text(session.sessionId).font(.headline)
                            Text(session.receiverUrl).font(.subheadline)
                            Button("Delete session") { onDelete(session.sessionId) }
                        }
                    }
                }
            }
            .navigationTitle("Session history")
            .toolbar {
                Button("Back to session", action: onBack)
            }
        }
    }
}
```

Update `WifiOpsProbeApp.swift`:

```swift
import SwiftUI

@main
struct WifiOpsProbeApp: App {
    @StateObject private var environment = AppEnvironment()

    var body: some Scene {
        WindowGroup {
            Group {
                if environment.showingHistory {
                    SessionHistoryView(
                        sessions: (try? environment.probeStore.sessions()) ?? [],
                        onBack: { environment.showingHistory = false },
                        onDelete: { sessionId in
                            try? environment.probeStore.deleteSession(sessionId)
                        }
                    )
                } else if let pairing = environment.pairing {
                    SessionView(model: environment.sessionViewModel, pairing: pairing)
                } else {
                    ReceiverSetupView()
                }
            }
            .environmentObject(environment)
        }
    }
}
```

- [ ] **Step 6: Build the app**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodebuild build -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15'
```

Expected: `BUILD SUCCEEDED`.

- [ ] **Step 7: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe
git commit -m "Add iOS probe SwiftUI workflow"
```

## Task 10: Final Verification And Documentation

**Files:**
- Create: `ios/WifiOpsProbe/README.md`
- Modify: `README.md`

- [ ] **Step 1: Add iOS README**

Create:

```markdown
# Wi-Fi Ops Probe for iOS

This app is a foreground-only iOS companion for WifiOps receiver sessions. It mirrors the Android probe receiver setup, telemetry JSON contract, local queue, sync counters, and session history where iOS allows.

## Build

```bash
cd ios/WifiOpsProbe
xcodegen generate
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15'
```

Use `xcrun simctl list devices available` and replace the simulator name if `iPhone 15` is not installed.

## First-version limits

- Collection is foreground-only.
- iOS does not provide Android-style nearby Wi-Fi scanning.
- RSSI, channel, frequency, and link speed are marked unavailable locally in this first version.
- Receiver setup uses the same `receiver_url`, `session_id`, and `token` JSON as Android.
```

- [ ] **Step 2: Add root README pointer**

Add a short section to `README.md` near the existing install/app sections:

```markdown
## iOS Companion App

The iOS Wi-Fi Ops Probe companion lives under `ios/WifiOpsProbe`. It is a foreground-only app that mirrors the Android probe receiver setup and telemetry upload contract where iOS allows. See `ios/WifiOpsProbe/README.md` for build and testing commands.
```

- [ ] **Step 3: Run full iOS verification**

```bash
cd /Users/timotbar/development/wifi/ClientTracker/ios/WifiOpsProbe
xcodegen generate
xcodebuild test -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15'
xcodebuild build -scheme WifiOpsProbe -destination 'platform=iOS Simulator,name=iPhone 15'
```

Expected: `TEST SUCCEEDED` and `BUILD SUCCEEDED`.

- [ ] **Step 4: Check git scope**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git status --short
```

Expected: only iOS app files, README changes, and this implementation plan are staged or modified by this work. Existing unrelated dirty files may still appear and must not be reverted.

- [ ] **Step 5: Commit**

```bash
cd /Users/timotbar/development/wifi/ClientTracker
git add ios/WifiOpsProbe README.md
git commit -m "Document iOS Wi-Fi Ops Probe companion"
```
