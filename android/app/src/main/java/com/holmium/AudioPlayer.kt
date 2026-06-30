package com.holmium

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import kotlinx.coroutines.*
import java.util.concurrent.ConcurrentLinkedQueue

class AudioPlayer {

    private val sampleRate = 24000
    private var audioTrack: AudioTrack? = null
    private var isPlaying = false
    private var playJob: Job? = null
    private val chunkQueue = ConcurrentLinkedQueue<ByteArray>()

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    init {
        val bufferSize = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )

        audioTrack = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(bufferSize * 2)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
    }

    fun queueChunk(pcmData: ByteArray) {
        chunkQueue.add(pcmData)
        if (!isPlaying) {
            startPlayback()
        }
    }

    private fun startPlayback() {
        isPlaying = true
        audioTrack?.play()

        playJob = scope.launch {
            while (isPlaying) {
                val chunk = chunkQueue.poll() ?: break
                audioTrack?.write(chunk, 0, chunk.size)
            }
            isPlaying = false
        }
    }

    fun stop() {
        isPlaying = false
        playJob?.cancel()
        chunkQueue.clear()
        try {
            audioTrack?.stop()
            audioTrack?.flush()
        } catch (_: Exception) {}
    }

    fun release() {
        stop()
        audioTrack?.release()
        audioTrack = null
    }
}
