package com.bobine.app

import android.content.Context
import com.google.android.gms.tasks.Tasks
import com.google.android.play.core.appupdate.AppUpdateInfo
import com.google.android.play.core.appupdate.AppUpdateManager
import com.google.android.play.core.appupdate.AppUpdateManagerFactory
import com.google.android.play.core.appupdate.AppUpdateOptions
import com.google.android.play.core.install.InstallStateUpdatedListener
import com.google.android.play.core.install.model.AppUpdateType
import com.google.android.play.core.install.model.InstallStatus
import com.google.android.play.core.install.model.UpdateAvailability
import org.json.JSONObject
import java.util.concurrent.TimeUnit

private const val UPDATE_REQUEST_CODE = 4108

/**
 * Mises à jour intégrées de Google Play (API « In-App Updates », mode souple) : c'est Google Play qui
 * télécharge et installe — Bobine ne télécharge ni n'installe jamais d'APK dans ce build. Disponible
 * seulement pour une installation faite DEPUIS Google Play (sinon l'API répond « non disponible »).
 * Chargée par réflexion depuis `StoreUpdates` (build « play » uniquement).
 */
class PlayUpdateProvider : StoreUpdateProvider {
    @Volatile private var manager: AppUpdateManager? = null
    @Volatile private var installState: String = "none"
    @Volatile private var listenerRegistered = false

    private val listener = InstallStateUpdatedListener { state ->
        installState = when (state.installStatus()) {
            InstallStatus.DOWNLOADING, InstallStatus.PENDING -> "downloading"
            InstallStatus.DOWNLOADED -> "downloaded"
            InstallStatus.INSTALLING -> "installing"
            InstallStatus.FAILED, InstallStatus.CANCELED -> "failed"
            else -> installState
        }
    }

    private fun manager(context: Context): AppUpdateManager {
        val existing = manager
        if (existing != null) return existing
        val created = AppUpdateManagerFactory.create(context.applicationContext)
        manager = created
        if (!listenerRegistered) {
            created.registerListener(listener)
            listenerRegistered = true
        }
        return created
    }

    private fun info(context: Context): AppUpdateInfo = Tasks.await(manager(context).appUpdateInfo, 15, TimeUnit.SECONDS)

    private fun describe(info: AppUpdateInfo): JSONObject {
        val state = when {
            info.installStatus() == InstallStatus.DOWNLOADED -> "downloaded"
            info.installStatus() == InstallStatus.DOWNLOADING || info.installStatus() == InstallStatus.PENDING -> "downloading"
            info.installStatus() == InstallStatus.INSTALLING -> "installing"
            info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE ||
                info.updateAvailability() == UpdateAvailability.DEVELOPER_TRIGGERED_UPDATE_IN_PROGRESS -> "available"
            else -> "none"
        }
        return JSONObject()
            .put("state", state)
            .put("version_code", if (state == "none") JSONObject.NULL else info.availableVersionCode())
            .put("flexible_allowed", info.isUpdateTypeAllowed(AppUpdateType.FLEXIBLE))
            .put("staleness_days", info.clientVersionStalenessDays() ?: JSONObject.NULL)
    }

    override fun check(context: Context): String = try {
        describe(info(context)).toString()
    } catch (e: Exception) {
        // Typique hors Google Play (APK installé à la main, émulateur sans Play Store) : pas une panne.
        JSONObject().put("state", "unavailable")
            .put("message", "Google Play ne propose pas de mise à jour pour cette installation (installée hors du Play Store ?).").toString()
    }

    override fun start(context: Context): String = try {
        val info = info(context)
        val activity = MainActivity.activeActivity?.get()
        when {
            info.updateAvailability() != UpdateAvailability.UPDATE_AVAILABLE ->
                JSONObject().put("error", "no_update").put("message", "Aucune mise à jour disponible.").toString()
            !info.isUpdateTypeAllowed(AppUpdateType.FLEXIBLE) ->
                JSONObject().put("error", "not_allowed").put("message", "Google Play ne permet pas la mise à jour intégrée pour le moment : ouvrez la fiche Google Play.").toString()
            activity == null ->
                JSONObject().put("error", "no_activity").put("message", "Ouvrez l'application au premier plan pour lancer la mise à jour.").toString()
            else -> {
                installState = "downloading"
                activity.runOnUiThread {
                    manager(context).startUpdateFlowForResult(info, activity, AppUpdateOptions.newBuilder(AppUpdateType.FLEXIBLE).build(), UPDATE_REQUEST_CODE)
                }
                JSONObject().put("ok", true).toString()
            }
        }
    } catch (e: Exception) {
        JSONObject().put("error", "update_failed").put("message", "La mise à jour via Google Play n'a pas pu démarrer.").toString()
    }

    override fun complete(context: Context): String = try {
        manager(context).completeUpdate() // redémarre l'application une fois l'installation faite
        JSONObject().put("ok", true).toString()
    } catch (e: Exception) {
        JSONObject().put("error", "update_failed").put("message", "L'installation de la mise à jour a échoué.").toString()
    }
}
