package com.holmium

import android.content.Intent
import android.net.Uri
import androidx.appcompat.app.AppCompatActivity

object ShareHandler {

    fun handle(activity: AppCompatActivity, intent: Intent, onText: (String) -> Unit) {
        when (intent.action) {
            Intent.ACTION_SEND -> {
                when (intent.type) {
                    "text/plain", "text/html" -> {
                        val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return
                        val sourceApp = getSourceApp(intent)
                        val formatted = "Shared from $sourceApp: $text"
                        onText(formatted)
                    }
                    "image/*" -> {
                        val imageUri = intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
                        if (imageUri != null) {
                            val sourceApp = getSourceApp(intent)
                            uploadAndSend(activity, imageUri, sourceApp)
                        }
                    }
                }
            }
        }
    }

    private fun getSourceApp(intent: Intent): String {
        val source = intent.getStringExtra(Intent.EXTRA_REFERRER_NAME)
            ?: intent.`package`
            ?: "unknown app"
        return source.substringAfterLast(".").replace("com.", "").ifEmpty { "unknown" }
    }

    private fun uploadAndSend(activity: AppCompatActivity, imageUri: Uri, sourceApp: String) {
        val prefs = HolmiumPreferences(activity)
        val ip = prefs.serverIp
        val port = prefs.serverPort
        val token = prefs.authToken

        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            try {
                val inputStream = activity.contentResolver.openInputStream(imageUri)
                val bytes = inputStream?.readBytes() ?: return@launch
                inputStream.close()

                val requestBody = okhttp3.MultipartBody.Builder()
                    .setType(okhttp3.MultipartBody.FORM)
                    .addFormDataPart("file", "share_image", bytes.toRequestBody("image/*".toMediaType()))
                    .build()

                val client = HolmiumApiClient.getClient(ip, port, token)
                val request = okhttp3.Request.Builder()
                    .url("https://$ip:$port/upload/file")
                    .header("X-Holmium-Token", token)
                    .post(requestBody)
                    .build()

                client.newCall(request).execute()
            } catch (_: Exception) {}
        }
    }
}

internal fun ByteArray.toRequestBody(contentType: okhttp3.MediaType?): okhttp3.RequestBody {
    return okhttp3.RequestBody.create(contentType, this)
}
