package com.wifiops.probe.data

import kotlinx.serialization.json.Json
import com.wifiops.probe.telemetry.ProbeResult
import org.junit.Assert.assertEquals
import org.junit.Test

class TelemetryModelsTest {
    @Test
    fun sampleRecordSerializesWithSnakeCaseContract() {
        val record = TelemetryRecord(
            schemaVersion = 1,
            sessionId = "walk_1",
            deviceId = "android_1",
            recordId = "r1",
            sequenceNumber = 1,
            recordType = "sample",
            clientTimestamp = "2026-05-27T14:05:31-07:00",
            appVersion = "0.1.0",
            androidApiLevel = 35,
            payload = TelemetryPayload(
                ssid = "corp-wifi",
                rssi = -63,
                channel = "36",
                ipv4Address = "192.0.2.45",
                ipv6Addresses = listOf("2001:db8::45"),
                ipAddresses = listOf("192.0.2.45", "2001:db8::45"),
                manufacturer = "Google",
                model = "Pixel",
                probes = mapOf("gateway" to ProbeResult(ok = true, latencyMs = 8)),
                availability = mapOf("ssid" to "unavailable_or_redacted")
            )
        )

        val json = Json.encodeToString(TelemetryRecord.serializer(), record)

        assertEquals(true, json.contains("\"schema_version\":1"))
        assertEquals(true, json.contains("\"session_id\":\"walk_1\""))
        assertEquals(true, json.contains("\"rssi\":-63"))
        assertEquals(true, json.contains("\"channel\":\"36\""))
        assertEquals(true, json.contains("\"ipv4_address\":\"192.0.2.45\""))
        assertEquals(true, json.contains("\"ipv6_addresses\":[\"2001:db8::45\"]"))
        assertEquals(true, json.contains("\"ip_addresses\":[\"192.0.2.45\",\"2001:db8::45\"]"))
        assertEquals(true, json.contains("\"manufacturer\":\"Google\""))
        assertEquals(true, json.contains("\"model\":\"Pixel\""))
        assertEquals(true, json.contains("\"probes\":{\"gateway\":{\"ok\":true,\"latency_ms\":8"))
        assertEquals(true, json.contains("\"ssid\":\"unavailable_or_redacted\""))
    }

    @Test
    fun recordEntityDefaultsMatchPendingRecordContract() {
        val record = RecordEntity(
            recordId = "r1",
            sessionId = "walk_1",
            sequenceNumber = 1,
            recordType = "sample",
            payloadJson = "{}",
            syncStatus = "pending",
            createdAtMillis = 1_768_000_000_000
        )

        assertEquals(0, record.retryCount)
        assertEquals("", record.lastError)
    }
}
