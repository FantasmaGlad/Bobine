package com.bobine.app

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.SweepGradient
import android.view.View
import android.view.animation.LinearInterpolator
import androidx.core.graphics.ColorUtils

private const val SWEEP_DEGREES = 270f
private const val ROTATION_MS = 1100L
private const val MIN_CONTRAST = 3.0

object SpinnerColors {
    fun arcColor(accent: Int, text: Int, background: Int): Int =
        if (ColorUtils.calculateContrast(accent or 0xFF000000.toInt(), background or 0xFF000000.toInt()) >= MIN_CONTRAST) accent else text

    fun gradient(arc: Int): IntArray = intArrayOf(ColorUtils.setAlphaComponent(arc, 0), ColorUtils.setAlphaComponent(arc, 40), arc)
}

class ArcSpinnerView(context: Context, arcColor: Int, trackColor: Int, sizeDp: Int) : View(context) {
    private val density = resources.displayMetrics.density
    private val sizePx = (sizeDp * density).toInt()
    private val strokePx = sizePx * 0.085f
    private val bounds = RectF()
    private var rotation = 0f

    private val trackPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = strokePx
        color = ColorUtils.setAlphaComponent(trackColor, 46) // ≈ 18 %
    }
    private val arcPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = strokePx
        strokeCap = Paint.Cap.ROUND
    }
    private val colors = SpinnerColors.gradient(arcColor)
    private val animator = ValueAnimator.ofFloat(0f, 360f).apply {
        duration = ROTATION_MS
        repeatCount = ValueAnimator.INFINITE
        interpolator = LinearInterpolator()
        addUpdateListener {
            rotation = it.animatedValue as Float
            invalidate()
        }
    }

    init {
        setLayerType(LAYER_TYPE_HARDWARE, null)
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        setMeasuredDimension(sizePx, sizePx)
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        val inset = strokePx / 2f
        bounds.set(inset, inset, w - inset, h - inset)
        arcPaint.shader = SweepGradient(w / 2f, h / 2f, colors, floatArrayOf(0f, 0.55f, SWEEP_DEGREES / 360f))
    }

    override fun onDraw(canvas: Canvas) {
        canvas.drawOval(bounds, trackPaint)
        canvas.save()
        canvas.rotate(rotation, width / 2f, height / 2f)
        canvas.drawArc(bounds, 0f, SWEEP_DEGREES, false, arcPaint)
        canvas.restore()
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        if (!animator.isStarted) animator.start()
    }

    override fun onDetachedFromWindow() {
        animator.cancel()
        super.onDetachedFromWindow()
    }

    override fun onVisibilityChanged(changedView: View, visibility: Int) {
        super.onVisibilityChanged(changedView, visibility)
        if (visibility == VISIBLE && isAttachedToWindow) { if (!animator.isStarted) animator.start() } else animator.pause()
    }
}
