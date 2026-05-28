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
import androidx.compose.ui.unit.dp
import com.wifiops.probe.pairing.PairingPayload

data class TelemetryCounters(
    val collected: Int = 0,
    val pending: Int = 0,
    val synced: Int = 0,
    val failed: Int = 0
)

data class SessionUiState(
    val pairing: PairingPayload,
    val running: Boolean = false,
    val receiverReachable: Boolean? = null,
    val counters: TelemetryCounters = TelemetryCounters(),
    val permissionMessage: String? = null
)

@Composable
fun SessionScreen(
    state: SessionUiState,
    modifier: Modifier = Modifier,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onPairDifferentReceiver: () -> Unit,
    onShowHistory: () -> Unit
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            text = "Session controls",
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
                    Text("Stop")
                }
            } else {
                Button(onClick = onStart, modifier = Modifier.weight(1f)) {
                    Text("Start")
                }
            }
            OutlinedButton(onClick = onPairDifferentReceiver, modifier = Modifier.weight(1f)) {
                Text("Pair")
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
