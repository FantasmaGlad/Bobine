package com.bobine.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.widget.ImageView
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

private const val SETTINGS_URL = "http://127.0.0.1:8000/api/settings"

/**
 * Icône d'écran de démarrage (mascotte Baamix) selon le canal de mise à jour courant — une
 * ressource `bobine_splash_logo_<canal>` par canal (cf. `drawable-nodpi/`, dérivées de
 * `Assets/Images/Versions/`). Repli sur « stable » si le canal est inconnu ou invalide.
 */
fun splashDrawableForChannel(channel: String?): Int = when (channel) {
    "beta" -> R.drawable.bobine_splash_logo_beta
    "canary" -> R.drawable.bobine_splash_logo_canary
    else -> R.drawable.bobine_splash_logo_stable
}

/**
 * Écran de chargement aux couleurs du canal de mise à jour, partagé par l'écran tactile
 * ([MainActivity]) et la sortie HDMI ([BobinePresentation]) — qui dupliquaient chacun leur
 * propre code.
 *
 * Cause du défaut corrigé : l'icône était toujours posée sur « stable », puis remplacée après une
 * interrogation asynchrone de `/api/settings` (4 essais de 0,8 s) ; le serveur Python embarqué
 * n'étant pas prêt au démarrage à froid, un utilisateur Bêta ou Canary voyait l'image « stable »
 * — parfois jusqu'au bout. Le canal est désormais lu SYNCHRONE dans les préférences natives
 * ([UpdateChannelPref], alimentées par l'interface web) avant la première image.
 */
object SplashChannel {
    private val mainHandler = Handler(Looper.getMainLooper())

    /** Icône à afficher dès la première image : dernier canal connu, « stable » au tout premier lancement. */
    fun initialDrawable(context: Context): Int = splashDrawableForChannel(UpdateChannelPref.load(context))

    /**
     * Repli pour le TOUT PREMIER lancement (aucune préférence encore reçue de l'interface web) :
     * interroge `/api/settings` en arrière-plan, mémorise le canal trouvé et corrige l'icône. Sans
     * effet quand la préférence existe déjà — l'interface web la tient à jour, inutile de solliciter
     * un serveur qui démarre à peine. Purement cosmétique, jamais bloquant.
     */
    fun refreshFromBackendIfUnknown(context: Context, logoView: ImageView) {
        if (UpdateChannelPref.load(context) != null) return
        val appContext = context.applicationContext
        Thread {
            var channel: String? = null
            for (attempt in 1..4) {
                try {
                    val connection = URL(SETTINGS_URL).openConnection() as HttpURLConnection
                    connection.connectTimeout = 800
                    connection.readTimeout = 800
                    if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                        val body = connection.inputStream.bufferedReader().use { it.readText() }
                        val value = JSONObject(body).optString("update_channel", "")
                        if (value.isNotEmpty()) channel = value
                    }
                    connection.disconnect()
                    if (channel != null) break
                } catch (e: Exception) {
                    // Serveur pas encore prêt : nouvelle tentative ci-dessous.
                }
                Thread.sleep(300)
            }
            val found = channel ?: return@Thread
            UpdateChannelPref.save(appContext, found)
            // La valeur est relue depuis les préférences : un canal invalide y a été refusé.
            val drawable = splashDrawableForChannel(UpdateChannelPref.load(appContext))
            mainHandler.post { logoView.setImageResource(drawable) }
        }.start()
    }
}
