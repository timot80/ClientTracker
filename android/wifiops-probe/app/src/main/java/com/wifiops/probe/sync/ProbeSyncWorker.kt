package com.wifiops.probe.sync

import com.wifiops.probe.data.ProbeRecordDao
import com.wifiops.probe.data.RecordEntity
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import java.io.IOException

class ProbeSyncWorker(
    private val dao: ProbeRecordDao,
    private val client: ProbeSyncTransport
) {
    suspend fun syncOnce(sessionId: String, receiverUrl: String, token: String): Int {
        val pending = dao.pendingRecords(sessionId, PendingLimit)
        if (pending.isEmpty()) {
            return 0
        }

        return try {
            val pendingIds = pending.mapTo(mutableSetOf()) { it.recordId }
            val acknowledgement = client.upload(
                receiverUrl = receiverUrl,
                sessionId = sessionId,
                token = token,
                recordsJson = buildRecordsJson(pending)
            )

            val syncedRecordIds = (acknowledgement.accepted + acknowledgement.duplicate)
                .filter { it in pendingIds }
            syncedRecordIds.forEach { recordId ->
                dao.updatePendingRecordStatus(sessionId, recordId, "synced")
            }
            acknowledgement.rejected.forEach { rejected ->
                if (rejected.recordId in pendingIds) {
                    dao.updatePendingRecordStatus(sessionId, rejected.recordId, "failed", rejected.error)
                }
            }
            syncedRecordIds.size
        } catch (exception: ProbeSyncHttpException) {
            val error = exception.message ?: "HTTP ${exception.statusCode}"
            if (exception.isRetryable) {
                markPendingRetries(sessionId, pending, error)
            } else {
                pending.forEach { record ->
                    dao.updatePendingRecordStatus(sessionId, record.recordId, "failed", error)
                }
            }
            0
        } catch (exception: IOException) {
            markPendingRetries(sessionId, pending, exception.message ?: exception::class.java.simpleName)
            0
        } catch (exception: Exception) {
            markPendingRetries(sessionId, pending, exception.message ?: exception::class.java.simpleName)
            0
        }
    }

    private suspend fun markPendingRetries(sessionId: String, pending: List<RecordEntity>, error: String) {
        pending.forEach { record ->
            dao.markPendingRetry(sessionId, record.recordId, error)
        }
    }

    companion object {
        private const val PendingLimit = 100

        fun buildRecordsJson(records: List<RecordEntity>): String {
            val payloads = records.map { record ->
                Json.parseToJsonElement(record.payloadJson).jsonObject
            }
            return Json.encodeToString(
                JsonObject.serializer(),
                JsonObject(mapOf("records" to JsonArray(payloads)))
            )
        }
    }
}
