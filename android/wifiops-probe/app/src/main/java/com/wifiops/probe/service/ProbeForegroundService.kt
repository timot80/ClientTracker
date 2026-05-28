package com.wifiops.probe.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.room.Room
import com.wifiops.probe.data.ProbeDatabase
import com.wifiops.probe.data.SessionEntity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class ProbeForegroundService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var database: ProbeDatabase

    override fun onCreate() {
        super.onCreate()
        database = Room.databaseBuilder(
            applicationContext,
            ProbeDatabase::class.java,
            "wifiops-probe.db"
        ).build()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, notification("wifiops walk test running"))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val session = sessionFromIntent(intent)
        if (session == null) {
            stopSelf(startId)
            return START_NOT_STICKY
        }

        serviceScope.launch {
            database.probeRecordDao().insertSession(session)
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
    }
}
