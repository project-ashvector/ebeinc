package online.ebeinc.talkietalkie;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

/**
 * v0.2.1 lifecycle handoff shell.
 *
 * The visible Activity still owns the proven full PTT connection. When the UI
 * is no longer visible, it explicitly releases WebRTC/microphone resources and
 * tells TalkieListeningService to take over receive-only listening.
 */
public class PersistentMainActivity extends EnhancedMainActivity {
    private static final String PREFS = "ebe_talkie_talkie";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private SharedPreferences prefs;
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        webView = findWebView(getWindow().getDecorView());
        if (webView != null) {
            webView.addJavascriptInterface(new PersistentBridge(), "EBEPersistent");
        }
    }

    @Override
    protected void onStart() {
        super.onStart();
        if (prefs == null) return;

        prefs.edit().putBoolean("ui_visible", true).apply();
        if (prefs.getBoolean("auto_connect", false)) {
            sendServiceAction(TalkieListeningService.ACTION_ACTIVITY_FOREGROUND);
            handler.postDelayed(() -> evaluate(
                    "window.ebeResumeFromBackground && window.ebeResumeFromBackground();"
            ), 650L);
        }
    }

    @Override
    protected void onStop() {
        if (prefs != null && !isChangingConfigurations()) {
            boolean shouldStay = prefs.getBoolean("auto_connect", false);
            prefs.edit().putBoolean("ui_visible", false).apply();

            if (shouldStay) {
                evaluate("window.ebeSuspendForBackground && window.ebeSuspendForBackground();");
                sendServiceAction(TalkieListeningService.ACTION_ACTIVITY_BACKGROUND);
            }
        }
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (webView != null) {
            try { webView.removeJavascriptInterface("EBEPersistent"); } catch (Exception ignored) {}
        }
        super.onDestroy();
    }

    private void sendServiceAction(String action) {
        Intent intent = new Intent(this, TalkieListeningService.class).setAction(action);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent);
            } else {
                startService(intent);
            }
        } catch (Exception ignored) {
        }
    }

    private void evaluate(String script) {
        if (webView == null) return;
        runOnUiThread(() -> {
            try { webView.evaluateJavascript(script, null); } catch (Exception ignored) {}
        });
    }

    private WebView findWebView(View view) {
        if (view instanceof WebView) return (WebView) view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                WebView found = findWebView(group.getChildAt(i));
                if (found != null) return found;
            }
        }
        return null;
    }

    public final class PersistentBridge {
        @JavascriptInterface
        public boolean isAlwaysOnReliabilityEnabled() {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            return pm != null && pm.isIgnoringBatteryOptimizations(getPackageName());
        }

        @JavascriptInterface
        public void requestAlwaysOnReliability() {
            runOnUiThread(() -> {
                try {
                    PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
                    if (pm != null && pm.isIgnoringBatteryOptimizations(getPackageName())) return;
                    Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                    intent.setData(Uri.parse("package:" + getPackageName()));
                    startActivity(intent);
                } catch (Exception directFailed) {
                    try {
                        Intent fallback = new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS);
                        startActivity(fallback);
                    } catch (Exception ignored) {
                    }
                }
            });
        }

        @JavascriptInterface
        public boolean isRoomPersistenceArmed() {
            return prefs != null && prefs.getBoolean("auto_connect", false);
        }
    }
}
