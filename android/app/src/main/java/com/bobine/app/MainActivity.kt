package com.bobine.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import android.view.WindowInsets
import android.view.WindowInsetsController
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

// Revision du 2026-09-09 (Lot 14, demande explicite utilisateur) : l'ecran
// tactile charge desormais /grid, pas /cinema - une grille de selection
// SEULE, qui ne bascule jamais vers un lecteur video local. Choisir un
// cours au toucher envoie un ordre "launch" sur le canal cable (meme
// mecanisme que les commandes admin play/pause/seek/stop deja existantes,
// cf. docs/plan-implementation-android.md Lot 14) - c'est BobinePresentation
// (HDMI, /cinema, cf. Lot 4) qui joue reellement le cours. Sans cette
// separation, la tablette aurait aussi redecode/rejoue la meme video que
// l'ecran HDMI des qu'un cours demarre (les deux chargeaient /cinema,
// qui ne distingue aucun role primaire/miroir dans son rendu).
private const val GRID_URL = "http://127.0.0.1:8000/grid/"

/**
 * Ecran tactile de la tablette (Lot 5, cf. docs/plan-implementation-android.md) :
 * plein ecran immersif au demarrage, mais PAS de Lock Task - un geste
 * standard Android (Accueil, multitache) reste actif a tout moment (CDC
 * docs/PortabiliteAndroid.md SS2/SS7, decision explicite : la tablette
 * reste utilisable pour autre chose, pas un poste dedie).
 *
 * Ne demarre plus le backend elle-meme depuis le Lot 6 : c'est
 * `BobineForegroundService` qui le fait, decouple du cycle de vie de
 * cette Activity - fermer l'app ne coupe plus la diffusion HDMI.
 */
class MainActivity : AppCompatActivity() {

    private val handler = Handler(Looper.getMainLooper())

    // POST_NOTIFICATIONS (API 33+) est une permission "dangereuse" - la
    // declarer dans le Manifest ne l'accorde PAS automatiquement, une
    // demande explicite a l'utilisateur est necessaire. Sans elle,
    // `startForeground()` (BobineForegroundService) demarre quand meme le
    // service normalement (pas de crash) mais la notification persistante
    // reste invisible - constate en pratique (Lot 6) : le service et le
    // serveur survivaient bien a la fermeture de l'app, mais
    // `dumpsys notification` ne montrait rien pour com.bobine.app.
    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { /* resultat ignore : au pire la notification reste invisible, rien de bloquant */ }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        requestIgnoreBatteryOptimizations()
        UpdateManager.checkForUpdate(this)

        startForegroundService(Intent(this, BobineForegroundService::class.java))
        // Pas d'appel a applyImmersiveFullscreen() ici : la fenetre n'est pas
        // encore attachee a ce stade (`window.insetsController` est null,
        // NullPointerException constatee en pratique). onWindowFocusChanged
        // ci-dessous s'en charge, garanti appele une fois la fenetre reelle.

        // Debug uniquement (build debug) : console JS visible dans logcat
        // (tag "WebViewConsole") et inspection chrome://inspect.
        WebView.setWebContentsDebuggingEnabled(true)

        val webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        // Meme raison que BobinePresentation.kt (cf. son commentaire) : sans
        // ce reglage, une mise a jour de l'app peut rester invisible sur cet
        // ecran (cache HTTP heuristique base sur un Last-Modified de fichier
        // normalise par le paquetage, sans rapport avec la vraie date de
        // build).
        webView.settings.cacheMode = WebSettings.LOAD_NO_CACHE
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
                    handler.postDelayed({ view.loadUrl(GRID_URL) }, 500)
                }
            }
        }
        setContentView(webView)
        webView.loadUrl(GRID_URL)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        // Reapplique l'immersion a chaque retour au premier plan : un geste
        // systeme (barre de notifications, multitache) la leve
        // temporairement, comportement standard Android a reproduire
        // volontairement (pas un blocage, juste une remise en place).
        if (hasFocus) applyImmersiveFullscreen()
    }

    // Lot 10 (cf. docs/plan-implementation-android.md) : sans exemption
    // Doze/optimisation batterie, le systeme peut ralentir/suspendre le
    // ForegroundService apres une longue inactivite ecran (le service
    // reste demarre, mais son travail de fond - reseau, timers - peut
    // etre differe). REQUEST_IGNORE_BATTERY_OPTIMIZATIONS est une
    // permission normale (pas de prompt) mais l'action elle-meme affiche
    // TOUJOURS une boite de dialogue systeme une fois - acceptable ici
    // (demande unique a l'installation initiale, pas a chaque demarrage,
    // cf. isIgnoringBatteryOptimizations ci-dessous), contrairement a un
    // contournement silencieux via Device Owner dont l'existence n'a pas
    // ete confirmee de facon fiable inter-OEM (cf. Decouvertes du Lot 10 -
    // HyperOS/MIUI est connu pour ignorer les mecanismes AOSP standards et
    // exiger des reglages constructeur additionnels, non automatisables
    // depuis l'app).
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
