package com.wifiops.probe.sync

import com.wifiops.probe.data.ProbeRecordDao
import com.wifiops.probe.data.RecordEntity
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject

class ProbeSyncWorker(
    private val dao: ProbeRecordDao,
    private val client: ProbeSyncClient
) {
    suspend fun syncOnce(sessionId: String, receiverUrl: String, token: String): Int {
        val pending = dao.pendingRecords(sessionId, PendingLimit)
        if (pending.isEmpty()) {
            return 0
        }

        return try {
            val acknowledgement = client.upload(
                receiverUrl = receiverUrl,
                sessionId = sessionId,
                token = token,
                recordsJson = buildRecordsJson(pending)
            )

            val syncedRecordIds = acknowledgement.accepted + acknowledgement.duplicate
            syncedRecordIds.forEach { recordId ->
                dao.updateRecordStatus(recordId, "synced")
            }
            acknowledgement.rejected.forEach { rejected ->
                dao.updateRecordStatus(rejected.recordId, "failed", rejected.error)
            }
            syncedRecordIds.size
        } catch (exception: Exception) {
            val error = exception.message ?: exception::class.java.simpleName
            pending.forEach { record ->
                dao.markRetry(record.recordId, error)
            }
            0
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
