package com.bobine.app

import android.content.Context
import android.graphics.Typeface
import android.view.Gravity
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

fun buildBootSplash(
    context: Context,
    background: Int,
    text: Int,
    accent: Int,
    logoDp: Int,
    logoGapDp: Int,
    spinnerDp: Int,
    textSp: Float,
): LinearLayout {
    val density = context.resources.displayMetrics.density
    val layout = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        gravity = Gravity.CENTER
        setBackgroundColor(background)
        layoutParams = FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT)
    }
    val logoSize = (logoDp * density).toInt()
    val logo = ImageView(context).apply {
        setImageResource(SplashChannel.initialDrawable(context))
        layoutParams = LinearLayout.LayoutParams(logoSize, logoSize).apply { bottomMargin = (logoGapDp * density).toInt() }
        adjustViewBounds = true
    }
    layout.addView(logo)
    SplashChannel.refreshFromBackendIfUnknown(context, logo)
    val spinner = ArcSpinnerView(context, SpinnerColors.arcColor(accent, text, background), text, spinnerDp).apply {
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            .apply { bottomMargin = (18 * density).toInt() }
    }
    layout.addView(spinner)
    val status = TextView(context).apply {
        this.text = "Démarrage de Bobine..."
        setTextColor(text)
        textSize = textSp
        typeface = Typeface.DEFAULT_BOLD
        gravity = Gravity.CENTER
    }
    layout.addView(status)
    return layout
}
