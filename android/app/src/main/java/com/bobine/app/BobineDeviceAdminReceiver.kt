package com.bobine.app

/**
 * Device Owner SANS Lock Task - CDC §7, décision explicite de ne pas
 * verrouiller la tablette (geste système standard toujours possible). Ce
 * receiver ne déclare AUCUNE politique de restriction
 * (`res/xml/device_admin.xml` est volontairement vide) : le statut de
 * Device Owner sert uniquement à débloquer, en prévision, des capacités
 * système réservées à ce rôle — aucune n'est exploitée aujourd'hui.
 * Notamment PAS l'installation silencieuse d'APK (`PackageInstaller` en
 * mode sans confirmation utilisateur) : décision explicite et maintenue
 * de toujours passer par la boîte de dialogue système standard pour
 * confirmer une mise à jour, même avec ce statut actif (cf.
 * UpdateManager.kt).
 *
 * Provisioning : `adb shell dpm set-device-owner
 * com.bobine.app/.BobineDeviceAdminReceiver`, exige qu'aucun compte ne
 * soit configuré sur l'appareil.
 */
class BobineDeviceAdminReceiver : android.app.admin.DeviceAdminReceiver()
