package com.wifiops.probe.telemetry

import android.net.Network
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.URI
import kotlin.system.measureTimeMillis

@Serializable
data class ProbeResult(
    val ok: Boolean,
    @SerialName("latency_ms")
    val latencyMs: Long? = null,
    val detail: String = ""
)

class ActiveProbeRunner(
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO
) {
    suspend fun tcpConnect(
        host: String,
        port: Int,
        timeoutMs: Int = 1000,
        network: Network? = null
    ): ProbeResult {
        if (network == null) {
            return ProbeResult(ok = false, detail = NO_WIFI_NETWORK)
        }

        return try {
            var failureDetail: String? = null
            val latencyMs = withContext(ioDispatcher) {
                measureTimeMillis {
                    val addresses = network.getAllByName(host)
                    failureDetail = connectFirstResolvedAddress(addresses, port) { socketAddress ->
                        network.socketFactory.createSocket().use { socket ->
                            socket.connect(socketAddress, timeoutMs)
                        }
                    }
                }
            }
            if (failureDetail == null) {
                ProbeResult(ok = true, latencyMs = latencyMs)
            } else {
                ProbeResult(ok = false, latencyMs = latencyMs, detail = failureDetail.orEmpty())
            }
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            ProbeResult(ok = false, detail = error.message.orEmpty())
        }
    }

    suspend fun dnsLookup(
        hostname: String,
        network: Network? = null
    ): ProbeResult {
        if (network == null) {
            return ProbeResult(ok = false, detail = NO_WIFI_NETWORK)
        }

        var addresses = emptyArray<InetAddress>()
        return try {
            val latencyMs = withContext(ioDispatcher) {
                measureTimeMillis {
                    addresses = network.getAllByName(hostname)
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
        timeoutMs: Int = 2000,
        network: Network? = null
    ): ProbeResult {
        if (network == null) {
            return ProbeResult(ok = false, detail = NO_WIFI_NETWORK)
        }

        var responseCode = -1
        return try {
            val latencyMs = withContext(ioDispatcher) {
                measureTimeMillis {
                    var connection: HttpURLConnection? = null
                    try {
                        connection = network.openConnection(URI(url).toURL()) as HttpURLConnection
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

    private companion object {
        const val NO_WIFI_NETWORK = "no_wifi_network"
    }
}

internal fun connectFirstResolvedAddress(
    addresses: Array<InetAddress>,
    port: Int,
    connect: (InetSocketAddress) -> Unit
): String? {
    if (addresses.isEmpty()) {
        return "no_resolved_addresses"
    }

    var lastError: IOException? = null
    for (address in addresses) {
        try {
            connect(InetSocketAddress(address, port))
            return null
        } catch (error: IOException) {
            lastError = error
        }
    }

    return lastError?.message ?: "connect_failed"
}
