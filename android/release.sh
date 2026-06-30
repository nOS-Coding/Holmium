#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== Holmium Android APK Build ==="

if [ ! -f "keystore.properties" ]; then
    echo "Missing keystore.properties. Creating template..."
    cat > keystore.properties << 'EOF'
storePassword=changeme
keyPassword=changeme
keyAlias=holmium
storeFile=../holmium.keystore
EOF
    echo "Edit keystore.properties with your credentials."
    exit 1
fi

echo "Building release APK..."
./gradlew assembleRelease

APK="app/build/outputs/apk/release/app-release.apk"
SIGNED="app/build/outputs/apk/release/holmium-signed.apk"

mkdir -p release

echo "Signing APK..."
if [ -f holmium.keystore ]; then
    cp "$APK" "$SIGNED"
    apksigner sign --ks holmium.keystore --ks-key-alias holmium "$SIGNED"
    cp "$SIGNED" release/holmium.apk
    echo "Signed APK: release/holmium.apk"
else
    echo "No keystore found. Unsigned APK at $APK"
    cp "$APK" release/holmium-unsigned.apk
fi

echo "Done."
