package com.bobine.app

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiInfo
import android.net.wifi.WifiManager
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject

private const val TAG = "WifiBridge"
private const val HIDDEN_SSID = "Android ne donne le nom du réseau qu'aux applications autorisées à la localisation, que Bobine ne demande pas."

object WifiBridge {
    @Suppress("DEPRECATION")
    fun wifiStatus(context: Context): String {
        return try {
            val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
                ?: return JSONObject().put("supported", false).put("reason", "Cet appareil n'a pas de Wi-Fi.").toString()
            val connectivity = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val network = connectivity.activeNetwork
            val caps = network?.let { connectivity.getNetworkCapabilities(it) }
            val onWifi = caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
            val transport = when {
                caps == null -> "none"
                onWifi -> "wifi"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
                else -> "other"
            }
            var current: Any = JSONObject.NULL
            if (onWifi) {
                val info: WifiInfo? = wifi.connectionInfo
                val rssi = info?.rssi ?: -100
                val ip = connectivity.getLinkProperties(network)?.linkAddresses
                    ?.firstOrNull { it.address is java.net.Inet4Address }?.address?.hostAddress
                val ssidRaw = info?.ssid?.trim('"')
                val ssid = ssidRaw?.takeIf { it.isNotBlank() && it != WifiManager.UNKNOWN_SSID }
                current = JSONObject()
                    .put("ssid", ssid ?: JSONObject.NULL)
                    .put("ssid_reason", if (ssid == null) HIDDEN_SSID else JSONObject.NULL)
                    .put("signal", Math.round(((rssi + 100) * 2.0).coerceIn(0.0, 100.0)).toInt())
                    .put("security", "").put("band", if ((info?.frequency ?: 0) >= 4900) "5 GHz" else "2.4 GHz")
                    .put("known", true).put("in_use", true).put("ip", ip ?: JSONObject.NULL)
            }
            JSONObject()
                .put("supported", true).put("enabled", wifi.isWifiEnabled).put("interface", "wlan0")
                .put("state", if (onWifi) "connected" else "disconnected")
                .put("transport", transport)
                .put("current", current).put("networks", JSONArray()).put("known", JSONArray())
                .put("read_only", true)
                .toString()
        } catch (e: Exception) {
            Log.w(TAG, "wifiStatus", e)
            bridgeError("wifi_failed", "Lecture de l'état du Wi-Fi impossible.")
        }
    }
}
