package com.wifiops.probe.telemetry

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.URI
import java.net.Socket
import kotlin.system.measureTimeMillis

data class ProbeResult(
    val ok: Boolean,
    val latencyMs: Long? = null,
    val detail: String = ""
)

class ActiveProbeRunner(
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO
) {
    suspend fun tcpConnect(
        host: String,
        port: Int,
        timeoutMs: Int = 1000
    ): ProbeResult {
        return try {
            val latencyMs = withContext(ioDispatcher) {
                measureTimeMillis {
                    Socket().use { socket ->
                        socket.connect(InetSocketAddress(host, port), timeoutMs)
                    }
                }
            }
            ProbeResult(ok = true, latencyMs = latencyMs)
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            ProbeResult(ok = false, detail = error.message.orEmpty())
        }
    }

    suspend fun dnsLookup(hostname: String): ProbeResult {
        var addresses = emptyArray<InetAddress>()
        return try {
            val latencyMs = withContext(ioDispatcher) {
                measureTimeMillis {
                    addresses = InetAddress.getAllByName(hostname)
                }
            }
            ProbeResult(
                ok = addresses.isNotEmpty(),
                latencyMs = latencyMs,
                detail = addresses.joinToString(",") { it.hostAddress.orEmpty() }
            )
        } catch (error: CancellationException) {
            throw error
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
            val latencyMs = withContext(ioDispatcher) {
                measureTimeMillis {
                    var connection: HttpURLConnection? = null
                    try {
                        connection = URI(url).toURL().openConnection() as HttpURLConnection
                        connection.requestMethod = "GET"
                        connection.connectTimeout = timeoutMs
                        connection.readTimeout = timeoutMs
                        connection.useCaches = false
                        responseCode = connection.responseCode
                    } finally {
                        connection?.disconnect()
                    }
                }
            }
            ProbeResult(
                ok = responseCode in 200..399,
                latencyMs = latencyMs,
                detail = responseCode.toString()
            )
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            ProbeResult(ok = false, detail = error.message.orEmpty())
        }
    }
}
