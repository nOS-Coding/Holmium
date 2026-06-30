package com.holmium

import kotlinx.coroutines.*
import okhttp3.*
import java.io.File
import java.util.UUID

class VoiceSession(
    private val serverIp: String,
    private val serverPort: Int,
    private val authToken: String
) {
    private val client = HolmiumApiClient.getClient(serverIp, serverPort, authToken)
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var sessionId: String = UUID.randomUUID().toString()
    private val audioPlayer = AudioPlayer()

    suspend fun processAudio(audioPath: String): String {
        val transcript = stt(audioPath)
        val response = chat(transcript)
        tts(response)
        return transcript
    }

    private suspend fun stt(audioPath: String): String {
        val file = File(audioPath)
        val requestBody = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("audio", file.name, file.asRequestBody("audio/wav".toMediaType()))
            .build()

        val request = Request.Builder()
            .url("https://$serverIp:$serverPort/stt")
            .header("X-Holmium-Token", authToken)
            .post(requestBody)
            .build()

        val response = client.newCall(request).await()
        val body = response.body?.string() ?: "{}"
        val json = com.google.gson.JsonParser.parseString(body).asJsonObject
        return json.get("transcript")?.asString ?: ""
    }

    private suspend fun chat(message: String): String {
        val requestBody = com.google.gson.Gson().toJson(
            mapOf("content" to message, "session_id" to sessionId)
        )

        val request = Request.Builder()
            .url("https://$serverIp:$serverPort/chat")
            .header("X-Holmium-Token", authToken)
            .post(requestBody.toRequestBody("application/json".toMediaType()))
            .build()

        val response = client.newCall(request).await()
        return response.body?.string() ?: ""
    }

    private fun tts(text: String) {
        scope.launch {
            try {
                val sentences = text.split(Regex("(?<=[.!?])\\s+"))
                for (sentence in sentences) {
                    if (sentence.isBlank()) continue
                    val requestBody = com.google.gson.Gson().toJson(mapOf("text" to sentence))
                    val request = Request.Builder()
                        .url("https://$serverIp:$serverPort/tts")
                        .header("X-Holmium-Token", authToken)
                        .post(requestBody.toRequestBody("application/json".toMediaType()))
                        .build()
                    val response = client.newCall(request).await()
                    if (response.isSuccessful) {
                        val pcmData = response.body?.bytes()
                        if (pcmData != null) {
                            audioPlayer.queueChunk(pcmData)
                        }
                    }
                }
            } catch (_: Exception) {}
        }
    }

    fun release() {
        audioPlayer.release()
        scope.cancel()
    }
}
