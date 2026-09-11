package com.bobine.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.display.DisplayManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.util.Log
import android.view.Display
import android.view.WindowManager
import com.chaquo.python.Python

private const val NOTIFICATION_CHANNEL_ID = "bobine_service"
private const val NOTIFICATION_ID = 1
private const val TAG = "BobineForegroundService"

/**
 * Lot 6 (cf. docs/plan-implementation-android.md) : porte le backend Python
 * et la `Presentation` HDMI (Lot 4), DECOUPLE du cycle de vie de
 * `MainActivity` - c'est ce qui permet au cours de continuer de jouer sur
 * la sortie HDMI meme si l'app est fermee depuis le multitache (CDC
 * docs/ARCHITECTURE.md SS7 : la tablette reste utilisable pour autre
 * chose, pas un mode kiosque strict).
 *
 * Ne gere PAS encore l'exemption batterie (Device Owner, Lot 10) ni le
 * redemarrage apres un "kill" complet du processus par le systeme
 * (`onTaskRemoved` fait de son mieux mais un ForegroundService seul, sans
 * Device Owner, reste soumis aux politiques d'economie d'energie
 * agressives de certains constructeurs - risque deja documente au CDC SS7).
 */
class BobineForegroundService : Service() {

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
    // PARTIAL_WAKE_LOCK (CPU seul, pas l'ecran tactile - l'immersion du
    // Lot 5 s'occupe de l'ecran tactile separement) : empeche le systeme
    // de suspendre le CPU pendant qu'un cours est activement diffuse sur
    // la sortie HDMI, uniquement le temps ou la Presentation existe.
    private var wakeLock: PowerManager.WakeLock? = null

    // Lot 7 : par defaut, Android ne livre PAS les paquets multicast (mDNS
    // inclus) au processus applicatif tant qu'aucun MulticastLock n'est
    // detenu - la decouverte reseau du backend (zeroconf, bobine.local)
    // resterait invisible depuis un autre appareil du meme Wi-Fi sans
    // cela, meme si le serveur ecoute correctement. Un seul lock pour
    // toute la duree de vie du service (pas de reference-count fine par
    // requete : la decouverte doit rester possible en permanence, pas
    // seulement pendant une operation ponctuelle).
    private var multicastLock: WifiManager.MulticastLock? = null

    private val displayListener = object : DisplayManager.DisplayListener {
        override fun onDisplayAdded(displayId: Int) {
            Log.i(TAG, "Ecran externe detecte (displayId=$displayId)")
            showPresentationIfNeeded()
        }

        override fun onDisplayRemoved(displayId: Int) {
            Log.i(TAG, "Ecran externe retire (displayId=$displayId)")
            presentation?.dismiss()
            presentation = null
            releaseWakeLock()
        }

        override fun onDisplayChanged(displayId: Int) {}
    }

    // Lot 15 (docs/audit-android-2026-09-11.md §C3) : compte les tentatives
    // de demarrage differe du serveur Python quand getExternalFilesDir()
    // renvoie encore null (stockage pas encore monte au demarrage a froid -
    // rare mais deja observe sur d'autres apps Android en Direct Boot ou
    // juste apres un redemarrage). Avant ce lot, une valeur null etait
    // transmise telle quelle a bobine_bootstrap.py, qui retombait
    // SILENCIEUSEMENT sur le dossier interne prive AssetFinder/app/
    // (ecrase par Chaquopy a chaque mise a jour, cf. Lot 9) - source
    // probable des disparitions de bibliotheque rapportees (donnees ecrites
    // dans la mauvaise base le temps de cette fenetre, jusqu'au prochain
    // redemarrage du service).
    private var storageRetries = 0

    override fun onCreate() {
        super.onCreate()

        createNotificationChannel()
        // startForeground() DOIT etre appele tres tot (quelques secondes,
        // sous peine de ForegroundServiceDidNotStartInTimeException sur API
        // 31+) - deplace AVANT le demarrage du serveur Python (qui peut
        // desormais attendre le montage du stockage externe, cf.
        // startPythonServerWhenStorageReady ci-dessous) plutot qu'apres.
        startForeground(NOTIFICATION_ID, buildNotification())
        acquireMulticastLock()

        startPythonServerWhenStorageReady()

        displayManager = getSystemService(Context.DISPLAY_SERVICE) as DisplayManager
        displayManager.registerDisplayListener(displayListener, null)
        // Cas ou le dock/vidoprojecteur est deja branche avant le demarrage
        // du service (pas seulement un branchement en cours d'utilisation).
        showPresentationIfNeeded()
    }

    private fun startPythonServerWhenStorageReady() {
        // Lot 9 : stockage externe specifique a l'app (persiste entre mises
        // a jour, visible via un gestionnaire de fichiers/MTP) - reserve
        // aux MEDIAS depuis le Lot 15 (gros fichiers, cf.
        // bobine_bootstrap.py). PAS le dossier interne AssetFinder/app/ ou
        // Chaquopy redeploie les sources Python elles-memes (Lot 9).
        val externalFilesDir = applicationContext.getExternalFilesDir(null)?.absolutePath
        if (externalFilesDir == null) {
            storageRetries++
            if (storageRetries <= 30) {
                Log.w(TAG, "Stockage externe pas encore monte (tentative $storageRetries/30), nouvel essai dans 2s")
                handler.postDelayed({ startPythonServerWhenStorageReady() }, 2000)
            } else {
                Log.e(TAG, "Stockage externe indisponible apres 60s - abandon (le service reste actif, un redemarrage relancera cette sequence)")
            }
            return
        }
        // Lot 15 (docs/audit-android-2026-09-11.md §C1/C3) : dossier PRIVE
        // de l'app sur le stockage interne (f2fs natif, jamais FUSE) - base
        // SQLite, miniatures, logs, branding, pochettes radio.
        val internalFilesDir = applicationContext.filesDir.absolutePath
        // Lot 8 : dossier natif de l'app (seul emplacement d'ou Android 10+
        // autorise l'execution d'un binaire embarque, contrainte W^X) -
        // c'est la ou les jniLibs/<abi>/lib{ffmpeg,ffprobe}.so finissent
        // apres installation.
        val nativeLibraryDir = applicationContext.applicationInfo.nativeLibraryDir
        val py = Python.getInstance()
        py.getModule("bobine_bootstrap").callAttr(
            "start_server_once", externalFilesDir, nativeLibraryDir, internalFilesDir
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // START_STICKY : le systeme relance le service (sans le dernier
        // Intent) s'il le tue pour recuperer de la memoire - ne remplace
        // pas l'exemption batterie du Lot 10, mais aide sur les kills
        // "normaux" (pression memoire) par opposition aux politiques
        // d'economie d'energie constructeur agressives.
        return START_STICKY
    }

    override fun onDestroy() {
        displayManager.unregisterDisplayListener(displayListener)
        presentation?.dismiss()
        presentation = null
        releaseWakeLock()
        releaseMulticastLock()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun showPresentationIfNeeded() {
        if (presentation != null || presentationAttemptInFlight) return
        // displayId 0 = ecran interne de la tablette (jamais une sortie
        // HDMI) - cf. CDC SS3.2, une seule Presentation a la fois attendue
        // ici (un seul dock/sortie externe par appareil dans ce cas
        // d'usage).
        val external = displayManager.displays.firstOrNull { it.displayId != Display.DEFAULT_DISPLAY }
            ?: return

        // `Display` peut apparaitre dans DisplayManager.getDisplays() avant
        // que WindowManagerService ait fini d'enregistrer son propre
        // DisplayContent - Presentation.show() leve alors
        // InvalidDisplayException ("the specified display can not be
        // found"). Constate de facon systematique et reproductible sur
        // l'emulateur (Lot 4) juste apres le demarrage du service, y
        // compris apres un branchement a chaud simule - plausible aussi
        // sur un vrai branchement HDMI a chaud, pas seulement un artefact
        // d'emulateur. Repli en reessai avec un court delai plutot qu'un
        // crash : le redemarrage automatique START_STICKY masquait ce bug
        // sans le corriger (l'app plantait puis se retablissait seule).
        presentationAttemptInFlight = true
        try {
            Log.i(TAG, "Ouverture de la Presentation sur ${external.name} (id=${external.displayId})")
            presentation = BobinePresentation(this, external).also { it.show() }
            acquireWakeLock()
            presentationAttemptInFlight = false
            presentationRetries = 0
        } catch (e: WindowManager.InvalidDisplayException) {
            presentationRetries++
            if (presentationRetries <= 15) {
                // 15 x 500ms = 7,5s de marge : mesure en pratique (Lot 4),
                // 5 tentatives (2,5s) etaient insuffisantes sur un demarrage
                // a froid de l'app sur emulateur - le tout premier
                // rattachement de fenetre a un Display externe echoue de
                // facon systematique juste apres `onCreate()`, le temps que
                // le process finisse d'etablir sa connexion binder a
                // WindowManagerService ; un display ajoute plus tard (app
                // deja "chaude") reussit lui du premier coup, sans reessai.
                Log.w(TAG, "Affichage ${external.displayId} pas encore pret (tentative $presentationRetries/15), nouvel essai dans 500ms", e)
                handler.postDelayed({
                    presentationAttemptInFlight = false
                    showPresentationIfNeeded()
                }, 500)
            } else {
                Log.e(TAG, "Abandon apres 15 tentatives sur l'affichage ${external.displayId}", e)
                presentationAttemptInFlight = false
                presentationRetries = 0
            }
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
