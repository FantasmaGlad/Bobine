package com.bobine.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.UiModeManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

private const val GRID_PATH = "/grid/"
private const val KIOSK_PATH = "/kiosk"
private const val BACKEND_POLL_MS = 200L

class MainActivity : AppCompatActivity() {

    companion object {
        @Volatile
        var activeActivity: java.lang.ref.WeakReference<MainActivity>? = null
            private set

        fun isTvDevice(context: Context): Boolean {
            val uiModeManager = context.getSystemService(Context.UI_MODE_SERVICE) as? UiModeManager
            return uiModeManager?.currentModeType == Configuration.UI_MODE_TYPE_TELEVISION
                || context.packageManager.hasSystemFeature(PackageManager.FEATURE_LEANBACK)
                || context.packageName.endsWith(".tv")
        }
    }

    private val isTv: Boolean by lazy { isTvDevice(this) }

    private val handler = Handler(Looper.getMainLooper())
    private var loadRetry = Runnable { }
    private var webView: WebView? = null

    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { /* resultat ignore : au pire la notification reste invisible, rien de bloquant */ }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        activeActivity = java.lang.ref.WeakReference(this)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        requestIgnoreBatteryOptimizations()
        requestOverlayPermissionOnce()
        UpdateManager.cleanupStaleDownloads(this)

        startForegroundService(Intent(this, BobineForegroundService::class.java))

        if (isTv) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
        val initialPath = if (isTv) KIOSK_PATH else GRID_PATH

        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)

        val themeColors = ThemeColors.load(this)
        window.setBackgroundDrawable(android.graphics.drawable.ColorDrawable(themeColors.background))
        val rootLayout = android.widget.FrameLayout(this).apply {
            setBackgroundColor(themeColors.background)
        }

        val splashLayout = buildBootSplash(this, themeColors.background, themeColors.text, themeColors.accent, 140, 22, if (isTv) 56 else 40, 14f)

        var hasLoadedSuccessfully = false
        var lastPageFailed = false

        val webView = WebView(this)
        this.webView = webView
        webView.addJavascriptInterface(NativeBridge(applicationContext), "BobineNative")
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.databaseEnabled = true
        webView.settings.mediaPlaybackRequiresUserGesture = false
        webView.settings.cacheMode = WebSettings.LOAD_DEFAULT
        webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false)
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                Log.d("WebViewConsole", "${message.message()} (${message.sourceId()}:${message.lineNumber()})")
                return true
            }
        }
        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
                lastPageFailed = false
            }

            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest
            ): Boolean {
                val uri = request.url
                val path = uri.path ?: ""
                val host = uri.host ?: ""
                val isLocal = host == "127.0.0.1" || host == "localhost"

                if (!isTv) {
                    if (path != "/grid" && !path.startsWith("/grid/")) {
                        try {
                            val intent = Intent(Intent.ACTION_VIEW, uri)
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            view.context.startActivity(intent)
                            return true
                        } catch (e: Exception) {
                            Log.w("MainActivity", "Impossible d'ouvrir le navigateur externe pour $uri", e)
                        }
                    }
                } else {
                    if (!isLocal) {
                        try {
                            val intent = Intent(Intent.ACTION_VIEW, uri)
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            view.context.startActivity(intent)
                            return true
                        } catch (e: Exception) {
                            Log.w("MainActivity", "Impossible d'ouvrir le lien externe pour $uri", e)
                        }
                    }
                }
                return false
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError
            ) {
                if (request.isForMainFrame) {
                    lastPageFailed = true
                    handler.postDelayed({
                        if (!hasLoadedSuccessfully) {
                            loadWhenBackendReady(initialPath)
                        }
                    }, 400)
                }
            }

            override fun onPageFinished(view: WebView, url: String?) {
                if (!lastPageFailed && !hasLoadedSuccessfully && url != null && BackendEndpoint.isBackendUrl(this@MainActivity, url)) {
                    hasLoadedSuccessfully = true
                    splashLayout.animate()
                        .alpha(0f)
                        .setDuration(350)
                        .withEndAction {
                            splashLayout.visibility = android.view.View.GONE
                        }
                }
            }
        }
        rootLayout.addView(webView, android.widget.FrameLayout.LayoutParams(
            android.widget.FrameLayout.LayoutParams.MATCH_PARENT,
            android.widget.FrameLayout.LayoutParams.MATCH_PARENT
        ))
        rootLayout.addView(splashLayout)
        setContentView(rootLayout)
        androidx.core.view.WindowCompat.getInsetsController(window, rootLayout).isAppearanceLightStatusBars =
            androidx.core.graphics.ColorUtils.calculateLuminance(themeColors.background) > 0.5
        loadWhenBackendReady(initialPath)
    }

    private fun loadWhenBackendReady(path: String) {
        handler.removeCallbacks(loadRetry)
        val url = BackendEndpoint.url(this, path)
        if (url != null) {
            webView?.loadUrl(url)
        } else {
            loadRetry = Runnable { loadWhenBackendReady(path) }
            handler.postDelayed(loadRetry, BACKEND_POLL_MS)
        }
    }

    override fun onResume() {
        super.onResume()
        activeActivity = java.lang.ref.WeakReference(this)
        BobineForegroundService.notifyDisplayStateChanged()
        webView?.onResume()
    }

    override fun onPause() {
        webView?.onPause()
        super.onPause()
    }

    override fun onDestroy() {
        handler.removeCallbacks(loadRetry)
        if (activeActivity?.get() === this) {
            activeActivity = null
        }
        super.onDestroy()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) applyImmersiveFullscreen()
    }

    private fun requestOverlayPermissionOnce() {
        if (Settings.canDrawOverlays(this) || !StartOnBoot.isEnabled(this)) return
        val prefs = getSharedPreferences("bobine_native", MODE_PRIVATE)
        if (prefs.getBoolean("overlay_permission_asked", false)) return
        prefs.edit().putBoolean("overlay_permission_asked", true).apply()
        try {
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
        } catch (e: Exception) {
            Log.w("MainActivity", "Ecran de permission d'affichage indisponible sur cet appareil", e)
        }
    }

    private fun requestIgnoreBatteryOptimizations() {
        val powerManager = getSystemService(PowerManager::class.java)
        if (!powerManager.isIgnoringBatteryOptimizations(packageName)) {
            try {
                startActivity(Intent(
                    Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                    Uri.parse("package:$packageName")
                ))
            } catch (e: Exception) {
                Log.w("MainActivity", "Impossible de demander l'exemption batterie", e)
            }
        }
    }

    private fun relayKeyToWeb(key: String, keyCode: Int, toPresentation: Boolean) {
        val script = "window.dispatchEvent(new KeyboardEvent('keydown', " +
            "{ key: '$key', code: '$key', keyCode: $keyCode, which: $keyCode, bubbles: true, cancelable: true }))"
        webView?.evaluateJavascript(script, null)
        if (toPresentation) BobineForegroundService.currentPresentation?.webView?.evaluateJavascript(script, null)
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (isTv) {
            if (event.keyCode == KeyEvent.KEYCODE_BACK) {
                if (event.action == KeyEvent.ACTION_DOWN) {
                    if (webView?.canGoBack() == true) webView?.goBack()
                    else relayKeyToWeb("Escape", 27, toPresentation = false)
                }
                return true
            }
        }

        if (super.dispatchKeyEvent(event)) {
            return true
        }
        val pres = BobineForegroundService.currentPresentation
        if (pres != null && pres.isShowing) {
            if (pres.dispatchKeyEvent(event)) {
                return true
            }
        }
        return false
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView?.canGoBack() == true) {
            webView?.goBack()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
        if (super.dispatchGenericMotionEvent(event)) {
            return true
        }
        val pres = BobineForegroundService.currentPresentation
        if (pres != null && pres.isShowing) {
            if (pres.dispatchGenericMotionEvent(event)) {
                return true
            }
        }
        return false
    }

    private fun applyImmersiveFullscreen() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.insetsController?.let { controller ->
                controller.hide(WindowInsets.Type.systemBars())
                controller.systemBarsBehavior =
                    WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = (
                android.view.View.SYSTEM_UI_FLAG_IMMERSIVE or
                android.view.View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
                android.view.View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
                android.view.View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                android.view.View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                android.view.View.SYSTEM_UI_FLAG_FULLSCREEN
            )
        }
    }
}
