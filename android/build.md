# Android Build

## Requirements
- Android Studio Hedgehog 2023.1.1+ or command-line SDK
- Android SDK 34
- Kotlin 1.9.20+
- Gradle 8.2+
- JDK 17

## Dependencies
- OkHttp 4.x — HTTP + WebSocket client
- Kotlin Coroutines — async operations
- Retrofit 2.9 + Gson — REST API
- EncryptedSharedPreferences — secure settings storage
- ExoPlayer 2.19 — audio playback

## Build

```bash
cd android
./gradlew assembleRelease
```

APK at `app/build/outputs/apk/release/app-release.apk`.

## Signing
Create `android/keystore.properties`:
```
storePassword=<password>
keyPassword=<password>
keyAlias=holmium
storeFile=../holmium.keystore
```

Generate keystore:
```bash
keytool -genkey -v -keystore holmium.keystore -alias holmium -keyalg RSA -keysize 2048 -validity 10000
```

## Install
```bash
adb install app/build/outputs/apk/release/app-release.apk
```

WireGuard must be configured before first launch.
