package com.wifiops.probe.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
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
            .statusBarsPadding()
            .navigationBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 18.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        HeaderStatus(state)

        state.permissionMessage?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium
            )
        }

        SessionActions(
            running = state.running,
            onStart = onStart,
            onStop = onStop,
            onPairDifferentReceiver = onPairDifferentReceiver
        )

        HorizontalDivider()
        SectionTitle("Latest Wi-Fi sample")
        LatestTelemetry(state.latestTelemetry)

        HorizontalDivider()
        SectionTitle("Counters")
        CounterRow(state.counters)

        if (state.preflightChecks.isNotEmpty()) {
            HorizontalDivider()
            SectionTitle("Preflight")
            state.preflightChecks
                .sortedBy { if (it.state == PreflightState.Ready) 1 else 0 }
                .forEach { check ->
                    PreflightRow(check = check, onPreflightAction = onPreflightAction)
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
private fun HeaderStatus(state: SessionUiState) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = "Active session", style = MaterialTheme.typography.headlineSmall)
                Text(
                    text = state.pairing.sessionId,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            Column {
                Text(text = "Service", style = MaterialTheme.typography.labelLarge)
                Text(
                    text = if (state.running) "Running" else "Stopped",
                    color = if (state.running) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.titleMedium
                )
            }
        }
        CompactStatusLine(label = "Receiver", value = state.pairing.receiverUrl)
        CompactStatusLine(
            label = "Reachability",
            value = when (state.receiverReachable) {
                true -> "Reachable"
                false -> "Unreachable"
                null -> "Not checked"
            }
        )
    }
}

@Composable
private fun SessionActions(
    running: Boolean,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onPairDifferentReceiver: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        if (running) {
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
}

@Composable
private fun SectionTitle(text: String) {
    Text(text = text, style = MaterialTheme.typography.titleMedium)
}

@Composable
private fun PreflightRow(
    check: PreflightCheck,
    onPreflightAction: (PreflightRecoveryAction) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = check.title,
                style = MaterialTheme.typography.labelLarge,
                modifier = Modifier.weight(1f)
            )
            Text(
                text = check.state.label,
                color = preflightStateColor(check.state),
                style = MaterialTheme.typography.labelLarge
            )
        }
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
        CompactStatusLine(label = "Last sample", value = "No sample yet")
        CompactStatusLine(label = "Availability", value = "Unavailable")
        return
    }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            StatusTile(label = "RSSI", value = summary.rssi?.let { "$it dBm" } ?: "Unavailable", modifier = Modifier.weight(1f))
            StatusTile(
                label = "Channel",
                value = when {
                    summary.channel != null && summary.frequencyMhz != null -> "${summary.channel} / ${summary.frequencyMhz} MHz"
                    summary.channel != null -> summary.channel
                    summary.frequencyMhz != null -> "${summary.frequencyMhz} MHz"
                    else -> "Unavailable"
                },
                modifier = Modifier.weight(1f)
            )
        }
        CompactStatusLine(label = "SSID", value = summary.ssid ?: "Unavailable")
        CompactStatusLine(label = "BSSID", value = summary.bssid ?: "Unavailable")
        CompactStatusLine(label = "Availability", value = summary.availability)
        CompactStatusLine(label = "Upload", value = summary.uploadStatus)
        CompactStatusLine(label = "Last sample", value = summary.sampleTime ?: "No sample yet")
        CompactStatusLine(label = "Gateway probe", value = summary.gatewayProbe)
        CompactStatusLine(label = "DNS probe", value = summary.dnsProbe)
        CompactStatusLine(label = "HTTP probe", value = summary.httpProbe)
    }
}

@Composable
private fun CompactStatusLine(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(text = label, style = MaterialTheme.typography.labelLarge)
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
            maxLines = 2,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable
private fun StatusTile(label: String, value: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        Text(text = label, style = MaterialTheme.typography.labelLarge)
        Text(text = value, style = MaterialTheme.typography.titleMedium)
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
