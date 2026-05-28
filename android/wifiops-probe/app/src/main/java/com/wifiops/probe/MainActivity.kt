package com.wifiops.probe

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.room.Room
import com.wifiops.probe.data.ProbeDatabase
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.fillMaxSize
import com.wifiops.probe.pairing.PairingPayload
import com.wifiops.probe.service.ProbeForegroundService
import com.wifiops.probe.sync.ProbeSyncClient
import com.wifiops.probe.ui.TelemetryCounters
import com.wifiops.probe.ui.PairScreen
import com.wifiops.probe.ui.SessionHistoryScreen
import com.wifiops.probe.ui.SessionScreen
import com.wifiops.probe.ui.SessionSummary
import com.wifiops.probe.ui.SessionUiState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    private lateinit var database: ProbeDatabase
    private var pairingPayload by mutableStateOf<PairingPayload?>(null)
    private var probeRunning by mutableStateOf(false)
    private var showingHistory by mutableStateOf(false)
    private var permissionMessage by mutableStateOf<String?>(null)
    private var sessionHistory by mutableStateOf<List<SessionSummary>>(emptyList())
    private var sessionCounters by mutableStateOf(TelemetryCounters())
    private var receiverReachable by mutableStateOf<Boolean?>(null)
    private var counterRefreshJob: Job? = null
    private val syncClient = ProbeSyncClient()

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        if (results.values.all { it }) {
            startProbeService()
        } else {
            permissionMessage = "Required Wi-Fi probe permissions were not granted."
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        database = Room.databaseBuilder(
            applicationContext,
            ProbeDatabase::class.java,
            "wifiops-probe.db"
        ).build()
        refreshSessionHistory()
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    val paired = pairingPayload
                    when {
                        paired == null -> PairScreen(
                            onPaired = {
                                pairingPayload = it
                                sessionCounters = TelemetryCounters()
                                permissionMessage = null
                                showingHistory = false
                            }
                        )

                        showingHistory -> SessionHistoryScreen(
                            sessions = sessionHistory,
                            onBack = { showingHistory = false },
                            onExport = { exportSessionSummary(it) },
                            onDelete = { deleteSession(it) }
                        )

                        else -> SessionScreen(
                            state = SessionUiState(
                                pairing = paired,
                                running = probeRunning,
                                receiverReachable = receiverReachable,
                                counters = sessionCounters,
                                permissionMessage = permissionMessage
                            ),
                            onStart = { startProbeWithPermissions() },
                            onStop = { stopProbeService() },
                            onPairDifferentReceiver = {
                                stopProbeService()
                                pairingPayload = null
                                showingHistory = false
                            },
                            onShowHistory = {
                                refreshSessionHistory()
                                showingHistory = true
                            }
                        )
                    }
                }
            }
        }
    }

    private fun startProbeWithPermissions() {
        val missingPermissions = requiredRuntimePermissions()
            .filter { permission ->
                ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED
            }

        if (missingPermissions.isEmpty()) {
            startProbeService()
        } else {
            permissionLauncher.launch(missingPermissions.toTypedArray())
        }
    }

    private fun startProbeService() {
        val paired = pairingPayload ?: run {
            permissionMessage = "Pair a receiver before starting."
            return
        }
        permissionMessage = null
        receiverReachable = null
        ContextCompat.startForegroundService(
            this,
            Intent(this, ProbeForegroundService::class.java)
                .putExtra(ProbeForegroundService.EXTRA_RECEIVER_URL, paired.receiverUrl)
                .putExtra(ProbeForegroundService.EXTRA_SESSION_ID, paired.sessionId)
                .putExtra(ProbeForegroundService.EXTRA_TOKEN, paired.token)
        )
        probeRunning = true
        refreshSessionHistory()
        startCounterRefresh(paired.sessionId)
    }

    private fun stopProbeService() {
        stopService(Intent(this, ProbeForegroundService::class.java))
        probeRunning = false
        counterRefreshJob?.cancel()
        counterRefreshJob = null
        receiverReachable = null
        pairingPayload?.sessionId?.let { refreshSessionCounters(it) }
    }

    private fun startCounterRefresh(sessionId: String) {
        counterRefreshJob?.cancel()
        counterRefreshJob = lifecycleScope.launch {
            while (isActive) {
                refreshSessionCounters(sessionId)
                pairingPayload?.receiverUrl?.let { refreshReceiverReachability(it) }
                refreshSessionHistory()
                delay(1_000)
            }
        }
    }

    private fun refreshSessionCounters(sessionId: String) {
        if (!::database.isInitialized) {
            return
        }
        lifecycleScope.launch {
            sessionCounters = loadCounters(sessionId)
        }
    }

    private fun refreshReceiverReachability(receiverUrl: String) {
        lifecycleScope.launch {
            receiverReachable = withContext(Dispatchers.IO) {
                runCatching { syncClient.health(receiverUrl) }.getOrDefault(false)
            }
        }
    }

    private fun refreshSessionHistory() {
        if (!::database.isInitialized) {
            return
        }
        lifecycleScope.launch {
            sessionHistory = withContext(Dispatchers.IO) {
                val dao = database.probeRecordDao()
                dao.sessions().map { session ->
                    SessionSummary(
                        sessionId = session.sessionId,
                        receiverUrl = session.receiverUrl,
                        counters = loadCounters(session.sessionId)
                    )
                }
            }
        }
    }

    private suspend fun loadCounters(sessionId: String): TelemetryCounters = withContext(Dispatchers.IO) {
        val dao = database.probeRecordDao()
        val pending = dao.countByStatus(sessionId, "pending")
        val synced = dao.countByStatus(sessionId, "synced")
        val failed = dao.countByStatus(sessionId, "failed")
        TelemetryCounters(
            collected = pending + synced + failed,
            pending = pending,
            synced = synced,
            failed = failed
        )
    }

    private fun deleteSession(sessionId: String) {
        if (pairingPayload?.sessionId == sessionId) {
            stopProbeService()
            pairingPayload = null
            sessionCounters = TelemetryCounters()
            receiverReachable = null
            showingHistory = false
        }
        lifecycleScope.launch {
            withContext(Dispatchers.IO) {
                val dao = database.probeRecordDao()
                dao.deleteRecordsForSession(sessionId)
                dao.deleteSession(sessionId)
            }
            refreshSessionHistory()
        }
    }

    private fun exportSessionSummary(sessionId: String) {
        val session = sessionHistory.firstOrNull { it.sessionId == sessionId } ?: return
        val text = buildString {
            appendLine("wifiops Android probe session")
            appendLine("Session: ${session.sessionId}")
            appendLine("Receiver: ${session.receiverUrl}")
            appendLine("Pending: ${session.counters.pending}")
            appendLine("Synced: ${session.counters.synced}")
            appendLine("Failed: ${session.counters.failed}")
        }
        startActivity(
            Intent.createChooser(
                Intent(Intent.ACTION_SEND)
                    .setType("text/plain")
                    .putExtra(Intent.EXTRA_SUBJECT, "wifiops probe ${session.sessionId}")
                    .putExtra(Intent.EXTRA_TEXT, text),
                "Export session"
            )
        )
    }

    private fun requiredRuntimePermissions(): List<String> {
        return when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU -> listOf(
                Manifest.permission.NEARBY_WIFI_DEVICES,
                Manifest.permission.POST_NOTIFICATIONS
            )

            Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q -> listOf(
                Manifest.permission.ACCESS_FINE_LOCATION
            )

            else -> emptyList()
        }
    }
}
