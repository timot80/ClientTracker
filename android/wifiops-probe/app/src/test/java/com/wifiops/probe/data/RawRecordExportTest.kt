package com.wifiops.probe.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class RawRecordExportTest {
    @Test
    fun rawRecordExportIncludesSessionMetadataAndDecodedRecords() {
        val session = SessionEntity(
            sessionId = "walk_1",
            receiverUrl = "http://receiver.local:8080",
            token = "secret",
            deviceId = "android_1",
            createdAtMillis = 1_768_000_000_000
        )
        val records = listOf(
            record(
                recordId = "r1",
                sequenceNumber = 1,
                payloadJson = """{"record_id":"r1","payload":{"ssid":"corp-wifi","rssi":-60}}"""
            ),
            record(
                recordId = "r2",
                sequenceNumber = 2,
                payloadJson = """{"record_id":"r2","payload":{"ipv4_address":"192.0.2.4"}}"""
            )
        )

        val exportJson = buildRawRecordExportJson(
            session = session,
            records = records,
            exportedAtMillis = 1_768_000_001_000
        )

        val export = Json.parseToJsonElement(exportJson).jsonObject
        assertEquals("wifiops_probe_raw_records", export["export"]!!.jsonObject["format"]!!.jsonPrimitive.content)
        assertEquals("1", export["export"]!!.jsonObject["schema_version"]!!.jsonPrimitive.content)
        assertEquals("1768000001000", export["export"]!!.jsonObject["exported_at_millis"]!!.jsonPrimitive.content)
        assertEquals("walk_1", export["session"]!!.jsonObject["session_id"]!!.jsonPrimitive.content)
        assertEquals("http://receiver.local:8080", export["session"]!!.jsonObject["receiver_url"]!!.jsonPrimitive.content)
        assertEquals("2", export["record_count"]!!.jsonPrimitive.content)
        assertEquals("r1", export["records"]!!.jsonArray[0].jsonObject["record_id"]!!.jsonPrimitive.content)
        assertEquals("corp-wifi", export["records"]!!.jsonArray[0].jsonObject["payload"]!!.jsonObject["ssid"]!!.jsonPrimitive.content)
        assertEquals("192.0.2.4", export["records"]!!.jsonArray[1].jsonObject["payload"]!!.jsonObject["ipv4_address"]!!.jsonPrimitive.content)
        assertFalse(exportJson.contains("secret"))
    }

    private fun record(recordId: String, sequenceNumber: Long, payloadJson: String): RecordEntity {
        return RecordEntity(
            recordId = recordId,
            sessionId = "walk_1",
            sequenceNumber = sequenceNumber,
            recordType = "sample",
            payloadJson = payloadJson,
            syncStatus = "pending",
            createdAtMillis = 1_768_000_000_000 + sequenceNumber
        )
    }
}
