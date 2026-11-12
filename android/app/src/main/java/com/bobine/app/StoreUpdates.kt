package com.bobine.app

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import org.json.JSONObject

private const val TAG = "StoreUpdates"
private const val PROVIDER_CLASS = "com.bobine.app.PlayUpdateProvider"

interface StoreUpdateProvider {
    fun check(context: Context): String

    fun start(context: Context): String

    fun complete(context: Context): String
}

object StoreUpdates {
    private val provider: StoreUpdateProvider? by lazy {
        if (!BuildConfig.STORE_BUILD) return@lazy null
        try {
            Class.forName(PROVIDER_CLASS).getDeclaredConstructor().newInstance() as StoreUpdateProvider
        } catch (e: Exception) {
            Log.w(TAG, "Fournisseur de mises à jour de la boutique indisponible", e)
            null
        }
    }

    private fun unavailable(): String =
        JSONObject().put("state", "unavailable").put("message", "Les mises à jour intégrées ne sont pas disponibles sur cette installation.").toString()

    fun check(context: Context): String = try { provider?.check(context) ?: unavailable() } catch (e: Exception) {
        Log.w(TAG, "check", e); unavailable()
    }

    fun start(context: Context): String = try { provider?.start(context) ?: unavailable() } catch (e: Exception) {
        Log.w(TAG, "start", e); unavailable()
    }

    fun complete(context: Context): String = try { provider?.complete(context) ?: unavailable() } catch (e: Exception) {
        Log.w(TAG, "complete", e); unavailable()
    }

    fun openListing(context: Context): String {
        val id = context.packageName
        return try {
            try {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$id")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            } catch (e: ActivityNotFoundException) {
                context.startActivity(
                    Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$id")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            }
            JSONObject().put("ok", true).toString()
        } catch (e: Exception) {
            Log.w(TAG, "openListing", e)
            JSONObject().put("error", "listing_failed").put("message", "Impossible d'ouvrir Google Play sur cet appareil.").toString()
        }
    }
}
