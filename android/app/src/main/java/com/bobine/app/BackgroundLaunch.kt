package com.bobine.app

import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Handler
import android.provider.Settings
import android.util.Log
import android.view.View
import android.view.WindowManager

private const val TAG = "BackgroundLaunch"

private fun startScreen(context: Context, launch: Intent): Boolean = try {
    context.startActivity(launch)
    true
} catch (e: Exception) {
    Log.w(TAG, "Ouverture de l'ecran refusee : ${e.message}")
    false
}

fun launchScreenFromBackground(context: Context, handler: Handler) {
    val launch = Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
    if (!Settings.canDrawOverlays(context)) {
        Log.w(TAG, "Permission d'affichage par-dessus les autres applications absente : l'ecran s'ouvrira au lancement manuel")
        startScreen(context, launch)
        return
    }
    val windowManager = context.getSystemService(WindowManager::class.java)
    val anchor = View(context)
    val params = WindowManager.LayoutParams(
        1, 1,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
        PixelFormat.TRANSLUCENT,
    )
    try {
        windowManager.addView(anchor, params)
    } catch (e: Exception) {
        Log.w(TAG, "Fenetre d'ancrage impossible : ${e.message}")
    }
    handler.postDelayed({
        if (startScreen(context, launch)) Log.i(TAG, "Ecran ouvert apres le demarrage")
        handler.postDelayed({
            try {
                windowManager.removeView(anchor)
            } catch (_: Exception) {
            }
        }, 4000)
    }, 400)
}
