package com.bobine.app

import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.webkit.JavascriptInterface

private const val PREFS = "bobine_native"
private const val KEY_BG = "theme_bg"
private const val KEY_FG = "theme_fg"
private const val KEY_START_ON_BOOT = "start_on_boot"
private val HEX_COLOR = Regex("^#[0-9a-fA-F]{6}$")

/** Couleurs du thème choisi dans l'application, pour l'écran de chargement. */
object ThemeColors {
    data class Pair(val background: Int, val text: Int)

    /** Dernières couleurs envoyées par l'interface web ; à défaut, clair ou sombre selon le système. */
    fun load(context: Context): Pair {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val bg = prefs.getString(KEY_BG, null)
        val fg = prefs.getString(KEY_FG, null)
        if (bg != null && fg != null && HEX_COLOR.matches(bg) && HEX_COLOR.matches(fg)) {
            return Pair(Color.parseColor(bg), Color.parseColor(fg))
        }
        val night = (context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        return if (night) Pair(Color.parseColor("#0b0e14"), Color.parseColor("#94a3b8"))
        else Pair(Color.parseColor("#f6f7f9"), Color.parseColor("#5b5b6b"))
    }

    fun save(context: Context, background: String, text: String) {
        if (!HEX_COLOR.matches(background) || !HEX_COLOR.matches(text)) return
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_BG, background).putString(KEY_FG, text).apply()
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
 * thème et réglage de démarrage. Aucune autre capacité n'est exposée.
 */
class NativeBridge(private val context: Context) {
    @JavascriptInterface
    fun setThemeColors(background: String, text: String) = ThemeColors.save(context, background, text)

    @JavascriptInterface
    fun getStartOnBoot(): Boolean = StartOnBoot.isEnabled(context)

    @JavascriptInterface
    fun setStartOnBoot(enabled: Boolean) = StartOnBoot.set(context, enabled)
}
