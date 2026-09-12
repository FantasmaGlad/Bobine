// Module applicatif Android — cf. docs/plan-implementation-android.md, Lot 0/1.
plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// Lot 13 (cf. docs/plan-implementation-android.md) : signature release.
// Cle dediee generee hors depot (~/.bobine-signing/ sur la machine de
// build initiale, jamais commitee) - lue ici via variables d'environnement
// (secrets GitHub Actions en CI : ANDROID_KEYSTORE_PATH pointe vers le
// fichier decode a partir du secret ANDROID_KEYSTORE_BASE64, cf. le job
// android-build de ci.yml). Absentes en local -> pas de signingConfig
// applique, `assembleRelease` produit alors un APK non signe (utilisable
// pour inspecter le build, pas pour l'installer en mise a jour reelle).
val androidKeystorePath: String? = System.getenv("ANDROID_KEYSTORE_PATH")
val androidKeystorePassword: String? = System.getenv("ANDROID_KEYSTORE_PASSWORD")
val androidKeyAlias: String? = System.getenv("ANDROID_KEY_ALIAS")
val androidKeyPassword: String? = System.getenv("ANDROID_KEY_PASSWORD")
val hasReleaseSigningConfig = listOf(androidKeystorePath, androidKeystorePassword, androidKeyAlias, androidKeyPassword).all { !it.isNullOrBlank() }

// Lot 11 (cf. docs/plan-implementation-android.md, §"versions dynamiques") :
// mêmes deux valeurs injectées par la CI que sur les autres plateformes
// (VERSION/COMMIT bundlés, cf. ci.yml) plutôt que la constante figée
// utilisée jusqu'ici. Le job android-build positionne :
// - ANDROID_VERSION_NAME = needs.version.outputs.display_version, DEJA du
//   format "x.y.z" (tag Stable) ou "x.y.z-beta" (push main) partagé avec
//   Windows/macOS/Linux - aucun format Android-specifique invente ici.
// - ANDROID_VERSION_CODE = nombre de commits sur main (`git rev-list
//   --count HEAD`) - entier strictement croissant à chaque commit, condition
//   exigée par Android pour qu'une mise à jour (Lot 11) soit acceptée
//   par-dessus une installation existante ; un tag Stable pointant sur un
//   commit de main garde la meme propriete de croissance (pas de retour en
//   arriere), contrairement a un compteur reinitialise par run CI.
// Absentes en local -> repli sur les anciennes constantes figees (build de
// developpement uniquement, jamais installe comme mise a jour d'une
// version CI reelle).
val rootVersionFile = rootProject.projectDir.resolve("../VERSION")
val fallbackVersionName = if (rootVersionFile.exists()) rootVersionFile.readText().trim() else "3.0.5"
val androidVersionName: String = System.getenv("ANDROID_VERSION_NAME") ?: fallbackVersionName
val androidVersionCode: Int = System.getenv("ANDROID_VERSION_CODE")?.toIntOrNull() ?: 220

android {
    namespace = "com.bobine.app"
    // CDC docs/ARCHITECTURE.md §2 : minSdk/targetSdk API 34-36, priorité
    // donnée à l'avenir plutôt qu'à la compatibilité descendante. compileSdk 36
    // correspond à la tablette pilote réelle (Xiaomi Pad 8, Android 16).
    compileSdk = 36

    if (hasReleaseSigningConfig) {
        signingConfigs {
            create("release") {
                storeFile = file(androidKeystorePath!!)
                storePassword = androidKeystorePassword
                keyAlias = androidKeyAlias
                keyPassword = androidKeyPassword
            }
        }
    }

    defaultConfig {
        applicationId = "com.bobine.app"
        minSdk = 34
        targetSdk = 36
        versionCode = androidVersionCode
        versionName = androidVersionName

        ndk {
            // arm64-v8a : tablettes réelles (checklist matérielle, CDC §6).
            // x86_64 : émulateur sur machine de développement x86_64.
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (hasReleaseSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    // Lot 8 : par defaut (AGP recent), les libs natives restent compressees
    // DANS l'APK et sont mappees en memoire par dlopen sans jamais toucher
    // le disque - parfait pour de vraies bibliotheques partagees (Chaquopy),
    // mais laisse android:applicationInfo.nativeLibraryDir VIDE. Or
    // libffmpeg.so/libffprobe.so ne sont pas de vraies bibliotheques : ce
    // sont des EXECUTABLES renommes en .so pour profiter du seul mecanisme
    // de packaging natif d'Android, executes via subprocess.run (pas
    // dlopen) - il leur faut un vrai fichier sur disque, avec le bit
    // executable, pour que execve() fonctionne. useLegacyPackaging force
    // l'extraction classique de TOUTES les libs natives a l'installation
    // (constate en pratique : sans ceci, nativeLibraryDir existe mais reste
    // vide malgre un packaging Gradle reussi - piege facile a rater vu
    // qu'aucune erreur n'est levee avant l'echec runtime de subprocess.run).
    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }

    // Lot 15 (docs/audit-android-2026-09-11.md §5 étape 15.4) : génération de
    // BuildConfig désactivée par défaut depuis AGP 8+ (surface d'API
    // réduite par défaut) — nécessaire pour BuildConfig.DEBUG, utilisé par
    // MainActivity.kt pour ne garder le débogage WebView qu'en build debug.
    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    // Pas de bloc kotlinOptions { jvmTarget = ... } : DSL supprimee par le
    // support Kotlin integre d'AGP 9+ (constate pendant le Lot 0, cf.
    // Decouvertes du plan). compileOptions ci-dessus suffit a fixer la
    // cible JVM 17 pour Kotlin comme pour Java.
}

// Lot 2 (cf. docs/plan-implementation-android.md) : mise en scène du vrai
// backend/app/ et du frontend statique compile, SANS copier tout backend/
// (qui contient .venv/, data/, tests/, alembic/ - non pertinents/indesirables
// dans l'APK).
//
// Chaquopy monte le contenu de `chaquopy.sourceSets` sous un dossier FIXE
// `AssetFinder/app/` sur l'appareil (constate en pratique, Lot 2 - pas
// derive du nom "backend" choisi ici) : la logique de chemins reelle de
// `backend/app/main.py` (3 `.parent` pour retomber sur un `frontend/out`
// sibling de `backend/`) ne peut donc PAS fonctionner telle quelle sur
// Android, `AssetFinder/app/` etant un palier fixe imbrique par Chaquopy,
// pas un vrai sibling adressable. `main.py` a une branche Android dediee
// (detectee via `hasattr(sys, "getandroidapilevel")`) qui attend plutot
// `frontend_out/` comme sibling du paquet `app/` - d'ou la disposition
// choisie ici :
//   build/pyStage/backend/app/...          <- chaquopy.sourceSets pointe ici
//   build/pyStage/backend/frontend_out/...  <- sibling de app/, PAS de backend/
val pyStageDir = layout.buildDirectory.dir("pyStage")

val buildFrontend = tasks.register<Exec>("buildFrontendStatic") {
    workingDir = rootProject.projectDir.resolve("../frontend")
    commandLine("npm", "run", "build")
    inputs.dir(workingDir.resolve("src"))
    inputs.file(workingDir.resolve("package.json"))
    inputs.file(workingDir.resolve("next.config.ts"))
    outputs.dir(workingDir.resolve("out"))
}

val stagePythonSources = tasks.register<Copy>("stagePythonSources") {
    dependsOn(buildFrontend)
    // backend/app/ uniquement (pas backend/.venv, data, tests, alembic...).
    from(rootProject.projectDir.resolve("../backend/app")) {
        into("backend/app")
        exclude("**/__pycache__/**")
    }
    from(rootProject.projectDir.resolve("../frontend/out")) {
        into("backend/frontend_out")
    }
    from(rootProject.projectDir.resolve("../VERSION")) {
        into("backend/app")
    }
    from(rootProject.projectDir.resolve("../VERSION")) {
        into("backend")
    }
    if (rootProject.projectDir.resolve("../COMMIT").exists()) {
        from(rootProject.projectDir.resolve("../COMMIT")) {
            into("backend/app")
        }
        from(rootProject.projectDir.resolve("../COMMIT")) {
            into("backend")
        }
    }
    into(pyStageDir)
}

// Chaquopy doit voir les sources mises en scene AVANT de les fusionner dans
// l'APK. Le hook preBuild seul ne suffit pas : la validation stricte de
// Gradle 9 (constatee en pratique, Lot 2) exige une dependance EXPLICITE
// entre la tache qui lit `pyStageDir` (mergeDebugPythonSources /
// mergeReleasePythonSources) et celle qui l'ecrit, sinon
// "Property has implicit dependency" fait echouer le build - une
// dependance transitive via preBuild ne compte pas comme telle.
tasks.named("preBuild") {
    dependsOn(stagePythonSources)
}
tasks.matching { it.name.startsWith("merge") && it.name.endsWith("PythonSources") }
    .configureEach { dependsOn(stagePythonSources) }

chaquopy {
    sourceSets {
        getByName("main") {
            srcDir(pyStageDir.map { it.dir("backend") })
        }
    }
    defaultConfig {
        // Python 3.13 : c'est la version majeure.mineure disponible sur cette
        // machine de développement (buildPython doit matcher exactement en
        // majeur.mineur — cf. Découvertes du Lot 0 dans le plan
        // d'implémentation, seuls python3.13 et python3.14 sont installés
        // ici, pas 3.10/3.11/3.12).
        version = "3.13"

        pip {
            // DECISION ACTEE (Lot 0, cf. Decouvertes du plan et CDC SS3.1) :
            // pydantic-core (extension Rust, dependance dure de Pydantic v2)
            // N'A AUCUNE distribution Android reelle - pip installe sinon
            // silencieusement `pydantic-core==0.0.1`, un PLACEHOLDER VIDE
            // publie en 2022 par l'auteur de Pydantic, sans code reel.
            // Decision utilisateur : downgrade Pydantic v1 (pur Python,
            // aucune extension native) UNIQUEMENT sur le profil Android -
            // les autres plateformes restent en Pydantic v2/FastAPI
            // recents. Versions epinglees ci-dessous confirmees par un
            // build complet reussi (APK genere) :
            install("pydantic==1.10.26")
            install("fastapi==0.99.1")
            // Sans l'extra [standard] : httptools n'a aucune distribution
            // Android (confirme, cf. Decouvertes du plan Lot 0). uvicorn nu
            // retombe sur h11 (pur Python, deja resolu par ailleurs).
            install("uvicorn==0.52.1")
            // websockets : /ws/playback (sync de lecture temps reel, coeur
            // de Bobine) NE FONCTIONNE PAS avec uvicorn nu seul - "No
            // supported WebSocket library detected", 404 sur /ws/playback
            // (constate en pratique, Lot 3). uvicorn[standard] regroupe
            // websockets ET httptools/uvloop (ces deux derniers sans
            // distribution Android, cf. Lot 0) - installer websockets seul
            // recupere le support WebSocket sans les extras bloquants.
            install("websockets")
            install("sqlalchemy==2.0.51")
            install("alembic==1.18.5")
            install("python-multipart==0.0.32")
            install("apscheduler==3.11.3")
            install("tzlocal==5.4.4")
            // tzdata : Android n'a pas de base systeme /usr/share/zoneinfo
            // a l'emplacement attendu par le module stdlib `zoneinfo` (a la
            // difference des distributions Linux desktop) - decouvert au
            // Lot 2 en executant reellement app.main sur un emulateur
            // (ZoneInfoNotFoundError via scheduler_manager -> tzlocal).
            // Absent de backend/requirements.txt car inutile ailleurs.
            install("tzdata")
            install("aiofiles==25.1.0")
            // pillow==12.3.0 (version desktop) indisponible pour Android -
            // seule la 11.0.0 existe sur l'index Chaquopy (confirme en
            // test, Decouvertes du plan Lot 0). API stable entre ces
            // versions pour l'usage de Bobine (vignettes/redimensionnement).
            install("pillow==11.0.0")
            // psutil==7.2.2 (desktop) indisponible - seule 7.1.3 existe
            // pour Android (confirme en test, Decouvertes du plan Lot 0).
            install("psutil==7.1.3")
            install("pystray==0.19.5")
            // zeroconf==0.151.3 (desktop) indisponible - la plus recente
            // pour Android est 0.39.4, un ecart de version notable (a
            // surveiller pour des differences d'API dans un lot ulterieur,
            // cf. Decouvertes du plan Lot 0) mais l'API coeur (Zeroconf,
            // ServiceInfo, register_service) est stable sur cette plage.
            install("zeroconf==0.39.4")
            // watchdog : AUCUNE distribution Android, non resolu a ce
            // stade - volontairement absent (cf. Decouvertes du plan
            // Lot 0). backend/app/utils/watcher.py devra etre adapte
            // (implementation maison ctypes/inotify ou polling) pour le
            // profil Android specifiquement - non fait ici.
        }
        // Points de compatibilite Pydantic v1 restant a traiter dans
        // backend/app/ pour le profil Android (identifies par grep,
        // perimetre volontairement petit - cf. Decouvertes du plan
        // Lot 0) : `pydantic_settings.BaseSettings` (config.py:6, remplacer
        // par `pydantic.BaseSettings` integre a v1 sur ce profil),
        // `field_validator` (routers/radio_announcements.py:20,75, syntaxe
        // v1 = `validator`), `payload.model_dump(...)` (routers/settings.py:339,
        // syntaxe v1 = `.dict(...)`). Non fait a ce stade (Lot 0 ne valide
        // que la resolution des dependances, pas encore l'import du vrai
        // backend/app/ - cf. Lot 2).
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    // registerForActivityResult/ActivityResultContracts (demande de la
    // permission POST_NOTIFICATIONS a l'execution, Lot 6).
    implementation("androidx.activity:activity-ktx:1.9.3")
}
