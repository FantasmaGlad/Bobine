package com.bobine.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.widget.ImageView
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

private const val SETTINGS_PATH = "/api/settings"

fun splashDrawableForChannel(channel: String?): Int = when (channel) {
    "beta" -> R.drawable.bobine_splash_logo_beta
    "canary" -> R.drawable.bobine_splash_logo_canary
    else -> R.drawable.bobine_splash_logo_stable
}

object SplashChannel {
    private val mainHandler = Handler(Looper.getMainLooper())

    fun initialDrawable(context: Context): Int =
        splashDrawableForChannel(
            if (BuildConfig.STORE_BUILD) BuildConfig.DEFAULT_RELEASE_CHANNEL
            else UpdateChannelPref.load(context) ?: BuildConfig.BUILD_CHANNEL,
        )

    fun refreshFromBackendIfUnknown(context: Context, logoView: ImageView) {
        if (UpdateChannelPref.load(context) != null) return
        val appContext = context.applicationContext
        Thread {
            var channel: String? = null
            for (attempt in 1..4) {
                try {
                    val url = BackendEndpoint.url(appContext, SETTINGS_PATH)
                    if (url == null) {
                        Thread.sleep(300)
                        continue
                    }
                    val connection = URL(url).openConnection() as HttpURLConnection
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
                }
                Thread.sleep(300)
            }
            val found = channel ?: return@Thread
            UpdateChannelPref.save(appContext, found)
            val drawable = splashDrawableForChannel(UpdateChannelPref.load(appContext))
            mainHandler.post { logoView.setImageResource(drawable) }
        }.start()
    }
}
