package com.wifiops.probe.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.room.Room
import com.wifiops.probe.MainActivity
import com.wifiops.probe.data.ProbeDatabase
import com.wifiops.probe.data.RecordEntity
import com.wifiops.probe.data.SessionEntity
import com.wifiops.probe.data.TelemetryRecord
import com.wifiops.probe.sync.ProbeSyncClient
import com.wifiops.probe.sync.ProbeSyncWorker
import com.wifiops.probe.telemetry.ActiveProbeRunner
import com.wifiops.probe.telemetry.ProbeResult
import com.wifiops.probe.telemetry.WifiTelemetryCollector
import com.wifiops.probe.telemetry.gatewayProbeHost
import com.wifiops.probe.telemetry.wifiNetwork
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

class ProbeForegroundService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var database: ProbeDatabase
    private lateinit var connectivityManager: ConnectivityManager
    private lateinit var collector: WifiTelemetryCollector
    private val probeRunner = ActiveProbeRunner()
    private lateinit var syncWorker: ProbeSyncWorker
    private var activeSessionId: String? = null
    private var collectionJob: Job? = null
    private var sequenceNumber = 0L

    override fun onCreate() {
        super.onCreate()
        database = Room.databaseBuilder(
            applicationContext,
            ProbeDatabase::class.java,
            "wifiops-probe.db"
        ).build()
        val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        connectivityManager = getSystemService(ConnectivityManager::class.java)
        collector = WifiTelemetryCollector(wifiManager, connectivityManager)
        syncWorker = ProbeSyncWorker(database.probeRecordDao(), ProbeSyncClient())
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, notification("Starting collection"))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            collectionJob?.cancel()
            collectionJob = null
            activeSessionId = null
            publishServiceState(running = false, session = null)
            stopSelf(startId)
            return START_NOT_STICKY
        }

        val session = sessionFromIntent(intent)
        if (session == null) {
            stopSelf(startId)
            return START_NOT_STICKY
        }

        if (activeSessionId != session.sessionId) {
            collectionJob?.cancel()
            activeSessionId = session.sessionId
            sequenceNumber = 0L
        }
        publishServiceState(running = true, session = session)

        if (collectionJob?.isActive == true) {
            startForeground(NOTIFICATION_ID, notification("Session ${session.sessionId}: collection active"))
            return START_STICKY
        }

        collectionJob = serviceScope.launch {
            database.probeRecordDao().insertSession(session)
            sequenceNumber = database.probeRecordDao().maxSequenceForSession(session.sessionId)
            collectAndSync(session)
        }
        startForeground(NOTIFICATION_ID, notification("Session ${session.sessionId}: collection active"))
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        publishServiceState(running = false, session = null)
        serviceScope.cancel()
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    private fun sessionFromIntent(intent: Intent?): SessionEntity? {
        val receiverUrl = intent?.getStringExtra(EXTRA_RECEIVER_URL)?.takeIf { it.isNotBlank() } ?: return null
        val sessionId = intent.getStringExtra(EXTRA_SESSION_ID)?.takeIf { it.isNotBlank() } ?: return null
        val token = intent.getStringExtra(EXTRA_TOKEN)?.takeIf { it.isNotBlank() } ?: return null
        return SessionEntity(
            sessionId = sessionId,
            receiverUrl = receiverUrl,
            token = token,
            deviceId = Build.MODEL.orEmpty().ifBlank { "android" },
            createdAtMillis = System.currentTimeMillis()
        )
    }

    private suspend fun collectAndSync(session: SessionEntity) {
        while (serviceScope.isActive && activeSessionId == session.sessionId) {
            val record = telemetryRecord(session)
            database.probeRecordDao().insertRecord(
                RecordEntity(
                    recordId = record.recordId,
                    sessionId = record.sessionId,
                    sequenceNumber = record.sequenceNumber,
                    recordType = record.recordType,
                    payloadJson = Json.encodeToString(TelemetryRecord.serializer(), record),
                    syncStatus = "pending",
                    createdAtMillis = System.currentTimeMillis()
                )
            )
            val synced = syncWorker.syncOnce(session.sessionId, session.receiverUrl, session.token)
            updateNotification(
                "Session ${session.sessionId}: collected sample #$sequenceNumber, uploaded $synced pending records"
            )
            delay(SAMPLE_INTERVAL_MS)
        }
    }

    private suspend fun telemetryRecord(session: SessionEntity): TelemetryRecord {
        val nextSequence = ++sequenceNumber
        val basePayload = collector.collect()
        val probes = collectActiveProbes(basePayload.gateway, session.receiverUrl)
        return TelemetryRecord(
            schemaVersion = 1,
            sessionId = session.sessionId,
            deviceId = session.deviceId,
            recordId = "${session.sessionId}-$nextSequence",
            sequenceNumber = nextSequence,
            recordType = "sample",
            clientTimestamp = OffsetDateTime.now().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME),
            appVersion = "0.1.0",
            androidApiLevel = Build.VERSION.SDK_INT,
            payload = basePayload.copy(
                manufacturer = Build.MANUFACTURER,
                model = Build.MODEL,
                probes = probes
            )
        )
    }

    private suspend fun collectActiveProbes(gateway: String?, receiverUrl: String): Map<String, ProbeResult> {
        val network = wifiNetwork(connectivityManager)
        val gatewayProbeHost = gatewayProbeHost(
            gateway = gateway,
            interfaceName = network?.let { connectivityManager.getLinkProperties(it)?.interfaceName }
        )
        val probes = linkedMapOf<String, ProbeResult>()
        if (!gatewayProbeHost.isNullOrBlank()) {
            probes["gateway"] = probeRunner.tcpConnect(gatewayProbeHost, DNS_PORT, ACTIVE_PROBE_TIMEOUT_MS, network)
        } else if (!gateway.isNullOrBlank()) {
            probes["gateway"] = ProbeResult(ok = false, detail = "gateway_scope_unavailable")
        } else {
            probes["gateway"] = ProbeResult(ok = false, detail = "gateway_unavailable")
        }
        probes["dns"] = probeRunner.dnsLookup(DEFAULT_DNS_HOSTNAME, network)
        probes["http"] = probeRunner.httpGet("${receiverUrl.trimEnd('/')}/health", ACTIVE_PROBE_TIMEOUT_MS, network)
        return probes
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Wi-Fi Ops Probe",
                NotificationManager.IMPORTANCE_LOW
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text))
    }

    private fun notification(text: String): Notification {
        val session = activeSessionId
        val contentIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java)
                .setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                .apply {
                    activeSessionDetails?.let {
                        putExtra(EXTRA_RECEIVER_URL, it.receiverUrl)
                        putExtra(EXTRA_SESSION_ID, it.sessionId)
                        putExtra(EXTRA_TOKEN, it.token)
                    }
                },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stopIntent = PendingIntent.getService(
            this,
            1,
            Intent(this, ProbeForegroundService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle("Wi-Fi Ops Probe running")
            .setContentText(text)
            .setContentIntent(contentIntent)
            .setOngoing(true)
            .addAction(android.R.drawable.ic_media_pause, "Stop session", stopIntent)
            .build()
    }

    private var activeSessionDetails: SessionEntity? = null

    private fun publishServiceState(running: Boolean, session: SessionEntity?) {
        activeSessionDetails = session
        getSharedPreferences(SERVICE_PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_SERVICE_RUNNING, running)
            .putString(KEY_SERVICE_SESSION_ID, session?.sessionId.orEmpty())
            .apply()
        sendBroadcast(Intent(ACTION_STATE_CHANGED).setPackage(packageName))
    }

    companion object {
        const val EXTRA_RECEIVER_URL = "com.wifiops.probe.extra.RECEIVER_URL"
        const val EXTRA_SESSION_ID = "com.wifiops.probe.extra.SESSION_ID"
        const val EXTRA_TOKEN = "com.wifiops.probe.extra.TOKEN"

        const val ACTION_STOP = "com.wifiops.probe.action.STOP"
        const val ACTION_STATE_CHANGED = "com.wifiops.probe.action.STATE_CHANGED"
        const val CHANNEL_ID = "probe"
        const val NOTIFICATION_ID = 1001
        const val SERVICE_PREFS = "probe_service"
        const val KEY_SERVICE_RUNNING = "running"
        const val KEY_SERVICE_SESSION_ID = "session_id"
        const val SAMPLE_INTERVAL_MS = 1_000L
        const val ACTIVE_PROBE_TIMEOUT_MS = 1_000
        const val DNS_PORT = 53
        const val DEFAULT_DNS_HOSTNAME = "example.com"
    }
}
