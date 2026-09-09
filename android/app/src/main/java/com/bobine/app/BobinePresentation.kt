package com.bobine.app

import android.annotation.SuppressLint
import android.app.Presentation
import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Display
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient

// 127.0.0.1 (PAS 127.0.0.2 comme l'ecran tactile, cf. MainActivity) :
// isWiredDisplay() (frontend/src/lib/useDisplayOutputRedirect.ts) classe
// cet hostname exact "cable" - la sortie HDMI doit suivre le reglage
// cableOutput choisi par l'admin (CDC docs/PortabiliteAndroid.md SS4),
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

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val webView = WebView(context)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.databaseEnabled = true
        webView.settings.mediaPlaybackRequiresUserGesture = false
        // Reglage decouvert lors d'un correctif ulterieur (cf.
        // docs/plan-implementation-android.md, "cache HTTP WebView") : le
        // backend local est reinstalle avec du code different a chaque mise
        // a jour de l'app, mais l'export statique Next.js voit son horodatage
        // de fichier normalise a une date fixe tres ancienne par le
        // paquetage - sans ce reglage, la WebView calcule une fraicheur HTTP
        // heuristique de plusieurs ANNEES a partir de ce Last-Modified absurde
        // et ne recharge alors plus jamais /cinema depuis le reseau, meme
        // apres une reinstallation avec un frontend different. Le cout d'un
        // aller-retour reseau est negligeable ici (backend en local, 127.0.0.1).
        webView.settings.cacheMode = android.webkit.WebSettings.LOAD_NO_CACHE
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
    }
}
