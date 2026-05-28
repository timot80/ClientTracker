package com.wifiops.probe

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.content.ContextCompat
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.fillMaxSize
import com.wifiops.probe.pairing.PairingPayload
import com.wifiops.probe.service.ProbeForegroundService
import com.wifiops.probe.ui.PairScreen
import com.wifiops.probe.ui.SessionHistoryScreen
import com.wifiops.probe.ui.SessionScreen
import com.wifiops.probe.ui.SessionUiState

class MainActivity : ComponentActivity() {
    private var pairingPayload by mutableStateOf<PairingPayload?>(null)
    private var probeRunning by mutableStateOf(false)
    private var showingHistory by mutableStateOf(false)
    private var permissionMessage by mutableStateOf<String?>(null)

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
                            sessions = emptyList(),
                            onBack = { showingHistory = false },
                            onExport = { },
                            onDelete = { }
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
                            onShowHistory = { showingHistory = true }
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
        permissionMessage = null
        ContextCompat.startForegroundService(
            this,
            Intent(this, ProbeForegroundService::class.java)
        )
        probeRunning = true
    }

    private fun stopProbeService() {
        stopService(Intent(this, ProbeForegroundService::class.java))
        probeRunning = false
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
