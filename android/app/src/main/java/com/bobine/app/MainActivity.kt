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

// Revision du 2026-09-09 : l'ecran
// tactile charge desormais /grid, pas /cinema - une grille de selection
// SEULE, qui ne bascule jamais vers un lecteur video local. Choisir un
// cours au toucher envoie un ordre "launch" sur le canal cable (meme
// mecanisme que les commandes admin play/pause/seek/stop deja existantes) - c'est BobinePresentation
// (HDMI, /cinema) qui joue reellement le cours. Sans cette
// separation, la tablette aurait aussi redecode/rejoue la meme video que
// l'ecran HDMI des qu'un cours demarre (les deux chargeaient /cinema,
// qui ne distingue aucun role primaire/miroir dans son rendu).
private const val GRID_URL = "http://127.0.0.1:8000/grid/"
// Sur Android TV / Google TV, l'ecran principal est le grand ecran de la TV.
// On charge /kiosk par defaut, concu pour la navigation D-Pad a la telecommande.
private const val KIOSK_URL = "http://127.0.0.1:8000/kiosk"

/**
 * Ecran tactile de la tablette ou affichage Leanback Android TV :
 * plein ecran immersif au demarrage, mais PAS de Lock Task - un geste
 * standard Android (Accueil, multitache) reste actif a tout moment.
 *
 * Ne demarre plus le backend elle-meme : c'est
 * `BobineForegroundService` qui le fait, decouple du cycle de vie de
 * cette Activity - fermer l'app ne coupe plus la diffusion HDMI.
 */
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

    private val handler = Handler(Looper.getMainLooper())
    // champ de classe
    // plutot qu'une simple val locale de onCreate() - necessaire pour
    // relayer onResume()/onPause() de l'Activity vers la WebView
    // (webView.onResume()/onPause() pilotent son cycle de rendu interne,
    // distinct du cycle de vie Android).
    private var webView: WebView? = null

    // POST_NOTIFICATIONS (API 33+) est une permission "dangereuse" - la
    // declarer dans le Manifest ne l'accorde PAS automatiquement, une
    // demande explicite a l'utilisateur est necessaire. Sans elle,
    // `startForeground()` (BobineForegroundService) demarre quand meme le
    // service normalement (pas de crash) mais la notification persistante
    // reste invisible - constate en pratique : le service et le
    // serveur survivaient bien a la fermeture de l'app, mais
    // `dumpsys notification` ne montrait rien pour com.bobine.app.
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
        // Plus de telechargement spontane ici (cf. UpdateManager) : seulement
        // le menage d'un APK deja installe ou perime.
        UpdateManager.cleanupStaleDownloads(this)

        startForegroundService(Intent(this, BobineForegroundService::class.java))
        // Pas d'appel a applyImmersiveFullscreen() ici : la fenetre n'est pas
        // encore attachee a ce stade (`window.insetsController` est null,
        // NullPointerException constatee en pratique). onWindowFocusChanged
        // ci-dessous s'en charge, garanti appele une fois la fenetre reelle.

        val isTv = isTvDevice(this)
        if (isTv) {
            // Sur Android TV : neutralise la veille d'ecran Daydream / Ambient pendant l'utilisation de Bobine
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
        val initialUrl = if (isTv) KIOSK_URL else GRID_URL

        // Debug uniquement (build debug) : console JS visible dans logcat
        // (tag "WebViewConsole") et inspection chrome://inspect. Restreint
        // au build debug : rester actif en release ouvrait une
        // surface de debogage locale inutile en production, sans aucun
        // benefice (personne n'inspecte un kiosque de salle via USB).
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)

        // Conteneur racine avec écran de chargement statique (logo Bobine)
        // Masque le temps de démarrage du serveur Python embarqué (1 à 2s)
        // évitant l'affichage de l'erreur réseau standard d'Android ("net::ERR_CONNECTION_REFUSED").
        // Couleurs du thème choisi dans l'application (envoyées par l'interface web à chaque
        // changement), pour que l'écran de chargement ne soit plus un noir fixe.
        val themeColors = ThemeColors.load(this)
        window.setBackgroundDrawable(android.graphics.drawable.ColorDrawable(themeColors.background))
        val rootLayout = android.widget.FrameLayout(this).apply {
            setBackgroundColor(themeColors.background)
        }

        val splashLayout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            gravity = android.view.Gravity.CENTER
            setBackgroundColor(themeColors.background)
            layoutParams = android.widget.FrameLayout.LayoutParams(
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT,
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT
            )
        }

        val logoSizePx = (140 * resources.displayMetrics.density).toInt()
        val logoView = android.widget.ImageView(this).apply {
            setImageResource(SplashChannel.initialDrawable(this@MainActivity))
            layoutParams = android.widget.LinearLayout.LayoutParams(logoSizePx, logoSizePx).apply {
                bottomMargin = (22 * resources.displayMetrics.density).toInt()
            }
            adjustViewBounds = true
        }
        splashLayout.addView(logoView)
        SplashChannel.refreshFromBackendIfUnknown(this, logoView)

        val progressBar = android.widget.ProgressBar(this).apply {
            isIndeterminate = true
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                bottomMargin = (16 * resources.displayMetrics.density).toInt()
            }
        }
        splashLayout.addView(progressBar)

        val statusText = android.widget.TextView(this).apply {
            text = "Démarrage de Bobine..."
            setTextColor(themeColors.text)
            textSize = 14f
            typeface = android.graphics.Typeface.DEFAULT_BOLD
            gravity = android.view.Gravity.CENTER
        }
        splashLayout.addView(statusText)

        var hasLoadedSuccessfully = false
        var lastPageFailed = false

        val webView = WebView(this)
        this.webView = webView
        webView.addJavascriptInterface(NativeBridge(applicationContext), "BobineNative")
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.databaseEnabled = true
        webView.settings.mediaPlaybackRequiresUserGesture = false
        // LOAD_DEFAULT plutot que LOAD_NO_CACHE : le serveur impose deja une revalidation
        // systematique (Cache-Control: no-cache + ETag, cf.
        // RevalidateStaticFiles dans backend/app/main.py, ajoute APRES la
        // decouverte initiale du probleme de cache HTTP heuristique
        // mentionnee dans l'historique de ce fichier) - un fichier inchange
        // recoit desormais un 304 quasi gratuit au lieu d'un retelechargement
        // integral a CHAQUE chargement de page, couteux sur ce materiel
        // (h11 pur Python, stockage externe FUSE). Le bouton « Synchronisation
        // des ecrans » (clearCachesAndReload cote frontend) continue de vider
        // le cache HTTP explicitement pour forcer une vraie mise a jour.
        webView.settings.cacheMode = WebSettings.LOAD_DEFAULT
        // priorite de rendu
        // elevee meme quand cette Activity passe en arriere-plan (l'admin
        // ouvert dans Chrome par-dessus) - sans ceci, le systeme peut
        // deprioriser fortement le compositeur de cette WebView, aggravant
        // les saccades constatees lors d'un retour au premier plan.
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
                    // Mode tablette / mobile tactile :
                    // Si la navigation quitte la grille (ex: acces a l'administration / ou tout lien externe),
                    // on l'ouvre directement dans le navigateur systeme par defaut pour ne pas pieger l'utilisateur
                    // dans une WebView en plein ecran sans barre de navigation ni retour.
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
                    // Mode Android TV & Google TV :
                    // L'utilisateur navigue au D-Pad de la telecommande entre /kiosk, /cinema, /radio, etc.
                    // Tout le contenu local Bobine reste dans la WebView. Seuls les liens distants tiers ouvrent un navigateur externe.
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
                    // Ne pas révéler la page d'erreur blanche/brute du navigateur
                    handler.postDelayed({
                        if (!hasLoadedSuccessfully) {
                            view.loadUrl(initialUrl)
                        }
                    }, 400)
                }
            }

            override fun onPageFinished(view: WebView, url: String?) {
                if (!lastPageFailed && !hasLoadedSuccessfully && url != null && url.startsWith("http://127.0.0.1:8000")) {
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
        // Icones de la barre d'etat lisibles : sombres sur un theme clair, claires sur un theme sombre.
        androidx.core.view.WindowCompat.getInsetsController(window, rootLayout).isAppearanceLightStatusBars =
            androidx.core.graphics.ColorUtils.calculateLuminance(themeColors.background) > 0.5
        webView.loadUrl(initialUrl)
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
        if (activeActivity?.get() === this) {
            activeActivity = null
        }
        super.onDestroy()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        // Reapplique l'immersion a chaque retour au premier plan : un geste
        // systeme (barre de notifications, multitache) la leve
        // temporairement, comportement standard Android a reproduire
        // volontairement (pas un blocage, juste une remise en place).
        if (hasFocus) applyImmersiveFullscreen()
    }

    // sans exemption
    // Doze/optimisation batterie, le systeme peut ralentir/suspendre le
    // ForegroundService apres une longue inactivite ecran (le service
    // reste demarre, mais son travail de fond - reseau, timers - peut
    // etre differe). REQUEST_IGNORE_BATTERY_OPTIMIZATIONS est une
    // permission normale (pas de prompt) mais l'action elle-meme affiche
    // TOUJOURS une boite de dialogue systeme une fois - acceptable ici
    // (demande unique a l'installation initiale, pas a chaque demarrage,
    // cf. isIgnoringBatteryOptimizations ci-dessous), contrairement a un
    // contournement silencieux via Device Owner dont l'existence n'a pas
    // ete confirmee de facon fiable inter-OEM ( -
    // HyperOS/MIUI est connu pour ignorer les mecanismes AOSP standards et
    // exiger des reglages constructeur additionnels, non automatisables
    // depuis l'app).
    /**
     * Demande UNE fois la permission « afficher par-dessus d'autres applications », necessaire
     * pour rouvrir l'ecran seul apres un redemarrage. Certains appareils (Android TV) n'ont pas
     * cet ecran de reglages : le serveur redemarre quand meme, l'ecran s'ouvre au lancement.
     */
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

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        // Priorite a l'interface locale tactile de la tablette (/grid) :
        // si MainActivity ou sa WebView consomme l'evenement (navigation, enter, play/pause),
        // on ne le deroute pas.
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
        // Navigation D-Pad telecommande Android TV : le bouton retour revient a la vue precedente
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
