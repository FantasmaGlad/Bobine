package com.bobine.app

import android.content.Context
import android.net.wifi.WifiManager
import android.os.PowerManager
import android.util.Log

private const val TAG = "ServiceLocks"

class ServiceLocks(private val context: Context) {
    private var wakeLock: PowerManager.WakeLock? = null
    private var multicastLock: WifiManager.MulticastLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    private val wifiManager: WifiManager
        get() = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager

    fun acquireWake() {
        if (wakeLock?.isHeld == true) return
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Bobine:hdmiPlayback").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    fun releaseWake() {
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
    }

    fun acquireMulticast() {
        if (multicastLock?.isHeld == true) return
        multicastLock = wifiManager.createMulticastLock("Bobine:mdns").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    fun releaseMulticast() {
        multicastLock?.let { if (it.isHeld) it.release() }
        multicastLock = null
    }

    fun acquireWifi() {
        if (wifiLock?.isHeld == true) return
        try {
            wifiLock = wifiManager.createWifiLock(WifiManager.WIFI_MODE_FULL_LOW_LATENCY, "Bobine:faible-latence").apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Verrou Wi-Fi a faible latence indisponible", e)
        }
    }

    fun releaseWifi() {
        wifiLock?.let { if (it.isHeld) it.release() }
        wifiLock = null
    }

    fun refreshNetwork() {
        releaseMulticast()
        acquireMulticast()
        acquireWifi()
    }

    fun releaseAll() {
        releaseWake()
        releaseMulticast()
        releaseWifi()
    }
}
