package com.bobine.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context

private const val NOTIFICATION_CHANNEL_ID = "bobine_service"

const val SERVICE_NOTIFICATION_ID = 1

fun serviceNotification(context: Context): Notification {
    val channel = NotificationChannel(NOTIFICATION_CHANNEL_ID, "Bobine", NotificationManager.IMPORTANCE_LOW)
    context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    val openApp = context.packageManager.getLaunchIntentForPackage(context.packageName)
    val pending = PendingIntent.getActivity(context, 0, openApp, PendingIntent.FLAG_IMMUTABLE)
    return Notification.Builder(context, NOTIFICATION_CHANNEL_ID)
        .setContentTitle("Bobine")
        .setContentText("Bobine diffuse en arrière-plan")
        .setSmallIcon(android.R.drawable.ic_media_play)
        .setContentIntent(pending)
        .setOngoing(true)
        .build()
}
