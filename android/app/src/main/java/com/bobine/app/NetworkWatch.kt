package com.bobine.app

import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.util.Log

private const val TAG = "NetworkWatch"

class NetworkWatch(private val manager: ConnectivityManager, private val locks: ServiceLocks) {
    private val defaultCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            Log.i(TAG, "Reseau disponible (network=$network) - re-acquisition du verrou multicast mDNS")
            locks.refreshNetwork()
            publish()
        }

        override fun onLost(network: Network) = publish()
    }

    private fun lanCallback() = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) = publish()
        override fun onLinkPropertiesChanged(network: Network, linkProperties: LinkProperties) = publish()
        override fun onLost(network: Network) = publish()
    }

    private val lanCallbacks = listOf(
        NetworkCapabilities.TRANSPORT_WIFI to lanCallback(),
        NetworkCapabilities.TRANSPORT_ETHERNET to lanCallback(),
    )

    fun publish() = LanAddress.publish(LanAddress.current(manager))

    fun start() {
        try {
            manager.registerDefaultNetworkCallback(defaultCallback)
        } catch (e: Exception) {
            Log.w(TAG, "Echec de l'enregistrement du callback reseau (re-acquisition multicast desactivee) : ${e.message}")
        }
        try {
            for ((transport, callback) in lanCallbacks) {
                manager.registerNetworkCallback(NetworkRequest.Builder().addTransportType(transport).build(), callback)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Echec de l'enregistrement du callback LAN : ${e.message}")
        }
        publish()
    }

    fun stop() {
        try {
            manager.unregisterNetworkCallback(defaultCallback)
            lanCallbacks.forEach { (_, callback) -> manager.unregisterNetworkCallback(callback) }
        } catch (e: Exception) {
            Log.w(TAG, "Echec du desenregistrement du callback reseau : ${e.message}")
        }
    }
}
