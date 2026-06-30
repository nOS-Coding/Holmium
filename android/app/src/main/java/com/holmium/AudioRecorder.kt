package com.holmium

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.*
import java.io.*

class AudioRecorder {

    private var audioRecord: AudioRecord? = null
    private var isRecording = false
    private val sampleRate = 16000
    private var recordingJob: Job? = null

    fun startRecording(outputPath: String) {
        if (isRecording) return

        val bufferSize = AudioRecord.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )

        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize
        )

        if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
            audioRecord?.release()
            audioRecord = null
            return
        }

        audioRecord?.startRecording()
        isRecording = true

        recordingJob = CoroutineScope(Dispatchers.IO).launch {
            val pcmData = ByteArray(bufferSize)
            val pcmFile = File.createTempFile("recording", ".pcm")
            val outputStream = FileOutputStream(pcmFile)

            while (isRecording && audioRecord != null) {
                val bytesRead = audioRecord?.read(pcmData, 0, bufferSize) ?: 0
                if (bytesRead > 0) {
                    outputStream.write(pcmData, 0, bytesRead)
                }
            }

            outputStream.close()
            audioRecord?.stop()
            audioRecord?.release()
            audioRecord = null

            writeWav(pcmFile, outputPath)
            pcmFile.delete()
        }
    }

    fun stopRecording() {
        isRecording = false
        recordingJob?.cancel()
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
    }

    private fun writeWav(pcmFile: File, wavPath: String) {
        val pcmData = pcmFile.readBytes()
        val totalDataLen = pcmData.size + 36
        val sampleRate = 16000
        val channels = 1
        val bitsPerSample = 16
        val byteRate = sampleRate * channels * bitsPerSample / 8
        val blockAlign = channels * bitsPerSample / 8

        val dos = DataOutputStream(FileOutputStream(wavPath))
        dos.writeBytes("RIFF")
        dos.writeInt(Integer.reverseBytes(totalDataLen))
        dos.writeBytes("WAVE")
        dos.writeBytes("fmt ")
        dos.writeInt(Integer.reverseBytes(16))
        dos.writeShort(Integer.reverseBytes(1))
        dos.writeShort(Integer.reverseBytes(channels))
        dos.writeInt(Integer.reverseBytes(sampleRate))
        dos.writeInt(Integer.reverseBytes(byteRate))
        dos.writeShort(Integer.reverseBytes(blockAlign))
        dos.writeShort(Integer.reverseBytes(bitsPerSample))
        dos.writeBytes("data")
        dos.writeInt(Integer.reverseBytes(pcmData.size))
        dos.write(pcmData)
        dos.close()
    }
}
