package com.bobine.app

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothClass
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiInfo
import android.net.wifi.WifiManager
import android.provider.Settings
import android.util.Log
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

private const val TAG = "DeviceBridge"
private const val PERMISSION_REQUEST_CODE = 4107
private const val PERMISSION_MESSAGE =
    "Autorisez « Appareils à proximité » dans la boîte de dialogue affichée sur l'appareil Android, puis réessayez."

/**
 * Pont « Périphériques » appelé par le backend Python (Chaquopy, `devices/android.py`) : sorties audio,
 * Bluetooth et état du Wi-Fi. Chaque méthode renvoie une chaîne JSON — `{"error": code, "message": ...}`
 * en cas de refus ou d'échec, jamais une exception qui traverserait Chaquopy.
 *
 * Limites ASSUMÉES d'Android (documentées dans docs/ARCHITECTURE.md, section Périphériques) :
 *  - aucune API publique ne change la sortie audio par défaut, ne connecte/déconnecte un profil
 *    Bluetooth déjà appairé ni n'oublie un appareil → réglages du système (`openSettings`) ;
 *  - depuis Android 10, une application ne peut plus scanner/connecter/oublier un réseau Wi-Fi :
 *    lecture seule de l'état, sans SSID (la lecture du nom exige la localisation précise, permission
 *    sensible que Bobine NE demande PAS) ;
 *  - l'appairage ouvre la boîte de dialogue système sur l'appareil (confirmation à l'écran).
 */
object DeviceBridge {
    private val discovered = ConcurrentHashMap<String, JSONObject>()
    @Volatile private var receiverRegistered = false
    @Volatile private var discovering = false
    @Volatile private var pairing: JSONObject? = null

    private fun error(code: String, message: String): String =
        JSONObject().put("error", code).put("message", message).toString()

    private fun ok(extra: JSONObject = JSONObject()): String = extra.put("ok", true).toString()

    // ------------------------------------------------------------------ audio
    private fun audioKind(type: Int): String = when (type) {
        AudioDeviceInfo.TYPE_BUILTIN_SPEAKER, AudioDeviceInfo.TYPE_BUILTIN_EARPIECE -> "internal"
        AudioDeviceInfo.TYPE_HDMI, AudioDeviceInfo.TYPE_HDMI_ARC, AudioDeviceInfo.TYPE_HDMI_EARC -> "hdmi"
        AudioDeviceInfo.TYPE_USB_DEVICE, AudioDeviceInfo.TYPE_USB_HEADSET, AudioDeviceInfo.TYPE_USB_ACCESSORY -> "usb"
        AudioDeviceInfo.TYPE_WIRED_HEADPHONES, AudioDeviceInfo.TYPE_WIRED_HEADSET, AudioDeviceInfo.TYPE_LINE_ANALOG,
        AudioDeviceInfo.TYPE_LINE_DIGITAL -> "jack"
        AudioDeviceInfo.TYPE_BLUETOOTH_A2DP, AudioDeviceInfo.TYPE_BLUETOOTH_SCO, AudioDeviceInfo.TYPE_BLE_HEADSET,
        AudioDeviceInfo.TYPE_BLE_SPEAKER, AudioDeviceInfo.TYPE_BLE_BROADCAST -> "bluetooth"
        AudioDeviceInfo.TYPE_REMOTE_SUBMIX, AudioDeviceInfo.TYPE_BUS -> "virtual"
        else -> "other"
    }

    /** Sorties audio ; « par défaut » = celles où Android route actuellement le média. */
    fun audioList(context: Context): String = try {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val media = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build()
        val routedIds = audio.getAudioDevicesForAttributes(media).map { it.id }.toSet()
        val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC).coerceAtLeast(1)
        val volume = audio.getStreamVolume(AudioManager.STREAM_MUSIC).toDouble() / max
        val muted = audio.isStreamMute(AudioManager.STREAM_MUSIC)
        val devices = JSONArray()
        var defaultId: String? = null
        for (d in audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
            val isDefault = d.id in routedIds
            if (isDefault && defaultId == null) defaultId = d.id.toString()
            devices.put(
                JSONObject()
                    .put("id", d.id.toString())
                    .put("name", d.productName?.toString().orEmpty().ifBlank { "Sortie ${d.id}" })
                    .put("description", "")
                    .put("manufacturer", "")
                    .put("kind", audioKind(d.type))
                    .put("is_default", isDefault)
                    .put("available", true)
                    .put("volume", if (isDefault) volume else JSONObject.NULL)
                    .put("muted", if (isDefault) muted else JSONObject.NULL)
            )
        }
        JSONObject().put("supported", true).put("devices", devices).put("default_id", defaultId ?: JSONObject.NULL).toString()
    } catch (e: Exception) {
        Log.w(TAG, "audioList", e)
        error("audio_failed", "Lecture des sorties audio impossible.")
    }

    /** `volume` < 0 : inchangé ; `muted` : -1 inchangé, 0 son actif, 1 coupé. Agit sur le volume média du système. */
    fun audioSetVolume(context: Context, volume: Double, muted: Int): String = try {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if (volume >= 0.0) {
            val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            audio.setStreamVolume(AudioManager.STREAM_MUSIC, Math.round(volume.coerceIn(0.0, 1.0) * max).toInt(), 0)
        }
        if (muted >= 0) {
            audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, if (muted == 1) AudioManager.ADJUST_MUTE else AudioManager.ADJUST_UNMUTE, 0)
        }
        ok()
    } catch (e: SecurityException) {
        error("not_authorized", "Android refuse de modifier le volume (mode Ne pas déranger ?).")
    } catch (e: Exception) {
        Log.w(TAG, "audioSetVolume", e)
        error("audio_failed", "Réglage du volume impossible.")
    }

    // ------------------------------------------------------------------ Bluetooth
    private fun adapter(context: Context): BluetoothAdapter? =
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter

    private fun missingBluetoothPermissions(context: Context, needScan: Boolean): List<String> {
        val wanted = buildList {
            add(Manifest.permission.BLUETOOTH_CONNECT)
            if (needScan) add(Manifest.permission.BLUETOOTH_SCAN)
        }
        return wanted.filter { ContextCompat.checkSelfPermission(context, it) != PackageManager.PERMISSION_GRANTED }
    }

    /** Demande les permissions « Appareils à proximité » (boîte de dialogue système sur l'appareil). */
    private fun requestPermissions(missing: List<String>): String {
        val activity = MainActivity.activeActivity?.get()
        if (activity != null) {
            activity.runOnUiThread { ActivityCompat.requestPermissions(activity, missing.toTypedArray(), PERMISSION_REQUEST_CODE) }
        }
        return error("permission_required", PERMISSION_MESSAGE)
    }

    /** Action explicite de l'utilisateur (bouton « Autoriser ») : affiche la demande « Appareils à proximité ». */
    fun bluetoothRequestPermission(context: Context): String {
        val missing = missingBluetoothPermissions(context, needScan = true)
        return if (missing.isEmpty()) ok() else requestPermissions(missing)
    }

    /** Vrai si l'appareil possède un Bluetooth (aucune demande d'autorisation). */
    fun hasBluetooth(context: Context): Boolean =
        context.packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH)

    private fun kindOf(device: BluetoothDevice): String {
        @SuppressLint("MissingPermission")
        val cls = device.bluetoothClass ?: return "other"
        return when (cls.deviceClass) {
            BluetoothClass.Device.AUDIO_VIDEO_HEADPHONES -> "headphones"
            BluetoothClass.Device.AUDIO_VIDEO_WEARABLE_HEADSET, BluetoothClass.Device.AUDIO_VIDEO_HANDSFREE -> "headset"
            BluetoothClass.Device.AUDIO_VIDEO_LOUDSPEAKER, BluetoothClass.Device.AUDIO_VIDEO_PORTABLE_AUDIO,
            BluetoothClass.Device.AUDIO_VIDEO_HIFI_AUDIO, BluetoothClass.Device.AUDIO_VIDEO_CAR_AUDIO -> "speaker"
            BluetoothClass.Device.PERIPHERAL_KEYBOARD, BluetoothClass.Device.PERIPHERAL_KEYBOARD_POINTING -> "keyboard"
            BluetoothClass.Device.PERIPHERAL_POINTING -> "mouse"
            else -> when (cls.majorDeviceClass) {
                BluetoothClass.Device.Major.PHONE -> "phone"
                BluetoothClass.Device.Major.COMPUTER -> "computer"
                else -> "other"
            }
        }
    }

    /** Adresses actuellement connectées en audio (A2DP / casque), via les profils publics. */
    @SuppressLint("MissingPermission")
    private fun connectedAddresses(context: Context, adapter: BluetoothAdapter): Set<String> {
        val connected = ConcurrentHashMap.newKeySet<String>()
        for (profile in intArrayOf(BluetoothProfile.A2DP, BluetoothProfile.HEADSET)) {
            val latch = CountDownLatch(1)
            val listener = object : BluetoothProfile.ServiceListener {
                override fun onServiceConnected(p: Int, proxy: BluetoothProfile) {
                    try { proxy.connectedDevices.forEach { connected.add(it.address) } } catch (_: SecurityException) {}
                    adapter.closeProfileProxy(p, proxy)
                    latch.countDown()
                }
                override fun onServiceDisconnected(p: Int) { latch.countDown() }
            }
            if (adapter.getProfileProxy(context, listener, profile)) latch.await(2, TimeUnit.SECONDS)
        }
        return connected
    }

    @SuppressLint("MissingPermission")
    private fun deviceJson(device: BluetoothDevice, connected: Set<String>, rssi: Int?): JSONObject = JSONObject()
        .put("address", device.address)
        .put("name", device.alias ?: device.name ?: device.address)
        .put("paired", device.bondState == BluetoothDevice.BOND_BONDED)
        .put("connected", device.address in connected)
        .put("trusted", device.bondState == BluetoothDevice.BOND_BONDED)
        .put("rssi", rssi ?: JSONObject.NULL)
        .put("kind", kindOf(device))
        .put("profiles", JSONArray())
        .put("battery", JSONObject.NULL)

    @SuppressLint("MissingPermission")
    fun bluetoothStatus(context: Context): String {
        return try {
            val adapter = adapter(context) ?: return error("no_adapter", "Cet appareil n'a pas de Bluetooth.")
            val missing = missingBluetoothPermissions(context, needScan = false)
            if (missing.isNotEmpty()) return error("permission_required", PERMISSION_MESSAGE)
            val powered = adapter.isEnabled
            val devices = JSONArray()
            if (powered) {
                val connected = connectedAddresses(context, adapter)
                val seen = HashSet<String>()
                for (d in adapter.bondedDevices) {
                    seen.add(d.address)
                    devices.put(deviceJson(d, connected, null))
                }
                for ((address, found) in discovered) if (address !in seen) devices.put(found)
            }
            JSONObject()
                .put("supported", true).put("powered", powered).put("discovering", discovering)
                .put("adapter_name", adapter.name ?: "")
                .put("devices", devices)
                .put("pending_pairing", JSONObject.NULL) // l'appairage se confirme dans la boîte de dialogue système
                .put("pairing", pairing ?: JSONObject.NULL)
                .toString()
        } catch (e: Exception) {
            Log.w(TAG, "bluetoothStatus", e)
            error("bt_failed", "Lecture du Bluetooth impossible.")
        }
    }

    /** Active le Bluetooth : Android exige la boîte de dialogue système (`adapter.enable()` est sans effet). */
    fun bluetoothRequestEnable(context: Context): String {
        return try {
            val adapter = adapter(context) ?: return error("no_adapter", "Cet appareil n'a pas de Bluetooth.")
            val missing = missingBluetoothPermissions(context, needScan = false)
            if (missing.isNotEmpty()) return requestPermissions(missing)
            if (!adapter.isEnabled) {
                context.startActivity(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            ok()
        } catch (e: Exception) {
            Log.w(TAG, "bluetoothRequestEnable", e)
            error("bt_failed", "Activation du Bluetooth impossible.")
        }
    }

    private val receiver = object : BroadcastReceiver() {
        @SuppressLint("MissingPermission")
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                BluetoothDevice.ACTION_FOUND -> {
                    val device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java) ?: return
                    val rssi = intent.getShortExtra(BluetoothDevice.EXTRA_RSSI, Short.MIN_VALUE).toInt().takeIf { it != Short.MIN_VALUE.toInt() }
                    discovered[device.address] = deviceJson(device, emptySet(), rssi)
                }
                BluetoothAdapter.ACTION_DISCOVERY_FINISHED -> discovering = false
                BluetoothDevice.ACTION_BOND_STATE_CHANGED -> {
                    val device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java) ?: return
                    val state = intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, BluetoothDevice.ERROR)
                    val label = when (state) {
                        BluetoothDevice.BOND_BONDING -> "pairing"
                        BluetoothDevice.BOND_BONDED -> "paired"
                        else -> "failed"
                    }
                    pairing = JSONObject().put("address", device.address).put("state", label)
                        .put("error", if (label == "failed") "Appairage refusé ou annulé." else JSONObject.NULL)
                    if (label == "paired") discovered.remove(device.address)
                }
            }
        }
    }

    private fun ensureReceiver(context: Context) {
        if (receiverRegistered) return
        val filter = IntentFilter().apply {
            addAction(BluetoothDevice.ACTION_FOUND)
            addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED)
            addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED)
        }
        ContextCompat.registerReceiver(context.applicationContext, receiver, filter, ContextCompat.RECEIVER_EXPORTED)
        receiverRegistered = true
    }

    @SuppressLint("MissingPermission")
    fun bluetoothScan(context: Context, on: Boolean): String {
        return try {
            val adapter = adapter(context) ?: return error("no_adapter", "Cet appareil n'a pas de Bluetooth.")
            val missing = missingBluetoothPermissions(context, needScan = true)
            if (missing.isNotEmpty()) return requestPermissions(missing)
            if (on) {
                if (!adapter.isEnabled) return error("not_ready", "Activez d'abord le Bluetooth.")
                ensureReceiver(context)
                discovered.clear()
                discovering = adapter.startDiscovery()
            } else {
                adapter.cancelDiscovery()
                discovering = false
            }
            ok()
        } catch (e: Exception) {
            Log.w(TAG, "bluetoothScan", e)
            error("bt_failed", "Recherche Bluetooth impossible.")
        }
    }

    @SuppressLint("MissingPermission")
    fun bluetoothPair(context: Context, address: String): String {
        return try {
            val adapter = adapter(context) ?: return error("no_adapter", "Cet appareil n'a pas de Bluetooth.")
            val missing = missingBluetoothPermissions(context, needScan = false)
            if (missing.isNotEmpty()) return requestPermissions(missing)
            if (!BluetoothAdapter.checkBluetoothAddress(address.uppercase())) return error("bad_address", "Adresse Bluetooth invalide.")
            ensureReceiver(context)
            adapter.cancelDiscovery() // un appairage pendant une recherche échoue souvent
            discovering = false
            val device = adapter.getRemoteDevice(address.uppercase())
            pairing = JSONObject().put("address", device.address).put("state", "pairing").put("error", JSONObject.NULL)
            if (!device.createBond()) {
                pairing = JSONObject().put("address", device.address).put("state", "failed").put("error", "Appairage impossible.")
                return error("pair_failed", "Android a refusé de lancer l'appairage.")
            }
            ok()
        } catch (e: Exception) {
            Log.w(TAG, "bluetoothPair", e)
            error("bt_failed", "Appairage impossible.")
        }
    }

    // ------------------------------------------------------------------ Wi-Fi (lecture seule)
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
                // Sans la localisation précise (jamais demandée), Android masque le nom : « <unknown ssid> ».
                val ssid = ssidRaw?.takeIf { it.isNotBlank() && it != WifiManager.UNKNOWN_SSID }
                current = JSONObject()
                    .put("ssid", ssid ?: JSONObject.NULL)
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
            error("wifi_failed", "Lecture de l'état du Wi-Fi impossible.")
        }
    }

    // ------------------------------------------------------------------ réglages du système
    fun openSettings(context: Context, target: String): String = try {
        val action = when (target) {
            "wifi" -> Settings.ACTION_WIFI_SETTINGS
            "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
            "sound" -> Settings.ACTION_SOUND_SETTINGS
            else -> return error("bad_target", "Réglage inconnu.")
        }
        try {
            context.startActivity(Intent(action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (e: android.content.ActivityNotFoundException) {
            // Certains boîtiers Android TV n'exposent pas ces écrans : repli sur les réglages généraux.
            context.startActivity(Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        ok()
    } catch (e: Exception) {
        Log.w(TAG, "openSettings", e)
        error("settings_failed", "Impossible d'ouvrir les réglages d'Android.")
    }
}
