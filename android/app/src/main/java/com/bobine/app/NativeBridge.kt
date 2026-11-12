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

object ThemeColors {
    data class Pair(val background: Int, val text: Int, val accent: Int = text)

    private const val DEFAULT_BACKGROUND = "#ffffff"
    private const val DEFAULT_TEXT = "#252d41"
    private const val DEFAULT_ACCENT = "#697485"

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

object UpdateChannelPref {
    private val VALID: Set<String> = BuildConfig.RELEASE_CHANNELS.split(",").toSet()

    fun load(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_UPDATE_CHANNEL, null)
            ?.takeIf { it in VALID }

    fun save(context: Context, channel: String) {
        if (channel !in VALID) return
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_UPDATE_CHANNEL, channel).apply()
    }
}

object StartOnBoot {
    fun isEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_START_ON_BOOT, MainActivity.isTvDevice(context))

    fun set(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY_START_ON_BOOT, enabled).apply()
    }
}

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
