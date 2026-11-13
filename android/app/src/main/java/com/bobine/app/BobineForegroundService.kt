package com.bobine.app

import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.display.DisplayManager
import android.net.ConnectivityManager
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import android.view.Display

private const val TAG = "BobineForegroundService"
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
            svc.handler.post { svc.showPresentationIfNeeded() }
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private val locks = ServiceLocks(this)
    private val reporter = DisplayStateReporter(this, handler)
    private lateinit var displayManager: DisplayManager
    private var network: NetworkWatch? = null
    private var presentation: BobinePresentation? = null
    private var presentationRetries = 0
    private var presentationAttemptInFlight = false

    private val displayListener = object : DisplayManager.DisplayListener {
        override fun onDisplayAdded(displayId: Int) {
            Log.i(TAG, "Ecran detecte (displayId=$displayId) : ${describeDisplays()}")
            presentationRetries = 0
            refreshDisplays()
        }

        override fun onDisplayRemoved(displayId: Int) {
            Log.i(TAG, "Ecran retire (displayId=$displayId) : ${describeDisplays()}")
            val current = presentation
            if (current != null && (current.display.displayId == displayId || externalDisplays().isEmpty())) closePresentation()
            refreshDisplays()
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

    private val reconcileRunnable = object : Runnable {
        override fun run() {
            val current = presentation
            if (current != null && !current.isShowing) {
                Log.w(TAG, "Presentation fermee par le systeme : reouverture")
                closePresentation()
            }
            refreshDisplays()
            handler.postDelayed(this, RECONCILE_INTERVAL_MS)
        }
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
        startForeground(SERVICE_NOTIFICATION_ID, serviceNotification(this))
        locks.acquireMulticast()
        locks.acquireWifi()
        network = NetworkWatch(getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager, locks).also { it.start() }
        EmbeddedServer(this, handler).startWhenStorageReady()
        displayManager = getSystemService(Context.DISPLAY_SERVICE) as DisplayManager
        displayManager.registerDisplayListener(displayListener, null)
        Log.i(TAG, "Ecrans au demarrage : ${describeDisplays()}")
        refreshDisplays()
        handler.postDelayed(reconcileRunnable, RECONCILE_INTERVAL_MS)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.getBooleanExtra(EXTRA_LAUNCH_SCREEN, false) == true) launchScreenFromBackground(this, handler)
        return START_STICKY
    }

    override fun onDestroy() {
        if (instance === this) instance = null
        handler.removeCallbacks(reconcileRunnable)
        reporter.cancel()
        displayManager.unregisterDisplayListener(displayListener)
        presentation?.dismiss()
        presentation = null
        currentPresentation = null
        locks.releaseAll()
        network?.stop()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun externalDisplays(): List<Display> =
        displayManager.displays
            .filter { it.displayId != Display.DEFAULT_DISPLAY && (it.flags and Display.FLAG_PRIVATE) == 0 }
            .sortedByDescending { (it.flags and Display.FLAG_PRESENTATION) != 0 }

    private fun describeDisplays(): String =
        displayManager.displays.joinToString { "[id=${it.displayId} nom='${it.name}' flags=0x${Integer.toHexString(it.flags)} etat=${it.state}]" }

    private fun refreshDisplays() {
        showPresentationIfNeeded()
        reportDisplayState()
    }

    private fun reportDisplayState() {
        val externals = externalDisplays()
        reporter.report(externals.size, externals.firstOrNull()?.let { "${it.mode.physicalWidth}x${it.mode.physicalHeight}" })
    }

    private fun closePresentation() {
        presentation?.dismiss()
        presentation = null
        currentPresentation = null
        locks.releaseWake()
    }

    private fun presentationContext(): Context {
        val activity = MainActivity.activeActivity?.get()
        return if (activity != null && !activity.isFinishing && !activity.isDestroyed) activity else this
    }

    private fun showPresentationIfNeeded() {
        if (MainActivity.isTvDevice(this)) return
        if (presentation != null || presentationAttemptInFlight) return
        val external = externalDisplays().firstOrNull() ?: return
        val context = presentationContext()
        presentationAttemptInFlight = true
        try {
            Log.i(TAG, "Ouverture de la Presentation sur ${external.name} (id=${external.displayId}, flags=0x${Integer.toHexString(external.flags)}, context=${context.javaClass.simpleName})")
            presentation = BobinePresentation(context, external).also {
                it.show()
                currentPresentation = it
            }
            locks.acquireWake()
            presentationAttemptInFlight = false
            presentationRetries = 0
        } catch (e: Exception) {
            presentation = null
            currentPresentation = null
            retryPresentation(external.displayId, e)
        }
    }

    private fun retryPresentation(displayId: Int, error: Exception) {
        presentationRetries++
        val delayMs = if (presentationRetries <= PRESENTATION_FAST_RETRIES) PRESENTATION_FAST_DELAY_MS else PRESENTATION_SLOW_DELAY_MS
        if (presentationRetries == 1 || presentationRetries == PRESENTATION_FAST_RETRIES + 1) {
            Log.w(TAG, "Presentation impossible sur l'ecran $displayId (tentative $presentationRetries), nouvel essai dans ${delayMs}ms", error)
        }
        handler.postDelayed({
            presentationAttemptInFlight = false
            showPresentationIfNeeded()
        }, delayMs)
    }
}
