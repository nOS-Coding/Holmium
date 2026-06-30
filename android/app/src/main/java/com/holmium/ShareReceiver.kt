package com.holmium

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class ShareReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_SEND) {
            val shareIntent = Intent(context, MainActivity::class.java).apply {
                action = Intent.ACTION_SEND
                putExtra(Intent.EXTRA_TEXT, intent.getStringExtra(Intent.EXTRA_TEXT))
                putExtra(Intent.EXTRA_HTML_TEXT, intent.getStringExtra(Intent.EXTRA_HTML_TEXT))
                if (intent.hasExtra(Intent.EXTRA_STREAM)) {
                    putExtra(Intent.EXTRA_STREAM, intent.getParcelableExtra(Intent.EXTRA_STREAM))
                }
                type = intent.type
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            context.startActivity(shareIntent)
        }
    }
}
