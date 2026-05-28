package com.wifiops.probe.sync

import com.wifiops.probe.data.ProbeRecordDao
import com.wifiops.probe.data.RecordEntity
import com.wifiops.probe.data.SessionEntity
import java.io.IOException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProbeSyncWorkerTest {
    @Test
    fun acceptedAndDuplicatePendingRecordsBecomeSynced() = runTest {
        val dao = FakeProbeRecordDao(
            mutableListOf(
                record("r1"),
                record("r2"),
                record("other_session", sessionId = "walk_2")
            )
        )
        val worker = ProbeSyncWorker(
            dao,
            FakeProbeSyncTransport(
                acknowledgement = ProbeAcknowledgement(
                    accepted = listOf("r1", "other_session"),
                    duplicate = listOf("r2", "missing")
                )
            )
        )

        val syncedCount = worker.syncOnce("walk_1", "http://receiver", "token")

        assertEquals(2, syncedCount)
        assertEquals("synced", dao.record("r1").syncStatus)
        assertEquals("synced", dao.record("r2").syncStatus)
        assertEquals("pending", dao.record("other_session").syncStatus)
    }

    @Test
    fun rejectedPendingRecordsBecomeFailedAndUnknownIdsAreIgnored() = runTest {
        val dao = FakeProbeRecordDao(mutableListOf(record("r1")))
        val worker = ProbeSyncWorker(
            dao,
            FakeProbeSyncTransport(
                acknowledgement = ProbeAcknowledgement(
                    rejected = listOf(
                        RejectedRecord("r1", "invalid_payload"),
                        RejectedRecord("missing", "wrong_batch")
                    )
                )
            )
        )

        worker.syncOnce("walk_1", "http://receiver", "token")

        assertEquals("failed", dao.record("r1").syncStatus)
        assertEquals("invalid_payload", dao.record("r1").lastError)
        assertTrue(dao.ignoredUpdates.isEmpty())
    }

    @Test
    fun transientUploadFailureMarksPendingRecordsForRetry() = runTest {
        val dao = FakeProbeRecordDao(mutableListOf(record("r1"), record("r2")))
        val worker = ProbeSyncWorker(
            dao,
            FakeProbeSyncTransport(exception = IOException("timeout"))
        )

        worker.syncOnce("walk_1", "http://receiver", "token")

        assertEquals("pending", dao.record("r1").syncStatus)
        assertEquals(1, dao.record("r1").retryCount)
        assertEquals("timeout", dao.record("r1").lastError)
        assertEquals(1, dao.record("r2").retryCount)
    }

    @Test
    fun permanentReceiverErrorFailsPendingRecords() = runTest {
        val dao = FakeProbeRecordDao(mutableListOf(record("r1")))
        val worker = ProbeSyncWorker(
            dao,
            FakeProbeSyncTransport(exception = ProbeSyncHttpException(400, """{"error":"invalid_json"}"""))
        )

        worker.syncOnce("walk_1", "http://receiver", "token")

        assertEquals("failed", dao.record("r1").syncStatus)
        assertTrue(dao.record("r1").lastError.contains("HTTP 400"))
    }

    @Test
    fun authErrorsRemainPendingForRepairAndRetry() = runTest {
        val dao = FakeProbeRecordDao(mutableListOf(record("r1")))
        val worker = ProbeSyncWorker(
            dao,
            FakeProbeSyncTransport(exception = ProbeSyncHttpException(401, """{"error":"unauthorized"}"""))
        )

        worker.syncOnce("walk_1", "http://receiver", "bad_token")

        assertEquals("pending", dao.record("r1").syncStatus)
        assertEquals(1, dao.record("r1").retryCount)
        assertTrue(dao.record("r1").lastError.contains("HTTP 401"))
    }

    @Test
    fun serverErrorsRemainRetryable() = runTest {
        val dao = FakeProbeRecordDao(mutableListOf(record("r1")))
        val worker = ProbeSyncWorker(
            dao,
            FakeProbeSyncTransport(exception = ProbeSyncHttpException(503, "busy"))
        )

        worker.syncOnce("walk_1", "http://receiver", "token")

        assertEquals("pending", dao.record("r1").syncStatus)
        assertEquals(1, dao.record("r1").retryCount)
        assertTrue(dao.record("r1").lastError.contains("HTTP 503"))
    }

    private fun record(recordId: String, sessionId: String = "walk_1") = RecordEntity(
        recordId = recordId,
        sessionId = sessionId,
        sequenceNumber = 1,
        recordType = "sample",
        payloadJson = """{"record_id":"$recordId","payload":{"rssi":-60}}""",
        syncStatus = "pending",
        createdAtMillis = 1_768_000_000_000
    )
}

private class FakeProbeSyncTransport(
    private val acknowledgement: ProbeAcknowledgement = ProbeAcknowledgement(),
    private val exception: Exception? = null
) : ProbeSyncTransport {
    override fun upload(
        receiverUrl: String,
        sessionId: String,
        token: String,
        recordsJson: String
    ): ProbeAcknowledgement {
        exception?.let { throw it }
        return acknowledgement
    }
}

private class FakeProbeRecordDao(
    private val records: MutableList<RecordEntity>
) : ProbeRecordDao {
    val ignoredUpdates = mutableListOf<String>()

    override suspend fun insertSession(session: SessionEntity) = Unit

    override suspend fun insertRecord(record: RecordEntity) {
        records.add(record)
    }

    override suspend fun pendingRecords(sessionId: String, limit: Int): List<RecordEntity> {
        return records
            .filter { it.sessionId == sessionId && it.syncStatus == "pending" }
            .sortedBy { it.sequenceNumber }
            .take(limit)
    }

    override suspend fun updatePendingRecordStatus(
        sessionId: String,
        recordId: String,
        status: String,
        lastError: String
    ) {
        val index = records.indexOfFirst {
            it.sessionId == sessionId && it.recordId == recordId && it.syncStatus == "pending"
        }
        if (index < 0) {
            ignoredUpdates.add(recordId)
            return
        }
        records[index] = records[index].copy(syncStatus = status, lastError = lastError)
    }

    override suspend fun markPendingRetry(sessionId: String, recordId: String, lastError: String) {
        val index = records.indexOfFirst {
            it.sessionId == sessionId && it.recordId == recordId && it.syncStatus == "pending"
        }
        if (index < 0) {
            ignoredUpdates.add(recordId)
            return
        }
        records[index] = records[index].copy(
            retryCount = records[index].retryCount + 1,
            lastError = lastError
        )
    }

    override suspend fun countByStatus(sessionId: String, status: String): Int {
        return records.count { it.sessionId == sessionId && it.syncStatus == status }
    }

    override suspend fun maxSequenceForSession(sessionId: String): Long {
        return records.filter { it.sessionId == sessionId }.maxOfOrNull { it.sequenceNumber } ?: 0L
    }

    override suspend fun sessions(): List<SessionEntity> = emptyList()

    override suspend fun deleteRecordsForSession(sessionId: String) = Unit

    override suspend fun deleteSession(sessionId: String) = Unit

    fun record(recordId: String): RecordEntity {
        return records.first { it.recordId == recordId }
    }
}
