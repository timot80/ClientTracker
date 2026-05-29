package com.wifiops.probe

import android.Manifest
import android.os.Build
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PermissionPolicyTest {
    @Test
    fun runtimePermissionsForAndroidThirteenIncludeNearbyFineLocationAndNotifications() {
        val permissions = requiredRuntimePermissions(Build.VERSION_CODES.TIRAMISU)

        assertEquals(
            listOf(
                Manifest.permission.NEARBY_WIFI_DEVICES,
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.POST_NOTIFICATIONS
            ),
            permissions
        )
    }

    @Test
    fun runtimePermissionsForAndroidTwelveLAndBelowUseFineLocationForWifiIdentity() {
        val permissions = requiredRuntimePermissions(Build.VERSION_CODES.S_V2)

        assertEquals(listOf(Manifest.permission.ACCESS_FINE_LOCATION), permissions)
    }

    @Test
    fun runtimePermissionsDoNotRequestBackgroundLocationInRegularDialog() {
        val permissions = requiredRuntimePermissions(Build.VERSION_CODES.UPSIDE_DOWN_CAKE)

        assertFalse(permissions.contains(Manifest.permission.ACCESS_BACKGROUND_LOCATION))
    }

    @Test
    fun notificationDenialIsLimitedDataNotBlocked() {
        val checks = preflightChecks(
            PermissionGrantState(
                apiLevel = Build.VERSION_CODES.TIRAMISU,
                nearbyWifiGranted = true,
                fineLocationGranted = true,
                backgroundLocationGranted = false,
                notificationsGranted = false,
                wifiConnected = true,
                receiverReachable = true
            )
        )

        val notificationCheck = checks.first { it.id == PreflightCheckId.Notifications }

        assertEquals(PreflightState.LimitedData, notificationCheck.state)
        assertFalse(notificationCheck.blocksSession)
        assertEquals("Limited notification status", notificationCheck.title)
    }

    @Test
    fun fineLocationDenialBlocksWifiIdentityOnAndroidThirteen() {
        val checks = preflightChecks(
            PermissionGrantState(
                apiLevel = Build.VERSION_CODES.TIRAMISU,
                nearbyWifiGranted = true,
                fineLocationGranted = false,
                backgroundLocationGranted = false,
                notificationsGranted = true,
                wifiConnected = true,
                receiverReachable = true
            )
        )

        val locationCheck = checks.first { it.id == PreflightCheckId.Location }

        assertEquals(PreflightState.Blocked, locationCheck.state)
        assertTrue(locationCheck.blocksSession)
    }

    @Test
    fun backgroundLocationIsNeededForServiceWifiIdentityOnAndroidTenAndNewer() {
        assertTrue(needsBackgroundLocationForServiceWifiIdentity(Build.VERSION_CODES.Q))
        assertTrue(needsBackgroundLocationForServiceWifiIdentity(Build.VERSION_CODES.S_V2))
        assertFalse(needsBackgroundLocationForServiceWifiIdentity(Build.VERSION_CODES.TIRAMISU))
        assertFalse(needsBackgroundLocationForServiceWifiIdentity(Build.VERSION_CODES.P))
    }
}
