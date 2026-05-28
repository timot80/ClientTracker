package com.wifiops.probe.sync

import com.wifiops.probe.data.RecordEntity
import org.junit.Assert.assertEquals
import org.junit.Test

class ProbeSyncClientTest {
    @Test
    fun acknowledgementParsesAcceptedDuplicateAndRejectedRecords() {
        val ack = ProbeSyncClient.parseAcknowledgement(
            """
            {
              "accepted": ["r1"],
              "duplicate": ["r2"],
              "rejected": [{"record_id": "r3", "error": "missing_payload"}]
            }
            """.trimIndent()
        )

        assertEquals(listOf("r1"), ack.accepted)
        assertEquals(listOf("r2"), ack.duplicate)
        assertEquals("missing_payload", ack.rejected.first().error)
    }

    @Test
    fun batchJsonEmbedsPayloadObjectsInsteadOfQuotedStrings() {
        val records = listOf(
            RecordEntity(
                recordId = "r1",
                sessionId = "walk_1",
                sequenceNumber = 1,
                recordType = "sample",
                payloadJson = """{"record_id":"r1","payload":{"rssi":-60}}""",
                syncStatus = "pending",
                createdAtMillis = 1_768_000_000_000
            ),
            RecordEntity(
                recordId = "r2",
                sessionId = "walk_1",
                sequenceNumber = 2,
                recordType = "sample",
                payloadJson = """{"record_id":"r2","payload":{"rssi":-61}}""",
                syncStatus = "pending",
                createdAtMillis = 1_768_000_000_001
            )
        )

        val json = ProbeSyncWorker.buildRecordsJson(records)

        assertEquals(
            """{"records":[{"record_id":"r1","payload":{"rssi":-60}},{"record_id":"r2","payload":{"rssi":-61}}]}""",
            json
        )
    }
}
