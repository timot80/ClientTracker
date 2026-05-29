package com.wifiops.probe.pairing

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import java.net.URI

@Serializable
data class PairingPayload(
    @SerialName("receiver_url")
    val receiverUrl: String,
    @SerialName("session_id")
    val sessionId: String,
    val token: String
) {
    companion object {
        private val json = Json { ignoreUnknownKeys = true }

        fun parse(raw: String): PairingPayload {
            val decoded = try {
                json.decodeFromString(serializer(), raw)
            } catch (exception: SerializationException) {
                throw IllegalArgumentException("Pairing payload must include receiver_url, session_id, and token", exception)
            } catch (exception: IllegalArgumentException) {
                throw IllegalArgumentException("Pairing payload is not valid JSON", exception)
            }
            return decoded.normalized()
        }

        fun fromManualFields(receiverUrl: String, sessionId: String, token: String): PairingPayload =
            PairingPayload(receiverUrl = receiverUrl, sessionId = sessionId, token = token).normalized()
    }

    private fun normalized(): PairingPayload {
        val normalizedReceiverUrl = receiverUrl.trim().trimEnd('/')
        val normalizedSessionId = sessionId.trim()
        val normalizedToken = token.trim()

        require(normalizedReceiverUrl.isNotEmpty()) { "Receiver URL is required" }
        require(normalizedSessionId.isNotEmpty()) { "Session ID is required" }
        require(normalizedToken.isNotEmpty()) { "Token is required" }
        require(normalizedReceiverUrl.isHttpUrl()) { "Receiver URL must start with http:// or https://" }

        return copy(
            receiverUrl = normalizedReceiverUrl,
            sessionId = normalizedSessionId,
            token = normalizedToken
        )
    }
}

private fun String.isHttpUrl(): Boolean {
    val uri = runCatching { URI(this) }.getOrNull() ?: return false
    return uri.scheme in setOf("http", "https") && !uri.host.isNullOrBlank()
}
