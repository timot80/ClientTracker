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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

data class SessionSummary(
    val sessionId: String,
    val receiverUrl: String,
    val counters: TelemetryCounters = TelemetryCounters()
)

@Composable
fun SessionHistoryScreen(
    sessions: List<SessionSummary>,
    modifier: Modifier = Modifier,
    onBack: () -> Unit,
    onExport: (String) -> Unit,
    onDelete: (String) -> Unit
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            text = "Session history",
            style = MaterialTheme.typography.headlineSmall
        )

        if (sessions.isEmpty()) {
            Text(
                text = "Previous sessions will appear here after local session persistence is enabled.",
                style = MaterialTheme.typography.bodyMedium
            )
        } else {
            sessions.forEach { session ->
                SessionSummaryRow(session = session, onExport = onExport, onDelete = onDelete)
            }
        }

        Button(
            onClick = onBack,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Back to session")
        }
    }
}

@Composable
private fun SessionSummaryRow(
    session: SessionSummary,
    onExport: (String) -> Unit,
    onDelete: (String) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(text = session.sessionId, style = MaterialTheme.typography.titleMedium)
        Text(text = session.receiverUrl, style = MaterialTheme.typography.bodyMedium)
        Text(
            text = "Collected ${session.counters.collected}  Pending ${session.counters.pending}  Synced ${session.counters.synced}  Failed ${session.counters.failed}",
            style = MaterialTheme.typography.bodySmall
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { onExport(session.sessionId) }) {
                Text("Export")
            }
            OutlinedButton(onClick = { onDelete(session.sessionId) }) {
                Text("Delete")
            }
        }
    }
}
