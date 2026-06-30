package com.holmium

import android.app.*
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.widget.Toast
import androidx.core.app.NotificationCompat
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import okhttp3.*
import java.net.URLDecoder
import java.util.concurrent.TimeUnit

class FcmService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var webSocket: WebSocket? = null
    private val channelId = "holmium_notifications"
    private var ntfyTopic: String = ""

    companion object {
        const val ACTION_COPY = "com.holmium.COPY_CLIPBOARD"
        const val EXTRA_COPY_TEXT = "copy_text"
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(2, buildNotification("Connecting..."))
        ntfyTopic = HolmiumPreferences(this).ntfyTopic
        connectNtfy()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Holmium Notifications",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Holmium push notifications"
                enableVibration(true)
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification {
        return NotificationCompat.Builder(this, channelId)
            .setContentTitle("Holmium")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
    }

    private fun connectNtfy() {
        if (ntfyTopic.isBlank()) return

        webSocket = HolmiumApiClient.buildWebSocket(
            "ntfy.sh", 443, "",
            "/$ntfyTopic/ws",
            object : WebSocketListener() {
                override fun onMessage(webSocket: WebSocket, text: String) {
                    handleNtfyMessage(text)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    scope.launch {
                        delay(5000)
                        connectNtfy()
                    }
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    scope.launch {
                        delay(5000)
                        connectNtfy()
                    }
                }
            }
        )
    }

    private fun handleNtfyMessage(json: String) {
        try {
            val obj = JsonParser.parseString(json).asJsonObject
            val event = obj.get("event")?.asString ?: return
            if (event != "message") return

            val title = obj.get("title")?.asString ?: "Holmium"
            val message = obj.get("message")?.asString ?: ""

            var copyText: String? = null
            val actions = obj.getAsJsonArray("actions")
            if (actions != null) {
                for (element in actions) {
                    val action = element.asJsonObject
                    if (action.get("action")?.asString == "copy") {
                        val url = action.get("url")?.asString ?: continue
                        if (url.startsWith("holmium://clipboard?text=")) {
                            copyText = URLDecoder.decode(
                                url.removePrefix("holmium://clipboard?text="), "UTF-8"
                            )
                        }
                    }
                }
            }

            val notificationId = obj.get("id")?.asString?.hashCode() ?: 0
            showNotification(notificationId, title, message, copyText)
        } catch (_: Exception) {}
    }

    private fun copyToClipboard(text: String) {
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText("Holmium", text)
        clipboard.setPrimaryClip(clip)
        Toast.makeText(this, "Copied to clipboard", Toast.LENGTH_SHORT).show()
    }

    private fun showNotification(id: Int, title: String, message: String, copyText: String? = null) {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this, id, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val prefs = HolmiumPreferences(this)
        val builder = NotificationCompat.Builder(this, channelId)
            .setContentTitle(title)
            .setContentText(message)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(if (prefs.notificationSound) NotificationCompat.PRIORITY_HIGH else NotificationCompat.PRIORITY_LOW)
            .apply {
                if (!prefs.notificationSound) {
                    setSilent(true)
                }
            }

        if (copyText != null) {
            val copyIntent = Intent(this, FcmService::class.java).apply {
                action = ACTION_COPY
                putExtra(EXTRA_COPY_TEXT, copyText)
            }
            val copyPendingIntent = PendingIntent.getService(
                this, id + 1, copyIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            builder.addAction(
                android.R.drawable.ic_menu_edit, "Copy",
                copyPendingIntent
            )
        }

        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(id, builder.build())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_COPY) {
            val text = intent.getStringExtra(EXTRA_COPY_TEXT)
            if (text != null) {
                copyToClipboard(text)
            }
            return START_NOT_STICKY
        }
        return super.onStartCommand(intent, flags, startId)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        webSocket?.close(1000, "Service stopped")
        scope.cancel()
        super.onDestroy()
    }
}
