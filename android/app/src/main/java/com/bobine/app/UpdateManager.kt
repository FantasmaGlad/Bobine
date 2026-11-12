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
import java.net.InetSocketAddress
import java.net.Proxy
import java.net.URL
import java.security.MessageDigest

private const val TAG = "UpdateManager"

private const val UPDATE_CALLBACK_PATH = "/api/updates/_android-callback"

private const val UPDATE_NOTIFICATION_CHANNEL_ID = "bobine_updates"
private const val UPDATE_NOTIFICATION_ID = 1001
private const val APK_FILE_NAME = "bobine-update.apk"
private const val MAX_DOWNLOAD_ATTEMPTS = 3
private const val CONNECT_TIMEOUT_MS = 15_000
private const val READ_TIMEOUT_MS = 30_000

private class UpdateRejected(message: String) : IllegalStateException(message)

object UpdateManager {

    fun downloadAndInstall(context: Context, downloadUrl: String, expectedDigest: String, socksProxy: String?) {
        val appContext = context.applicationContext
        if (!appContext.packageManager.canRequestPackageInstalls()) {
            openUnknownSourcesSettings(appContext)
            reportCallback(
                appContext,
                "error",
                "Autorisation requise : activez « Autoriser depuis cette source » pour Bobine dans l'écran Android qui vient de s'ouvrir, puis relancez la mise à jour.",
            )
            return
        }
        Thread({
            try {
                val expected = expectedDigest.substringAfter(':').lowercase()
                if (expected.length != 64) throw UpdateRejected("Empreinte SHA-256 invalide reçue du serveur.")
                val apk = fetchVerifiedApk(appContext, downloadUrl, expected, socksProxy)
                validatePackage(appContext, apk)
                reportCallback(appContext, "downloaded", "APK vérifié — confirmez l'installation sur l'appareil.")
                Handler(Looper.getMainLooper()).post { offerInstall(appContext, apk) }
            } catch (e: Exception) {
                Log.e(TAG, "Erreur téléchargement ou vérification de l'APK : ${e.message}", e)
                reportCallback(appContext, "error", e.message ?: "Échec du téléchargement de l'APK.")
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

    private fun fetchVerifiedApk(context: Context, url: String, expectedSha256: String, socksProxy: String?): File {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val target = File(dir, APK_FILE_NAME)
        if (target.exists() && sha256(target) == expectedSha256) return target
        target.delete()

        val part = File(dir, "$APK_FILE_NAME.part")
        var lastError: IOException? = null
        for (attempt in 1..MAX_DOWNLOAD_ATTEMPTS) {
            try {
                downloadTo(context, part, url, socksProxy)
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

    private fun downloadTo(context: Context, part: File, url: String, socksProxy: String?) {
        val connection = (if (socksProxy == null) URL(url).openConnection() else URL(url).openConnection(socksProxyOf(socksProxy)))
            as HttpURLConnection
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
                            if (percent != lastPercent && now - lastReportAt >= 1000) {
                                lastPercent = percent
                                lastReportAt = now
                                reportCallback(context, "progress", "Téléchargement : $percent %", percent)
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
        return Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }

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

    private fun socksProxyOf(address: String): Proxy {
        val host = address.substringBeforeLast(':').trim('[', ']')
        val port = address.substringAfterLast(':').toIntOrNull() ?: throw UpdateRejected("Adresse du proxy Tor invalide : $address")
        return Proxy(Proxy.Type.SOCKS, InetSocketAddress(host, port))
    }

    private fun reportCallback(context: Context, status: String, message: String, percent: Int? = null) {
        try {
            val url = BackendEndpoint.url(context, UPDATE_CALLBACK_PATH)
                ?: throw java.io.IOException("serveur embarque pas encore pret")
            val connection = URL(url).openConnection() as HttpURLConnection
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
