package com.wifiops.probe.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import com.wifiops.probe.telemetry.ProbeResult

@Serializable
data class TelemetryRecord(
    @SerialName("schema_version")
    val schemaVersion: Int,
    @SerialName("session_id")
    val sessionId: String,
    @SerialName("device_id")
    val deviceId: String,
    @SerialName("record_id")
    val recordId: String,
    @SerialName("sequence_number")
    val sequenceNumber: Long,
    @SerialName("record_type")
    val recordType: String,
    @SerialName("client_timestamp")
    val clientTimestamp: String,
    @SerialName("app_version")
    val appVersion: String,
    @SerialName("android_api_level")
    val androidApiLevel: Int,
    val payload: TelemetryPayload
)

@Serializable
data class TelemetryPayload(
    val ssid: String? = null,
    val bssid: String? = null,
    val rssi: Int? = null,
    @SerialName("frequency_mhz")
    val frequencyMhz: Int? = null,
    val channel: String? = null,
    @SerialName("tx_link_mbps")
    val txLinkMbps: Int? = null,
    @SerialName("rx_link_mbps")
    val rxLinkMbps: Int? = null,
    @SerialName("ipv4_address")
    val ipv4Address: String? = null,
    @SerialName("ipv6_addresses")
    val ipv6Addresses: List<String> = emptyList(),
    @SerialName("ip_addresses")
    val ipAddresses: List<String> = emptyList(),
    val gateway: String? = null,
    val dns: List<String> = emptyList(),
    val manufacturer: String? = null,
    val model: String? = null,
    val probes: Map<String, ProbeResult> = emptyMap(),
    val availability: Map<String, String> = emptyMap()
)
