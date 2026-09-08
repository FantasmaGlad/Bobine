package com.bobine.app

import android.os.Bundle
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.PyObject
import com.chaquo.python.Python

/**
 * Activite minimale du Lot 1 (cf. docs/plan-implementation-android.md) :
 * pas encore de WebView (Lot 5), pas encore de ForegroundService (Lot 6) -
 * juste la preuve que Chaquopy demarre et que les dependances du Lot 0
 * s'importent reellement sur l'appareil, pas seulement au moment du
 * `pip install` cote machine de developpement.
 */
class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val status = TextView(this).apply {
            setPadding(32, 64, 32, 32)
            textSize = 14f
        }
        setContentView(ScrollView(this).apply { addView(status) })

        status.text = "Verification des dependances (Lot 0)...\n"

        try {
            val py = Python.getInstance()
            val spikeCheck: PyObject = py.getModule("spike_check")
            val result: PyObject = spikeCheck.callAttr("run")
            // run() retourne un tuple Python (ok_count, total, details) -
            // asList() le convertit en liste Java indexable.
            val parts = result.asList()
            val okCount = parts[0].toInt()
            val total = parts[1].toInt()
            val details = parts[2].toString()

            status.text = "Lot 0 - $okCount/$total paquets importes avec succes\n\n$details"
        } catch (e: Exception) {
            status.text = "ECHEC demarrage Python/Chaquopy :\n${e}"
        }
    }
}
