package com.holmium

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import java.io.File

class VoiceActivity : AppCompatActivity() {

    private lateinit var recordButton: Button
    private lateinit var statusText: TextView
    private lateinit var transcriptText: TextView

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var audioRecorder: AudioRecorder? = null
    private var audioPlayer: AudioPlayer? = null
    private var voiceSession: VoiceSession? = null

    private var serverIp: String = "10.0.0.1"
    private var serverPort: Int = 8765
    private var authToken: String = ""

    private var isRecording = false

    override fun onCreate(savedInstanceState: Bundle?) {
        ThemeManager.apply(this)
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_voice)

        recordButton = findViewById(R.id.recordButton)
        statusText = findViewById(R.id.statusText)
        transcriptText = findViewById(R.id.transcriptText)

        val prefs = HolmiumPreferences(this)
        serverIp = prefs.serverIp
        serverPort = prefs.serverPort
        authToken = prefs.authToken

        checkPermissions()

        recordButton.setOnClickListener {
            if (!isRecording) {
                startRecording()
            } else {
                stopRecording()
            }
        }
    }

    private fun checkPermissions() {
        val needed = mutableListOf<String>()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            needed.add(Manifest.permission.RECORD_AUDIO)
        }
        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), 100)
        }
    }

    private fun startRecording() {
        audioRecorder = AudioRecorder()
        audioPlayer = AudioPlayer()
        voiceSession = VoiceSession(serverIp, serverPort, authToken)

        val file = File(cacheDir, "voice_input.wav")
        audioRecorder?.startRecording(file.absolutePath)
        isRecording = true
        recordButton.text = "Stop"
        statusText.text = "Recording..."
        transcriptText.text = ""
    }

    private fun stopRecording() {
        audioRecorder?.stopRecording()
        isRecording = false
        recordButton.text = "Record"
        statusText.text = "Transcribing..."

        val file = File(cacheDir, "voice_input.wav")
        scope.launch {
            try {
                val transcript = voiceSession?.processAudio(file.absolutePath) ?: ""
                transcriptText.text = transcript
                statusText.text = "Done"
            } catch (e: Exception) {
                statusText.text = "Error: ${e.message}"
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
        audioRecorder?.stopRecording()
        audioPlayer?.stop()
    }
}
