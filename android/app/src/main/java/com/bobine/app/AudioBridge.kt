package com.bobine.app

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject

private const val TAG = "AudioBridge"

object AudioBridge {
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
        bridgeError("audio_failed", "Lecture des sorties audio impossible.")
    }

    private fun encodingLabel(encoding: Int): String = when (encoding) {
        android.media.AudioFormat.ENCODING_PCM_8BIT -> "PCM 8 bits"
        android.media.AudioFormat.ENCODING_PCM_16BIT -> "PCM 16 bits"
        android.media.AudioFormat.ENCODING_PCM_24BIT_PACKED -> "PCM 24 bits"
        android.media.AudioFormat.ENCODING_PCM_32BIT -> "PCM 32 bits"
        android.media.AudioFormat.ENCODING_PCM_FLOAT -> "PCM flottant"
        android.media.AudioFormat.ENCODING_AC3 -> "Dolby Digital (AC-3)"
        android.media.AudioFormat.ENCODING_E_AC3 -> "Dolby Digital Plus"
        android.media.AudioFormat.ENCODING_DTS -> "DTS"
        else -> "Encodage $encoding"
    }

    fun audioDetails(context: Context, id: String): String = try {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val device = audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS).firstOrNull { it.id.toString() == id }
            ?: return bridgeError("not_found", "Cette sortie audio n'est plus disponible.")
        val rates = device.sampleRates.filter { it > 0 }
        val channels = device.channelCounts.maxOrNull()
        JSONObject()
            .put("supported", true)
            .put("id", id)
            .put("name", device.productName?.toString().orEmpty().ifBlank { "Sortie $id" })
            .put("state", "unknown")
            .put("channels", channels ?: JSONObject.NULL)
            .put("channel_map", JSONArray())
            .put("sample_rate", rates.maxOrNull() ?: JSONObject.NULL)
            .put("format", device.encodings.takeIf { it.isNotEmpty() }?.joinToString(", ") { encodingLabel(it) } ?: JSONObject.NULL)
            .put("latency_ms", JSONObject.NULL)
            .put("card", device.address.takeIf { it.isNotBlank() } ?: JSONObject.NULL)
            .put("bus", audioKind(device.type))
            .put("api", "android")
            .put("codec", JSONObject.NULL)
            .put("profile", JSONObject.NULL)
            .put("profiles", JSONArray())
            .put("balance", JSONObject.NULL)
            .put("level", JSONObject.NULL)
            .put("muted", JSONObject.NULL)
            .toString()
    } catch (e: Exception) {
        Log.w(TAG, "audioDetails", e)
        bridgeError("audio_failed", "Analyse de la sortie audio impossible.")
    }

    fun audioSetVolume(context: Context, volume: Double, muted: Int): String = try {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if (volume >= 0.0) {
            val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            audio.setStreamVolume(AudioManager.STREAM_MUSIC, Math.round(volume.coerceIn(0.0, 1.0) * max).toInt(), 0)
        }
        if (muted >= 0) {
            audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, if (muted == 1) AudioManager.ADJUST_MUTE else AudioManager.ADJUST_UNMUTE, 0)
        }
        bridgeOk()
    } catch (e: SecurityException) {
        bridgeError("not_authorized", "Android refuse de modifier le volume (mode Ne pas déranger ?).")
    } catch (e: Exception) {
        Log.w(TAG, "audioSetVolume", e)
        bridgeError("audio_failed", "Réglage du volume impossible.")
    }
}
