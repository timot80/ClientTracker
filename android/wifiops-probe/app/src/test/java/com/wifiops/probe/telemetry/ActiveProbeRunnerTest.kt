package com.wifiops.probe.telemetry

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Runnable
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.coroutines.CoroutineContext

@OptIn(ExperimentalCoroutinesApi::class)
class ActiveProbeRunnerTest {
    @Test
    fun dnsLookupPropagatesCancellationFromIoDispatcher() = runTest {
        val runner = ActiveProbeRunner(CancellingDispatcher)

        val thrown = try {
            runner.dnsLookup("example.com")
            null
        } catch (error: Throwable) {
            error
        }

        assertTrue(thrown is CancellationException)
    }

    private object CancellingDispatcher : CoroutineDispatcher() {
        override fun dispatch(context: CoroutineContext, block: Runnable) {
            throw CancellationException("cancelled")
        }
    }
}
