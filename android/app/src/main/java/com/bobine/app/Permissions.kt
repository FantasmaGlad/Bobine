package com.bobine.app

import android.Manifest
import android.app.Activity
import android.bluetooth.BluetoothManager
import android.content.ActivityNotFoundException
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

    fun hasBluetooth(context: Context): Boolean {
        val pm = context.packageManager
        if (pm.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH) || pm.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) {
            return true
        }
        return (context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter != null
    }

    fun runtime(context: Context): List<String> =
        startupRuntimePermissions(Build.VERSION.SDK_INT, hasBluetooth(context))

    fun missing(context: Context, wanted: List<String>): List<String> =
        wanted.filter { ContextCompat.checkSelfPermission(context, it) != PackageManager.PERMISSION_GRANTED }

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

    fun openPackageSettings(context: Context, action: String, allowGenericFallback: Boolean = false): Boolean {
        for ((intentAction, uriText) in packageSettingsSpecs(action, context.packageName, allowGenericFallback)) {
            val intent = (if (uriText != null) Intent(intentAction, Uri.parse(uriText)) else Intent(intentAction))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            try {
                context.startActivity(intent)
                return true
            } catch (e: ActivityNotFoundException) {
                Log.w("Permissions", "Ecran systeme $intentAction (${uriText ?: "generique"}) indisponible", e)
            } catch (e: Exception) {
                Log.w("Permissions", "Ouverture de $intentAction impossible", e)
            }
        }
        return false
    }

    private fun openAppSettings(activity: Activity) {
        openPackageSettings(activity, Settings.ACTION_APPLICATION_DETAILS_SETTINGS, allowGenericFallback = false)
    }
}
