package com.bobine.app

import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
import com.chaquo.python.Python
import java.net.Inet4Address

private const val TAG = "LanAddress"
private const val LAN_IP_ENV = "BOBINE_LAN_IP"

/**
 * Adresse IPv4 du réseau local (Wi-Fi ou Ethernet), lue sur les réseaux Android
 * eux-mêmes. La route par défaut peut être un VPN ou le réseau mobile : l'adresse
 * que la socket UDP du backend y trouverait ne serait alors pas joignable depuis
 * les autres appareils du Wi-Fi.
 */
object LanAddress {

    @Suppress("DEPRECATION")
    fun current(manager: ConnectivityManager): String? {
        var wifi: String? = null
        var wired: String? = null
        for (network in manager.allNetworks) {
            val caps = manager.getNetworkCapabilities(network) ?: continue
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) continue
            val isWired = caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
            val isWifi = caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
            if (!isWired && !isWifi) continue
            val ip = manager.getLinkProperties(network)?.linkAddresses
                ?.map { it.address }
                ?.firstOrNull { it is Inet4Address && !it.isLoopbackAddress && !it.isLinkLocalAddress }
                ?.hostAddress ?: continue
            if (isWired) wired = wired ?: ip else wifi = wifi ?: ip
        }
        return wired ?: wifi
    }

    /** Transmet l'adresse au backend Python (variable lue par `app/utils/network.py`). */
    fun publish(ip: String?) {
        Thread({
            try {
                val environ = Python.getInstance().getModule("os").get("environ") ?: return@Thread
                if (ip == null) {
                    environ.callAttr("pop", LAN_IP_ENV, null)
                } else {
                    environ.callAttr("__setitem__", LAN_IP_ENV, ip)
                }
                Log.i(TAG, "Adresse du reseau local : ${ip ?: "aucune"}")
            } catch (e: Exception) {
                Log.w(TAG, "Publication de l'adresse locale impossible : ${e.message}")
            }
        }, "bobine-lan-address").start()
    }
}
