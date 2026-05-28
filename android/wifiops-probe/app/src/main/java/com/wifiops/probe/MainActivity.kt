package com.wifiops.probe

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.room.Room
import com.wifiops.probe.data.ProbeDatabase
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.fillMaxSize
import com.wifiops.probe.pairing.PairingPayload
import com.wifiops.probe.data.RecordEntity
import com.wifiops.probe.data.TelemetryRecord
import com.wifiops.probe.data.buildRawRecordExportJson
import com.wifiops.probe.service.ProbeForegroundService
import com.wifiops.probe.sync.ProbeSyncClient
import com.wifiops.probe.ui.LatestTelemetrySummary
import com.wifiops.probe.ui.TelemetryCounters
import com.wifiops.probe.ui.PairScreen
import com.wifiops.probe.ui.SessionHistoryScreen
import com.wifiops.probe.ui.SessionScreen
import com.wifiops.probe.ui.SessionSummary
import com.wifiops.probe.ui.SessionUiState
import com.wifiops.probe.ui.theme.WifiOpsTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json

class MainActivity : ComponentActivity() {
    private lateinit var database: ProbeDatabase
    private var pairingPayload by mutableStateOf<PairingPayload?>(null)
    private var probeRunning by mutableStateOf(false)
    private var showingHistory by mutableStateOf(false)
    private var permissionMessage by mutableStateOf<String?>(null)
    private var sessionHistory by mutableStateOf<List<SessionSummary>>(emptyList())
    private var sessionCounters by mutableStateOf(TelemetryCounters())
    private var latestTelemetry by mutableStateOf<LatestTelemetrySummary?>(null)
    private var receiverReachable by mutableStateOf<Boolean?>(null)
    private var savedPairing by mutableStateOf<PairingPayload?>(null)
    private var preflightChecks by mutableStateOf<List<PreflightCheck>>(emptyList())
    private var counterRefreshJob: Job? = null
    private val syncClient = ProbeSyncClient()
    private val serviceStateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            syncProbeRunningFromServiceState()
        }
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        val blockingDenied = requiredRuntimePermissions()
            .filterNot { it == Manifest.permission.POST_NOTIFICATIONS }
            .any { permission -> results[permission] == false && !hasPermission(permission) }
        if (!blockingDenied) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                !hasPermission(Manifest.permission.POST_NOTIFICATIONS)
            ) {
                permissionMessage = "Notifications are off. Collection can continue, but session status may not appear while the app is backgrounded."
            }
            startProbeWithPermissions()
        } else {
            permissionMessage = "Required Wi-Fi probe permissions were not granted."
            refreshPreflightChecks()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        database = Room.databaseBuilder(
            applicationContext,
            ProbeDatabase::class.java,
            "wifiops-probe.db"
        ).build()
        savedPairing = loadSavedPairing()
        restorePairingFromIntent(intent)
        refreshSessionHistory()
        refreshPreflightChecks()
        setContent {
            WifiOpsTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    val paired = pairingPayload
                    when {
                        paired == null -> PairScreen(
                            savedPairing = savedPairing,
                            onPaired = {
                                pairingPayload = it
                                savedPairing = it
                                savePairing(it)
                                sessionCounters = TelemetryCounters()
                                latestTelemetry = null
                                permissionMessage = null
                                showingHistory = false
                                refreshSessionData(it.sessionId)
                                refreshReceiverReachability(it.receiverUrl)
                                refreshPreflightChecks()
                            }
                        )

                        showingHistory -> SessionHistoryScreen(
                            sessions = sessionHistory,
                            activeSessionId = paired.sessionId.takeIf { probeRunning },
                            onBack = { showingHistory = false },
                            onExportSummary = { exportSessionSummary(it) },
                            onExportRecords = { exportSessionRecords(it) },
                            onDelete = { deleteSession(it) }
                        )

                        else -> SessionScreen(
                            state = SessionUiState(
                                pairing = paired,
                                running = probeRunning,
                                receiverReachable = receiverReachable,
                                counters = sessionCounters,
                                latestTelemetry = latestTelemetry,
                                preflightChecks = preflightChecks,
                                permissionMessage = permissionMessage
                            ),
                            onStart = { startProbeWithPermissions() },
                            onStop = { stopProbeService() },
                            onPairDifferentReceiver = {
                                stopProbeService()
                                pairingPayload = null
                                savedPairing = loadSavedPairing()
                                showingHistory = false
                            },
                            onShowHistory = {
                                refreshSessionHistory()
                                showingHistory = true
                            },
                            onPreflightAction = { handlePreflightAction(it) }
                        )
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        restorePairingFromIntent(intent)
        syncProbeRunningFromServiceState()
        pairingPayload?.let {
            refreshSessionData(it.sessionId)
            refreshReceiverReachability(it.receiverUrl)
        }
        refreshPreflightChecks()
    }

    override fun onResume() {
        super.onResume()
        registerReceiverCompat()
        syncProbeRunningFromServiceState()
        refreshPreflightChecks()
    }

    override fun onPause() {
        unregisterReceiver(serviceStateReceiver)
        super.onPause()
    }

    private fun startProbeWithPermissions() {
        val missingPermissions = requiredRuntimePermissions()
            .filterNot { it == Manifest.permission.POST_NOTIFICATIONS }
            .filter { permission ->
                !hasPermission(permission)
            }

        if (missingPermissions.isNotEmpty()) {
            permissionLauncher.launch(missingPermissions.toTypedArray())
        } else {
            val currentPreflightChecks = computePreflightChecks()
            preflightChecks = currentPreflightChecks
            val blockingCheck = currentPreflightChecks.firstOrNull { it.blocksSession }
            if (blockingCheck != null) {
                permissionMessage = "${blockingCheck.title}: ${blockingCheck.detail}"
                return
            }
            continueAfterRuntimePermissions()
        }
    }

    private fun continueAfterRuntimePermissions() {
        if (!hasBackgroundLocationForServiceWifiIdentity()) {
            permissionMessage = "Background location is off. Foreground collection can start, but Wi-Fi identity may be limited when the app is backgrounded."
        }
        startProbeService()
    }

    private fun hasBackgroundLocationForServiceWifiIdentity(): Boolean {
        return !needsBackgroundLocationForServiceWifiIdentity() ||
            hasPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
    }

    private fun hasPermission(permission: String): Boolean {
        return ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED
    }

    private fun startProbeService() {
        val paired = pairingPayload ?: run {
            permissionMessage = "Set up a receiver before starting."
            return
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            hasPermission(Manifest.permission.POST_NOTIFICATIONS)
        ) {
            permissionMessage = null
        }
        receiverReachable = null
        setProbeServiceState(running = true, sessionId = paired.sessionId)
        ContextCompat.startForegroundService(
            this,
            Intent(this, ProbeForegroundService::class.java)
                .putExtra(ProbeForegroundService.EXTRA_RECEIVER_URL, paired.receiverUrl)
                .putExtra(ProbeForegroundService.EXTRA_SESSION_ID, paired.sessionId)
                .putExtra(ProbeForegroundService.EXTRA_TOKEN, paired.token)
        )
        probeRunning = true
        refreshSessionHistory()
        refreshPreflightChecks()
        startCounterRefresh(paired.sessionId)
    }

    private fun stopProbeService() {
        stopService(Intent(this, ProbeForegroundService::class.java))
        probeRunning = false
        counterRefreshJob?.cancel()
        counterRefreshJob = null
        receiverReachable = null
        setProbeServiceState(running = false, sessionId = pairingPayload?.sessionId)
        pairingPayload?.sessionId?.let { refreshSessionData(it) }
        refreshPreflightChecks()
    }

    private fun startCounterRefresh(sessionId: String) {
        counterRefreshJob?.cancel()
        counterRefreshJob = lifecycleScope.launch {
            while (isActive) {
                syncProbeRunningFromServiceState()
                if (!probeRunning) {
                    counterRefreshJob = null
                    break
                }
                refreshSessionData(sessionId)
                pairingPayload?.receiverUrl?.let { refreshReceiverReachability(it) }
                refreshSessionHistory()
                refreshPreflightChecks()
                delay(1_000)
            }
        }
    }

    private fun refreshSessionData(sessionId: String) {
        if (!::database.isInitialized) {
            return
        }
        lifecycleScope.launch {
            sessionCounters = loadCounters(sessionId)
            latestTelemetry = loadLatestTelemetrySummary(sessionId)
        }
    }

    private fun refreshReceiverReachability(receiverUrl: String) {
        lifecycleScope.launch {
            receiverReachable = withContext(Dispatchers.IO) {
                runCatching { syncClient.health(receiverUrl) }.getOrDefault(false)
            }
            refreshPreflightChecks()
        }
    }

    private fun refreshPreflightChecks() {
        preflightChecks = computePreflightChecks()
    }

    private fun handlePreflightAction(action: PreflightRecoveryAction) {
        when (action) {
            PreflightRecoveryAction.Retry -> {
                permissionMessage = null
                refreshPreflightChecks()
            }

            PreflightRecoveryAction.OpenSettings -> openAppSettings()
            PreflightRecoveryAction.TestAgain -> {
                permissionMessage = null
                receiverReachable = null
                pairingPayload?.receiverUrl?.let { refreshReceiverReachability(it) }
                refreshPreflightChecks()
            }
        }
    }

    private fun openAppSettings() {
        startActivity(
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                .setData(Uri.fromParts("package", packageName, null))
        )
    }

    private fun computePreflightChecks(): List<PreflightCheck> {
        val grants = PermissionGrantState(
            apiLevel = Build.VERSION.SDK_INT,
            nearbyWifiGranted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                hasPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
            } else {
                false
            },
            fineLocationGranted = hasPermission(Manifest.permission.ACCESS_FINE_LOCATION),
            backgroundLocationGranted = hasPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION),
            notificationsGranted = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                hasPermission(Manifest.permission.POST_NOTIFICATIONS),
            wifiConnected = isWifiConnected(),
            receiverReachable = receiverReachable
        )
        return preflightChecks(grants)
    }

    private fun isWifiConnected(): Boolean {
        val connectivityManager = getSystemService(ConnectivityManager::class.java)
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
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

    private suspend fun loadLatestTelemetrySummary(sessionId: String): LatestTelemetrySummary? = withContext(Dispatchers.IO) {
        database.probeRecordDao()
            .latestRecordForSession(sessionId)
            ?.toLatestTelemetrySummary()
    }

    private fun RecordEntity.toLatestTelemetrySummary(): LatestTelemetrySummary {
        val record = runCatching {
            TelemetryJson.decodeFromString(TelemetryRecord.serializer(), payloadJson)
        }.getOrNull() ?: return LatestTelemetrySummary(
            availability = "Limited",
            uploadStatus = syncStatusLabel(syncStatus)
        )
        val payload = record.payload
        return LatestTelemetrySummary(
            ssid = payload.ssid,
            bssid = payload.bssid,
            rssi = payload.rssi,
            channel = payload.channel,
            frequencyMhz = payload.frequencyMhz,
            availability = availabilityLabel(payload.availability, payload.ssid, payload.bssid, payload.rssi, payload.channel),
            sampleTime = record.clientTimestamp,
            uploadStatus = syncStatusLabel(syncStatus),
            gatewayProbe = probeStatus(payload.probes["gateway"]),
            dnsProbe = probeStatus(payload.probes["dns"]),
            httpProbe = probeStatus(payload.probes["http"])
        )
    }

    private fun availabilityLabel(
        availability: Map<String, String>,
        ssid: String?,
        bssid: String?,
        rssi: Int?,
        channel: String?
    ): String {
        return when {
            availability.values.any { it.contains("redacted", ignoreCase = true) } -> "Redacted"
            ssid != null && bssid != null && rssi != null && channel != null -> "Available"
            availability.isNotEmpty() -> "Limited"
            else -> "Unavailable"
        }
    }

    private fun syncStatusLabel(status: String): String {
        return when (status) {
            "pending" -> "Pending upload"
            "synced" -> "Synced"
            "failed" -> "Upload failed"
            else -> status.ifBlank { "Unknown" }
        }
    }

    private fun probeStatus(probe: com.wifiops.probe.telemetry.ProbeResult?): String {
        return when {
            probe == null -> "Unavailable"
            probe.ok && probe.latencyMs != null -> "OK ${probe.latencyMs} ms"
            probe.ok -> "OK"
            probe.detail.isNotBlank() -> "Failed: ${probe.detail}"
            else -> "Failed"
        }
    }

    private fun deleteSession(sessionId: String) {
        if (pairingPayload?.sessionId == sessionId) {
            stopProbeService()
            pairingPayload = null
            sessionCounters = TelemetryCounters()
            latestTelemetry = null
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

    private fun restorePairingFromIntent(intent: Intent?) {
        val receiverUrl = intent?.getStringExtra(ProbeForegroundService.EXTRA_RECEIVER_URL).orEmpty()
        val sessionId = intent?.getStringExtra(ProbeForegroundService.EXTRA_SESSION_ID).orEmpty()
        val token = intent?.getStringExtra(ProbeForegroundService.EXTRA_TOKEN).orEmpty()
        if (receiverUrl.isBlank() || sessionId.isBlank() || token.isBlank()) {
            return
        }
        runCatching {
            PairingPayload.fromManualFields(receiverUrl, sessionId, token)
        }.onSuccess {
            pairingPayload = it
            savedPairing = it
            savePairing(it)
            showingHistory = false
        }
    }

    private fun syncProbeRunningFromServiceState() {
        val preferences = getSharedPreferences(SERVICE_PREFS, Context.MODE_PRIVATE)
        val running = preferences.getBoolean(KEY_SERVICE_RUNNING, false)
        val sessionId = preferences.getString(KEY_SERVICE_SESSION_ID, "").orEmpty()
        if (!running && probeRunning) {
            probeRunning = false
            counterRefreshJob?.cancel()
            counterRefreshJob = null
        } else if (running && pairingPayload?.sessionId == sessionId) {
            probeRunning = true
        }
    }

    private fun setProbeServiceState(running: Boolean, sessionId: String?) {
        getSharedPreferences(SERVICE_PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_SERVICE_RUNNING, running)
            .putString(KEY_SERVICE_SESSION_ID, sessionId.orEmpty())
            .apply()
    }

    private fun registerReceiverCompat() {
        val filter = IntentFilter(ProbeForegroundService.ACTION_STATE_CHANGED)
        ContextCompat.registerReceiver(
            this,
            serviceStateReceiver,
            filter,
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
    }

    private fun exportSessionSummary(sessionId: String) {
        val session = sessionHistory.firstOrNull { it.sessionId == sessionId } ?: return
        val text = buildString {
            appendLine("Wi-Fi Ops Probe session summary")
            appendLine("Session: ${session.sessionId}")
            appendLine("Receiver: ${session.receiverUrl}")
            appendLine("Pending: ${session.counters.pending}")
            appendLine("Synced: ${session.counters.synced}")
            appendLine("Failed: ${session.counters.failed}")
            appendLine()
            appendLine("Raw record export is not included in this summary. Raw records may contain network identifiers and device/session metadata.")
        }
        startActivity(
            Intent.createChooser(
                Intent(Intent.ACTION_SEND)
                    .setType("text/plain")
                    .putExtra(Intent.EXTRA_SUBJECT, "Wi-Fi Ops Probe ${session.sessionId}")
                    .putExtra(Intent.EXTRA_TEXT, text),
                "Export summary"
            )
        )
    }

    private fun exportSessionRecords(sessionId: String) {
        lifecycleScope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val dao = database.probeRecordDao()
                    val session = dao.session(sessionId) ?: error("Session $sessionId was not found")
                    val records = dao.recordsForSession(sessionId)
                    buildRawRecordExportJson(
                        session = session,
                        records = records,
                        exportedAtMillis = System.currentTimeMillis()
                    )
                }
            }
            result.onSuccess { json ->
                shareRawRecordExport(sessionId, json)
            }.onFailure { error ->
                Toast.makeText(
                    this@MainActivity,
                    error.message ?: "Unable to export records",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    private fun shareRawRecordExport(sessionId: String, json: String) {
        startActivity(
            Intent.createChooser(
                Intent(Intent.ACTION_SEND)
                    .setType("application/json")
                    .putExtra(Intent.EXTRA_SUBJECT, "Wi-Fi Ops Probe records $sessionId")
                    .putExtra(Intent.EXTRA_TEXT, json),
                "Export records"
            )
        )
    }

    private fun loadSavedPairing(): PairingPayload? {
        val preferences = getSharedPreferences(PAIRING_PREFS, Context.MODE_PRIVATE)
        val receiverUrl = preferences.getString(KEY_RECEIVER_URL, "").orEmpty()
        val sessionId = preferences.getString(KEY_SESSION_ID, "").orEmpty()
        val token = preferences.getString(KEY_TOKEN, "").orEmpty()
        return runCatching {
            PairingPayload.fromManualFields(receiverUrl, sessionId, token)
        }.getOrNull()
    }

    private fun savePairing(pairing: PairingPayload) {
        getSharedPreferences(PAIRING_PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_RECEIVER_URL, pairing.receiverUrl)
            .putString(KEY_SESSION_ID, pairing.sessionId)
            .putString(KEY_TOKEN, pairing.token)
            .apply()
    }

    private companion object {
        val TelemetryJson = Json { ignoreUnknownKeys = true }
        const val PAIRING_PREFS = "pairing"
        const val SERVICE_PREFS = "probe_service"
        const val KEY_RECEIVER_URL = "receiver_url"
        const val KEY_SESSION_ID = "session_id"
        const val KEY_TOKEN = "token"
        const val KEY_SERVICE_RUNNING = "running"
        const val KEY_SERVICE_SESSION_ID = "session_id"
    }
}
