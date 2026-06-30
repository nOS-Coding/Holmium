package com.holmium

import android.os.Bundle
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import kotlinx.coroutines.*

class SettingsActivity : AppCompatActivity() {

    private lateinit var serverIpInput: EditText
    private lateinit var serverPortInput: EditText
    private lateinit var authTokenInput: EditText
    private lateinit var ttsToggle: Switch
    private lateinit var clipboardSyncToggle: Switch
    private lateinit var notificationToggle: Switch
    private lateinit var themeSpinner: Spinner
    private lateinit var testConnectionButton: Button
    private lateinit var statusText: TextView
    private lateinit var aboutText: TextView

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    override fun onCreate(savedInstanceState: Bundle?) {
        ThemeManager.apply(this)
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        serverIpInput = findViewById(R.id.serverIpInput)
        serverPortInput = findViewById(R.id.serverPortInput)
        authTokenInput = findViewById(R.id.authTokenInput)
        ttsToggle = findViewById(R.id.ttsToggle)
        clipboardSyncToggle = findViewById(R.id.clipboardSyncToggle)
        notificationToggle = findViewById(R.id.notificationToggle)
        themeSpinner = findViewById(R.id.themeSpinner)
        testConnectionButton = findViewById(R.id.testConnectionButton)
        statusText = findViewById(R.id.statusText)
        aboutText = findViewById(R.id.aboutText)

        aboutText.text = "Holmium v1.0.0\nPersonal AI OS Client"

        loadSettings()

        testConnectionButton.setOnClickListener { testConnection() }

        themeSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(p: AdapterView<*>?, v: View?, pos: Int, id: Long) {
                val theme = when (pos) {
                    0 -> "dark"
                    1 -> "light"
                    2 -> "system"
                    else -> "dark"
                }
                HolmiumPreferences(this@SettingsActivity).theme = theme
                ThemeManager.setTheme(theme)
                ThemeManager.apply(this@SettingsActivity)
            }
            override fun onNothingSelected(p: AdapterView<*>?) {}
        }
    }

    private fun loadSettings() {
        val prefs = HolmiumPreferences(this)
        serverIpInput.setText(prefs.serverIp)
        serverPortInput.setText(prefs.serverPort.toString())
        authTokenInput.setText(prefs.authToken)
        ttsToggle.isChecked = prefs.ttsEnabled
        clipboardSyncToggle.isChecked = prefs.clipboardSync
        notificationToggle.isChecked = prefs.notificationsEnabled

        val themeIdx = when (prefs.theme) {
            "light" -> 1
            "system" -> 2
            else -> 0
        }
        themeSpinner.setSelection(themeIdx)
    }

    private fun saveSettings() {
        val prefs = HolmiumPreferences(this)
        prefs.serverIp = serverIpInput.text.toString().ifEmpty { "holmium.local" }
        prefs.serverPort = serverPortInput.text.toString().toIntOrNull() ?: 443
        prefs.authToken = authTokenInput.text.toString()
        prefs.ttsEnabled = ttsToggle.isChecked
        prefs.clipboardSync = clipboardSyncToggle.isChecked
        prefs.notificationsEnabled = notificationToggle.isChecked
    }

    private fun testConnection() {
        saveSettings()
        statusText.text = "Testing..."
        scope.launch {
            try {
                val ip = serverIpInput.text.toString().ifEmpty { "holmium.local" }
                val port = serverPortInput.text.toString().toIntOrNull() ?: 443
                val token = authTokenInput.text.toString()
                val client = HolmiumApiClient.getClient(ip, port, token)
                val request = okhttp3.Request.Builder()
                    .url("https://$ip:$port/status")
                    .header("X-Holmium-Token", token)
                    .build()
                val response = client.newCall(request).await()
                if (response.isSuccessful) {
                    statusText.text = "Connected! Server OK."
                } else {
                    statusText.text = "Failed: HTTP ${response.code}"
                }
            } catch (e: Exception) {
                statusText.text = "Error: ${e.message}"
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        saveSettings()
        scope.cancel()
    }
}
