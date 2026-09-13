package com.bobine.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Notification
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
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

private const val TAG = "UpdateManager"

// Reutilise l'endpoint backend DEJA existant et teste sur les autres
// plateformes, plutot que d'interroger l'API GitHub Releases directement
// depuis Kotlin - une seule source de verite pour la logique de
// comparaison de version (canal Stable/Beta, cf. routers/updates.py), pas
// une deuxieme implementation a maintenir en parallele. Utilise 127.0.0.1
// (pas 127.0.0.2) : ceci n'est pas une requete de l'ecran tactile, peu
// importe le canal loopback (les deux atteignent le meme serveur).
private const val UPDATE_CHECK_URL = "http://127.0.0.1:8000/api/updates/check"

// Rappel vers l'orchestrateur de mise a jour cote Python (cf.
// routers/updates.py::android_update_callback) : le telechargement se fait
// dans CE thread Kotlin, de facon totalement asynchrone du point de vue de
// `apply_update()` cote Python (deja retourne au moment ou ce thread
// termine) - sans ce rappel, l'etat de mise a jour affiche dans Reglages
// restait bloque sur "telechargement en cours" indefiniment, meme apres un
// succes ou un echec reel.
private const val UPDATE_CALLBACK_URL = "http://127.0.0.1:8000/api/updates/_android-callback"

private const val UPDATE_NOTIFICATION_CHANNEL_ID = "bobine_updates"
private const val UPDATE_NOTIFICATION_ID = 1001

/**
 * Verifie une mise a jour disponible et, si un asset `.apk` direct existe
 * (routers/updates.py, profil "android"), le telecharge et declenche
 * l'installation standard Android (boite de dialogue systeme de
 * confirmation - pas de contournement silencieux, conforme a la decision
 * du CDC : "Android exige une interaction explicite pour ce type
 * d'installation hors store", decision reconfirmee lors de l'ajout de la
 * mise a jour automatique planifiee : seul le telechargement/la
 * verification se declenchent sans supervision, jamais l'installation
 * finale).
 *
 * Le premier asset `.apk` publie sur une release GitHub est arrive avec
 * V3.0.5 (pipeline CI, job `release-stable`) - ce chemin dispose donc
 * desormais d'un fichier reel a telecharger a chaque verification, mais
 * reste a valider par un passage complet sur un appareil physique avant
 * d'etre considere pleinement fiable en production.
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
    fun downloadAndInstall(context: Context, downloadUrl: String) {
        Thread {
            try {
                val apkFile = downloadApk(context, downloadUrl)
                notifyApkReady(context)
                reportCallback("downloaded", "APK téléchargé — confirmation d'installation en attente.")
                Handler(Looper.getMainLooper()).post { triggerInstall(context, apkFile) }
            } catch (e: Exception) {
                Log.e(TAG, "Erreur téléchargement ou installation de l'APK : ${e.message}", e)
                reportCallback("error", e.message ?: "Échec du téléchargement de l'APK.")
            }
        }.start()
    }

    /** Signale l'issue du téléchargement à l'orchestrateur Python (cf.
     * routers/updates.py::android_update_callback) — best-effort, une
     * défaillance de ce rappel ne doit jamais empêcher l'installation
     * elle-même de se poursuivre. */
    private fun reportCallback(status: String, message: String) {
        try {
            val connection = URL(UPDATE_CALLBACK_URL).openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            val body = JSONObject().put("status", status).put("message", message).toString()
            OutputStreamWriter(connection.outputStream).use { it.write(body) }
            connection.inputStream.use { it.readBytes() }
            connection.disconnect()
        } catch (e: Exception) {
            Log.w(TAG, "Échec du rappel vers l'orchestrateur de mise à jour (non bloquant)", e)
        }
    }

    /** Notification système : la tablette n'affiche l'application Bobine
     * qu'en avant-plan (`/grid`/`/cinema`), une mise à jour téléchargée
     * pendant la nuit (planification automatique) n'a sinon aucun moyen
     * visible de signaler qu'une confirmation d'installation l'attend. */
    private fun notifyApkReady(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        val channel = NotificationChannel(
            UPDATE_NOTIFICATION_CHANNEL_ID,
            "Bobine — Mises à jour",
            NotificationManager.IMPORTANCE_DEFAULT,
        )
        manager.createNotificationChannel(channel)

        val openAppIntent = context.packageManager.getLaunchIntentForPackage(context.packageName)
        val pendingIntent = PendingIntent.getActivity(
            context, 0, openAppIntent, PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = Notification.Builder(context, UPDATE_NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Mise à jour Bobine prête")
            .setContentText("Ouvrez Bobine pour confirmer l'installation.")
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()
        manager.notify(UPDATE_NOTIFICATION_ID, notification)
    }

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
