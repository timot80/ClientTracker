package com.wifiops.probe.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
    onPaired: (PairingPayload) -> Unit
) {
    var receiverUrl by remember(savedPairing) { mutableStateOf(savedPairing?.receiverUrl.orEmpty()) }
    var sessionId by remember(savedPairing) { mutableStateOf(savedPairing?.sessionId.orEmpty()) }
    var token by remember(savedPairing) { mutableStateOf(savedPairing?.token.orEmpty()) }
    var payloadJson by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(
            text = "Receiver setup",
            style = MaterialTheme.typography.headlineSmall
        )
        Text(
            text = "Enter the receiver values shown by the wifiops receiver setup command.",
            style = MaterialTheme.typography.bodyMedium
        )

        savedPairing?.let { saved ->
            Text(
                text = "Saved receiver",
                style = MaterialTheme.typography.titleMedium
            )
            Text(
                text = saved.receiverUrl,
                style = MaterialTheme.typography.bodyMedium
            )
            OutlinedButton(
                onClick = { onPaired(saved) },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Use saved receiver")
            }
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Set up new receiver",
                style = MaterialTheme.typography.titleMedium
            )
        }

        OutlinedTextField(
            value = receiverUrl,
            onValueChange = { receiverUrl = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Receiver URL") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri)
        )
        OutlinedTextField(
            value = sessionId,
            onValueChange = { sessionId = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Session ID") }
        )
        OutlinedTextField(
            value = token,
            onValueChange = { token = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Token") },
            visualTransformation = PasswordVisualTransformation()
        )

        Button(
            onClick = {
                runCatching {
                    PairingPayload.fromManualFields(receiverUrl, sessionId, token)
                }.onSuccess {
                    error = null
                    onPaired(it)
                }.onFailure {
                    error = it.message ?: "Receiver setup values are invalid"
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Set up new receiver")
        }

        Spacer(Modifier.height(8.dp))
        Text(
            text = "Or paste receiver setup JSON",
            style = MaterialTheme.typography.titleMedium
        )
        OutlinedTextField(
            value = payloadJson,
            onValueChange = { payloadJson = it },
            modifier = Modifier
                .fillMaxWidth()
                .height(112.dp),
            label = { Text("Receiver setup JSON") }
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.End
        ) {
            OutlinedButton(
                onClick = {
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
            ) {
                Text("Use JSON")
            }
        }

        error?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium
            )
        }
    }
}
