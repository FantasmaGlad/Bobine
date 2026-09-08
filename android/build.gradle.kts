// Racine du projet Android — cf. docs/plan-implementation-android.md, Lot 1.
//
// Versions choisies pour le spike de compatibilité (Lot 0) :
// - AGP 9.2.1 : dernier correctif de la dernière version explicitement
//   testée par Chaquopy 17.0 (plage documentée 7.3.x-9.2.x — les versions
//   plus récentes, ex. 9.4.0 disponible au moment de l'écriture, ne sont
//   « pas testées » par Chaquopy et ne sont donc pas retenues ici).
// - Kotlin : PAS de plugin org.jetbrains.kotlin.android déclaré ici — AGP 9.0+
//   a introduit un support Kotlin intégré (« built-in Kotlin ») et REFUSE
//   l'ancien plugin séparé (erreur de build constatée pendant le Lot 0,
//   cf. Découvertes du plan). AGP tire lui-même le Kotlin Gradle Plugin
//   2.2.10 comme dépendance runtime — rien à déclarer côté projet.
// - Chaquopy 17.0.0 : dernière version publiée (2025-11-30) — voir
//   Découvertes du Lot 0 dans le plan d'implémentation, la documentation
//   consultée pendant la rédaction du CDC citait une version bien plus
//   ancienne (12.0.0, 2022) trouvée sur l'ancien dépôt Maven maison
//   chaquo.com/maven ; la distribution actuelle passe par mavenCentral().
plugins {
    id("com.android.application") version "9.2.1" apply false
    id("com.chaquo.python") version "17.0.0" apply false
}
