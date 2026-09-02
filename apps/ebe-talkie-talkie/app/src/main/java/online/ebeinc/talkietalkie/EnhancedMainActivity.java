package online.ebeinc.talkietalkie;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * v0.2.0 social shell layered over the proven MainActivity PTT/WebRTC core.
 * Accounts, friends, synced rooms, PIN gates and profile images live in the
 * Cloudflare social API while MainActivity remains authoritative for audio.
 */
public class EnhancedMainActivity extends MainActivity {
    private static final String PREFS = "ebe_talkie_talkie";
    private static final String AUTH_TOKEN = "social_auth_token";
    private static final String ALERT_CHANNEL_ID = "ebe_talkie_talk_alerts";
    private static final int ALERT_NOTIFICATION_ID = 1410;
    private static final int PICK_AVATAR_REQUEST = 2020;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService avatarExecutor = Executors.newSingleThreadExecutor();

    private SharedPreferences prefs;
    private AudioManager audioManager;
    private NotificationManager notificationManager;
    private WebView webView;
    private boolean activityVisible;
    private String lastAlertTalker = "";
    private long lastAlertAt;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        audioManager = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
        notificationManager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        createTalkAlertChannel();

        webView = findWebView(getWindow().getDecorView());
        if (webView != null) {
            webView.addJavascriptInterface(new ExtrasBridge(), "EBEExtras");
            webView.addJavascriptInterface(new SocialBridge(), "EBESocial");
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false);
                webView.getSettings().setOffscreenPreRaster(true);
            }
            webView.setWebViewClient(new WebViewClient() {
                @Override
                public void onPageFinished(WebView view, String url) {
                    super.onPageFinished(view, url);
                    injectSocialUi();
                }
            });
            mainHandler.postDelayed(this::injectSocialUi, 900L);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        activityVisible = true;
        if (notificationManager != null) notificationManager.cancel(ALERT_NOTIFICATION_ID);
    }

    @Override
    protected void onPause() {
        activityVisible = false;
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            try { webView.removeJavascriptInterface("EBEExtras"); } catch (Exception ignored) {}
            try { webView.removeJavascriptInterface("EBESocial"); } catch (Exception ignored) {}
        }
        avatarExecutor.shutdownNow();
        mainHandler.removeCallbacksAndMessages(null);
        super.onDestroy();
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

    private void injectSocialUi() {
        if (webView == null) return;
        try {
            String script = readAsset("social-v020.js");
            if (!script.isEmpty()) webView.evaluateJavascript(script, null);
        } catch (Exception ignored) {
        }
    }

    private String readAsset(String name) {
        try (InputStream in = getAssets().open(name);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
            return out.toString(StandardCharsets.UTF_8.name());
        } catch (Exception ignored) {
            return "";
        }
    }

    private void createTalkAlertChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || notificationManager == null) return;
        NotificationChannel channel = new NotificationChannel(
                ALERT_CHANNEL_ID,
                "Talk alerts",
                NotificationManager.IMPORTANCE_HIGH
        );
        channel.setDescription("Heads-up alert when someone speaks while Talkie Talkie is behind another app or call.");
        channel.setShowBadge(false);
        channel.enableVibration(true);
        channel.setVibrationPattern(new long[]{0, 90, 70, 130});
        channel.setSound(null, null);
        notificationManager.createNotificationChannel(channel);
    }

    private boolean communicationAudioBusy() {
        if (audioManager == null) return false;
        int mode = audioManager.getMode();
        return mode == AudioManager.MODE_IN_COMMUNICATION ||
                mode == AudioManager.MODE_IN_CALL ||
                (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && mode == AudioManager.MODE_CALL_SCREENING);
    }

    private void showTalkAlert(String rawName) {
        String name = rawName == null ? "Someone" : rawName.trim();
        if (name.isEmpty()) name = "Someone";
        if (name.length() > 32) name = name.substring(0, 32);
        String me = prefs.getString("name", "");
        if (me != null && !me.trim().isEmpty() && name.equalsIgnoreCase(me.trim())) return;
        if (activityVisible && !communicationAudioBusy()) return;

        long now = System.currentTimeMillis();
        if (name.equalsIgnoreCase(lastAlertTalker) && now - lastAlertAt < 2200L) return;
        lastAlertTalker = name;
        lastAlertAt = now;
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) return;
        if (notificationManager == null) return;

        Intent openIntent = new Intent(this, EnhancedMainActivity.class);
        openIntent.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent openPending = PendingIntent.getActivity(
                this, 1410, openIntent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, ALERT_CHANNEL_ID)
                : new Notification.Builder(this);
        builder.setSmallIcon(R.drawable.ic_stat_talkie)
                .setContentTitle(name + " is talking")
                .setContentText("EBE Talkie Talkie · tap to open the room")
                .setContentIntent(openPending)
                .setAutoCancel(true)
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setOnlyAlertOnce(false)
                .setTimeoutAfter(6500L);
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            builder.setPriority(Notification.PRIORITY_HIGH).setDefaults(Notification.DEFAULT_VIBRATE);
        }
        notificationManager.notify(ALERT_NOTIFICATION_ID, builder.build());
    }

    private void launchAvatarPicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");
        startActivityForResult(intent, PICK_AVATAR_REQUEST);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != PICK_AVATAR_REQUEST || resultCode != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        avatarExecutor.execute(() -> {
            try {
                String dataUrl = makeAvatarDataUrl(uri);
                mainHandler.post(() -> sendAvatarResult(dataUrl, null));
            } catch (Exception error) {
                mainHandler.post(() -> sendAvatarResult(null, "Could not load that picture."));
            }
        });
    }

    private String makeAvatarDataUrl(Uri uri) throws Exception {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            BitmapFactory.decodeStream(in, null, bounds);
        }
        int sample = 1;
        int max = Math.max(bounds.outWidth, bounds.outHeight);
        while (max / sample > 1024) sample *= 2;

        BitmapFactory.Options decode = new BitmapFactory.Options();
        decode.inSampleSize = Math.max(1, sample);
        Bitmap source;
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            source = BitmapFactory.decodeStream(in, null, decode);
        }
        if (source == null) throw new IllegalArgumentException("Unsupported image");
        int side = Math.min(source.getWidth(), source.getHeight());
        int x = (source.getWidth() - side) / 2;
        int y = (source.getHeight() - side) / 2;
        Bitmap square = Bitmap.createBitmap(source, x, y, side, side);
        Bitmap scaled = Bitmap.createScaledBitmap(square, 256, 256, true);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        scaled.compress(Bitmap.CompressFormat.JPEG, 82, out);
        if (out.size() > 135_000) {
            out.reset();
            scaled.compress(Bitmap.CompressFormat.JPEG, 68, out);
        }
        if (scaled != square) scaled.recycle();
        if (square != source) square.recycle();
        source.recycle();
        return "data:image/jpeg;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP);
    }

    private void sendAvatarResult(String dataUrl, String error) {
        if (webView == null) return;
        if (dataUrl != null) {
            webView.evaluateJavascript("window.ebeSocialAvatarSelected && window.ebeSocialAvatarSelected(" + JSONObject.quote(dataUrl) + ");", null);
        } else {
            webView.evaluateJavascript("window.ebeSocialAvatarError && window.ebeSocialAvatarError(" + JSONObject.quote(error == null ? "Avatar error" : error) + ");", null);
        }
    }

    public final class ExtrasBridge {
        @JavascriptInterface
        public void notifyTalker(String name) {
            mainHandler.post(() -> showTalkAlert(name));
        }

        @JavascriptInterface
        public boolean isCommunicationAudioBusy() {
            return communicationAudioBusy();
        }
    }

    public final class SocialBridge {
        @JavascriptInterface
        public String getApiBaseUrl() {
            return BuildConfig.TALKIE_API_URL;
        }

        @JavascriptInterface
        public String getAuthToken() {
            return prefs.getString(AUTH_TOKEN, "");
        }

        @JavascriptInterface
        public void saveAuthToken(String token) {
            prefs.edit().putString(AUTH_TOKEN, token == null ? "" : token.trim()).apply();
        }

        @JavascriptInterface
        public void clearAuthToken() {
            prefs.edit().remove(AUTH_TOKEN).apply();
        }

        @JavascriptInterface
        public void setAccountUsername(String username) {
            String safe = username == null ? "" : username.trim();
            if (safe.length() > 32) safe = safe.substring(0, 32);
            prefs.edit().putString("name", safe).apply();
        }

        @JavascriptInterface
        public void pickAvatar() {
            mainHandler.post(EnhancedMainActivity.this::launchAvatarPicker);
        }
    }
}
