package com.wifiops.probe.telemetry

import android.net.ConnectivityManager
import android.net.wifi.WifiManager
import com.wifiops.probe.data.TelemetryPayload
import java.net.Inet4Address

fun channelFromFrequency(frequencyMhz: Int?): String? {
    return when (frequencyMhz) {
        null -> null
        in 2412..2472 -> (((frequencyMhz - 2412) / 5) + 1).toString()
        2484 -> "14"
        in 5000..5895 -> ((frequencyMhz - 5000) / 5).toString()
        in 5925..7125 -> ((frequencyMhz - 5950) / 5).toString()
        else -> null
    }
}

class WifiTelemetryCollector(
    private val wifiManager: WifiManager,
    private val connectivityManager: ConnectivityManager
) {
    fun collect(): TelemetryPayload {
        val wifiInfo = wifiManager.connectionInfo
        val activeNetwork = connectivityManager.activeNetwork
        val linkProperties = activeNetwork?.let(connectivityManager::getLinkProperties)
        val availability = linkedMapOf<String, String>()

        val ssid = wifiInfo?.ssid.redactedSsid()
        if (ssid == null) {
            availability["ssid"] = "unavailable_or_redacted"
        }

        val bssid = wifiInfo?.bssid.redactedBssid()
        if (bssid == null) {
            availability["bssid"] = "unavailable_or_redacted"
        }

        val rssi = wifiInfo?.rssi?.takeUnless { it == INVALID_RSSI }
        if (rssi == null) {
            availability["rssi"] = "unavailable"
        }

        val frequencyMhz = wifiInfo?.frequency?.takeIf { it > 0 }
        if (frequencyMhz == null) {
            availability["frequencyMhz"] = "unavailable"
        }

        val channel = channelFromFrequency(frequencyMhz)
        if (channel == null) {
            availability["channel"] = if (frequencyMhz == null) {
                "unavailable"
            } else {
                "unknown_frequency"
            }
        }

        val txLinkMbps = wifiInfo?.txLinkSpeedMbps?.takeIf { it >= 0 }
        if (txLinkMbps == null) {
            availability["txLinkMbps"] = "unavailable"
        }

        val rxLinkMbps = wifiInfo?.rxLinkSpeedMbps?.takeIf { it >= 0 }
        if (rxLinkMbps == null) {
            availability["rxLinkMbps"] = "unavailable"
        }

        val gateway = linkProperties
            ?.routes
            ?.firstOrNull { it.isDefaultRoute }
            ?.gateway
            ?.hostAddress
        if (gateway == null) {
            availability["gateway"] = "unavailable"
        }

        val dns = linkProperties
            ?.dnsServers
            ?.mapNotNull { it.hostAddress }
            .orEmpty()
        if (dns.isEmpty()) {
            availability["dns"] = "unavailable"
        }

        val ipv4Address = linkProperties
            ?.linkAddresses
            ?.firstOrNull { it.address is Inet4Address }
            ?.address
            ?.hostAddress

        return TelemetryPayload(
            ssid = ssid,
            bssid = bssid,
            rssi = rssi,
            frequencyMhz = frequencyMhz,
            channel = channel,
            txLinkMbps = txLinkMbps,
            rxLinkMbps = rxLinkMbps,
            ipv4Address = ipv4Address,
            gateway = gateway,
            dns = dns,
            availability = availability
        )
    }
}

private fun String?.redactedSsid(): String? {
    val value = this?.trim()?.trim('"')
    return value?.takeUnless { it.isEmpty() || it == WifiManager.UNKNOWN_SSID }
}

private fun String?.redactedBssid(): String? {
    return this?.takeUnless { it == "02:00:00:00:00:00" }
}

private const val INVALID_RSSI = -127
