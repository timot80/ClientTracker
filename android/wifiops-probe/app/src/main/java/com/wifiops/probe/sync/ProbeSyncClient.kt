package com.wifiops.probe.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

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

class ProbeSyncClient(private val http: OkHttpClient = OkHttpClient()) {
    fun health(receiverUrl: String): Boolean {
        val request = Request.Builder()
            .url("${receiverUrl.trimEnd('/')}/health")
            .get()
            .build()

        http.newCall(request).execute().use { response ->
            return response.isSuccessful
        }
    }

    fun upload(
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
            check(response.isSuccessful) { "Upload failed with HTTP ${response.code}: $body" }
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
