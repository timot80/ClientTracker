package com.wifiops.probe.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val WifiOpsLightColors = lightColorScheme(
    primary = Color(0xFF005EB8),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD7E7FF),
    onPrimaryContainer = Color(0xFF002F5F),
    secondary = Color(0xFF9A6400),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFE0A3),
    onSecondaryContainer = Color(0xFF2E1D00),
    tertiary = Color(0xFF147A3D),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFB9F3C7),
    onTertiaryContainer = Color(0xFF00210B),
    error = Color(0xFFBA1A1A),
    background = Color(0xFFFBFCFE),
    onBackground = Color(0xFF1A1C1E),
    surface = Color(0xFFFBFCFE),
    onSurface = Color(0xFF1A1C1E),
    surfaceVariant = Color(0xFFE0E3EB),
    onSurfaceVariant = Color(0xFF43474E),
    outline = Color(0xFF73777F)
)

@Composable
fun WifiOpsTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = WifiOpsLightColors,
        content = content
    )
}
