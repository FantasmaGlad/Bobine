package com.bobine.app

import android.content.Context
import android.os.Process
import org.json.JSONObject
import java.io.File

/**
 * Adresse du backend Python embarqué, sur la boucle locale.
 *
 * Le port n'est plus figé côté Kotlin : au démarrage, le serveur choisit son port d'écoute (le
 * port configuré s'il est libre, sinon un port de repli — `app/utils/port.py`) et le publie dans
 * `backend-runtime.json`, à la racine du stockage INTERNE de l'application (`filesDir`, le
 * même dossier que celui que `BobineForegroundService` transmet à Python). Le fichier est lu
 * directement plutôt que par un appel Chaquopy : la lecture ne dépend ni du verrou de l'interpréteur
 * ni de l'état de Python, et ne bloque jamais le fil principal.
 *
 * Le fichier n'est valable que s'il a été écrit par CE processus (le serveur tourne dans le
 * processus de l'application) : celui d'un lancement précédent, resté après un arrêt brutal, est
 * ignoré. Tant que le serveur n'a rien publié, [port] et [url] renvoient null : l'appelant attend
 * et réessaie, au lieu de deviner un port qui pourrait être celui d'une autre application.
 */
object BackendEndpoint {
    /** Même nom que `RUNTIME_FILE_NAME` dans `app/utils/port.py`. */
    private const val RUNTIME_FILE_NAME = "backend-runtime.json"
    private const val HOST = "127.0.0.1"

    /** Port publié par le serveur de ce processus, ou null s'il n'écoute pas encore. */
    fun port(context: Context): Int? = try {
        parsePort(File(context.applicationContext.filesDir, RUNTIME_FILE_NAME).readText(), Process.myPid())
    } catch (e: Exception) {
        null
    }

    /** URL absolue de [path] (commençant par « / ») sur le backend, ou null tant que le port est inconnu. */
    fun url(context: Context, path: String): String? = port(context)?.let { "http://$HOST:$it$path" }

    /** Vrai si [url] est une page du backend de ce processus. */
    fun isBackendUrl(context: Context, url: String?): Boolean {
        val port = port(context) ?: return false
        return url != null && url.startsWith("http://$HOST:$port")
    }

    /** Contenu du fichier d'exécution → port, si le pid est [expectedPid] et le port valide. */
    internal fun parsePort(json: String, expectedPid: Int): Int? {
        val data = JSONObject(json)
        if (data.optInt("pid", -1) != expectedPid) return null
        val port = data.optInt("port", -1)
        return if (port in 1..65535) port else null
    }
}
