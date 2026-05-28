package com.wifiops.probe.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.room.Room
import com.wifiops.probe.data.ProbeDatabase
import com.wifiops.probe.data.RecordEntity
import com.wifiops.probe.data.SessionEntity
import com.wifiops.probe.data.TelemetryRecord
import com.wifiops.probe.sync.ProbeSyncClient
import com.wifiops.probe.sync.ProbeSyncWorker
import com.wifiops.probe.telemetry.WifiTelemetryCollector
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
    private lateinit var collector: WifiTelemetryCollector
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
        val connectivityManager = getSystemService(ConnectivityManager::class.java)
        collector = WifiTelemetryCollector(wifiManager, connectivityManager)
        syncWorker = ProbeSyncWorker(database.probeRecordDao(), ProbeSyncClient())
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, notification("wifiops walk test running"))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
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

        if (collectionJob?.isActive == true) {
            startForeground(NOTIFICATION_ID, notification("wifiops session ${session.sessionId} running"))
            return START_STICKY
        }

        collectionJob = serviceScope.launch {
            database.probeRecordDao().insertSession(session)
            sequenceNumber = database.probeRecordDao().maxSequenceForSession(session.sessionId)
            collectAndSync(session)
        }
        startForeground(NOTIFICATION_ID, notification("wifiops session ${session.sessionId} running"))
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
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
            syncWorker.syncOnce(session.sessionId, session.receiverUrl, session.token)
            delay(SAMPLE_INTERVAL_MS)
        }
    }

    private fun telemetryRecord(session: SessionEntity): TelemetryRecord {
        val nextSequence = ++sequenceNumber
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
            payload = collector.collect()
        )
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Probe",
                NotificationManager.IMPORTANCE_LOW
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun notification(text: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentText(text)
            .setOngoing(true)
            .build()
    }

    companion object {
        const val EXTRA_RECEIVER_URL = "com.wifiops.probe.extra.RECEIVER_URL"
        const val EXTRA_SESSION_ID = "com.wifiops.probe.extra.SESSION_ID"
        const val EXTRA_TOKEN = "com.wifiops.probe.extra.TOKEN"

        const val CHANNEL_ID = "probe"
        const val NOTIFICATION_ID = 1001
        const val SAMPLE_INTERVAL_MS = 1_000L
    }
}
