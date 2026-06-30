package com.holmium

import okhttp3.*
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.*

object HolmiumApiClient {

    private val clients = mutableMapOf<String, OkHttpClient>()

    fun getClient(serverIp: String, serverPort: Int, authToken: String): OkHttpClient {
        val key = "$serverIp:$serverPort"
        return clients.getOrPut(key) {
            val trustAllCerts = arrayOf(object : X509TrustManager {
                override fun checkClientTrusted(certs: Array<X509Certificate>, authType: String) {}
                override fun checkServerTrusted(certs: Array<X509Certificate>, authType: String) {}
                override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
            })

            val sslContext = SSLContext.getInstance("TLS")
            sslContext.init(null, trustAllCerts, SecureRandom())

            OkHttpClient.Builder()
                .sslSocketFactory(sslContext.socketFactory, trustAllCerts[0])
                .hostnameVerifier { _, _ -> true }
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .addInterceptor { chain ->
                    val original = chain.request()
                    val request = original.newBuilder()
                        .header("X-Holmium-Token", authToken)
                        .method(original.method, original.body)
                        .build()
                    chain.proceed(request)
                }
                .build()
        }
    }

    fun buildWebSocket(
        serverIp: String,
        serverPort: Int,
        authToken: String,
        path: String,
        listener: WebSocketListener
    ): WebSocket {
        val client = getClient(serverIp, serverPort, authToken)
        val url = "wss://$serverIp:$serverPort$path"
        val request = Request.Builder()
            .url(url)
            .header("X-Holmium-Token", authToken)
            .build()
        return client.newWebSocket(request, listener)
    }
}
