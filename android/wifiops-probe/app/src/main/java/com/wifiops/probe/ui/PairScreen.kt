package com.wifiops.probe.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.wifiops.probe.pairing.PairingPayload

@Composable
fun PairScreen(
    modifier: Modifier = Modifier,
    savedPairing: PairingPayload? = null,
    cameraPermissionGranted: Boolean = false,
    cameraPermissionMessage: String? = null,
    onRequestCameraPermission: () -> Unit = {},
    onPaired: (PairingPayload) -> Unit
) {
    var receiverUrl by remember(savedPairing) { mutableStateOf(savedPairing?.receiverUrl.orEmpty()) }
    var sessionId by remember(savedPairing) { mutableStateOf(savedPairing?.sessionId.orEmpty()) }
    var token by remember(savedPairing) { mutableStateOf(savedPairing?.token.orEmpty()) }
    var payloadJson by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var scanning by remember { mutableStateOf(false) }
    var waitingForCameraPermission by remember { mutableStateOf(false) }
    var fallbackMode by remember { mutableStateOf<SetupFallbackMode?>(null) }

    LaunchedEffect(cameraPermissionGranted, waitingForCameraPermission) {
        if (cameraPermissionGranted && waitingForCameraPermission) {
            scanning = true
            waitingForCameraPermission = false
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .statusBarsPadding()
            .navigationBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 18.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            text = "Receiver setup",
            style = MaterialTheme.typography.headlineSmall
        )
        Text(
            text = "Scan the receiver QR code, paste setup JSON, or enter receiver details.",
            style = MaterialTheme.typography.bodyMedium
        )
        Button(
            onClick = {
                error = null
                if (cameraPermissionGranted) {
                    scanning = true
                } else {
                    waitingForCameraPermission = true
                    onRequestCameraPermission()
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Scan receiver QR code")
        }

        cameraPermissionMessage?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium
            )
        }

        if (scanning) {
            Text(
                text = "Point the camera at the receiver setup QR code.",
                style = MaterialTheme.typography.bodyMedium
            )
            QrScannerView(
                onQrText = { raw ->
                    runCatching {
                        PairingPayload.parse(raw)
                    }.onSuccess {
                        error = null
                        receiverUrl = it.receiverUrl
                        sessionId = it.sessionId
                        token = it.token
                        scanning = false
                        onPaired(it)
                    }.onFailure {
                        error = it.message ?: "QR code does not contain receiver setup JSON"
                    }
                },
                onError = {
                    error = it
                }
            )
            OutlinedButton(
                onClick = { scanning = false },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Cancel scan")
            }
        }

        savedPairing?.let { saved ->
            HorizontalDivider()
            SectionTitle("Saved receiver")
            Text(text = saved.receiverUrl, style = MaterialTheme.typography.bodyMedium)
            OutlinedButton(
                onClick = { onPaired(saved) },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Use saved receiver")
            }
        }

        error?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium
            )
        }

        HorizontalDivider()
        SectionTitle("Fallback setup")
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            OutlinedButton(
                onClick = { fallbackMode = SetupFallbackMode.PasteJson },
                modifier = Modifier.weight(1f)
            ) {
                Text("Paste JSON")
            }
            OutlinedButton(
                onClick = { fallbackMode = SetupFallbackMode.ManualEntry },
                modifier = Modifier.weight(1f)
            ) {
                Text("Enter manually")
            }
        }

        when (fallbackMode) {
            SetupFallbackMode.PasteJson -> PasteJsonSection(
                payloadJson = payloadJson,
                onPayloadJsonChange = { payloadJson = it },
                onSubmit = {
                    runCatching {
                        PairingPayload.parse(payloadJson)
                    }.onSuccess {
                        error = null
                        receiverUrl = it.receiverUrl
                        sessionId = it.sessionId
                        token = it.token
                        onPaired(it)
                    }.onFailure {
                        error = it.message ?: "Receiver setup JSON is invalid"
                    }
                }
            )

            SetupFallbackMode.ManualEntry -> ManualEntrySection(
                receiverUrl = receiverUrl,
                sessionId = sessionId,
                token = token,
                onReceiverUrlChange = { receiverUrl = it },
                onSessionIdChange = { sessionId = it },
                onTokenChange = { token = it },
                onSubmit = {
                    runCatching {
                        PairingPayload.fromManualFields(receiverUrl, sessionId, token)
                    }.onSuccess {
                        error = null
                        onPaired(it)
                    }.onFailure {
                        error = it.message ?: "Receiver setup values are invalid"
                    }
                }
            )

            null -> Text(
                text = "Use these only if scanning is not available.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

private enum class SetupFallbackMode {
    PasteJson,
    ManualEntry
}

@Composable
private fun SectionTitle(text: String) {
    Text(text = text, style = MaterialTheme.typography.titleMedium)
}

@Composable
private fun PasteJsonSection(
    payloadJson: String,
    onPayloadJsonChange: (String) -> Unit,
    onSubmit: () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedTextField(
            value = payloadJson,
            onValueChange = onPayloadJsonChange,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 120.dp),
            label = { Text("Receiver setup JSON") }
        )
        Button(
            onClick = onSubmit,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Use pasted setup")
        }
    }
}

@Composable
private fun ManualEntrySection(
    receiverUrl: String,
    sessionId: String,
    token: String,
    onReceiverUrlChange: (String) -> Unit,
    onSessionIdChange: (String) -> Unit,
    onTokenChange: (String) -> Unit,
    onSubmit: () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedTextField(
            value = receiverUrl,
            onValueChange = onReceiverUrlChange,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Receiver URL") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri)
        )
        OutlinedTextField(
            value = sessionId,
            onValueChange = onSessionIdChange,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Session ID") }
        )
        OutlinedTextField(
            value = token,
            onValueChange = onTokenChange,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Token") },
            visualTransformation = PasswordVisualTransformation()
        )

        Button(
            onClick = onSubmit,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Use receiver details")
        }
    }
}
