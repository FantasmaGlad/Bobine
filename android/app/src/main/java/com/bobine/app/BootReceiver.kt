package com.bobine.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat

private const val TAG = "BootReceiver"

/**
 * Relance Bobine après un redémarrage de l'appareil ou une mise à jour de l'application :
 * le serveur embarqué (service au premier plan) repart seul, puis l'écran s'ouvre. Sans ce
 * récepteur, rien ne redémarrait le service : l'écran restait vide jusqu'à un lancement manuel.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        val afterUpdate = action == Intent.ACTION_MY_PACKAGE_REPLACED
        if (!afterUpdate && !StartOnBoot.isEnabled(context)) {
            Log.i(TAG, "Demarrage automatique desactive ($action) : rien a relancer")
            return
        }
        Log.i(TAG, "Relance de Bobine apres $action")
        try {
            ContextCompat.startForegroundService(
                context,
                Intent(context, BobineForegroundService::class.java).putExtra(BobineForegroundService.EXTRA_LAUNCH_SCREEN, true),
            )
        } catch (e: Exception) {
            Log.w(TAG, "Demarrage du service refuse : ${e.message}")
        }
    }
}
