package com.wifiops.probe.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
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
    val isRetryable: Boolean = statusCode !in 400..499
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
