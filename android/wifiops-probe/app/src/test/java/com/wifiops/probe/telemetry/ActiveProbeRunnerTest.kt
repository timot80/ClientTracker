package com.wifiops.probe.telemetry

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ActiveProbeRunnerTest {
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
