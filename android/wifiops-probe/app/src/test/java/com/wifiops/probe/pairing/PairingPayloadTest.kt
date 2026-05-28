package com.wifiops.probe.pairing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class PairingPayloadTest {
    @Test
    fun parsesPairingPayloadJson() {
        val payload = PairingPayload.parse(
            """{"receiver_url":"http://192.0.2.10:8765","session_id":"walk_1","token":"secret"}"""
        )

        assertEquals("http://192.0.2.10:8765", payload.receiverUrl)
        assertEquals("walk_1", payload.sessionId)
        assertEquals("secret", payload.token)
    }

    @Test
    fun trimsManualFields() {
        val payload = PairingPayload.fromManualFields(
            receiverUrl = "  http://192.0.2.10:8765/  ",
            sessionId = " walk_1 ",
            token = " secret "
        )

        assertEquals("http://192.0.2.10:8765", payload.receiverUrl)
        assertEquals("walk_1", payload.sessionId)
        assertEquals("secret", payload.token)
    }

    @Test
    fun rejectsMissingRequiredJsonFields() {
        assertThrows(IllegalArgumentException::class.java) {
            PairingPayload.parse("""{"receiver_url":"http://192.0.2.10:8765","session_id":"walk_1"}""")
        }
    }

    @Test
    fun rejectsBlankRequiredFields() {
        assertThrows(IllegalArgumentException::class.java) {
            PairingPayload.fromManualFields(
                receiverUrl = "http://192.0.2.10:8765",
                sessionId = "",
                token = "secret"
            )
        }
    }

    @Test
    fun rejectsNonHttpReceiverUrls() {
        assertThrows(IllegalArgumentException::class.java) {
            PairingPayload.fromManualFields(
                receiverUrl = "ftp://192.0.2.10:8765",
                sessionId = "walk_1",
                token = "secret"
            )
        }
    }
}
