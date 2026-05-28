package com.wifiops.probe.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject

fun buildRawRecordExportJson(
    session: SessionEntity,
    records: List<RecordEntity>,
    exportedAtMillis: Long
): String {
    val rawRecords = records.map { record ->
        Json.parseToJsonElement(record.payloadJson).jsonObject
    }
    return Json.encodeToString(
        JsonObject.serializer(),
        JsonObject(
            mapOf(
                "export" to JsonObject(
                    mapOf(
                        "format" to JsonPrimitive("wifiops_probe_raw_records"),
                        "schema_version" to JsonPrimitive(1),
                        "exported_at_millis" to JsonPrimitive(exportedAtMillis)
                    )
                ),
                "session" to JsonObject(
                    mapOf(
                        "session_id" to JsonPrimitive(session.sessionId),
                        "receiver_url" to JsonPrimitive(session.receiverUrl),
                        "device_id" to JsonPrimitive(session.deviceId),
                        "created_at_millis" to JsonPrimitive(session.createdAtMillis)
                    )
                ),
                "record_count" to JsonPrimitive(rawRecords.size),
                "records" to JsonArray(rawRecords)
            )
        )
    )
}
