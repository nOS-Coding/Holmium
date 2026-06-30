package com.holmium

import android.app.Activity
import android.content.Context
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate

object ThemeManager {

    fun apply(activity: Activity) {
        val prefs = HolmiumPreferences(activity)
        setTheme(prefs.theme)
    }

    fun setTheme(theme: String) {
        when (theme) {
            "dark" -> AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES)
            "light" -> AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO)
            "system" -> AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM)
        }
    }
}

class HolmiumPreferences(context: Context) {

    private val prefs = context.getSharedPreferences("holmium_prefs", Context.MODE_PRIVATE)

    var serverIp: String
        get() = prefs.getString("server_ip", "10.0.0.1") ?: "10.0.0.1"
        set(value) = prefs.edit().putString("server_ip", value).apply()

    var serverPort: Int
        get() = prefs.getInt("server_port", 8765)
        set(value) = prefs.edit().putInt("server_port", value).apply()

    var authToken: String
        get() = prefs.getString("auth_token", "") ?: ""
        set(value) = prefs.edit().putString("auth_token", value).apply()

    var ttsEnabled: Boolean
        get() = prefs.getBoolean("tts_enabled", true)
        set(value) = prefs.edit().putBoolean("tts_enabled", value).apply()

    var sttLanguage: String
        get() = prefs.getString("stt_language", "en") ?: "en"
        set(value) = prefs.edit().putString("stt_language", value).apply()

    var notificationSound: Boolean
        get() = prefs.getBoolean("notification_sound", true)
        set(value) = prefs.edit().putBoolean("notification_sound", value).apply()

    var textSize: Int
        get() = prefs.getInt("text_size", 14)
        set(value) = prefs.edit().putInt("text_size", value).apply()

    var theme: String
        get() = prefs.getString("theme", "dark") ?: "dark"
        set(value) = prefs.edit().putString("theme", value).apply()

    var wakeWordEnabled: Boolean
        get() = prefs.getBoolean("wake_word_enabled", false)
        set(value) = prefs.edit().putBoolean("wake_word_enabled", value).apply()

    var wakeWordKey: String
        get() = prefs.getString("wake_word_key", "") ?: ""
        set(value) = prefs.edit().putString("wake_word_key", value).apply()

    var clipboardSync: Boolean
        get() = prefs.getBoolean("clipboard_sync", true)
        set(value) = prefs.edit().putBoolean("clipboard_sync", value).apply()

    var notificationsEnabled: Boolean
        get() = prefs.getBoolean("notifications_enabled", true)
        set(value) = prefs.edit().putBoolean("notifications_enabled", value).apply()

    var wgImagePort: Int
        get() = prefs.getInt("wg_image_port", 8766)
        set(value) = prefs.edit().putInt("wg_image_port", value).apply()

    var ntfyTopic: String
        get() = prefs.getString("ntfy_topic", "") ?: ""
        set(value) = prefs.edit().putString("ntfy_topic", value).apply()
}
