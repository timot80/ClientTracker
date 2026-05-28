package com.wifiops.probe

import android.Manifest
import android.os.Build
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PermissionPolicyTest {
    @Test
    fun runtimePermissionsForAndroidThirteenIncludeNearbyNotificationsAndFineLocation() {
        val permissions = requiredRuntimePermissions(Build.VERSION_CODES.TIRAMISU)

        assertEquals(
            listOf(
                Manifest.permission.NEARBY_WIFI_DEVICES,
                Manifest.permission.POST_NOTIFICATIONS,
                Manifest.permission.ACCESS_FINE_LOCATION
            ),
            permissions
        )
    }

    @Test
    fun runtimePermissionsDoNotRequestBackgroundLocationInRegularDialog() {
        val permissions = requiredRuntimePermissions(Build.VERSION_CODES.UPSIDE_DOWN_CAKE)

        assertFalse(permissions.contains(Manifest.permission.ACCESS_BACKGROUND_LOCATION))
    }

    @Test
    fun backgroundLocationIsNeededForServiceWifiIdentityOnAndroidTenAndNewer() {
        assertTrue(needsBackgroundLocationForServiceWifiIdentity(Build.VERSION_CODES.Q))
        assertTrue(needsBackgroundLocationForServiceWifiIdentity(Build.VERSION_CODES.UPSIDE_DOWN_CAKE))
        assertFalse(needsBackgroundLocationForServiceWifiIdentity(Build.VERSION_CODES.P))
    }
}
