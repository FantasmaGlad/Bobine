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
private const val DISPLAY_STATE_URL = "http://127.0.0.1:8000/api/display/state"
// Re-émission périodique de l'état des écrans : le rapport
// côté backend est volontairement gardé en mémoire (un fait matériel
// instantané) ; si le serveur Python redémarre sans que le service le fasse,
// ce rappel le remet à jour. Sert aussi de filet de réconciliation de la
// `Presentation` (cf. reconcileDisplays).
private const val RECONCILE_INTERVAL_MS = 60_000L
// Cadence des nouvelles tentatives d'ouverture de la `Presentation` : rapide au
// début (le WindowManager peut ne pas être prêt), puis lente et SANS abandon
// définitif — un projecteur dont l'EDID arrive tard n'est ainsi jamais perdu.
private const val PRESENTATION_FAST_RETRIES = 15
private const val PRESENTATION_FAST_DELAY_MS = 500L
private const val PRESENTATION_SLOW_DELAY_MS = 5_000L

/**
 * porte le backend Python
 * et la `Presentation` HDMI, DECOUPLE du cycle de vie de
 * `MainActivity` - c'est ce qui permet au cours de continuer de jouer sur
 * la sortie HDMI meme si l'app est fermee depuis le multitache.
 *
 * L'exemption batterie est demandee via la boite de dialogue systeme
 * standard (`MainActivity.requestIgnoreBatteryOptimizations`, appelee une
 * fois a l'installation) plutot qu'un contournement silencieux via Device
 * Owner - fiabilite inter-OEM non confirmee (HyperOS/MIUI notamment
 * ignore les mecanismes AOSP standards). Le redemarrage apres un "kill"
 * complet du processus par le systeme reste en revanche non garanti
 * (`onTaskRemoved` fait de son mieux mais un ForegroundService seul reste
 * soumis aux politiques d'economie d'energie agressives de certains
 * constructeurs).
 */
class BobineForegroundService : Service() {

    companion object {
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
    // Empeche deux chaines de reessai concurrentes de s'executer en
    // parallele (constate en pratique : le listener DisplayManager ET
    // l'appel explicite de onCreate() peuvent toutes deux declencher une
    // premiere tentative quasi simultanee, epuisant les 5 essais en
    // quelques dizaines de ms au lieu d'un vrai backoff de 500ms chacun).
    private var presentationAttemptInFlight = false
    // PARTIAL_WAKE_LOCK (CPU seul, pas l'ecran tactile - l'immersion de
    // MainActivity s'occupe de l'ecran tactile separement) : empeche le systeme
    // de suspendre le CPU pendant qu'un cours est activement diffuse sur
    // la sortie HDMI, uniquement le temps ou la Presentation existe.
    private var wakeLock: PowerManager.WakeLock? = null

    // par defaut, Android ne livre PAS les paquets multicast (mDNS
    // inclus) au processus applicatif tant qu'aucun MulticastLock n'est
    // detenu - la decouverte reseau du backend (zeroconf, bobine.local)
    // resterait invisible depuis un autre appareil du meme Wi-Fi sans
    // cela, meme si le serveur ecoute correctement. Un seul lock pour
    // toute la duree de vie du service (pas de reference-count fine par
    // requete : la decouverte doit rester possible en permanence, pas
    // seulement pendant une operation ponctuelle).
    private var multicastLock: WifiManager.MulticastLock? = null

    // Re-acquisition du verrou multicast sur changement de reseau : une
    // acquisition unique a onCreate() ne suffit pas toujours - certains
    // pilotes radio (HyperOS/MIUI notamment, deja connus pour leur propre
    // gestion Wi-Fi hors-AOSP) reinitialisent le filtrage multicast lors
    // d'une reassociation (nouveau reseau, ou simple perte puis retour de
    // connexion), laissant la decouverte mDNS (zeroconf, bobine.local)
    // invisible depuis un autre appareil du Wi-Fi jusqu'au redemarrage
    // complet du service - cause plausible de l'instabilite mDNS
    // constatee en usage reel sur ce profil.
    private var connectivityManager: ConnectivityManager? = null
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            Log.i(TAG, "Reseau disponible (network=$network) - re-acquisition du verrou multicast mDNS")
            releaseMulticastLock()
            acquireMulticastLock()
        }
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
            // Ne ferme la Presentation que si SON ecran a disparu (ou s'il n'y
            // a plus aucun ecran externe) : retirer un autre ecran virtuel ne
            // doit pas couper la sortie HDMI.
            val current = presentation
            if (current != null && (current.display.displayId == displayId || externalDisplays().isEmpty())) {
                current.dismiss()
                presentation = null
                currentPresentation = null
                releaseWakeLock()
            }
            // Un autre ecran externe peut prendre le relais immediatement.
            showPresentationIfNeeded()
            reportDisplayState()
        }

        // Un ecran deja connu change (resolution/mode negocie apres coup, mise
        // sous tension d'un projecteur, EDID tardif...) : avant ce correctif ce
        // callback etait vide, et une Presentation abandonnee ou jamais ouverte
        // n'etait plus jamais retentee sans rebrancher le cable.
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

    /**
     * Ecrans EXTERNES reellement utilisables comme sortie de diffusion : tout
     * `Display` autre que l'ecran integre, SAUF les ecrans prives (virtuels
     * crees par une autre application, ex. enregistrement d'ecran) qui n'ont
     * aucune raison de recevoir /cinema. Les ecrans marques `FLAG_PRESENTATION`
     * passent en premier. Volontairement pas limite a la categorie
     * PRESENTATION : le HDMI de la tablette pilote n'a pas ete verifie comme
     * portant ce drapeau sur tous les OEM (HyperOS), l'exclure aurait pu
     * supprimer la vraie sortie.
     */
    private fun externalDisplays(): List<Display> =
        displayManager.displays
            .filter { it.displayId != Display.DEFAULT_DISPLAY && (it.flags and Display.FLAG_PRIVATE) == 0 }
            .sortedByDescending { (it.flags and Display.FLAG_PRESENTATION) != 0 }

    private fun describeDisplays(): String =
        displayManager.displays.joinToString { "[id=${it.displayId} nom='${it.name}' flags=0x${Integer.toHexString(it.flags)} etat=${it.state}]" }

    /**
     * Remonte au backend le nombre d'ecrans externes REELLEMENT connectes
     * (`PUT /api/display/state`) : le mode d'affichage cable
     * effectif en est derive cote serveur (>= 1 ecran = double ecran), sans
     * reglage manuel — avant, ce signal n'etait envoye qu'une fois et un echec
     * (serveur Python embarque pas encore a l'ecoute au demarrage a froid) etait
     * perdu pour de bon.
     *
     * Rejouable : en cas d'echec on reessaie avec un delai croissant tant que
     * la valeur a envoyer n'a pas change entre-temps ; chaque appel annule les
     * tentatives precedentes (compteur de generation) pour ne jamais ecraser un
     * etat recent par un plus ancien. Thread dedie, jamais sur le thread
     * principal.
     */
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
            val connection = URL(DISPLAY_STATE_URL).openConnection() as HttpURLConnection
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
            // Backend pas encore pret (demarrage a froid) : on retente, delai
            // croissant plafonne, tant que cette valeur reste la plus recente.
            val delayMs = minOf(1000L * (attempt + 1), 10_000L)
            Log.w(TAG, "Rapport d'etat des ecrans en echec (tentative ${attempt + 1}), nouvel essai dans ${delayMs}ms", e)
            handler.postDelayed({
                Thread { postDisplayState(count, resolution, generation, attempt + 1) }.start()
            }, delayMs)
        }
    }

    /**
     * Filet de reconciliation periodique : (re)ouvre la Presentation si un
     * ecran externe existe sans elle, la recree si le systeme l'a fermee, et
     * re-emet l'etat des ecrans au backend.
     */
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

    // compte les tentatives
    // de demarrage differe du serveur Python quand getExternalFilesDir()
    // renvoie encore null (stockage pas encore monte au demarrage a froid -
    // rare mais deja observe sur d'autres apps Android en Direct Boot ou
    // juste apres un redemarrage). Avant ce lot, une valeur null etait
    // transmise telle quelle a bobine_bootstrap.py, qui retombait
    // SILENCIEUSEMENT sur le dossier interne prive AssetFinder/app/
    // (ecrase par Chaquopy a chaque mise a jour) - source
    // probable des disparitions de bibliotheque rapportees (donnees ecrites
    // dans la mauvaise base le temps de cette fenetre, jusqu'au prochain
    // redemarrage du service).
    private var storageRetries = 0

    override fun onCreate() {
        super.onCreate()
        instance = this

        createNotificationChannel()
        // startForeground() DOIT etre appele tres tot (quelques secondes,
        // sous peine de ForegroundServiceDidNotStartInTimeException sur API
        // 31+) - deplace AVANT le demarrage du serveur Python (qui peut
        // desormais attendre le montage du stockage externe, cf.
        // startPythonServerWhenStorageReady ci-dessous) plutot qu'apres.
        startForeground(NOTIFICATION_ID, buildNotification())
        acquireMulticastLock()
        connectivityManager = (getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager).also {
            try {
                it.registerDefaultNetworkCallback(networkCallback)
            } catch (e: Exception) {
                Log.w(TAG, "Echec de l'enregistrement du callback reseau (re-acquisition multicast desactivee) : ${e.message}")
            }
        }

        startPythonServerWhenStorageReady()

        displayManager = getSystemService(Context.DISPLAY_SERVICE) as DisplayManager
        displayManager.registerDisplayListener(displayListener, null)
        // Cas ou le dock/vidoprojecteur est deja branche avant le demarrage
        // du service (pas seulement un branchement en cours d'utilisation).
        Log.i(TAG, "Ecrans au demarrage : ${describeDisplays()}")
        showPresentationIfNeeded()
        // Etat des ecrans rapporte AU DEMARRAGE meme sans ecran externe (0), et
        // re-emis periodiquement (cf. reconcileRunnable).
        reportDisplayState()
        handler.postDelayed(reconcileRunnable, RECONCILE_INTERVAL_MS)
    }

    private fun startPythonServerWhenStorageReady() {
        // stockage externe specifique a l'app (persiste entre mises
        // a jour, visible via un gestionnaire de fichiers/MTP) - reserve
        // aux MEDIAS (gros fichiers, voir
        // bobine_bootstrap.py). PAS le dossier interne AssetFinder/app/ ou
        // Chaquopy redeploie les sources Python elles-memes.
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
        // Stockage amovible USB / SSD / SD (index >= 1) prioritaire s'il est inscriptible
        // (crucial pour Android TV ou l'eMMC interne est souvent limite a ~4-8 Go)
        val removableDir = externalFilesDirs.drop(1).firstOrNull { it.canWrite() }
        val selectedExternalDir = if (removableDir != null) {
            Log.i(TAG, "Stockage amovible USB detecte et selectionne : ${removableDir.absolutePath} (espace libre: ${removableDir.freeSpace / (1024 * 1024)} Mo)")
            removableDir.absolutePath
        } else {
            externalFilesDirs.first().absolutePath
        }

        // dossier PRIVE
        // de l'app sur le stockage interne (f2fs natif, jamais FUSE) - base
        // SQLite, miniatures, logs, branding, pochettes radio.
        val internalFilesDir = applicationContext.filesDir.absolutePath
        // dossier natif de l'app (seul emplacement d'ou Android 10+
        // autorise l'execution d'un binaire embarque, contrainte W^X) -
        // c'est la ou les jniLibs/<abi>/lib{ffmpeg,ffprobe}.so finissent
        // apres installation.
        val nativeLibraryDir = applicationContext.applicationInfo.nativeLibraryDir
        val py = Python.getInstance()
        py.getModule("bobine_bootstrap").callAttr(
            "start_server_once", selectedExternalDir, nativeLibraryDir, internalFilesDir, BuildConfig.VERSION_NAME
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // START_STICKY : le systeme relance le service (sans le dernier
        // Intent) s'il le tue pour recuperer de la memoire - ne remplace
        // pas l'exemption batterie, mais aide sur les kills
        // "normaux" (pression memoire) par opposition aux politiques
        // d'economie d'energie constructeur agressives.
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
        try {
            connectivityManager?.unregisterNetworkCallback(networkCallback)
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
            // Sur Android TV : l'ecran principal est deja le diffuseur unique (pas de Presentation secondaire)
            return
        }
        if (presentation != null || presentationAttemptInFlight) return
        // displayId 0 = ecran interne de la tablette (jamais une sortie
        // HDMI) - une seule Presentation a la fois attendue
        // ici (un seul dock/sortie externe par appareil dans ce cas
        // d'usage). Voir externalDisplays() pour le filtrage des ecrans prives.
        val external = externalDisplays().firstOrNull() ?: return

        // `Display` peut apparaitre dans DisplayManager.getDisplays() avant
        // que WindowManagerService ait fini d'enregistrer son propre
        // DisplayContent - Presentation.show() leve alors
        // InvalidDisplayException ("the specified display can not be
        // found"). Constate de facon systematique et reproductible sur
        // l'emulateur juste apres le demarrage du service, y
        // compris apres un branchement a chaud simule - plausible aussi
        // sur un vrai branchement HDMI a chaud, pas seulement un artefact
        // d'emulateur. Repli en reessai avec un court delai plutot qu'un
        // crash : le redemarrage automatique START_STICKY masquait ce bug
        // sans le corriger (l'app plantait puis se retablissait seule).
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
            // Toute exception (InvalidDisplayException attendue au demarrage,
            // mais aussi BadTokenException/SecurityException selon l'OEM) est
            // retentee SANS abandon definitif : 15 essais rapides (7,5 s, mesure
            // en pratique) puis un essai toutes les 5 s. Auparavant,
            // l'abandon apres 15 essais laissait un projecteur a EDID tardif
            // noir jusqu'a un rebranchement du cable.
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
