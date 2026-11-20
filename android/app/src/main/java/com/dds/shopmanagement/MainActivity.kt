package com.dds.shopmanagement

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.databaseEnabled = true
            settings.allowFileAccess = true
            webViewClient = WebViewClient()
            webChromeClient = WebChromeClient()
        }
        setContentView(webView)

        // Show clean startup message while embedded Python boots
        webView.loadData(
            """
            <html><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f8fafc;color:#0f172a;">
              <div style="text-align:center;">
                <h2>Mon Commerce</h2>
                <p>Démarrage du serveur local... / جاري تشغيل النظام...</p>
              </div>
            </body></html>
            """.trimIndent(),
            "text/html",
            "UTF-8"
        )

        val dataPath = filesDir.absolutePath

        thread {
            if (!Python.isStarted()) {
                Python.start(AndroidPlatform(this))
            }
            val py = Python.getInstance()
            val osModule = py.getModule("os")
            osModule["environ"]?.callAttr("__setitem__", "SHOP_DATA_DIR", dataPath)

            // Start Uvicorn in background thread
            thread {
                val uvicorn = py.getModule("uvicorn")
                uvicorn.callAttr("run", "app.main:app", "127.0.0.1", 8765)
            }

            // Wait until FastAPI /api/v1/health responds, then load the app
            for (i in 1..60) {
                try {
                    val conn = URL("http://127.0.0.1:8765/api/v1/health").openConnection() as HttpURLConnection
                    conn.connectTimeout = 500
                    conn.readTimeout = 500
                    if (conn.responseCode == 200) {
                        runOnUiThread {
                            webView.loadUrl("http://127.0.0.1:8765/")
                        }
                        break
                    }
                } catch (_: Exception) {
                    Thread.sleep(500)
                }
            }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
