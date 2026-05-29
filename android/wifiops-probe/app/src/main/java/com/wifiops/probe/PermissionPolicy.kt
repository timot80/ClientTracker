package com.wifiops.probe

import android.Manifest
import android.os.Build

fun requiredRuntimePermissions(apiLevel: Int = Build.VERSION.SDK_INT): List<String> {
    return when {
        apiLevel >= Build.VERSION_CODES.TIRAMISU -> listOf(
            Manifest.permission.NEARBY_WIFI_DEVICES,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.POST_NOTIFICATIONS
        )

        apiLevel >= Build.VERSION_CODES.Q -> listOf(
            Manifest.permission.ACCESS_FINE_LOCATION
        )

        else -> emptyList()
    }
}

fun needsBackgroundLocationForServiceWifiIdentity(apiLevel: Int = Build.VERSION.SDK_INT): Boolean {
    return apiLevel in Build.VERSION_CODES.Q..Build.VERSION_CODES.S_V2
}

enum class PreflightState(val label: String) {
    Ready("Ready"),
    NeedsAction("Needs action"),
    LimitedData("Limited data"),
    Blocked("Blocked")
}

enum class PreflightRecoveryAction(val label: String) {
    Retry("Retry"),
    OpenSettings("Open settings"),
    TestAgain("Test again")
}

enum class PreflightCheckId {
    NearbyWifi,
    Location,
    BackgroundLocation,
    Notifications,
    WifiConnected,
    ReceiverReachable,
    DataDisclosure
}

data class PermissionGrantState(
    val apiLevel: Int = Build.VERSION.SDK_INT,
    val nearbyWifiGranted: Boolean,
    val fineLocationGranted: Boolean,
    val backgroundLocationGranted: Boolean,
    val notificationsGranted: Boolean,
    val wifiConnected: Boolean,
    val receiverReachable: Boolean?
)

data class PreflightCheck(
    val id: PreflightCheckId,
    val title: String,
    val detail: String,
    val state: PreflightState,
    val recoveryAction: PreflightRecoveryAction? = null,
    val blocksSession: Boolean = state == PreflightState.Blocked
)

fun preflightChecks(grants: PermissionGrantState): List<PreflightCheck> {
    val checks = mutableListOf<PreflightCheck>()

    if (grants.apiLevel >= Build.VERSION_CODES.TIRAMISU) {
        checks += PreflightCheck(
            id = PreflightCheckId.NearbyWifi,
            title = "Nearby Wi-Fi permission",
            detail = if (grants.nearbyWifiGranted) {
                "Wi-Fi identity, signal, and channel collection are available."
            } else {
                "Allow Nearby Wi-Fi so samples can include SSID, BSSID, RSSI, and channel."
            },
            state = if (grants.nearbyWifiGranted) PreflightState.Ready else PreflightState.Blocked,
            recoveryAction = if (grants.nearbyWifiGranted) null else PreflightRecoveryAction.OpenSettings
        )
    }

    if (grants.apiLevel >= Build.VERSION_CODES.Q) {
        checks += PreflightCheck(
            id = PreflightCheckId.Location,
            title = "Precise location permission",
            detail = if (grants.fineLocationGranted) {
                "Android can expose SSID, BSSID, RSSI, and channel for this Wi-Fi session."
            } else {
                "Allow precise location so Android can expose SSID, BSSID, RSSI, and channel."
            },
            state = if (grants.fineLocationGranted) PreflightState.Ready else PreflightState.Blocked,
            recoveryAction = if (grants.fineLocationGranted) null else PreflightRecoveryAction.OpenSettings
        )
    }

    if (needsBackgroundLocationForServiceWifiIdentity(grants.apiLevel)) {
        checks += PreflightCheck(
            id = PreflightCheckId.BackgroundLocation,
            title = "Background location",
            detail = if (grants.backgroundLocationGranted) {
                "Collection can continue while the app is backgrounded."
            } else {
                "Allow all-the-time location to keep Wi-Fi identity available during background collection."
            },
            state = if (grants.backgroundLocationGranted) PreflightState.Ready else PreflightState.NeedsAction,
            recoveryAction = if (grants.backgroundLocationGranted) null else PreflightRecoveryAction.OpenSettings,
            blocksSession = false
        )
    }

    checks += PreflightCheck(
        id = PreflightCheckId.Notifications,
        title = if (grants.notificationsGranted || grants.apiLevel < Build.VERSION_CODES.TIRAMISU) {
            "Notifications ready"
        } else {
            "Limited notification status"
        },
        detail = if (grants.notificationsGranted || grants.apiLevel < Build.VERSION_CODES.TIRAMISU) {
            "Session status can appear while collection is running."
        } else {
            "Collection can continue, but session status may not appear while the app is backgrounded."
        },
        state = if (grants.notificationsGranted || grants.apiLevel < Build.VERSION_CODES.TIRAMISU) {
            PreflightState.Ready
        } else {
            PreflightState.LimitedData
        },
        recoveryAction = if (grants.notificationsGranted || grants.apiLevel < Build.VERSION_CODES.TIRAMISU) {
            null
        } else {
            PreflightRecoveryAction.OpenSettings
        },
        blocksSession = false
    )

    checks += PreflightCheck(
        id = PreflightCheckId.WifiConnected,
        title = "Wi-Fi connection",
        detail = if (grants.wifiConnected) {
            "Device is connected to Wi-Fi."
        } else {
            "Connect to Wi-Fi before starting a useful walk-test session."
        },
        state = if (grants.wifiConnected) PreflightState.Ready else PreflightState.Blocked,
        recoveryAction = if (grants.wifiConnected) null else PreflightRecoveryAction.Retry
    )

    checks += PreflightCheck(
        id = PreflightCheckId.ReceiverReachable,
        title = "Receiver",
        detail = when (grants.receiverReachable) {
            true -> "Receiver is reachable."
            false -> "Receiver is unreachable. Local collection can continue if uploads fail later."
            null -> "Receiver has not been tested."
        },
        state = when (grants.receiverReachable) {
            true -> PreflightState.Ready
            false -> PreflightState.Blocked
            null -> PreflightState.NeedsAction
        },
        recoveryAction = if (grants.receiverReachable == true) null else PreflightRecoveryAction.TestAgain
    )

    checks += PreflightCheck(
        id = PreflightCheckId.DataDisclosure,
        title = "Operational data disclosure",
        detail = "Records can include SSID, BSSID, RSSI, channel, IP information, probe results, timestamps, session IDs, device model, receiver destination, and upload status.",
        state = PreflightState.Ready,
        blocksSession = false
    )

    return checks
}
