# Android Setup Guide

## Prerequisites
- Android phone (API 29+, Android 10+)
- WireGuard app from Play Store or F-Droid
- Holmium APK (build from `android/` or sideload)

## Step 1: WireGuard Configuration

1. Install WireGuard app from Play Store
2. Open the Holmium Android config from the first-run wizard QR code:
   - On Holmium PC during first-run, a QR code is displayed
   - Scan with WireGuard app
3. Or manually enter:
   ```
   [Interface]
   PrivateKey = <from register_peers.sh output>
   Address = 10.0.0.3/32
   DNS = 10.0.0.1
   
   [Peer]
   PublicKey = <server public key>
   AllowedIPs = 0.0.0.0/0
   Endpoint = <server-public-ip>:51820
   PersistentKeepalive = 25
   ```
4. Toggle WireGuard ON

## Step 2: Install APK

```bash
adb install holmium.apk
```
Or download directly and open on the phone to install.

## Step 3: Configure Holmium App

1. Open Holmium app
2. Go to Settings (gear icon)
3. Set:
   - Server IP: `10.0.0.1` (default)
   - Server Port: `8765` (default)
   - Auth Token: from `/etc/holmium/token` on server
   - TTS: on (optional)
   - STT Language: English
   - Theme: Dark (default), Light, or System
   - Notification Sound: on

## Step 4: Test Connection

1. In Settings, tap "Test Connection"
2. Should show "Connected! Server OK."
3. Return to chat screen
4. Type a message — it goes through WireGuard to Holmium

## Features
- Chat with streaming responses
- Voice recording + playback
- Push notifications via ntfy.sh
- Wake word "Hey Holmium" (OFF by default)
- Share sheet integration
- Memory browser
- Theme toggle (dark/light/system)

## Troubleshooting
- **Cannot connect**: Verify WireGuard is ON, server IP correct, token matches
- **No notifications**: Check ntfy topic in settings, verify FCM registration
- **Voice not working**: Check RECORD_AUDIO permission
