package com.wifiops.probe.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.wifiops.probe.PreflightCheck
import com.wifiops.probe.PreflightRecoveryAction
import com.wifiops.probe.PreflightState
import com.wifiops.probe.pairing.PairingPayload

data class TelemetryCounters(
    val collected: Int = 0,
    val pending: Int = 0,
    val synced: Int = 0,
    val failed: Int = 0
)

data class LatestTelemetrySummary(
    val ssid: String? = null,
    val bssid: String? = null,
    val rssi: Int? = null,
    val channel: String? = null,
    val frequencyMhz: Int? = null,
    val availability: String = "Unavailable",
    val sampleTime: String? = null,
    val uploadStatus: String = "No sample yet",
    val gatewayProbe: String = "Unavailable",
    val dnsProbe: String = "Unavailable",
    val httpProbe: String = "Unavailable"
)

data class SessionUiState(
    val pairing: PairingPayload,
    val running: Boolean = false,
    val receiverReachable: Boolean? = null,
    val counters: TelemetryCounters = TelemetryCounters(),
    val latestTelemetry: LatestTelemetrySummary? = null,
    val preflightChecks: List<PreflightCheck> = emptyList(),
    val permissionMessage: String? = null
)

@Composable
fun SessionScreen(
    state: SessionUiState,
    modifier: Modifier = Modifier,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onPairDifferentReceiver: () -> Unit,
    onShowHistory: () -> Unit,
    onPreflightAction: (PreflightRecoveryAction) -> Unit
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            text = "Active session",
            style = MaterialTheme.typography.headlineSmall
        )
        StatusLine(label = "Receiver", value = state.pairing.receiverUrl)
        StatusLine(label = "Session", value = state.pairing.sessionId)
        StatusLine(label = "Service", value = if (state.running) "Running" else "Stopped")
        StatusLine(
            label = "Receiver status",
            value = when (state.receiverReachable) {
                true -> "Reachable"
                false -> "Unreachable"
                null -> "Not checked"
            }
        )

        if (state.preflightChecks.isNotEmpty()) {
            HorizontalDivider()
            Text(
                text = "Preflight",
                style = MaterialTheme.typography.titleMedium
            )
            state.preflightChecks.forEach { check ->
                PreflightRow(check = check, onPreflightAction = onPreflightAction)
            }
        }

        HorizontalDivider()
        Text(
            text = "Latest Wi-Fi sample",
            style = MaterialTheme.typography.titleMedium
        )
        LatestTelemetry(state.latestTelemetry)

        HorizontalDivider()
        Text(
            text = "Telemetry counters",
            style = MaterialTheme.typography.titleMedium
        )
        CounterRow(state.counters)

        state.permissionMessage?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            if (state.running) {
                Button(onClick = onStop, modifier = Modifier.weight(1f)) {
                    Text("Stop session")
                }
            } else {
                Button(onClick = onStart, modifier = Modifier.weight(1f)) {
                    Text("Start session")
                }
            }
            OutlinedButton(onClick = onPairDifferentReceiver, modifier = Modifier.weight(1f)) {
                Text("Change receiver")
            }
        }

        OutlinedButton(
            onClick = onShowHistory,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Session history")
        }
    }
}

@Composable
private fun PreflightRow(
    check: PreflightCheck,
    onPreflightAction: (PreflightRecoveryAction) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(text = check.title, style = MaterialTheme.typography.labelLarge)
        Text(
            text = check.state.label,
            color = preflightStateColor(check.state),
            style = MaterialTheme.typography.bodyLarge
        )
        Text(text = check.detail, style = MaterialTheme.typography.bodyMedium)
        check.recoveryAction?.let { action ->
            OutlinedButton(onClick = { onPreflightAction(action) }) {
                Text(action.label)
            }
        }
    }
}

@Composable
private fun preflightStateColor(state: PreflightState): Color {
    return when (state) {
        PreflightState.Ready -> MaterialTheme.colorScheme.tertiary
        PreflightState.NeedsAction,
        PreflightState.LimitedData -> MaterialTheme.colorScheme.secondary
        PreflightState.Blocked -> MaterialTheme.colorScheme.error
    }
}

@Composable
private fun LatestTelemetry(summary: LatestTelemetrySummary?) {
    if (summary == null) {
        StatusLine(label = "Last sample", value = "No sample yet")
        StatusLine(label = "Availability", value = "Unavailable")
        return
    }

    StatusLine(label = "SSID", value = summary.ssid ?: "Unavailable")
    StatusLine(label = "BSSID", value = summary.bssid ?: "Unavailable")
    StatusLine(label = "RSSI", value = summary.rssi?.let { "$it dBm" } ?: "Unavailable")
    StatusLine(
        label = "Channel",
        value = when {
            summary.channel != null && summary.frequencyMhz != null -> "${summary.channel} (${summary.frequencyMhz} MHz)"
            summary.channel != null -> summary.channel
            summary.frequencyMhz != null -> "${summary.frequencyMhz} MHz"
            else -> "Unavailable"
        }
    )
    StatusLine(label = "Availability", value = summary.availability)
    StatusLine(label = "Last sample", value = summary.sampleTime ?: "No sample yet")
    StatusLine(label = "Last upload status", value = summary.uploadStatus)
    StatusLine(label = "Gateway probe", value = summary.gatewayProbe)
    StatusLine(label = "DNS probe", value = summary.dnsProbe)
    StatusLine(label = "HTTP probe", value = summary.httpProbe)
}

@Composable
private fun StatusLine(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(text = label, style = MaterialTheme.typography.labelLarge)
        Text(text = value, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun CounterRow(counters: TelemetryCounters) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Counter("Collected", counters.collected)
        Counter("Pending", counters.pending)
        Counter("Synced", counters.synced)
        Counter("Failed", counters.failed)
    }
}

@Composable
private fun Counter(label: String, value: Int) {
    Column {
        Text(text = value.toString(), style = MaterialTheme.typography.titleLarge)
        Text(text = label, style = MaterialTheme.typography.labelMedium)
    }
}
