package com.bobine.app

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.util.Log
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

object Permissions {
    private const val REQUEST_CODE = 4107
    private const val PREFS = "bobine_permissions"

    @Volatile private var pending: List<String> = emptyList()

    val bluetooth: List<String> = listOf(Manifest.permission.BLUETOOTH_CONNECT, Manifest.permission.BLUETOOTH_SCAN)

    fun runtime(context: Context): List<String> = buildList {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) add(Manifest.permission.POST_NOTIFICATIONS)
        if (context.packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH)) addAll(bluetooth)
    }

    fun missing(context: Context, wanted: List<String>): List<String> =
        wanted.filter { ContextCompat.checkSelfPermission(context, it) != PackageManager.PERMISSION_GRANTED }

    fun requestNew(activity: Activity) {
        val prefs = activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        ask(activity, missing(activity, runtime(activity)).filterNot { prefs.getBoolean(it, false) })
    }

    fun request(activity: Activity, wanted: List<String>) {
        val absent = missing(activity, wanted)
        if (absent.isEmpty()) return
        val prefs = activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val blocked = absent.any { prefs.getBoolean(it, false) && !ActivityCompat.shouldShowRequestPermissionRationale(activity, it) }
        if (blocked) openAppSettings(activity) else ask(activity, absent)
    }

    private fun ask(activity: Activity, permissions: List<String>) {
        if (permissions.isEmpty()) return
        activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .apply { permissions.forEach { putBoolean(it, true) } }.apply()
        ActivityCompat.requestPermissions(activity, permissions.toTypedArray(), REQUEST_CODE)
    }

    fun requestWhenVisible(context: Context, wanted: List<String>) {
        val activity = MainActivity.activeActivity?.get()
        if (activity != null && !activity.isFinishing) {
            activity.runOnUiThread { request(activity, wanted) }
        } else {
            pending = missing(context, wanted)
        }
    }

    fun resumePending(activity: Activity) {
        val wanted = pending
        pending = emptyList()
        if (wanted.isNotEmpty()) request(activity, wanted)
    }

    private fun openAppSettings(activity: Activity) {
        try {
            activity.startActivity(
                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${activity.packageName}"))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        } catch (e: Exception) {
            Log.w("Permissions", "Réglages de l'application indisponibles sur cet appareil", e)
        }
    }
}
