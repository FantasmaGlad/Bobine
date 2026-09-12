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

// 127.0.0.1 (PAS 127.0.0.2 comme l'ecran tactile, cf. MainActivity) :
// isWiredDisplay() (frontend/src/lib/useDisplayOutputRedirect.ts) classe
// cet hostname exact "cable" - la sortie HDMI doit suivre le reglage
// cableOutput choisi par l'admin (CDC docs/ARCHITECTURE.md SS4),
// exactement comme le canal Cable existant sur mini PC x86.
private const val CINEMA_URL = "http://127.0.0.1:8000/cinema/"

/**
 * Lot 4 (cf. docs/plan-implementation-android.md) : rendu independant sur
 * l'ecran externe (HDMI via le dock USB-C), pas une simple recopie de
 * l'ecran tactile - c'est le mecanisme standard Android pour du contenu
 * reellement distinct par ecran (utilise par Chromecast/Android Auto).
 * Possede sa propre WebView, chargeant /cinema.
 */
class BobinePresentation(context: Context, display: Display) : Presentation(context, display) {

    private val handler = Handler(Looper.getMainLooper())
    var webView: WebView? = null
        private set

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Configuration de la fenetre pour accepter les touches, manettes et le pointeur externe
        window?.let { win ->
            win.clearFlags(WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE)
            win.decorView.isFocusable = true
            win.decorView.isFocusableInTouchMode = true
        }

        val webView = WebView(context)
        this.webView = webView
        webView.isFocusable = true
        webView.isFocusableInTouchMode = true
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.databaseEnabled = true
        webView.settings.mediaPlaybackRequiresUserGesture = false
        // LOAD_DEFAULT plutot que LOAD_NO_CACHE (Lot 15, docs/audit-android-
        // 2026-09-11.md §C4) : le probleme de fraicheur heuristique qui avait
        // motive LOAD_NO_CACHE est desormais couvert cote SERVEUR
        // (Cache-Control: no-cache + ETag sur le frontend statique, cf.
        // RevalidateStaticFiles dans backend/app/main.py) - une revalidation
        // ETag (304, quasi gratuite) suffit desormais a garantir la
        // fraicheur, sans re-telecharger integralement les bundles JS/CSS
        // (plusieurs Mo) a CHAQUE chargement de /cinema, couteux sur ce
        // materiel (h11 pur Python, stockage externe FUSE) et repete tres
        // souvent ici (reconnexion WebSocket, boot_id different -> reload
        // complet). Le bouton « Synchronisation des ecrans »
        // (clearCachesAndReload cote frontend) continue de vider le cache
        // HTTP explicitement pour forcer une vraie mise a jour.
        webView.settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
        // Lot 15 (docs/audit-android-2026-09-11.md §C2/C5) : priorite de
        // rendu elevee explicite - cette Presentation tourne portee par un
        // ForegroundService SANS Activity visible (importance systeme
        // potentiellement plus basse qu'une app au premier plan), alors
        // qu'elle affiche le flux video principal sur l'ecran HDMI. Sans
        // ceci, le compositeur de cette WebView herite d'une priorite par
        // defaut qui peut etre deprioritisee par le systeme au profit de
        // l'app au premier plan (ex. l'admin ouvert dans Chrome) - cause
        // probable des saccades video constatees.
        webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false)
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                Log.d("BobinePresentationConsole", "${message.message()} (${message.sourceId()}:${message.lineNumber()})")
                return true
            }
        }
        webView.webViewClient = object : WebViewClient() {
            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError
            ) {
                // Meme raison qu'au Lot 2 (MainActivity) : le serveur peut ne
                // pas encore ecouter au tout premier affichage.
                if (request.isForMainFrame) {
                    handler.postDelayed({ view.loadUrl(CINEMA_URL) }, 500)
                }
            }
        }
        setContentView(webView)
        webView.loadUrl(CINEMA_URL)
        webView.onResume()
        webView.requestFocus()
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
        webView?.onPause()
        super.onStop()
    }
}
