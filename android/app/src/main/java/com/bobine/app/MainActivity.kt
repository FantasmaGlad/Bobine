package com.bobine.app

import android.annotation.SuppressLint
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python

// 127.0.0.2 (pas 127.0.0.1) : tout le bloc 127.0.0.0/8 est loopback, donc
// atteint le meme serveur local (confirme en pratique, Lot 3 - `nc` sur
// l'emulateur), mais useDisplayOutputRedirect() (frontend) classe "cable"
// UNIQUEMENT la chaine exacte "127.0.0.1"/"localhost" - cf.
// docs/PortabiliteAndroid.md SS4. L'ecran tactile (ce WebView) doit rester
// "reseau" pour ne pas suivre le reglage cableOutput destine a la sortie
// HDMI (Lot 4, qui chargera lui http://127.0.0.1:8000/cinema).
private const val KIOSK_URL = "http://127.0.0.2:8000/kiosk/"

/**
 * Activite minimale du Lot 2 (cf. docs/plan-implementation-android.md) :
 * demarre le vrai backend `app.main` (mis en scene par la tache Gradle
 * `stagePythonSources`) et affiche `/kiosk` dans une WebView - validation
 * de bout en bout backend+frontend, pas encore l'UI shell finale (Lot 5)
 * ni la persistance en arriere-plan (Lot 6).
 */
class MainActivity : AppCompatActivity() {

    private val handler = Handler(Looper.getMainLooper())

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val py = Python.getInstance()
        // `start_server_once` demarre uvicorn dans un thread Python et
        // rend la main IMMEDIATEMENT (le serveur n'ecoute pas encore) -
        // charger l'URL sans attendre echoue avec ERR_CONNECTION_REFUSED
        // (constate en pratique, Lot 2). D'ou la reessai automatique
        // ci-dessous plutot qu'un chargement direct.
        py.getModule("bobine_bootstrap").callAttr("start_server_once")

        // Debug uniquement (build debug) : console JS visible dans logcat
        // (tag "WebViewConsole") et inspection chrome://inspect — utile
        // pour diagnostiquer le routage /kiosk vs /cinema (Lot 3) et au-dela.
        WebView.setWebContentsDebuggingEnabled(true)

        val webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                Log.d("WebViewConsole", "${message.message()} (${message.sourceId()}:${message.lineNumber()})")
                return true
            }
        }
        webView.webViewClient = object : WebViewClient() {
            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError
            ) {
                if (request.isForMainFrame) {
                    handler.postDelayed({ view.loadUrl(KIOSK_URL) }, 500)
                }
            }
        }
        setContentView(webView)
        webView.loadUrl(KIOSK_URL)
    }
}
