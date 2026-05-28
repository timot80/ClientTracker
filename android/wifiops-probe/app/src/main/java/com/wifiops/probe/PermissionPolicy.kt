package com.wifiops.probe

import android.Manifest
import android.os.Build

fun requiredRuntimePermissions(apiLevel: Int = Build.VERSION.SDK_INT): List<String> {
    return when {
        apiLevel >= Build.VERSION_CODES.TIRAMISU -> listOf(
            Manifest.permission.NEARBY_WIFI_DEVICES,
            Manifest.permission.POST_NOTIFICATIONS,
            Manifest.permission.ACCESS_FINE_LOCATION
        )

        apiLevel >= Build.VERSION_CODES.Q -> listOf(
            Manifest.permission.ACCESS_FINE_LOCATION
        )

        else -> emptyList()
    }
}

fun needsBackgroundLocationForServiceWifiIdentity(apiLevel: Int = Build.VERSION.SDK_INT): Boolean {
    return apiLevel >= Build.VERSION_CODES.Q
}
