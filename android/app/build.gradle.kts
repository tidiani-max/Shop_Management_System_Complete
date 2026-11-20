plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.dds.shopmanagement"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.dds.shopmanagement"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"

        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            install("fastapi>=0.115")
            install("uvicorn>=0.30")
            install("SQLAlchemy>=2.0")
            install("alembic>=1.13")
            install("argon2-cffi>=23.1")
            install("python-multipart>=0.0.9")
            install("pydantic>=2.7")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("../../backend")
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.webkit:webkit:1.11.0")
}
