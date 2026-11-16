package com.bobine.app

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
import android.util.Log
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

private const val TAG = "BluetoothBridge"
private const val PERMISSION_MESSAGE =
    "Autorisez « Appareils à proximité » sur l'appareil Android, Bobine ouvert au premier plan, puis réessayez."

object BluetoothBridge {
    private val discovered = ConcurrentHashMap<String, JSONObject>()
    @Volatile private var receiverRegistered = false
    @Volatile private var discovering = false
    @Volatile private var pairing: JSONObject? = null

    private fun adapter(context: Context): BluetoothAdapter? =
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter

    private fun missingBluetooth(context: Context): Boolean =
        Permissions.missing(context, Permissions.bluetooth).isNotEmpty()

    private fun permissionRequired(context: Context): String {
        Permissions.requestWhenVisible(context, Permissions.bluetooth)
        return bridgeError("permission_required", PERMISSION_MESSAGE)
    }

    fun bluetoothRequestPermission(context: Context): String {
        return if (missingBluetooth(context)) permissionRequired(context) else bridgeOk()
    }

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
            val adapter = adapter(context) ?: return bridgeError("no_adapter", "Cet appareil n'a pas de Bluetooth.")
            if (missingBluetooth(context)) return bridgeError("permission_required", PERMISSION_MESSAGE)
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
            bridgeError("bt_failed", "Lecture du Bluetooth impossible.")
        }
    }

    fun bluetoothRequestEnable(context: Context): String {
        return try {
            val adapter = adapter(context) ?: return bridgeError("no_adapter", "Cet appareil n'a pas de Bluetooth.")
            if (missingBluetooth(context)) return permissionRequired(context)
            if (!adapter.isEnabled) {
                context.startActivity(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            bridgeOk()
        } catch (e: Exception) {
            Log.w(TAG, "bluetoothRequestEnable", e)
            bridgeError("bt_failed", "Activation du Bluetooth impossible.")
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
            val adapter = adapter(context) ?: return bridgeError("no_adapter", "Cet appareil n'a pas de Bluetooth.")
            if (missingBluetooth(context)) return permissionRequired(context)
            if (on) {
                if (!adapter.isEnabled) return bridgeError("not_ready", "Activez d'abord le Bluetooth.")
                ensureReceiver(context)
                discovered.clear()
                discovering = adapter.startDiscovery()
            } else {
                adapter.cancelDiscovery()
                discovering = false
            }
            bridgeOk()
        } catch (e: Exception) {
            Log.w(TAG, "bluetoothScan", e)
            bridgeError("bt_failed", "Recherche Bluetooth impossible.")
        }
    }

    @SuppressLint("MissingPermission")
    fun bluetoothPair(context: Context, address: String): String {
        return try {
            val adapter = adapter(context) ?: return bridgeError("no_adapter", "Cet appareil n'a pas de Bluetooth.")
            if (missingBluetooth(context)) return permissionRequired(context)
            if (!BluetoothAdapter.checkBluetoothAddress(address.uppercase())) return bridgeError("bad_address", "Adresse Bluetooth invalide.")
            ensureReceiver(context)
            adapter.cancelDiscovery() // un appairage pendant une recherche échoue souvent
            discovering = false
            val device = adapter.getRemoteDevice(address.uppercase())
            pairing = JSONObject().put("address", device.address).put("state", "pairing").put("error", JSONObject.NULL)
            if (!device.createBond()) {
                pairing = JSONObject().put("address", device.address).put("state", "failed").put("error", "Appairage impossible.")
                return bridgeError("pair_failed", "Android a refusé de lancer l'appairage.")
            }
            bridgeOk()
        } catch (e: Exception) {
            Log.w(TAG, "bluetoothPair", e)
            bridgeError("bt_failed", "Appairage impossible.")
        }
    }
}
