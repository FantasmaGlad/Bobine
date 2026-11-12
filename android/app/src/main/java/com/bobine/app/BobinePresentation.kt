package com.bobine.app

import android.annotation.SuppressLint
import android.app.Presentation
import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Display
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.WindowManager
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient

private const val CINEMA_PATH = "/cinema/?channel=cable"
private const val BACKEND_POLL_MS = 200L

class BobinePresentation(context: Context, display: Display) : Presentation(context, display) {

    private val handler = Handler(Looper.getMainLooper())
    var webView: WebView? = null
        private set

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window?.let { win ->
            win.addFlags(WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE)
            if (context !is android.app.Activity) {
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                    win.setType(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY)
                } else {
                    @Suppress("DEPRECATION")
                    win.setType(WindowManager.LayoutParams.TYPE_SYSTEM_ALERT)
                }
            }
        }

        val rootLayout = android.widget.FrameLayout(context).apply {
            setBackgroundColor(android.graphics.Color.parseColor("#0b0e14"))
        }

        val presentationBackground = android.graphics.Color.parseColor("#0b0e14")
        val presentationText = android.graphics.Color.parseColor("#94a3b8")
        val splashLayout = buildBootSplash(context, presentationBackground, presentationText, ThemeColors.load(context).accent, 160, 24, 56, 15f)

        var hasLoadedSuccessfully = false
        var lastPageFailed = false

        val webView = WebView(context)
        this.webView = webView
        webView.isFocusable = true
        webView.isFocusableInTouchMode = true
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.databaseEnabled = true
        webView.settings.mediaPlaybackRequiresUserGesture = false
        webView.settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
        webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false)
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                Log.d("BobinePresentationConsole", "${message.message()} (${message.sourceId()}:${message.lineNumber()})")
                return true
            }
        }
        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
                lastPageFailed = false
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
                            loadWhenBackendReady()
                        }
                    }, 400)
                }
            }

            override fun onPageFinished(view: WebView, url: String?) {
                if (!lastPageFailed && !hasLoadedSuccessfully && url != null && BackendEndpoint.isBackendUrl(context, url)) {
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
        loadWhenBackendReady()
        webView.onResume()
    }

    private var loadRetry = Runnable { }

    private fun loadWhenBackendReady() {
        handler.removeCallbacks(loadRetry)
        val url = BackendEndpoint.url(context, CINEMA_PATH)
        if (url != null) {
            webView?.loadUrl(url)
        } else {
            loadRetry = Runnable { loadWhenBackendReady() }
            handler.postDelayed(loadRetry, BACKEND_POLL_MS)
        }
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (webView?.dispatchKeyEvent(event) == true) {
            return true
        }
        return super.dispatchKeyEvent(event)
    }

    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
        if (webView?.dispatchGenericMotionEvent(event) == true) {
            return true
        }
        return super.dispatchGenericMotionEvent(event)
    }

    override fun dispatchTouchEvent(event: MotionEvent): Boolean {
        if (webView?.dispatchTouchEvent(event) == true) {
            return true
        }
        return super.dispatchTouchEvent(event)
    }

    override fun onStop() {
        handler.removeCallbacks(loadRetry)
        webView?.onPause()
        super.onStop()
    }
}
