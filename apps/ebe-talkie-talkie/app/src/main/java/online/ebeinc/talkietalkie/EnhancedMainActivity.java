package online.ebeinc.talkietalkie;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.AudioManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Locale;

/**
 * v0.1.4 shell layered over the proven radio core.
 *
 * MainActivity remains responsible for microphone/WebRTC/MQTT behavior.
 * This activity adds persistent named rooms, call-aware talk alerts, and the
 * saved-room presence UI while keeping the known-good audio path isolated.
 */
public class EnhancedMainActivity extends MainActivity {
    private static final String PREFS = "ebe_talkie_talkie";
    private static final String SAVED_ROOMS = "saved_rooms_json";
    private static final String ALERT_CHANNEL_ID = "ebe_talkie_talk_alerts";
    private static final int ALERT_NOTIFICATION_ID = 1410;
    private static final String ROOM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final SecureRandom secureRandom = new SecureRandom();

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
        seedFamilyRoomIfNeeded();

        webView = findWebView(getWindow().getDecorView());
        if (webView != null) {
            webView.addJavascriptInterface(new ExtrasBridge(), "EBEExtras");
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false);
                webView.getSettings().setOffscreenPreRaster(true);
            }

            webView.setWebViewClient(new WebViewClient() {
                @Override
                public void onPageFinished(WebView view, String url) {
                    super.onPageFinished(view, url);
                    injectEnhancements();
                }
            });

            mainHandler.postDelayed(this::injectEnhancements, 900L);
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
        }
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

    private void injectEnhancements() {
        if (webView == null) return;
        try {
            String script = readAsset("enhancements-v014.js");
            if (script != null && !script.isEmpty()) {
                webView.evaluateJavascript(script, null);
            }
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

    private void seedFamilyRoomIfNeeded() {
        String raw = prefs.getString(SAVED_ROOMS, "");
        if (raw != null && !raw.trim().isEmpty() && !"[]".equals(raw.trim())) return;

        String current = prefs.getString("room", "EBE-9WEN-F9H9-8EP3");
        try {
            JSONArray rooms = new JSONArray();
            JSONObject room = new JSONObject();
            room.put("name", "Family");
            room.put("code", current);
            rooms.put(room);
            prefs.edit().putString(SAVED_ROOMS, rooms.toString()).apply();
        } catch (Exception ignored) {
        }
    }

    private String sanitizeRoomName(String name) {
        if (name == null) return "";
        String safe = name.trim().replaceAll("[\\r\\n\\t]", " ");
        if (safe.length() > 32) safe = safe.substring(0, 32);
        return safe;
    }

    private String sanitizeRoomCode(String code) {
        if (code == null) return "";
        String safe = code.trim().toUpperCase(Locale.US).replaceAll("[^A-Z0-9_-]", "");
        if (safe.length() > 64) safe = safe.substring(0, 64);
        return safe;
    }

    private String generateRoomCode() {
        StringBuilder code = new StringBuilder("EBE");
        for (int group = 0; group < 3; group++) {
            code.append('-');
            for (int i = 0; i < 4; i++) {
                code.append(ROOM_ALPHABET.charAt(secureRandom.nextInt(ROOM_ALPHABET.length())));
            }
        }
        return code.toString();
    }

    private synchronized JSONArray loadRooms() {
        String raw = prefs.getString(SAVED_ROOMS, "[]");
        try {
            return new JSONArray(raw == null ? "[]" : raw);
        } catch (Exception ignored) {
            return new JSONArray();
        }
    }

    private synchronized void storeRooms(JSONArray rooms) {
        prefs.edit().putString(SAVED_ROOMS, rooms.toString()).apply();
    }

    private synchronized boolean saveNamedRoomInternal(String name, String code) {
        String safeName = sanitizeRoomName(name);
        String safeCode = sanitizeRoomCode(code);
        if (safeName.isEmpty() || safeCode.length() < 8) return false;

        JSONArray rooms = loadRooms();
        JSONArray updated = new JSONArray();
        boolean replaced = false;

        for (int i = 0; i < rooms.length(); i++) {
            JSONObject existing = rooms.optJSONObject(i);
            if (existing == null) continue;
            String existingCode = sanitizeRoomCode(existing.optString("code", ""));
            if (safeCode.equals(existingCode)) {
                JSONObject replacement = new JSONObject();
                try {
                    replacement.put("name", safeName);
                    replacement.put("code", safeCode);
                    updated.put(replacement);
                } catch (Exception ignored) {}
                replaced = true;
            } else {
                updated.put(existing);
            }
        }

        if (!replaced) {
            JSONObject room = new JSONObject();
            try {
                room.put("name", safeName);
                room.put("code", safeCode);
                updated.put(room);
            } catch (Exception ignored) {
                return false;
            }
        }

        storeRooms(updated);
        return true;
    }

    private synchronized boolean deleteNamedRoomInternal(String code) {
        String safeCode = sanitizeRoomCode(code);
        if (safeCode.isEmpty()) return false;

        JSONArray rooms = loadRooms();
        JSONArray updated = new JSONArray();
        boolean removed = false;
        for (int i = 0; i < rooms.length(); i++) {
            JSONObject existing = rooms.optJSONObject(i);
            if (existing == null) continue;
            String existingCode = sanitizeRoomCode(existing.optString("code", ""));
            if (safeCode.equals(existingCode)) {
                removed = true;
            } else {
                updated.put(existing);
            }
        }
        if (removed) storeRooms(updated);
        return removed;
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
                checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            return;
        }
        if (notificationManager == null) return;

        Intent openIntent = new Intent(this, EnhancedMainActivity.class);
        openIntent.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent openPending = PendingIntent.getActivity(
                this,
                1410,
                openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

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
            builder.setPriority(Notification.PRIORITY_HIGH)
                    .setDefaults(Notification.DEFAULT_VIBRATE);
        }

        notificationManager.notify(ALERT_NOTIFICATION_ID, builder.build());
    }

    public final class ExtrasBridge {
        @JavascriptInterface
        public String getSavedRoomsJson() {
            return loadRooms().toString();
        }

        @JavascriptInterface
        public String createRoom(String name) {
            String safeName = sanitizeRoomName(name);
            if (safeName.isEmpty()) return "";
            String code = generateRoomCode();
            if (!saveNamedRoomInternal(safeName, code)) return "";
            return code;
        }

        @JavascriptInterface
        public boolean saveRoomBookmark(String name, String code) {
            return saveNamedRoomInternal(name, code);
        }

        @JavascriptInterface
        public boolean deleteRoom(String code) {
            return deleteNamedRoomInternal(code);
        }

        @JavascriptInterface
        public void notifyTalker(String name) {
            mainHandler.post(() -> showTalkAlert(name));
        }

        @JavascriptInterface
        public boolean isCommunicationAudioBusy() {
            return communicationAudioBusy();
        }
    }
}
