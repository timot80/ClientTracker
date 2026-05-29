package com.wifiops.probe.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
    activeSessionId: String? = null,
    modifier: Modifier = Modifier,
    onBack: () -> Unit,
    onExportSummary: (String) -> Unit,
    onExportRecords: (String) -> Unit,
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
                text = "No sessions yet. Completed sessions will appear here.",
                style = MaterialTheme.typography.bodyMedium
            )
        } else {
            Text(
                text = "Export records shares raw JSON and may include network identifiers, IP information, timestamps, device model, and receiver destination.",
                style = MaterialTheme.typography.bodySmall
            )
            sessions.forEach { session ->
                SessionSummaryRow(
                    session = session,
                    isActive = session.sessionId == activeSessionId,
                    onExportSummary = onExportSummary,
                    onExportRecords = onExportRecords,
                    onDelete = onDelete
                )
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
    isActive: Boolean,
    onExportSummary: (String) -> Unit,
    onExportRecords: (String) -> Unit,
    onDelete: (String) -> Unit
) {
    var confirmingDelete by remember(session.sessionId) { mutableStateOf(false) }

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(text = session.sessionId, style = MaterialTheme.typography.titleMedium)
        Text(text = session.receiverUrl, style = MaterialTheme.typography.bodyMedium)
        Text(
            text = "Collected ${session.counters.collected}  Pending ${session.counters.pending}  Synced ${session.counters.synced}  Failed ${session.counters.failed}",
            style = MaterialTheme.typography.bodySmall
        )
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = { onExportSummary(session.sessionId) },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Export summary")
            }
            OutlinedButton(
                onClick = { onExportRecords(session.sessionId) },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Export records")
            }
            OutlinedButton(
                onClick = { confirmingDelete = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Delete session")
            }
        }
    }

    if (confirmingDelete) {
        AlertDialog(
            onDismissRequest = { confirmingDelete = false },
            title = { Text("Delete session ${session.sessionId}?") },
            text = {
                Text(
                    if (isActive) {
                        "This session is active. Deleting it will stop collection and remove local records for this session. Saved receiver details will remain."
                    } else {
                        "This removes local records for this session. Saved receiver details will remain."
                    }
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmingDelete = false
                        onDelete(session.sessionId)
                    }
                ) {
                    Text("Delete session")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmingDelete = false }) {
                    Text("Cancel")
                }
            }
        )
    }
}
