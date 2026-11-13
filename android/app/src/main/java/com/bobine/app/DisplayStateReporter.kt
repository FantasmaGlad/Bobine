package com.bobine.app

import android.content.Context
import android.os.Handler
import android.util.Log
import org.json.JSONObject
import java.io.IOException
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

private const val TAG = "DisplayStateReporter"
private const val DISPLAY_STATE_PATH = "/api/display/state"

class DisplayStateReporter(private val context: Context, private val handler: Handler) {
    @Volatile private var generation = 0

    fun report(count: Int, resolution: String?) {
        val current = ++generation
        Thread { post(count, resolution, current, 0) }.start()
    }

    fun cancel() {
        generation++
    }

    private fun post(count: Int, resolution: String?, current: Int, attempt: Int) {
        if (current != generation) return
        try {
            send(count, resolution)
            Log.i(TAG, "Etat des ecrans rapporte au backend : $count ecran(s) externe(s)")
        } catch (e: Exception) {
            val delayMs = minOf(1000L * (attempt + 1), 10_000L)
            Log.w(TAG, "Rapport d'etat des ecrans en echec (tentative ${attempt + 1}), nouvel essai dans ${delayMs}ms", e)
            handler.postDelayed({ Thread { post(count, resolution, current, attempt + 1) }.start() }, delayMs)
        }
    }

    private fun send(count: Int, resolution: String?) {
        val url = BackendEndpoint.url(context.applicationContext, DISPLAY_STATE_PATH) ?: throw IOException("serveur embarque pas encore pret")
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.requestMethod = "PUT"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        connection.connectTimeout = 5000
        connection.readTimeout = 5000
        val body = JSONObject()
            .put("external_count", count)
            .put("source", "android")
            .apply { if (resolution != null) put("resolution", resolution) }
            .toString()
        OutputStreamWriter(connection.outputStream).use { it.write(body) }
        connection.inputStream.use { it.readBytes() }
        connection.disconnect()
    }
}
