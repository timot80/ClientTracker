package com.wifiops.probe.telemetry

import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import com.wifiops.probe.data.TelemetryPayload
import java.net.Inet4Address
import java.net.Inet6Address

fun channelFromFrequency(frequencyMhz: Int?): String? {
    return when (frequencyMhz) {
        null -> null
        in 2412..2472 -> (((frequencyMhz - 2412) / 5) + 1).toString()
        2484 -> "14"
        in 5000..5895 -> ((frequencyMhz - 5000) / 5).toString()
        5935 -> "2"
        in 5955..7115 -> ((frequencyMhz - 5950) / 5).toString()
        else -> null
    }
}

fun wifiNetwork(connectivityManager: ConnectivityManager): Network? {
    return selectWifiNetwork(connectivityManager.allNetworks) { network ->
        connectivityManager.getNetworkCapabilities(network)
            ?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
    }
}

internal fun <T> selectWifiNetwork(
    candidates: Array<T>,
    hasWifiTransport: (T) -> Boolean
): T? {
    return candidates.firstOrNull(hasWifiTransport)
}

class WifiTelemetryCollector(
    private val wifiManager: WifiManager,
    private val connectivityManager: ConnectivityManager
) {
    fun collect(): TelemetryPayload {
        val wifiInfo = wifiManager.connectionInfo
        val network = wifiNetwork(connectivityManager)
        val linkProperties = network?.let(connectivityManager::getLinkProperties)
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
            availability["gateway"] = if (network == null) "no_wifi_network" else "unavailable"
        }

        val dns = linkProperties
            ?.dnsServers
            ?.mapNotNull { it.hostAddress }
            .orEmpty()
        if (dns.isEmpty()) {
            availability["dns"] = if (network == null) "no_wifi_network" else "unavailable"
        }

        val ipv4Address = linkProperties
            ?.linkAddresses
            ?.firstOrNull { it.address is Inet4Address }
            ?.address
            ?.hostAddress
        val ipAddresses = linkProperties
            ?.linkAddresses
            ?.mapNotNull { it.address.hostAddress?.withoutIpv6Scope() }
            .orEmpty()
        val ipv6Addresses = linkProperties
            ?.linkAddresses
            ?.mapNotNull { linkAddress ->
                linkAddress.address
                    .takeIf { it is Inet6Address }
                    ?.hostAddress
                    ?.withoutIpv6Scope()
            }
            .orEmpty()
        if (ipAddresses.isEmpty()) {
            availability["ipAddresses"] = if (network == null) "no_wifi_network" else "unavailable"
        }

        return TelemetryPayload(
            ssid = ssid,
            bssid = bssid,
            rssi = rssi,
            frequencyMhz = frequencyMhz,
            channel = channel,
            txLinkMbps = txLinkMbps,
            rxLinkMbps = rxLinkMbps,
            ipv4Address = ipv4Address,
            ipv6Addresses = ipv6Addresses,
            ipAddresses = ipAddresses,
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

private fun String.withoutIpv6Scope(): String {
    return substringBefore("%")
}

private const val INVALID_RSSI = -127
