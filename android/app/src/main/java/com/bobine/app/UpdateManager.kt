package com.bobine.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

private const val TAG = "UpdateManager"

// Rappel vers l'orchestrateur de mise a jour cote Python (cf.
// routers/updates.py::android_update_callback) : le telechargement se fait
// dans CE thread Kotlin, de facon totalement asynchrone du point de vue de
// `apply_update()` cote Python (deja retourne au moment ou ce thread
// termine) - sans ce rappel, l'etat de mise a jour affiche dans Reglages
// restait bloque sur "telechargement en cours" indefiniment, meme apres un
// succes ou un echec reel. Utilise 127.0.0.1 (pas 127.0.0.2) : ceci n'est
// pas une requete de l'ecran tactile, les deux atteignent le meme serveur.
private const val UPDATE_CALLBACK_URL = "http://127.0.0.1:8000/api/updates/_android-callback"

private const val UPDATE_NOTIFICATION_CHANNEL_ID = "bobine_updates"
private const val UPDATE_NOTIFICATION_ID = 1001
private const val APK_FILE_NAME = "bobine-update.apk"
private const val MAX_DOWNLOAD_ATTEMPTS = 3
private const val CONNECT_TIMEOUT_MS = 15_000
private const val READ_TIMEOUT_MS = 30_000

/**
 * Une raison de refus explicable a l'utilisateur (paquet invalide, retour en
 * arriere interdit...) - distincte d'une panne reseau, qui est reessayee.
 */
private class UpdateRejected(message: String) : IllegalStateException(message)

/**
 * Telecharge l'APK de la release choisie dans Reglages, le VERIFIE, puis
 * declenche l'installation standard Android (boite de dialogue systeme de
 * confirmation - pas de contournement silencieux, conforme au principe
 * "Android exige une interaction explicite pour ce type
 * d'installation hors store"; seul le telechargement/la verification se
 * declenchent sans supervision, jamais l'installation finale).
 *
 * Contrairement a la premiere version de ce fichier :
 *  - plus AUCUN telechargement spontane au lancement de l'app (l'ancien
 *    `checkForUpdate` telechargeait et proposait l'installation a chaque
 *    ouverture, hors reglage "mise a jour automatique", et choisissait le
 *    premier `.apk` de la release - l'APK telephone, y compris sur Android
 *    TV, ou il s'installait comme une SECONDE application) ;
 *  - l'asset est choisi par le backend (variante telephone/TV) et son
 *    empreinte SHA-256 est verifiee ici avant tout ;
 *  - le paquet est controle (meme `applicationId`, meme signature,
 *    `versionCode` non inferieur) pour remplacer l'echec opaque "appli non
 *    installee" d'Android par une explication claire.
 */
object UpdateManager {

    /**
     * Point d'entree appele par le backend Python (profil Android,
     * `AndroidHandler.apply_update`). Rend la main immediatement : tout
     * progres/echec est rapporte via [reportCallback].
     */
    fun downloadAndInstall(context: Context, downloadUrl: String, expectedDigest: String) {
        val appContext = context.applicationContext
        // Sans l'autorisation « Installer des applications inconnues », Android
        // n'affiche qu'un écran de réglages puis abandonne l'installation sans
        // rien expliquer : on la demande AVANT de télécharger 50 Mo.
        if (!appContext.packageManager.canRequestPackageInstalls()) {
            openUnknownSourcesSettings(appContext)
            reportCallback(
                "error",
                "Autorisation requise : activez « Autoriser depuis cette source » pour Bobine dans l'écran Android qui vient de s'ouvrir, puis relancez la mise à jour.",
            )
            return
        }
        Thread({
            try {
                val expected = expectedDigest.substringAfter(':').lowercase()
                if (expected.length != 64) throw UpdateRejected("Empreinte SHA-256 invalide reçue du serveur.")
                val apk = fetchVerifiedApk(appContext, downloadUrl, expected)
                validatePackage(appContext, apk)
                reportCallback("downloaded", "APK vérifié — confirmez l'installation sur l'appareil.")
                Handler(Looper.getMainLooper()).post { offerInstall(appContext, apk) }
            } catch (e: Exception) {
                Log.e(TAG, "Erreur téléchargement ou vérification de l'APK : ${e.message}", e)
                reportCallback("error", e.message ?: "Échec du téléchargement de l'APK.")
            }
        }, "bobine-update").start()
    }

    private fun openUnknownSourcesSettings(context: Context) {
        try {
            context.startActivity(
                Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            )
        } catch (e: Exception) {
            Log.w(TAG, "Ouverture de l'ecran des sources inconnues impossible : ${e.message}")
        }
    }

    /**
     * Appele au lancement de l'app : supprime l'APK deja installe (ou
     * perime) pour ne pas garder ~50 Mo inutiles dans le cache, et retire
     * la notification "mise a jour prete" devenue sans objet.
     */
    fun cleanupStaleDownloads(context: Context) {
        Thread({
            try {
                val dir = File(context.cacheDir, "updates")
                val apk = File(dir, APK_FILE_NAME)
                File(dir, "$APK_FILE_NAME.part").delete()
                if (!apk.exists()) return@Thread
                val pm = context.packageManager
                val archive = pm.getPackageArchiveInfo(apk.absolutePath, 0)
                val installed = pm.getPackageInfo(context.packageName, 0)
                if (archive == null || archive.longVersionCode <= installed.longVersionCode) {
                    apk.delete()
                    context.getSystemService(NotificationManager::class.java)?.cancel(UPDATE_NOTIFICATION_ID)
                }
            } catch (e: Exception) {
                Log.w(TAG, "Nettoyage des mises à jour téléchargées impossible (non bloquant)", e)
            }
        }, "bobine-update-cleanup").start()
    }

    // --- Telechargement -----------------------------------------------------

    private fun fetchVerifiedApk(context: Context, url: String, expectedSha256: String): File {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val target = File(dir, APK_FILE_NAME)
        // Fichier deja telecharge ET verifie lors d'une tentative precedente
        // (ex. installation interrompue puis relancee) : inutile de
        // retelecharger 50 Mo sur un Wi-Fi de salle.
        if (target.exists() && sha256(target) == expectedSha256) return target
        target.delete()

        val part = File(dir, "$APK_FILE_NAME.part")
        var lastError: IOException? = null
        for (attempt in 1..MAX_DOWNLOAD_ATTEMPTS) {
            try {
                downloadTo(part, url)
                val actual = sha256(part)
                if (actual != expectedSha256) {
                    part.delete()
                    throw UpdateRejected(
                        "Empreinte SHA-256 invalide pour l'APK téléchargé " +
                            "(attendu ${expectedSha256.take(12)}…, obtenu ${actual.take(12)}…) — installation annulée par précaution.",
                    )
                }
                if (!part.renameTo(target)) throw IOException("Impossible de finaliser le fichier téléchargé.")
                return target
            } catch (e: IOException) {
                lastError = e
                part.delete()
                Log.w(TAG, "Téléchargement interrompu (tentative $attempt/$MAX_DOWNLOAD_ATTEMPTS) : ${e.message}")
                if (attempt < MAX_DOWNLOAD_ATTEMPTS) Thread.sleep(2000L * attempt)
            }
        }
        throw IOException("Téléchargement impossible après $MAX_DOWNLOAD_ATTEMPTS tentatives : ${lastError?.message}")
    }

    private fun downloadTo(part: File, url: String) {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = CONNECT_TIMEOUT_MS
        connection.readTimeout = READ_TIMEOUT_MS
        connection.instanceFollowRedirects = true
        try {
            if (connection.responseCode != HttpURLConnection.HTTP_OK) {
                throw IOException("Serveur de téléchargement : HTTP ${connection.responseCode}")
            }
            val total = connection.contentLengthLong
            val free = part.parentFile?.usableSpace ?: Long.MAX_VALUE
            if (total > 0 && free < total + total / 5) {
                throw UpdateRejected(
                    "Espace de stockage insuffisant pour la mise à jour (${free / 1_048_576} Mo libres, ${total / 1_048_576} Mo requis).",
                )
            }
            var read = 0L
            var lastPercent = -1
            var lastReportAt = 0L
            connection.inputStream.use { input ->
                part.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val n = input.read(buffer)
                        if (n < 0) break
                        output.write(buffer, 0, n)
                        read += n
                        if (total > 0) {
                            val percent = minOf(99, (read * 100 / total).toInt())
                            val now = System.currentTimeMillis()
                            // Au plus un rappel par seconde et par pourcent :
                            // l'etat est diffuse en WebSocket a chaque rappel.
                            if (percent != lastPercent && now - lastReportAt >= 1000) {
                                lastPercent = percent
                                lastReportAt = now
                                reportCallback("progress", "Téléchargement : $percent %", percent)
                            }
                        }
                    }
                }
            }
            if (total > 0 && read != total) throw IOException("Fichier tronqué ($read/$total octets reçus).")
        } finally {
            connection.disconnect()
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    // --- Validation du paquet ------------------------------------------------

    /**
     * Reproduit les controles du PackageInstaller AVANT d'ouvrir son
     * dialogue : celui-ci n'affiche, en cas d'echec, que "Application non
     * installee" sans aucune explication.
     */
    private fun validatePackage(context: Context, apk: File) {
        val pm = context.packageManager
        val archive = pm.getPackageArchiveInfo(apk.absolutePath, PackageManager.GET_SIGNING_CERTIFICATES)
            ?: throw UpdateRejected("Le fichier téléchargé n'est pas un APK Android valide.")
        if (archive.packageName != context.packageName) {
            throw UpdateRejected(
                "Cet APK (${archive.packageName}) ne correspond pas à l'application installée " +
                    "(${context.packageName}) — mauvaise variante téléphone / Android TV.",
            )
        }
        val installed = pm.getPackageInfo(context.packageName, PackageManager.GET_SIGNING_CERTIFICATES)
        if (archive.longVersionCode < installed.longVersionCode) {
            throw UpdateRejected(
                "Cette version (${archive.versionName}) est plus ancienne que celle installée " +
                    "(${installed.versionName}) : Android interdit tout retour en arrière sans désinstaller " +
                    "l'application, ce qui effacerait ses données. Patientez jusqu'à la prochaine version Stable.",
            )
        }
        val newSigners = archive.signingInfo?.apkContentsSigners
        val currentSigners = installed.signingInfo?.apkContentsSigners
        if (!newSigners.isNullOrEmpty() && !currentSigners.isNullOrEmpty() &&
            newSigners.none { candidate -> currentSigners.any { it == candidate } }
        ) {
            throw UpdateRejected(
                "Cet APK est signé avec une autre clé que l'application installée — Android refuserait la mise à jour.",
            )
        }
    }

    // --- Installation ----------------------------------------------------------

    /**
     * Android 10+ interdit a une application en arriere-plan d'ouvrir une
     * activite : le `startActivity` ci-dessous ne peut aboutir que si Bobine
     * est au premier plan. Dans tous les autres cas (mise a jour planifiee
     * de nuit, Chrome au premier plan...) la notification porte DIRECTEMENT
     * l'intention d'installation - un tap suffit, sans passer par
     * l'ouverture prealable de l'application comme avant.
     */
    private fun offerInstall(context: Context, apk: File) {
        val installIntent = buildInstallIntent(context, apk)
        notifyApkReady(context, installIntent)
        try {
            context.startActivity(installIntent)
        } catch (e: Exception) {
            Log.w(TAG, "Ouverture directe de l'installeur refusée (app en arrière-plan ?) — notification disponible", e)
        }
    }

    private fun buildInstallIntent(context: Context, apk: File): Intent {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", apk)
        // Intent.ACTION_VIEW sur un .apk affiche TOUJOURS la boite de dialogue
        // systeme d'installation (nom du paquet, permissions, confirmer) -
        // c'est le comportement voulu, pas un contournement a chercher a
        // eviter. REQUEST_INSTALL_PACKAGES (Manifest) envoie
        // l'utilisateur vers l'ecran "Autoriser cette source" si besoin.
        return Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }

    /** Notification systeme : la tablette n'affiche l'application Bobine
     * qu'en avant-plan (`/grid`/`/cinema`), une mise a jour telechargee
     * pendant la nuit (planification automatique) n'a sinon aucun moyen
     * visible de signaler qu'une confirmation d'installation l'attend. */
    private fun notifyApkReady(context: Context, installIntent: Intent) {
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        manager.createNotificationChannel(
            NotificationChannel(
                UPDATE_NOTIFICATION_CHANNEL_ID,
                "Bobine — Mises à jour",
                NotificationManager.IMPORTANCE_DEFAULT,
            ),
        )
        val pendingIntent = PendingIntent.getActivity(
            context, 1, installIntent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notification = Notification.Builder(context, UPDATE_NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Mise à jour Bobine prête")
            .setContentText("Touchez pour confirmer l'installation.")
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()
        manager.notify(UPDATE_NOTIFICATION_ID, notification)
    }

    // --- Rappel vers le backend ----------------------------------------------

    /** Signale progression/issue a l'orchestrateur Python (cf.
     * routers/updates.py::android_update_callback) — best-effort, une
     * defaillance de ce rappel ne doit jamais empecher la mise a jour
     * elle-meme de se poursuivre. */
    private fun reportCallback(status: String, message: String, percent: Int? = null) {
        try {
            val connection = URL(UPDATE_CALLBACK_URL).openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            val body = JSONObject().put("status", status).put("message", message).apply {
                if (percent != null) put("percent", percent)
            }.toString()
            OutputStreamWriter(connection.outputStream).use { it.write(body) }
            connection.inputStream.use { it.readBytes() }
            connection.disconnect()
        } catch (e: Exception) {
            Log.w(TAG, "Échec du rappel vers l'orchestrateur de mise à jour (non bloquant)", e)
        }
    }
}
