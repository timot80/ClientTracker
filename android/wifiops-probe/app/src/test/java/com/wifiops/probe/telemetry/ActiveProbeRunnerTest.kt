package com.wifiops.probe.telemetry

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.IOException
import java.net.InetAddress

@OptIn(ExperimentalCoroutinesApi::class)
class ActiveProbeRunnerTest {
    @Test
    fun connectFirstResolvedAddressTriesAddressesInOrderUntilSuccess() {
        val first = InetAddress.getByName("192.0.2.1")
        val second = InetAddress.getByName("192.0.2.2")
        val attempted = mutableListOf<String>()

        val failure = connectFirstResolvedAddress(arrayOf(first, second), 443) { socketAddress ->
            attempted += socketAddress.address.hostAddress.orEmpty()
            if (socketAddress.address == first) {
                throw IOException("first failed")
            }
        }

        assertNull(failure)
        assertEquals(listOf("192.0.2.1", "192.0.2.2"), attempted)
    }

    @Test
    fun connectFirstResolvedAddressReturnsLastFailureWhenAllAddressesFail() {
        val first = InetAddress.getByName("192.0.2.1")
        val second = InetAddress.getByName("192.0.2.2")

        val failure = connectFirstResolvedAddress(arrayOf(first, second), 443) { socketAddress ->
            throw IOException("${socketAddress.address.hostAddress} failed")
        }

        assertEquals("192.0.2.2 failed", failure)
    }

    @Test
    fun tcpConnectReturnsNoWifiNetworkWhenNetworkIsMissing() = runTest {
        val runner = ActiveProbeRunner()

        val result = runner.tcpConnect("example.com", 443, network = null)

        assertFalse(result.ok)
        assertEquals("no_wifi_network", result.detail)
    }

    @Test
    fun dnsLookupReturnsNoWifiNetworkWhenNetworkIsMissing() = runTest {
        val runner = ActiveProbeRunner()

        val result = runner.dnsLookup("example.com", network = null)

        assertFalse(result.ok)
        assertEquals("no_wifi_network", result.detail)
    }

    @Test
    fun httpGetReturnsNoWifiNetworkWhenNetworkIsMissing() = runTest {
        val runner = ActiveProbeRunner()

        val result = runner.httpGet("https://example.com", network = null)

        assertFalse(result.ok)
        assertEquals("no_wifi_network", result.detail)
    }
}
