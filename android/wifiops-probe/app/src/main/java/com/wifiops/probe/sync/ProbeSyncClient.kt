package com.wifiops.probe.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException

@Serializable
data class RejectedRecord(
    @SerialName("record_id")
    val recordId: String,
    val error: String
)

@Serializable
data class ProbeAcknowledgement(
    val accepted: List<String> = emptyList(),
    val duplicate: List<String> = emptyList(),
    val rejected: List<RejectedRecord> = emptyList()
)

interface ProbeSyncTransport {
    fun upload(
        receiverUrl: String,
        sessionId: String,
        token: String,
        recordsJson: String
    ): ProbeAcknowledgement
}

class ProbeSyncHttpException(
    val statusCode: Int,
    val responseBody: String
) : IOException("Upload failed with HTTP $statusCode: $responseBody") {
    val receiverErrorCode: String? = parseReceiverErrorCode(responseBody)
    val isRetryable: Boolean = statusCode != 400 || receiverErrorCode !in NonRetryableValidationErrors

    private companion object {
        val NonRetryableValidationErrors = setOf(
            "invalid_body",
            "missing_records",
            "too_many_records",
            "invalid_record",
            "missing_field",
            "unsupported_schema",
            "invalid_record_type",
            "invalid_string",
            "invalid_sequence",
            "invalid_android_api_level",
            "invalid_payload",
            "invalid_timestamp",
            "invalid_json",
            "invalid_content_length"
        )

        fun parseReceiverErrorCode(raw: String): String? {
            return runCatching {
                Json.parseToJsonElement(raw).let { element ->
                    (element as? JsonObject)?.get("error")?.jsonPrimitive?.contentOrNull
                }
            }.getOrNull()
        }
    }
}

class ProbeSyncClient(private val http: OkHttpClient = OkHttpClient()) : ProbeSyncTransport {
    fun health(receiverUrl: String): Boolean {
        val request = Request.Builder()
            .url("${receiverUrl.trimEnd('/')}/health")
            .get()
            .build()

        http.newCall(request).execute().use { response ->
            return response.isSuccessful
        }
    }

    override fun upload(
        receiverUrl: String,
        sessionId: String,
        token: String,
        recordsJson: String
    ): ProbeAcknowledgement {
        val request = Request.Builder()
            .url("${receiverUrl.trimEnd('/')}/api/v1/sessions/$sessionId/records")
            .post(recordsJson.toRequestBody(JsonMediaType))
            .header("Content-Type", "application/json")
            .header("Authorization", "Bearer $token")
            .build()

        http.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw ProbeSyncHttpException(response.code, body)
            }
            return parseAcknowledgement(body)
        }
    }

    companion object {
        private val JsonMediaType = "application/json".toMediaType()
        private val AckJson = Json { ignoreUnknownKeys = true }

        fun parseAcknowledgement(raw: String): ProbeAcknowledgement {
            return AckJson.decodeFromString(ProbeAcknowledgement.serializer(), raw)
        }
    }
}
