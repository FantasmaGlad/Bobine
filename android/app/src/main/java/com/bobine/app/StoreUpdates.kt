package com.bobine.app

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import org.json.JSONObject

private const val TAG = "StoreUpdates"
private const val PROVIDER_CLASS = "com.bobine.app.PlayUpdateProvider"

/** Fournisseur de mises à jour d'une boutique (implémenté uniquement par le build Google Play). */
interface StoreUpdateProvider {
    /** JSON : `{"state": "none|available|downloading|downloaded|installing|failed", "version_code": n, ...}`. */
    fun check(context: Context): String

    /** Démarre la mise à jour souple (téléchargement en arrière-plan, interface de Google Play). */
    fun start(context: Context): String

    /** Installe la mise à jour téléchargée (l'application redémarre). */
    fun complete(context: Context): String
}

/**
 * Mises à jour des builds distribués par une boutique : appelé par le backend Python (`AndroidHandler`)
 * depuis Réglages → Mises à jour. Le build libre n'a PAS de fournisseur (les mises à jour y passent par
 * le téléchargement des releases) : `provider()` y renvoie null et rien de Google n'est chargé.
 */
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

    /** Ouvre la fiche de l'application dans Google Play (repli : navigateur). Aucune bibliothèque Google requise. */
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
