package com.bobine.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.display.DisplayManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.provider.Settings
import android.view.View
import android.graphics.PixelFormat
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.util.Log
import android.view.Display
import android.view.WindowManager
import androidx.core.content.ContextCompat
import com.chaquo.python.Python
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

private const val NOTIFICATION_CHANNEL_ID = "bobine_service"
private const val NOTIFICATION_ID = 1
private const val TAG = "BobineForegroundService"
private const val DISPLAY_STATE_PATH = "/api/display/state"
private const val RECONCILE_INTERVAL_MS = 60_000L
private const val PRESENTATION_FAST_RETRIES = 15
private const val PRESENTATION_FAST_DELAY_MS = 500L
private const val PRESENTATION_SLOW_DELAY_MS = 5_000L

class BobineForegroundService : Service() {

    companion object {
        const val EXTRA_LAUNCH_SCREEN = "launch_screen"

        var currentPresentation: BobinePresentation? = null
            private set

        @Volatile
        private var instance: BobineForegroundService? = null

        fun notifyDisplayStateChanged() {
            val svc = instance ?: return
            svc.handler.post {
                svc.showPresentationIfNeeded()
            }
        }
    }

    private lateinit var displayManager: DisplayManager
    private var presentation: BobinePresentation? = null
    private val handler = Handler(Looper.getMainLooper())
    private var presentationRetries = 0
    private var presentationAttemptInFlight = false
    private var wakeLock: PowerManager.WakeLock? = null

    private var multicastLock: WifiManager.MulticastLock? = null

    private var wifiLock: WifiManager.WifiLock? = null

    private var connectivityManager: ConnectivityManager? = null
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            Log.i(TAG, "Reseau disponible (network=$network) - re-acquisition du verrou multicast mDNS")
            releaseMulticastLock()
            acquireMulticastLock()
            acquireWifiLock()
            publishLanAddress()
        }

        override fun onLost(network: Network) {
            publishLanAddress()
        }
    }

    private fun newLanCallback() = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) = publishLanAddress()
        override fun onLinkPropertiesChanged(network: Network, linkProperties: android.net.LinkProperties) = publishLanAddress()
        override fun onLost(network: Network) = publishLanAddress()
    }
    private val lanCallbacks = listOf(
        NetworkCapabilities.TRANSPORT_WIFI to newLanCallback(),
        NetworkCapabilities.TRANSPORT_ETHERNET to newLanCallback(),
    )

    private fun publishLanAddress() {
        val manager = connectivityManager ?: return
        LanAddress.publish(LanAddress.current(manager))
    }

    private val displayListener = object : DisplayManager.DisplayListener {
        override fun onDisplayAdded(displayId: Int) {
            Log.i(TAG, "Ecran detecte (displayId=$displayId) : ${describeDisplays()}")
            presentationRetries = 0
            showPresentationIfNeeded()
            reportDisplayState()
        }

        override fun onDisplayRemoved(displayId: Int) {
            Log.i(TAG, "Ecran retire (displayId=$displayId) : ${describeDisplays()}")
            val current = presentation
            if (current != null && (current.display.displayId == displayId || externalDisplays().isEmpty())) {
                current.dismiss()
                presentation = null
                currentPresentation = null
                releaseWakeLock()
            }
            showPresentationIfNeeded()
            reportDisplayState()
        }

        override fun onDisplayChanged(displayId: Int) {
            if (displayId == Display.DEFAULT_DISPLAY) return
            if (presentation == null) {
                Log.i(TAG, "Ecran modifie (displayId=$displayId) sans Presentation : nouvelle tentative")
                presentationRetries = 0
                showPresentationIfNeeded()
            }
            reportDisplayState()
        }
    }

    private fun externalDisplays(): List<Display> =
        displayManager.displays
            .filter { it.displayId != Display.DEFAULT_DISPLAY && (it.flags and Display.FLAG_PRIVATE) == 0 }
            .sortedByDescending { (it.flags and Display.FLAG_PRESENTATION) != 0 }

    private fun describeDisplays(): String =
        displayManager.displays.joinToString { "[id=${it.displayId} nom='${it.name}' flags=0x${Integer.toHexString(it.flags)} etat=${it.state}]" }

    private fun reportDisplayState() {
        val externals = externalDisplays()
        val count = externals.size
        val resolution = externals.firstOrNull()?.let { "${it.mode.physicalWidth}x${it.mode.physicalHeight}" }
        val generation = ++reportGeneration
        Thread { postDisplayState(count, resolution, generation, attempt = 0) }.start()
    }

    private fun postDisplayState(count: Int, resolution: String?, generation: Int, attempt: Int) {
        if (generation != reportGeneration) return // un etat plus recent a pris le relais
        try {
            val url = BackendEndpoint.url(applicationContext, DISPLAY_STATE_PATH)
                ?: throw java.io.IOException("serveur embarque pas encore pret")
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
            Log.i(TAG, "Etat des ecrans rapporte au backend : $count ecran(s) externe(s)")
        } catch (e: Exception) {
            val delayMs = minOf(1000L * (attempt + 1), 10_000L)
            Log.w(TAG, "Rapport d'etat des ecrans en echec (tentative ${attempt + 1}), nouvel essai dans ${delayMs}ms", e)
            handler.postDelayed({
                Thread { postDisplayState(count, resolution, generation, attempt + 1) }.start()
            }, delayMs)
        }
    }

    private val reconcileRunnable = object : Runnable {
        override fun run() {
            val current = presentation
            if (current != null && !current.isShowing) {
                Log.w(TAG, "Presentation fermee par le systeme : reouverture")
                presentation = null
                currentPresentation = null
                releaseWakeLock()
            }
            showPresentationIfNeeded()
            reportDisplayState()
            handler.postDelayed(this, RECONCILE_INTERVAL_MS)
        }
    }

    @Volatile private var reportGeneration = 0

    private var storageRetries = 0

    override fun onCreate() {
        super.onCreate()
        instance = this

        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        acquireMulticastLock()
        acquireWifiLock()
        connectivityManager = (getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager).also {
            try {
                it.registerDefaultNetworkCallback(networkCallback)
            } catch (e: Exception) {
                Log.w(TAG, "Echec de l'enregistrement du callback reseau (re-acquisition multicast desactivee) : ${e.message}")
            }
            try {
                for ((transport, callback) in lanCallbacks) {
                    it.registerNetworkCallback(NetworkRequest.Builder().addTransportType(transport).build(), callback)
                }
            } catch (e: Exception) {
                Log.w(TAG, "Echec de l'enregistrement du callback LAN : ${e.message}")
            }
        }
        publishLanAddress()

        startPythonServerWhenStorageReady()

        displayManager = getSystemService(Context.DISPLAY_SERVICE) as DisplayManager
        displayManager.registerDisplayListener(displayListener, null)
        Log.i(TAG, "Ecrans au demarrage : ${describeDisplays()}")
        showPresentationIfNeeded()
        reportDisplayState()
        handler.postDelayed(reconcileRunnable, RECONCILE_INTERVAL_MS)
    }

    private fun startPythonServerWhenStorageReady() {
        val externalFilesDirs = ContextCompat.getExternalFilesDirs(applicationContext, null).filterNotNull()
        if (externalFilesDirs.isEmpty()) {
            storageRetries++
            if (storageRetries <= 30) {
                Log.w(TAG, "Stockage externe pas encore monte (tentative $storageRetries/30), nouvel essai dans 2s")
                handler.postDelayed({ startPythonServerWhenStorageReady() }, 2000)
            } else {
                Log.e(TAG, "Stockage externe indisponible apres 60s - abandon (le service reste actif, un redemarrage relancera cette sequence)")
            }
            return
        }
        val removableDir = externalFilesDirs.drop(1).firstOrNull { it.canWrite() }
        val selectedExternalDir = if (removableDir != null) {
            Log.i(TAG, "Stockage amovible USB detecte et selectionne : ${removableDir.absolutePath} (espace libre: ${removableDir.freeSpace / (1024 * 1024)} Mo)")
            removableDir.absolutePath
        } else {
            externalFilesDirs.first().absolutePath
        }

        val internalFilesDir = applicationContext.filesDir.absolutePath
        val nativeLibraryDir = applicationContext.applicationInfo.nativeLibraryDir
        val py = Python.getInstance()
        py.getModule("bobine_bootstrap").callAttr(
            "start_server_once", selectedExternalDir, nativeLibraryDir, internalFilesDir, BuildConfig.VERSION_NAME
        )
    }

    private fun launchScreenFromBackground() {
        val launch = Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        if (!Settings.canDrawOverlays(this)) {
            Log.w(TAG, "Permission d'affichage par-dessus les autres applications absente : l'ecran s'ouvrira au lancement manuel")
            try {
                startActivity(launch)
            } catch (e: Exception) {
                Log.w(TAG, "Ouverture de l'ecran refusee : ${e.message}")
            }
            return
        }
        val windowManager = getSystemService(WindowManager::class.java)
        val anchor = View(this)
        val params = WindowManager.LayoutParams(
            1, 1,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
            PixelFormat.TRANSLUCENT,
        )
        try {
            windowManager.addView(anchor, params)
        } catch (e: Exception) {
            Log.w(TAG, "Fenetre d'ancrage impossible : ${e.message}")
        }
        handler.postDelayed({
            try {
                startActivity(launch)
                Log.i(TAG, "Ecran ouvert apres le demarrage")
            } catch (e: Exception) {
                Log.w(TAG, "Ouverture de l'ecran refusee : ${e.message}")
            }
            handler.postDelayed({
                try {
                    windowManager.removeView(anchor)
                } catch (_: Exception) {
                }
            }, 4000)
        }, 400)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.getBooleanExtra(EXTRA_LAUNCH_SCREEN, false) == true) {
            launchScreenFromBackground()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        if (instance === this) {
            instance = null
        }
        handler.removeCallbacks(reconcileRunnable)
        reportGeneration++ // annule les rapports en attente
        displayManager.unregisterDisplayListener(displayListener)
        presentation?.dismiss()
        presentation = null
        currentPresentation = null
        releaseWakeLock()
        releaseMulticastLock()
        releaseWifiLock()
        try {
            connectivityManager?.unregisterNetworkCallback(networkCallback)
            lanCallbacks.forEach { (_, callback) -> connectivityManager?.unregisterNetworkCallback(callback) }
        } catch (e: Exception) {
            Log.w(TAG, "Echec du desenregistrement du callback reseau : ${e.message}")
        }
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun getPresentationContext(): Context {
        val activity = MainActivity.activeActivity?.get()
        return if (activity != null && !activity.isFinishing && !activity.isDestroyed) {
            activity
        } else {
            this
        }
    }

    private fun showPresentationIfNeeded() {
        if (MainActivity.isTvDevice(this)) {
            return
        }
        if (presentation != null || presentationAttemptInFlight) return
        val external = externalDisplays().firstOrNull() ?: return

        val presentationContext = getPresentationContext()
        presentationAttemptInFlight = true
        try {
            Log.i(TAG, "Ouverture de la Presentation sur ${external.name} (id=${external.displayId}, flags=0x${Integer.toHexString(external.flags)}, context=${presentationContext.javaClass.simpleName})")
            presentation = BobinePresentation(presentationContext, external).also {
                it.show()
                currentPresentation = it
            }
            acquireWakeLock()
            presentationAttemptInFlight = false
            presentationRetries = 0
        } catch (e: Exception) {
            presentation = null
            currentPresentation = null
            presentationRetries++
            val delayMs = if (presentationRetries <= PRESENTATION_FAST_RETRIES) PRESENTATION_FAST_DELAY_MS else PRESENTATION_SLOW_DELAY_MS
            if (presentationRetries == 1 || presentationRetries == PRESENTATION_FAST_RETRIES + 1) {
                Log.w(TAG, "Presentation impossible sur l'ecran ${external.displayId} (tentative $presentationRetries), nouvel essai dans ${delayMs}ms", e)
            }
            handler.postDelayed({
                presentationAttemptInFlight = false
                showPresentationIfNeeded()
            }, delayMs)
        }
    }

    private fun acquireWakeLock() {
        if (wakeLock?.isHeld == true) return
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Bobine:hdmiPlayback").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    private fun releaseWakeLock() {
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
    }

    private fun acquireMulticastLock() {
        if (multicastLock?.isHeld == true) return
        val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        multicastLock = wifiManager.createMulticastLock("Bobine:mdns").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    private fun releaseMulticastLock() {
        multicastLock?.let { if (it.isHeld) it.release() }
        multicastLock = null
    }

    private fun acquireWifiLock() {
        if (wifiLock?.isHeld == true) return
        try {
            val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            wifiLock = wifiManager.createWifiLock(WifiManager.WIFI_MODE_FULL_LOW_LATENCY, "Bobine:faible-latence").apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Verrou Wi-Fi a faible latence indisponible", e)
        }
    }

    private fun releaseWifiLock() {
        wifiLock?.let { if (it.isHeld) it.release() }
        wifiLock = null
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            NOTIFICATION_CHANNEL_ID,
            "Bobine",
            NotificationManager.IMPORTANCE_LOW
        )
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val openAppIntent = packageManager.getLaunchIntentForPackage(packageName)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, openAppIntent,
            PendingIntent.FLAG_IMMUTABLE
        )
        return Notification.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Bobine")
            .setContentText("Bobine diffuse en arrière-plan")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }
}
