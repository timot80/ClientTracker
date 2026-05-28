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
import com.wifiops.probe.ui.TelemetryCounters
import com.wifiops.probe.ui.PairScreen
import com.wifiops.probe.ui.SessionHistoryScreen
import com.wifiops.probe.ui.SessionScreen
import com.wifiops.probe.ui.SessionSummary
import com.wifiops.probe.ui.SessionUiState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    private lateinit var database: ProbeDatabase
    private var pairingPayload by mutableStateOf<PairingPayload?>(null)
    private var probeRunning by mutableStateOf(false)
    private var showingHistory by mutableStateOf(false)
    private var permissionMessage by mutableStateOf<String?>(null)
    private var sessionHistory by mutableStateOf<List<SessionSummary>>(emptyList())

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
        ContextCompat.startForegroundService(
            this,
            Intent(this, ProbeForegroundService::class.java)
                .putExtra(ProbeForegroundService.EXTRA_RECEIVER_URL, paired.receiverUrl)
                .putExtra(ProbeForegroundService.EXTRA_SESSION_ID, paired.sessionId)
                .putExtra(ProbeForegroundService.EXTRA_TOKEN, paired.token)
        )
        probeRunning = true
        refreshSessionHistory()
    }

    private fun stopProbeService() {
        stopService(Intent(this, ProbeForegroundService::class.java))
        probeRunning = false
    }

    private fun refreshSessionHistory() {
        if (!::database.isInitialized) {
            return
        }
        lifecycleScope.launch {
            sessionHistory = withContext(Dispatchers.IO) {
                val dao = database.probeRecordDao()
                dao.sessions().map { session ->
                    val pending = dao.countByStatus(session.sessionId, "pending")
                    val synced = dao.countByStatus(session.sessionId, "synced")
                    val failed = dao.countByStatus(session.sessionId, "failed")
                    SessionSummary(
                        sessionId = session.sessionId,
                        receiverUrl = session.receiverUrl,
                        counters = TelemetryCounters(
                            collected = pending + synced + failed,
                            pending = pending,
                            synced = synced,
                            failed = failed
                        )
                    )
                }
            }
        }
    }

    private fun deleteSession(sessionId: String) {
        lifecycleScope.launch {
            withContext(Dispatchers.IO) {
                val dao = database.probeRecordDao()
                dao.deleteRecordsForSession(sessionId)
                dao.deleteSession(sessionId)
            }
            if (pairingPayload?.sessionId == sessionId) {
                stopProbeService()
                pairingPayload = null
                showingHistory = false
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
