plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

val androidKeystorePath: String? = System.getenv("ANDROID_KEYSTORE_PATH")
val androidKeystorePassword: String? = System.getenv("ANDROID_KEYSTORE_PASSWORD")
val androidKeyAlias: String? = System.getenv("ANDROID_KEY_ALIAS")
val androidKeyPassword: String? = System.getenv("ANDROID_KEY_PASSWORD")
val hasReleaseSigningConfig = listOf(androidKeystorePath, androidKeystorePassword, androidKeyAlias, androidKeyPassword).all { !it.isNullOrBlank() }

val rootVersionFile = rootProject.projectDir.resolve("../VERSION")
val fallbackVersionName = if (rootVersionFile.exists()) rootVersionFile.readText().trim() else "5.1.2"
val androidVersionName: String = System.getenv("ANDROID_VERSION_NAME") ?: fallbackVersionName
@Suppress("UNCHECKED_CAST")
val releaseChannelRegistry = groovy.json.JsonSlurper()
    .parse(rootProject.projectDir.resolve("release-channels.json")) as Map<String, Any?>
@Suppress("UNCHECKED_CAST")
val releaseChannelEntries = releaseChannelRegistry["channels"] as List<Map<String, Any?>>
val releaseChannels: List<String> = releaseChannelEntries.map { it["id"] as String }
val defaultReleaseChannel: String = releaseChannelRegistry["default"] as String
val bobineChannel: String = (
    providers.gradleProperty("bobineChannel").orNull
        ?: run {
            val suffixes = releaseChannelEntries.mapNotNull { it["versionSuffix"] as String? }.joinToString("|") { Regex.escape(it) }
            val match = Regex("^v?\\d+\\.\\d+\\.\\d+[-~]($suffixes)$", RegexOption.IGNORE_CASE).find(androidVersionName.trim())
            val suffix = match?.groupValues?.get(1)?.lowercase()
            releaseChannelEntries.firstOrNull { it["versionSuffix"] == suffix && suffix != null }?.get("id") as String?
        }
        ?: defaultReleaseChannel
    ).also { channel ->
        require(channel in releaseChannels) { "bobineChannel '$channel' inconnu (attendu : $releaseChannels)" }
    }
val fallbackVersionCode: Int = try {
    val process = ProcessBuilder("git", "rev-list", "--count", "HEAD")
        .directory(rootProject.projectDir)
        .redirectErrorStream(true)
        .start()
    val output = process.inputStream.bufferedReader().readText().trim()
    process.waitFor()
    output.toIntOrNull() ?: 222
} catch (_: Exception) {
    222
}
val androidVersionCode: Int = System.getenv("ANDROID_VERSION_CODE")?.toIntOrNull() ?: fallbackVersionCode

val emulatorBuild = providers.gradleProperty("bobineEmulator").map { it.toBoolean() }.getOrElse(false)

@Suppress("UNCHECKED_CAST")
val androidToolchain = groovy.json.JsonSlurper()
    .parse(rootProject.projectDir.resolve("toolchain.json")) as Map<String, Any?>

android {
    namespace = "com.bobine.app"
    compileSdk = (androidToolchain["compile_sdk"] as Number).toInt()
    buildToolsVersion = androidToolchain["build_tools"] as String

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
        minSdk = (androidToolchain["min_sdk"] as Number).toInt()
        targetSdk = (androidToolchain["target_sdk"] as Number).toInt()
        versionCode = androidVersionCode
        versionName = androidVersionName
        buildConfigField("String", "BUILD_CHANNEL", "\"$bobineChannel\"")
        buildConfigField("String", "RELEASE_CHANNELS", "\"${releaseChannels.joinToString(",")}\"")
        buildConfigField("String", "DEFAULT_RELEASE_CHANNEL", "\"$defaultReleaseChannel\"")
    }

    flavorDimensions += listOf("device")
    productFlavors {
        create("mobile") {
            dimension = "device"
            ndk {
                abiFilters += listOf("arm64-v8a")
                if (emulatorBuild) abiFilters += "x86_64"
            }
        }
        create("tv") {
            dimension = "device"
            applicationIdSuffix = ".tv"
            ndk {
                abiFilters += listOf("armeabi-v7a", "arm64-v8a")
                if (emulatorBuild) abiFilters += "x86_64"
            }
        }
    }

    sourceSets {
        getByName("main").res.srcDir("src/channel-$bobineChannel/res")
        getByName("tv").res.srcDir("src/tv-channel-$bobineChannel/res")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            buildConfigField("boolean", "STORE_BUILD", "false")
            if (hasReleaseSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
        create("play") {
            initWith(getByName("release"))
            matchingFallbacks += listOf("release")
            buildConfigField("boolean", "STORE_BUILD", "true")
        }
        debug {
            buildConfigField("boolean", "STORE_BUILD", "false")
        }
    }

    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

androidComponents {
    beforeVariants(selector().all()) { variant ->
        if (emulatorBuild && variant.buildType != "debug") variant.enable = false
    }
}

val pyStageDir = layout.buildDirectory.dir("pyStage")

val buildFrontend = tasks.register<Exec>("buildFrontendStatic") {
    workingDir = rootProject.projectDir.resolve("../frontend")
    commandLine("npm", "run", "build")
    inputs.dir(workingDir.resolve("src"))
    inputs.file(workingDir.resolve("package.json"))
    inputs.file(workingDir.resolve("next.config.ts"))
    inputs.file(workingDir.resolve("tsconfig.json"))
    inputs.dir(workingDir.resolve("scripts"))
    outputs.dir(workingDir.resolve("out"))
}

val stagePythonSources = tasks.register<Copy>("stagePythonSources") {
    dependsOn(buildFrontend)
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
    productFlavors {
        getByName("tv") { version = "3.11" }
    }
    defaultConfig {
        version = "3.13"

        pip {
            install("pydantic==1.10.26")
            install("fastapi==0.99.1")
            install("uvicorn==0.52.1")
            install("websockets==17.3")
            install("sqlalchemy==2.0.51")
            install("python-multipart==0.0.32")
            install("apscheduler==3.11.3")
            install("tzlocal==5.4.4")
            install("tzdata==2026.5")
            install("aiofiles==25.1.0")
            install("pillow==11.0.0")
            install("psutil==7.1.3")
            install("pystray==0.19.5")
            install("zeroconf==0.39.4")
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.appcompat:appcompat:1.8.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
    "playImplementation"("com.google.android.play:app-update:2.1.0")
}
