package com.bobine.app

import android.Manifest
import android.os.Build
import android.provider.Settings
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class StartupPermissionsTest {

    @Test
    fun runtimePermissionsIncludeNotificationsAndNearbyBluetoothOnApi33Plus() {
        assertEquals(
            listOf(
                Manifest.permission.POST_NOTIFICATIONS,
                Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.BLUETOOTH_SCAN,
            ),
            startupRuntimePermissions(Build.VERSION_CODES.UPSIDE_DOWN_CAKE, hasBluetooth = true),
        )
        assertEquals(
            listOf(Manifest.permission.POST_NOTIFICATIONS),
            startupRuntimePermissions(Build.VERSION_CODES.UPSIDE_DOWN_CAKE, hasBluetooth = false),
        )
        assertEquals(
            listOf(Manifest.permission.BLUETOOTH_CONNECT, Manifest.permission.BLUETOOTH_SCAN),
            startupRuntimePermissions(Build.VERSION_CODES.S_V2, hasBluetooth = true),
        )
    }

    @Test
    fun githubBuildWalksAllFourStepsSequentiallyWithoutOverlap() {
        val asked = mutableSetOf<StartupPermissionStep>()
        val sequence = mutableListOf<StartupPermissionStep>()
        val runtime = listOf(
            Manifest.permission.POST_NOTIFICATIONS,
            Manifest.permission.BLUETOOTH_CONNECT,
            Manifest.permission.BLUETOOTH_SCAN,
        )
        while (true) {
            val step = nextStartupPermissionStep(
                StartupPermissionState(
                    missingRuntime = runtime,
                    storeBuild = false,
                    canRequestPackageInstalls = false,
                    ignoringBatteryOptimizations = false,
                    canDrawOverlays = false,
                    askedSteps = asked,
                ),
            ) ?: break
            sequence.add(step)
            asked.add(step)
        }
        assertEquals(
            listOf(
                StartupPermissionStep.RUNTIME,
                StartupPermissionStep.INSTALL_PACKAGES,
                StartupPermissionStep.BATTERY_OPTIMIZATION,
                StartupPermissionStep.OVERLAY,
            ),
            sequence,
        )
    }

    @Test
    fun playStoreBuildNeverRequestsUnknownAppSources() {
        val asked = mutableSetOf<StartupPermissionStep>()
        val sequence = mutableListOf<StartupPermissionStep>()
        while (true) {
            val step = nextStartupPermissionStep(
                StartupPermissionState(
                    missingRuntime = listOf(Manifest.permission.POST_NOTIFICATIONS),
                    storeBuild = true,
                    canRequestPackageInstalls = false,
                    ignoringBatteryOptimizations = false,
                    canDrawOverlays = false,
                    askedSteps = asked,
                ),
            ) ?: break
            sequence.add(step)
            asked.add(step)
        }
        assertEquals(
            listOf(
                StartupPermissionStep.RUNTIME,
                StartupPermissionStep.BATTERY_OPTIMIZATION,
                StartupPermissionStep.OVERLAY,
            ),
            sequence,
        )
    }

    @Test
    fun alreadyGrantedStepsAreSkipped() {
        val step = nextStartupPermissionStep(
            StartupPermissionState(
                missingRuntime = emptyList(),
                storeBuild = false,
                canRequestPackageInstalls = true,
                ignoringBatteryOptimizations = true,
                canDrawOverlays = true,
                askedSteps = emptySet(),
            ),
        )
        assertNull(step)
    }

    @Test
    fun packageSettingsSpecsIncludeGenericFallbackForTvWhenRequested() {
        assertEquals(
            listOf(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES to "package:com.bobine.app.tv",
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES to null,
            ),
            packageSettingsSpecs(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, "com.bobine.app.tv", allowGenericFallback = true),
        )
        assertEquals(
            listOf(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS to "package:com.bobine.app"),
            packageSettingsSpecs(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, "com.bobine.app", allowGenericFallback = false),
        )
    }
}
