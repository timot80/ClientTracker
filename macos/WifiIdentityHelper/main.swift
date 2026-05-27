import AppKit
import CoreLocation
import CoreWLAN
import Foundation

final class WiFiIdentityApp: NSObject, NSApplicationDelegate, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var completed = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyThreeKilometers
        Timer.scheduledTimer(withTimeInterval: 30, repeats: false) { [weak self] _ in
            self?.emitAndQuit()
        }
        requestLocationAuthorization()
    }

    private func requestLocationAuthorization() {
        let status = currentStatus()
        switch status {
        case .notDetermined:
            manager.requestAlwaysAuthorization()
            manager.startUpdatingLocation()
            manager.requestLocation()
        case .authorizedAlways, .authorizedWhenInUse:
            manager.startUpdatingLocation()
            emitAndQuit()
        default:
            emitAndQuit()
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        handleAuthorizationChange()
    }

    func locationManager(_ manager: CLLocationManager, didChangeAuthorization status: CLAuthorizationStatus) {
        handleAuthorizationChange()
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        emitAndQuit()
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        if currentStatus() == .notDetermined {
            return
        }
        emitAndQuit()
    }

    private func handleAuthorizationChange() {
        switch currentStatus() {
        case .notDetermined:
            return
        case .authorizedAlways, .authorizedWhenInUse:
            manager.requestLocation()
        default:
            emitAndQuit()
        }
    }

    private func currentStatus() -> CLAuthorizationStatus {
        return manager.authorizationStatus
    }

    private func emitAndQuit() {
        guard !completed else {
            return
        }
        completed = true
        manager.stopUpdatingLocation()

        let wifiClient = CWWiFiClient.shared()
        let interface = wifiClient.interface()
        writeJSON([
            "authorization": statusName(currentStatus()),
            "bssid": interface?.bssid() ?? "",
            "interface": interface?.interfaceName ?? "",
            "ssid": interface?.ssid() ?? "",
        ])
        NSApp.terminate(nil)
    }
}

func outputFilePath() -> String? {
    let arguments = CommandLine.arguments
    guard let index = arguments.firstIndex(of: "--output"), arguments.count > index + 1 else {
        return nil
    }
    return arguments[index + 1]
}

func statusName(_ status: CLAuthorizationStatus) -> String {
    switch status {
    case .notDetermined:
        return "notDetermined"
    case .restricted:
        return "restricted"
    case .denied:
        return "denied"
    case .authorizedAlways:
        return "authorizedAlways"
    case .authorizedWhenInUse:
        return "authorizedWhenInUse"
    @unknown default:
        return "unknown"
    }
}

func writeJSON(_ payload: [String: String]) {
    guard
        let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys]),
        let output = String(data: data, encoding: .utf8)
    else {
        print("{\"error\":\"failed to encode JSON\"}")
        exit(1)
    }

    if let path = outputFilePath() {
        do {
            try output.write(toFile: path, atomically: true, encoding: .utf8)
        } catch {
            print("{\"error\":\"failed to write output file\"}")
            exit(1)
        }
        return
    }
    print(output)
}

let app = NSApplication.shared
let delegate = WiFiIdentityApp()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.activate(ignoringOtherApps: true)
app.run()
