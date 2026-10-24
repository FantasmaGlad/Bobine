package com.bobine.app

import android.content.Context
import android.graphics.Color
import android.webkit.JavascriptInterface

private const val PREFS = "bobine_native"
private const val KEY_BG = "theme_bg"
private const val KEY_FG = "theme_fg"
private const val KEY_ACCENT = "theme_accent"
private const val KEY_START_ON_BOOT = "start_on_boot"
private const val KEY_UPDATE_CHANNEL = "update_channel"
private val HEX_COLOR = Regex("^#[0-9a-fA-F]{6}$")

/** Couleurs du thème choisi dans l'application, pour l'écran de chargement. */
object ThemeColors {
    /** `accent` : couleur d'accent du thème (spinner de chargement) ; à défaut, la couleur du texte. */
    data class Pair(val background: Int, val text: Int, val accent: Int = text)

    /**
     * Thème par défaut tant que l'interface web n'a rien envoyé (premier lancement) : « lavande »,
     * le thème clair par défaut de l'application (valeurs de `:root[data-theme="lavande"]` dans
     * frontend/src/app/globals.css : `--bg-main`, `--text-main`, `--accent-primary`). Indépendant du
     * mode sombre du système : l'écran de chargement et l'interface ouvrent sur le même thème.
     */
    private const val DEFAULT_BACKGROUND = "#f7f6fb"
    private const val DEFAULT_TEXT = "#161126"
    private const val DEFAULT_ACCENT = "#7c3aed"

    /** Dernières couleurs envoyées par l'interface web ; à défaut, le thème lavande. */
    fun load(context: Context): Pair {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val bg = prefs.getString(KEY_BG, null)
        val fg = prefs.getString(KEY_FG, null)
        if (bg != null && fg != null && HEX_COLOR.matches(bg) && HEX_COLOR.matches(fg)) {
            val accent = prefs.getString(KEY_ACCENT, null)?.takeIf { HEX_COLOR.matches(it) }
            return Pair(Color.parseColor(bg), Color.parseColor(fg), accent?.let { Color.parseColor(it) } ?: Color.parseColor(fg))
        }
        return Pair(Color.parseColor(DEFAULT_BACKGROUND), Color.parseColor(DEFAULT_TEXT), Color.parseColor(DEFAULT_ACCENT))
    }

    /** Accent du thème, envoyé à part (anciens JS : méthode absente, l'accent retombe sur le texte). */
    fun saveAccent(context: Context, accent: String) {
        if (!HEX_COLOR.matches(accent)) return
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY_ACCENT, accent).apply()
    }

    fun save(context: Context, background: String, text: String) {
        if (!HEX_COLOR.matches(background) || !HEX_COLOR.matches(text)) return
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_BG, background).putString(KEY_FG, text).apply()
    }
}

/**
 * Canal de mise à jour choisi dans l'application (stable, bêta, canary), pour l'écran de
 * chargement. Même principe que [ThemeColors] : l'interface web envoie la valeur à chaque
 * changement, et le démarrage la LIT de façon synchrone — le logo du bon canal s'affiche dès
 * la première image, sans attendre le serveur Python embarqué (qui n'est pas encore prêt).
 */
object UpdateChannelPref {
    private val VALID = setOf("stable", "beta", "canary")

    /** Dernier canal connu, ou null avant tout premier envoi (premier lancement après installation). */
    fun load(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_UPDATE_CHANNEL, null)
            ?.takeIf { it in VALID }

    /** Enregistre un canal valide ; toute autre valeur est ignorée (la préférence reste intacte). */
    fun save(context: Context, channel: String) {
        if (channel !in VALID) return
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_UPDATE_CHANNEL, channel).apply()
    }
}

/** Réglage « lancer au démarrage de l'appareil » (activé par défaut sur Android TV). */
object StartOnBoot {
    fun isEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_START_ON_BOOT, MainActivity.isTvDevice(context))

    fun set(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY_START_ON_BOOT, enabled).apply()
    }
}

/**
 * Pont minimal exposé à l'interface web locale (`window.BobineNative`) : couleurs du
 * thème, canal de mise à jour (écran de chargement) et réglage de démarrage. Aucune autre capacité n'est exposée.
 */
class NativeBridge(private val context: Context) {
    @JavascriptInterface
    fun setThemeColors(background: String, text: String) = ThemeColors.save(context, background, text)

    @JavascriptInterface
    fun setThemeAccent(accent: String) = ThemeColors.saveAccent(context, accent)

    @JavascriptInterface
    fun setUpdateChannel(channel: String) = UpdateChannelPref.save(context, channel)

    @JavascriptInterface
    fun getStartOnBoot(): Boolean = StartOnBoot.isEnabled(context)

    @JavascriptInterface
    fun setStartOnBoot(enabled: Boolean) = StartOnBoot.set(context, enabled)
}
