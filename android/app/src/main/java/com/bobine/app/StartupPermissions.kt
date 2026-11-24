package com.bobine.app

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

private const val TAG = "StartupPermissions"
private const val PREFS_PERMISSIONS = "bobine_permissions"
private const val PREFS_LEGACY_NATIVE = "bobine_native"
private const val LEGACY_OVERLAY_ASKED_KEY = "overlay_permission_asked"

enum class StartupPermissionStep(val prefKey: String) {
    RUNTIME("startup_runtime"),
    INSTALL_PACKAGES("startup_install_packages"),
    BATTERY_OPTIMIZATION("startup_battery_optimization"),
    OVERLAY("startup_overlay"),
}

data class StartupPermissionState(
    val missingRuntime: List<String>,
    val storeBuild: Boolean,
    val canRequestPackageInstalls: Boolean,
    val ignoringBatteryOptimizations: Boolean,
    val canDrawOverlays: Boolean,
    val askedSteps: Set<StartupPermissionStep>,
)

fun startupRuntimePermissions(sdkInt: Int, hasBluetooth: Boolean): List<String> = buildList {
    if (sdkInt >= Build.VERSION_CODES.TIRAMISU) add(Manifest.permission.POST_NOTIFICATIONS)
    if (hasBluetooth) {
        add(Manifest.permission.BLUETOOTH_CONNECT)
        add(Manifest.permission.BLUETOOTH_SCAN)
    }
}

fun nextStartupPermissionStep(state: StartupPermissionState): StartupPermissionStep? = when {
    state.missingRuntime.isNotEmpty() && StartupPermissionStep.RUNTIME !in state.askedSteps ->
        StartupPermissionStep.RUNTIME
    !state.storeBuild && !state.canRequestPackageInstalls && StartupPermissionStep.INSTALL_PACKAGES !in state.askedSteps ->
        StartupPermissionStep.INSTALL_PACKAGES
    !state.ignoringBatteryOptimizations && StartupPermissionStep.BATTERY_OPTIMIZATION !in state.askedSteps ->
        StartupPermissionStep.BATTERY_OPTIMIZATION
    !state.canDrawOverlays && StartupPermissionStep.OVERLAY !in state.askedSteps ->
        StartupPermissionStep.OVERLAY
    else -> null
}

fun packageSettingsSpecs(action: String, packageName: String, allowGenericFallback: Boolean): List<Pair<String, String?>> =
    buildList {
        add(action to "package:$packageName")
        if (allowGenericFallback) add(action to null)
    }

class StartupPermissionFlow(private val activity: AppCompatActivity) {
    private val runtimeLauncher: ActivityResultLauncher<Array<String>> =
        activity.registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { advance() }

    private val settingsLauncher: ActivityResultLauncher<Intent> =
        activity.registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { advance() }

    fun start() = advance()

    private fun readState(): StartupPermissionState {
        val prefs = activity.getSharedPreferences(PREFS_PERMISSIONS, Context.MODE_PRIVATE)
        val legacyPrefs = activity.getSharedPreferences(PREFS_LEGACY_NATIVE, Context.MODE_PRIVATE)
        val missingRuntime = Permissions.missing(activity, Permissions.runtime(activity))
            .filterNot { prefs.getBoolean(it, false) }
        val asked = StartupPermissionStep.entries.filterTo(mutableSetOf()) { prefs.getBoolean(it.prefKey, false) }
        if (legacyPrefs.getBoolean(LEGACY_OVERLAY_ASKED_KEY, false)) asked.add(StartupPermissionStep.OVERLAY)
        val power = activity.getSystemService(PowerManager::class.java)
        return StartupPermissionState(
            missingRuntime = missingRuntime,
            storeBuild = BuildConfig.STORE_BUILD,
            canRequestPackageInstalls = activity.packageManager.canRequestPackageInstalls(),
            ignoringBatteryOptimizations = power?.isIgnoringBatteryOptimizations(activity.packageName) == true,
            canDrawOverlays = Settings.canDrawOverlays(activity),
            askedSteps = asked,
        )
    }

    private fun markStepAsked(step: StartupPermissionStep, runtimePermissions: List<String> = emptyList()) {
        val editor = activity.getSharedPreferences(PREFS_PERMISSIONS, Context.MODE_PRIVATE).edit()
        editor.putBoolean(step.prefKey, true)
        runtimePermissions.forEach { editor.putBoolean(it, true) }
        editor.apply()
    }

    private fun launchSettings(action: String, allowGenericFallback: Boolean): Boolean {
        for ((intentAction, uriText) in packageSettingsSpecs(action, activity.packageName, allowGenericFallback)) {
            val intent = if (uriText != null) Intent(intentAction, Uri.parse(uriText)) else Intent(intentAction)
            try {
                settingsLauncher.launch(intent)
                return true
            } catch (e: ActivityNotFoundException) {
                Log.w(TAG, "Ecran systeme $intentAction (${uriText ?: "generique"}) indisponible", e)
            } catch (e: SecurityException) {
                Log.w(TAG, "Ouverture de $intentAction refusee par le systeme", e)
            }
        }
        return false
    }

    private fun advance() {
        if (activity.isFinishing || activity.isDestroyed) return
        val state = readState()
        val step = nextStartupPermissionStep(state) ?: return
        when (step) {
            StartupPermissionStep.RUNTIME -> {
                markStepAsked(step, state.missingRuntime)
                runtimeLauncher.launch(state.missingRuntime.toTypedArray())
            }
            StartupPermissionStep.INSTALL_PACKAGES -> {
                markStepAsked(step)
                if (!launchSettings(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, allowGenericFallback = true)) advance()
            }
            StartupPermissionStep.BATTERY_OPTIMIZATION -> {
                markStepAsked(step)
                if (!launchSettings(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, allowGenericFallback = false)) advance()
            }
            StartupPermissionStep.OVERLAY -> {
                markStepAsked(step)
                if (!launchSettings(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, allowGenericFallback = true)) advance()
            }
        }
    }
}
