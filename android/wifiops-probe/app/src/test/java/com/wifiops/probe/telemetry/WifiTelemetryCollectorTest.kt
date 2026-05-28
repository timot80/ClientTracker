package com.wifiops.probe.telemetry

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class WifiTelemetryCollectorTest {
    @Test
    fun channelFromFrequencyHandlesFiveGhz() {
        assertEquals("36", channelFromFrequency(5180))
    }

    @Test
    fun channelFromFrequencyHandlesTwoPointFourGhz() {
        assertEquals("1", channelFromFrequency(2412))
        assertEquals("13", channelFromFrequency(2472))
        assertEquals("14", channelFromFrequency(2484))
    }

    @Test
    fun channelFromFrequencyHandlesSixGhz() {
        assertEquals("2", channelFromFrequency(5935))
        assertEquals("1", channelFromFrequency(5955))
        assertEquals("3", channelFromFrequency(5965))
        assertEquals("5", channelFromFrequency(5975))
    }

    @Test
    fun channelFromFrequencyReturnsNullForUnknownFrequency() {
        assertNull(channelFromFrequency(null))
        assertNull(channelFromFrequency(1234))
        assertNull(channelFromFrequency(5925))
        assertNull(channelFromFrequency(5950))
    }
}
