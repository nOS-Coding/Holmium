package com.holmium

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.*
import okhttp3.*

data class Fact(val key: String, val value: String)

class FactAdapter(private val facts: MutableList<Fact>) :
    RecyclerView.Adapter<FactAdapter.ViewHolder>() {

    inner class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val keyText: TextView = view.findViewById(R.id.factKey)
        val valueText: TextView = view.findViewById(R.id.factValue)
        val deleteButton: Button = view.findViewById(R.id.deleteFactButton)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_fact, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val fact = facts[position]
        holder.keyText.text = fact.key
        holder.valueText.text = fact.value

        holder.valueText.setOnClickListener {
            val editText = EditText(holder.itemView.context)
            editText.setText(fact.value)
            android.app.AlertDialog.Builder(holder.itemView.context)
                .setTitle(fact.key)
                .setView(editText)
                .setPositiveButton("Save") { _, _ ->
                    val newValue = editText.text.toString()
                    updateFact(fact.key, newValue)
                }
                .setNegativeButton("Cancel", null)
                .show()
        }

        holder.deleteButton.setOnClickListener {
            deleteFact(fact.key)
        }
    }

    override fun getItemCount() = facts.size

    private fun updateFact(key: String, value: String) {
        val idx = facts.indexOfFirst { it.key == key }
        if (idx >= 0) {
            facts[idx] = facts[idx].copy(value = value)
            notifyItemChanged(idx)
        }
    }

    private fun deleteFact(key: String) {
        val idx = facts.indexOfFirst { it.key == key }
        if (idx >= 0) {
            facts.removeAt(idx)
            notifyItemRemoved(idx)
        }
    }
}

class MemoryFragment : Fragment() {

    private lateinit var searchInput: EditText
    private lateinit var searchButton: Button
    private lateinit var recyclerView: RecyclerView
    private lateinit var adapter: FactAdapter
    private val facts = mutableListOf<Fact>()
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    private var serverIp: String = "10.0.0.1"
    private var serverPort: Int = 8765
    private var authToken: String = ""

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        val view = inflater.inflate(R.layout.fragment_memory, container, false)
        searchInput = view.findViewById(R.id.searchInput)
        searchButton = view.findViewById(R.id.searchButton)
        recyclerView = view.findViewById(R.id.factRecyclerView)

        adapter = FactAdapter(facts)
        recyclerView.layoutManager = LinearLayoutManager(context)
        recyclerView.adapter = adapter

        val prefs = HolmiumPreferences(requireContext())
        serverIp = prefs.serverIp
        serverPort = prefs.serverPort
        authToken = prefs.authToken

        loadFacts()

        searchButton.setOnClickListener {
            val query = searchInput.text.toString().trim()
            if (query.isNotEmpty()) searchFacts(query) else loadFacts()
        }

        return view
    }

    private fun loadFacts() {
        scope.launch {
            try {
                val client = HolmiumApiClient.getClient(serverIp, serverPort, authToken)
                val request = Request.Builder()
                    .url("https://$serverIp:$serverPort/memory/list")
                    .header("X-Holmium-Token", authToken)
                    .build()
                val response = client.newCall(request).await()
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "[]"
                    val type = object : com.google.gson.reflect.TypeToken<List<Map<String, String>>>() {}.type
                    val list: List<Map<String, String>> = com.google.gson.Gson().fromJson(body, type)
                    facts.clear()
                    for (m in list) {
                        facts.add(Fact(m["key"] ?: "", m["value"] ?: ""))
                    }
                    adapter.notifyDataSetChanged()
                }
            } catch (_: Exception) {}
        }
    }

    private fun searchFacts(query: String) {
        scope.launch {
            try {
                val client = HolmiumApiClient.getClient(serverIp, serverPort, authToken)
                val request = Request.Builder()
                    .url("https://$serverIp:$serverPort/memory/search?q=${java.net.URLEncoder.encode(query, "UTF-8")}")
                    .header("X-Holmium-Token", authToken)
                    .build()
                val response = client.newCall(request).await()
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "[]"
                    val type = object : com.google.gson.reflect.TypeToken<List<Map<String, String>>>() {}.type
                    val list: List<Map<String, String>> = com.google.gson.Gson().fromJson(body, type)
                    facts.clear()
                    for (m in list) {
                        facts.add(Fact(m["key"] ?: "", m["value"] ?: ""))
                    }
                    adapter.notifyDataSetChanged()
                }
            } catch (_: Exception) {}
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }
}
