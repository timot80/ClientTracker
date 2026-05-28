package com.wifiops.probe.data

import kotlinx.serialization.json.Json
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
            payload = TelemetryPayload(ssid = "corp-wifi", rssi = -63)
        )

        val json = Json.encodeToString(TelemetryRecord.serializer(), record)

        assertEquals(true, json.contains("\"schema_version\":1"))
        assertEquals(true, json.contains("\"session_id\":\"walk_1\""))
        assertEquals(true, json.contains("\"rssi\":-63"))
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
