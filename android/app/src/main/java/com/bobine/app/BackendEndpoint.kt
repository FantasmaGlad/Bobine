package com.bobine.app

import android.content.Context
import android.os.Process
import org.json.JSONObject
import java.io.File

object BackendEndpoint {
    private const val RUNTIME_FILE_NAME = "backend-runtime.json"
    private const val HOST = "127.0.0.1"

    fun port(context: Context): Int? = try {
        parsePort(File(context.applicationContext.filesDir, RUNTIME_FILE_NAME).readText(), Process.myPid())
    } catch (e: Exception) {
        null
    }

    fun url(context: Context, path: String): String? = port(context)?.let { "http://$HOST:$it$path" }

    fun isBackendUrl(context: Context, url: String?): Boolean {
        val port = port(context) ?: return false
        return url != null && url.startsWith("http://$HOST:$port")
    }

    internal fun parsePort(json: String, expectedPid: Int): Int? {
        val data = JSONObject(json)
        if (data.optInt("pid", -1) != expectedPid) return null
        val port = data.optInt("port", -1)
        return if (port in 1..65535) port else null
    }
}
