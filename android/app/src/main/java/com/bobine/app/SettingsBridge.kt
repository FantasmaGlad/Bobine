package com.bobine.app

import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.util.Log

private const val TAG = "SettingsBridge"

object SettingsBridge {
    fun openSettings(context: Context, target: String): String = try {
        val action = when (target) {
            "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
            "sound" -> Settings.ACTION_SOUND_SETTINGS
            else -> return bridgeError("bad_target", "Réglage inconnu.")
        }
        try {
            context.startActivity(Intent(action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (e: android.content.ActivityNotFoundException) {
            context.startActivity(Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        bridgeOk()
    } catch (e: Exception) {
        Log.w(TAG, "openSettings", e)
        bridgeError("settings_failed", "Impossible d'ouvrir les réglages d'Android.")
    }
}
