package com.holmium

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.google.android.material.color.MaterialColors
import kotlinx.coroutines.*
import okhttp3.*
import java.util.UUID

data class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: String,
    val content: String = "",
    val isStreaming: Boolean = false
)

class ChatAdapter(private val messages: MutableList<ChatMessage>) :
    RecyclerView.Adapter<ChatAdapter.ViewHolder>() {

    companion object {
        private const val VIEW_TYPE_USER = 0
        private const val VIEW_TYPE_HOLMIUM = 1
        private const val VIEW_TYPE_TYPING = 2
    }

    inner class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val bubble: TextView = view.findViewById(R.id.bubble)
        val container: View = view.findViewById(R.id.bubbleContainer)
    }

    override fun getItemViewType(position: Int): Int {
        val msg = messages[position]
        if (msg.role == "typing") return VIEW_TYPE_TYPING
        return if (msg.role == "user") VIEW_TYPE_USER else VIEW_TYPE_HOLMIUM
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val layout = if (viewType == VIEW_TYPE_USER) {
            R.layout.item_message_user
        } else {
            R.layout.item_message_holmium
        }
        val view = LayoutInflater.from(parent.context).inflate(layout, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val msg = messages[position]
        holder.bubble.text = if (msg.isStreaming) "${msg.content}█" else msg.content
    }

    override fun getItemCount() = messages.size
}

class MainActivity : AppCompatActivity() {

    private lateinit var recyclerView: RecyclerView
    private lateinit var inputField: EditText
    private lateinit var sendButton: ImageButton
    private lateinit var voiceButton: ImageButton
    private lateinit var bottomNav: BottomNavigationView
    private lateinit var statusIndicator: TextView

    private val messages = mutableListOf<ChatMessage>()
    private lateinit var adapter: ChatAdapter
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var currentSessionId: String = UUID.randomUUID().toString()

    private var serverIp: String = "10.0.0.1"
    private var serverPort: Int = 8765
    private var authToken: String = ""
    private var isConnected = false

    override fun onCreate(savedInstanceState: Bundle?) {
        ThemeManager.apply(this)
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        recyclerView = findViewById(R.id.recyclerView)
        inputField = findViewById(R.id.inputField)
        sendButton = findViewById(R.id.sendButton)
        voiceButton = findViewById(R.id.voiceButton)
        bottomNav = findViewById(R.id.bottomNavigation)
        statusIndicator = findViewById(R.id.statusIndicator)

        adapter = ChatAdapter(messages)
        recyclerView.layoutManager = LinearLayoutManager(this)
        recyclerView.adapter = adapter

        loadSettings()
        fetchLastMessages()

        bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_chat -> true
                R.id.nav_devices -> {
                    startActivity(android.content.Intent(this, SettingsActivity::class.java))
                    true
                }
                R.id.nav_settings -> {
                    startActivity(android.content.Intent(this, SettingsActivity::class.java))
                    true
                }
                else -> false
            }
        }

        sendButton.setOnClickListener {
            val text = inputField.text.toString().trim()
            if (text.isNotEmpty()) {
                sendMessage(text)
                inputField.text.clear()
            }
        }

        voiceButton.setOnClickListener {
            startActivity(android.content.Intent(this, VoiceActivity::class.java))
        }

        handleShareIntent()
        updateConnectionStatus()
    }

    private fun updateConnectionStatus() {
        statusIndicator.text = if (isConnected) "●" else "○"
        val color = if (isConnected) {
            ContextCompat.getColor(this, com.google.android.material.R.color.material_dynamic_primary40)
        } else {
            ContextCompat.getColor(this, com.google.android.material.R.color.material_dynamic_neutral40)
        }
        statusIndicator.setTextColor(color)
    }

    private fun loadSettings() {
        val prefs = HolmiumPreferences(this)
        serverIp = prefs.serverIp
        serverPort = prefs.serverPort
        authToken = prefs.authToken
    }

    private fun handleShareIntent() {
        val intent = intent
        if (intent?.action == android.content.Intent.ACTION_SEND) {
            ShareHandler.handle(this, intent) { text ->
                inputField.setText(text)
                sendMessage(text)
            }
        }
    }

    private fun fetchLastMessages() {
        scope.launch {
            try {
                val client = HolmiumApiClient.getClient(serverIp, serverPort, authToken)
                val request = Request.Builder()
                    .url("https://$serverIp:$serverPort/memory/recent")
                    .header("X-Holmium-Token", authToken)
                    .build()
                val response = client.newCall(request).await()
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "[]"
                    val gson = com.google.gson.Gson()
                    val type = object : com.google.gson.reflect.TypeToken<List<Map<String, String>>>() {}.type
                    val recent: List<Map<String, String>> = gson.fromJson(body, type)
                    messages.clear()
                    for (m in recent) {
                        messages.add(ChatMessage(role = m["role"] ?: "user", content = m["content"] ?: ""))
                    }
                    adapter.notifyDataSetChanged()
                    recyclerView.scrollToPosition(messages.size - 1)
                }
            } catch (e: Exception) {
                messages.add(ChatMessage(role = "holmium", content = "Could not connect to server. Check settings."))
                adapter.notifyDataSetChanged()
            }
        }
    }

    private fun sendMessage(text: String) {
        messages.add(ChatMessage(role = "user", content = text))
        adapter.notifyItemInserted(messages.size - 1)
        recyclerView.scrollToPosition(messages.size - 1)

        val typingMsg = ChatMessage(role = "typing", content = "")
        messages.add(typingMsg)
        adapter.notifyItemInserted(messages.size - 1)
        recyclerView.scrollToPosition(messages.size - 1)

        scope.launch {
            try {
                val client = HolmiumApiClient.getClient(serverIp, serverPort, authToken)
                val requestBody = com.google.gson.Gson().toJson(
                    mapOf("content" to text, "session_id" to currentSessionId)
                )
                val request = Request.Builder()
                    .url("https://$serverIp:$serverPort/chat")
                    .header("X-Holmium-Token", authToken)
                    .post(requestBody.toRequestBody("application/json".toMediaType()))
                    .build()

                val response = client.newCall(request).await()
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: ""
                    removeTyping()
                    val responseMsg = ChatMessage(role = "holmium", content = body)
                    messages.add(responseMsg)
                    adapter.notifyItemInserted(messages.size - 1)
                    recyclerView.scrollToPosition(messages.size - 1)
                } else {
                    removeTyping()
                    messages.add(ChatMessage(role = "holmium", content = "Error: ${response.code}"))
                    adapter.notifyItemInserted(messages.size - 1)
                    recyclerView.scrollToPosition(messages.size - 1)
                }
            } catch (e: Exception) {
                removeTyping()
                messages.add(ChatMessage(role = "holmium", content = "Connection failed: ${e.message}"))
                adapter.notifyItemInserted(messages.size - 1)
                recyclerView.scrollToPosition(messages.size - 1)
            }
        }
    }

    private fun removeTyping() {
        val idx = messages.indexOfLast { it.role == "typing" }
        if (idx >= 0) {
            messages.removeAt(idx)
            adapter.notifyItemRemoved(idx)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }
}
