package com.bobine.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

private const val TAG = "UpdateManager"

// Lot 11 (cf. docs/plan-implementation-android.md) : reutilise l'endpoint
// backend DEJA existant et teste sur les autres plateformes, plutot que
// d'interroger l'API GitHub Releases directement depuis Kotlin - une
// seule source de verite pour la logique de comparaison de version
// (canal Stable/Beta, cf. routers/updates.py), pas une deuxieme
// implementation a maintenir en parallele. Utilise 127.0.0.1 (pas
// 127.0.0.2) : ceci n'est pas une requete de l'ecran tactile, peu importe
// le canal loopback (les deux atteignent le meme serveur, cf. Lot 3).
private const val UPDATE_CHECK_URL = "http://127.0.0.1:8000/api/updates/check"

/**
 * Verifie une mise a jour disponible et, si un asset `.apk` direct existe
 * (routers/updates.py, profil "android" - cf. Decouvertes du Lot 11),
 * le telecharge et declenche l'installation standard Android (boite de
 * dialogue systeme de confirmation - pas de contournement silencieux,
 * conforme a la decision du CDC : "Android exige une interaction
 * explicite pour ce type d'installation hors store").
 *
 * INERTE en pratique tant que le Lot 13 ne publie pas d'APK sur les
 * releases publiques (decision actee, volontairement differee) :
 * `download_url` ne pointera jamais vers un `.apk` reel avant ca, donc
 * `checkForUpdate` ne fera jamais rien de plus qu'un log. Code prepare
 * et jamais teste en conditions reelles (aucun asset a telecharger).
 */
object UpdateManager {

    fun checkForUpdate(context: Context) {
        Thread {
            try {
                // Le backend (BobineForegroundService, demarre juste apres
                // cet appel dans MainActivity.onCreate()) met un court
                // instant a ecouter sur le port 8000 - sans ce delai, le
                // tout premier appel a froid echoue systematiquement en
                // ConnectException (constate en pratique), avant meme que
                // le serveur ait eu la moindre chance de demarrer.
                Thread.sleep(5000)
                val response = httpGet(UPDATE_CHECK_URL)
                val json = JSONObject(response)
                if (!json.optBoolean("online", false) || !json.optBoolean("has_update", false)) {
                    return@Thread
                }
                val downloadUrl = json.optString("download_url", "")
                if (!downloadUrl.endsWith(".apk")) {
                    // Pas d'asset direct (cas actuel, Lot 13 non publie) -
                    // juste informatif, aucune action possible depuis l'app.
                    Log.i(TAG, "Mise a jour disponible mais aucun .apk direct (${json.optString("latest_version")}) - voir $downloadUrl")
                    return@Thread
                }
                val apkFile = downloadApk(context, downloadUrl)
                Handler(Looper.getMainLooper()).post { triggerInstall(context, apkFile) }
            } catch (e: Exception) {
                Log.w(TAG, "Verification de mise a jour echouee (non bloquant)", e)
            }
        }.start()
    }

    private fun httpGet(url: String): String {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 5000
        connection.readTimeout = 5000
        try {
            return connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    private fun downloadApk(context: Context, url: String): File {
        val updatesDir = File(context.cacheDir, "updates").apply { mkdirs() }
        val outFile = File(updatesDir, "bobine-update.apk")
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 10000
        try {
            connection.inputStream.use { input ->
                outFile.outputStream().use { output -> input.copyTo(output) }
            }
        } finally {
            connection.disconnect()
        }
        return outFile
    }

    // Intent.ACTION_VIEW sur un .apk affiche TOUJOURS la boite de dialogue
    // systeme d'installation (nom du paquet, permissions, confirmer) -
    // c'est le comportement voulu, pas un contournement a chercher a
    // eviter (cf. CDC). REQUEST_INSTALL_PACKAGES (permission normale,
    // Manifest) evite seulement l'ecran intermediaire "Autoriser les
    // sources inconnues" - le Device Owner (Lot 10) en dispense aussi
    // automatiquement l'app d'apres la documentation Android (non
    // reverifie en pratique dans cette session, aucun .apk reel a tester).
    private fun triggerInstall(context: Context, apkFile: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", apkFile)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
