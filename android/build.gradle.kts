// Racine du projet Android.
//
// Versions choisies pour le spike de compatibilité :
// - AGP 9.2.1 : version déjà qualifiée par Bobine et explicitement
//   testée par Chaquopy 17.0 (plage documentée 7.3.x-9.4.x — les versions
//   hors de cette plage ne sont pas garanties. Le lot courant conserve
//   le couple déjà construit, sans migration de plugin).
// - Kotlin : PAS de plugin org.jetbrains.kotlin.android déclaré ici — AGP 9.0+
//   a introduit un support Kotlin intégré (« built-in Kotlin ») et REFUSE
//   l'ancien plugin séparé (erreur de build constatée en pratique). AGP tire lui-même le Kotlin Gradle Plugin
//   2.2.10 comme dépendance runtime — rien à déclarer côté projet.
// - Chaquopy 17.0.0 : version retenue et testée par Bobine — l'ancienne
//   documentation du projet citait une version bien plus
//   ancienne (12.0.0, 2022) trouvée sur l'ancien dépôt Maven maison
//   chaquo.com/maven ; la distribution actuelle passe par mavenCentral().
plugins {
    id("com.android.application") version "9.2.1" apply false
    id("com.chaquo.python") version "17.0.0" apply false
}
