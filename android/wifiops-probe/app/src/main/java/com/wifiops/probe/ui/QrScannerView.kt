package com.wifiops.probe.ui

import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

@Composable
fun QrScannerView(
    modifier: Modifier = Modifier,
    onQrText: (String) -> Unit,
    onError: (String) -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember {
        PreviewView(context).apply {
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            scaleType = PreviewView.ScaleType.FILL_CENTER
        }
    }
    val cameraExecutor = remember { Executors.newSingleThreadExecutor() }
    val scanner = remember { BarcodeScanning.getClient() }
    val scannerActive = remember { AtomicBoolean(true) }
    var hasResult by remember { mutableStateOf(false) }

    AndroidView(
        factory = { previewView },
        modifier = modifier
            .fillMaxWidth()
            .aspectRatio(3f / 4f)
    )

    LaunchedEffect(previewView, lifecycleOwner) {
        scannerActive.set(true)
        val cameraProvider = runCatching {
            ProcessCameraProvider.getInstance(context).get()
        }.getOrElse {
            if (scannerActive.get()) {
                onError("Unable to start camera preview.")
            }
            return@LaunchedEffect
        }
        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(previewView.surfaceProvider)
        }
        val analysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
            .also { imageAnalysis ->
                imageAnalysis.setAnalyzer(cameraExecutor) { imageProxy ->
                    analyzeQrImage(
                        imageProxy = imageProxy,
                        scanner = scanner,
                        isActive = { scannerActive.get() },
                        alreadyAccepted = { hasResult },
                        onQrText = {
                            if (scannerActive.get()) {
                                hasResult = true
                                onQrText(it)
                            }
                        },
                        onError = onError
                    )
                }
            }

        runCatching {
            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(
                lifecycleOwner,
                CameraSelector.DEFAULT_BACK_CAMERA,
                preview,
                analysis
            )
        }.onFailure {
            if (scannerActive.get()) {
                onError("Unable to bind camera scanner.")
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            scannerActive.set(false)
            cameraExecutor.shutdown()
            runCatching {
                ProcessCameraProvider.getInstance(context).get().unbindAll()
            }
            scanner.close()
        }
    }
}

@androidx.annotation.OptIn(ExperimentalGetImage::class)
private fun analyzeQrImage(
    imageProxy: ImageProxy,
    scanner: com.google.mlkit.vision.barcode.BarcodeScanner,
    isActive: () -> Boolean,
    alreadyAccepted: () -> Boolean,
    onQrText: (String) -> Unit,
    onError: (String) -> Unit
) {
    if (!isActive() || alreadyAccepted()) {
        imageProxy.close()
        return
    }
    val mediaImage = imageProxy.image
    if (mediaImage == null) {
        imageProxy.close()
        return
    }
    val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
    scanner.process(image)
        .addOnSuccessListener { barcodes ->
            if (!isActive()) {
                return@addOnSuccessListener
            }
            val rawValue = barcodes
                .firstOrNull { it.format == Barcode.FORMAT_QR_CODE && !it.rawValue.isNullOrBlank() }
                ?.rawValue
            if (!rawValue.isNullOrBlank()) {
                onQrText(rawValue)
            }
        }
        .addOnFailureListener {
            if (isActive()) {
                onError("Unable to read QR code.")
            }
        }
        .addOnCompleteListener {
            imageProxy.close()
        }
}
