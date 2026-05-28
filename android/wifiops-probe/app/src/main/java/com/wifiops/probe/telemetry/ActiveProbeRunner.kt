package com.wifiops.probe.telemetry

import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URL
import kotlin.system.measureTimeMillis

data class ProbeResult(
    val ok: Boolean,
    val latencyMs: Long? = null,
    val detail: String = ""
)

class ActiveProbeRunner {
    suspend fun tcpConnect(
        host: String,
        port: Int,
        timeoutMs: Int = 1000
    ): ProbeResult {
        return try {
            val latencyMs = measureTimeMillis {
                Socket().use { socket ->
                    socket.connect(InetSocketAddress(host, port), timeoutMs)
                }
            }
            ProbeResult(ok = true, latencyMs = latencyMs)
        } catch (error: Exception) {
            ProbeResult(ok = false, detail = error.message.orEmpty())
        }
    }

    suspend fun dnsLookup(hostname: String): ProbeResult {
        var addresses = emptyArray<InetAddress>()
        return try {
            val latencyMs = measureTimeMillis {
                addresses = InetAddress.getAllByName(hostname)
            }
            ProbeResult(
                ok = addresses.isNotEmpty(),
                latencyMs = latencyMs,
                detail = addresses.joinToString(",") { it.hostAddress.orEmpty() }
            )
        } catch (error: Exception) {
            ProbeResult(ok = false, detail = error.message.orEmpty())
        }
    }

    suspend fun httpGet(
        url: String,
        timeoutMs: Int = 2000
    ): ProbeResult {
        var responseCode = -1
        return try {
            val latencyMs = measureTimeMillis {
                val connection = URL(url).openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.connectTimeout = timeoutMs
                connection.readTimeout = timeoutMs
                connection.useCaches = false
                responseCode = connection.responseCode
                connection.disconnect()
            }
            ProbeResult(
                ok = responseCode in 200..399,
                latencyMs = latencyMs,
                detail = responseCode.toString()
            )
        } catch (error: Exception) {
            ProbeResult(ok = false, detail = error.message.orEmpty())
        }
    }
}
