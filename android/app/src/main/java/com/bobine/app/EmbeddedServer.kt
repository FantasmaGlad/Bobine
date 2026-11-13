package com.bobine.app

import android.content.Context
import android.os.Handler
import android.util.Log
import androidx.core.content.ContextCompat
import com.chaquo.python.Python

private const val TAG = "EmbeddedServer"
private const val STORAGE_MAX_RETRIES = 30
private const val STORAGE_RETRY_MS = 2000L

class EmbeddedServer(private val context: Context, private val handler: Handler) {
    private var retries = 0

    fun startWhenStorageReady() {
        val dirs = ContextCompat.getExternalFilesDirs(context.applicationContext, null).filterNotNull()
        if (dirs.isEmpty()) return retryLater()
        val removable = dirs.drop(1).firstOrNull { it.canWrite() }
        if (removable != null) {
            Log.i(TAG, "Stockage amovible USB detecte et selectionne : ${removable.absolutePath} (espace libre: ${removable.freeSpace / (1024 * 1024)} Mo)")
        }
        val external = (removable ?: dirs.first()).absolutePath
        Python.getInstance().getModule("bobine_bootstrap").callAttr(
            "start_server_once", external, context.applicationInfo.nativeLibraryDir, context.filesDir.absolutePath, BuildConfig.VERSION_NAME,
        )
    }

    private fun retryLater() {
        retries++
        if (retries > STORAGE_MAX_RETRIES) {
            Log.e(TAG, "Stockage externe indisponible apres 60s - abandon (le service reste actif, un redemarrage relancera cette sequence)")
            return
        }
        Log.w(TAG, "Stockage externe pas encore monte (tentative $retries/$STORAGE_MAX_RETRIES), nouvel essai dans 2s")
        handler.postDelayed({ startWhenStorageReady() }, STORAGE_RETRY_MS)
    }
}
