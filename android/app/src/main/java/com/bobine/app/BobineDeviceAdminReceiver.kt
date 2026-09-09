package com.bobine.app

/**
 * Lot 10 (cf. docs/plan-implementation-android.md) : Device Owner SANS
 * Lock Task - CDC §7, décision explicite de ne pas verrouiller la
 * tablette (geste système standard toujours possible, cf. Lot 5). Ce
 * receiver ne déclare AUCUNE politique de restriction
 * (`res/xml/device_admin.xml` est volontairement vide) : le statut de
 * Device Owner sert uniquement à débloquer des capacités système
 * réservées à ce rôle (ex. installation silencieuse d'APK au Lot 11),
 * pas à imposer quoi que ce soit à l'utilisateur.
 *
 * Provisioning (cf. Découvertes du Lot 10) : `adb shell dpm
 * set-device-owner com.bobine.app/.BobineDeviceAdminReceiver`, exige
 * qu'aucun compte ne soit configuré sur l'appareil.
 */
class BobineDeviceAdminReceiver : android.app.admin.DeviceAdminReceiver()
