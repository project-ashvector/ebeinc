package online.ebeinc.allthings140radio;

import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * Robust WebSocket client for ALLTHINGS140 Green Room live chat.
 */
public final class ChatClient {
    private static final String TAG = "AT140Chat";
    private static final String ENDPOINT = "wss://chat.ebeinc.online/ws";
    private static final String ORIGIN = "https://allthings140radio.online";

    public interface Listener {
        void onConnectionState(String stateText, boolean isOnline);
        void onHistoryLoaded(List<ChatMessage> messages, int presenceCount, String assignedName);
        void onNewMessage(ChatMessage message);
        void onPresenceUpdate(int presenceCount);
        void onReactionsUpdate(String trackId, Map<String, Integer> reactions);
        void onChatCleared();
        void onMessageDeleted(String messageId);
        void onErrorNotice(String message);
        default void onTermsRequired() { }
        default void onAuthenticated(String userId, String username) { }
    }

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final OkHttpClient httpClient;
    private Listener listener;
    private WebSocket webSocket;
    private boolean isExplicitlyClosed = false;
    private long reconnectDelayMs = 1000L;
    private Runnable reconnectRunnable;

    private String currentName = "";
    private String currentColor = "purple";
    private String accessToken = "";

    public ChatClient() {
        httpClient = new OkHttpClient.Builder()
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .pingInterval(25, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build();
    }

    public void setListener(Listener listener) {
        this.listener = listener;
    }

    public void setProfile(String name, String color) {
        if (name != null && !name.trim().isEmpty()) {
            this.currentName = name.trim();
        }
        if (color != null && !color.trim().isEmpty()) {
            this.currentColor = color.trim();
        }
        if (isConnected()) {
            sendJoin(this.currentName, this.currentColor);
        }
    }

    public void setAccessToken(String token) {
        accessToken = token != null ? token.trim() : "";
    }

    public boolean isAuthenticated() { return !accessToken.isEmpty(); }
    public String getAccessToken() { return accessToken; }

    public void connect() {
        isExplicitlyClosed = false;
        if (webSocket != null) return;

        cancelReconnect();
        notifyState("CONNECTING…", false);

        Request request = new Request.Builder()
                .url(ENDPOINT)
                .addHeader("Origin", ORIGIN)
                .build();

        webSocket = httpClient.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket ws, Response response) {
                mainHandler.post(() -> {
                    reconnectDelayMs = 1000L;
                    notifyState("CHAT LIVE", true);
                    if (!accessToken.isEmpty()) {
                        sendAuth(accessToken);
                    } else if (!currentName.isEmpty()) {
                        sendJoin(currentName, currentColor);
                    }
                });
            }

            @Override
            public void onMessage(WebSocket ws, String text) {
                handleIncomingJson(text);
            }

            @Override
            public void onClosed(WebSocket ws, int code, String reason) {
                mainHandler.post(() -> {
                    webSocket = null;
                    if (!isExplicitlyClosed) {
                        notifyState("RECONNECTING…", false);
                        scheduleReconnect();
                    } else {
                        notifyState("OFFLINE", false);
                    }
                });
            }

            @Override
            public void onFailure(WebSocket ws, Throwable t, Response response) {
                Log.w(TAG, "Chat WebSocket failure: " + t.getMessage());
                mainHandler.post(() -> {
                    webSocket = null;
                    if (!isExplicitlyClosed) {
                        notifyState("RECONNECTING…", false);
                        scheduleReconnect();
                    } else {
                        notifyState("OFFLINE", false);
                    }
                });
            }
        });
    }

    public void disconnect() {
        isExplicitlyClosed = true;
        cancelReconnect();
        if (webSocket != null) {
            webSocket.close(1000, "App closed chat");
            webSocket = null;
        }
        notifyState("OFFLINE", false);
    }

    public boolean isConnected() {
        return webSocket != null;
    }

    public void sendJoin(String name, String color) {
        if (webSocket == null) return;
        try {
            JSONObject obj = new JSONObject();
            obj.put("type", "join");
            obj.put("name", name);
            obj.put("color", color);
            webSocket.send(obj.toString());
        } catch (Exception e) {
            Log.e(TAG, "Failed to send join", e);
        }
    }

    private void sendAuth(String token) {
        try {
            JSONObject obj = new JSONObject();
            obj.put("type", "auth");
            obj.put("accessToken", token);
            webSocket.send(obj.toString());
        } catch (Exception e) { Log.e(TAG, "Failed to authenticate chat", e); }
    }

    public void sendTermsAccept() { sendSimple("terms_accept"); }

    public void sendReport(String messageId, String reason) {
        try {
            JSONObject obj = new JSONObject(); obj.put("type", "report");
            obj.put("messageId", messageId); obj.put("reason", reason);
            if (webSocket != null) webSocket.send(obj.toString());
        } catch (Exception e) { Log.e(TAG, "Failed to report message", e); }
    }

    public void sendBlock(String userId) { sendUserAction("block", userId); }
    public void sendUnblock(String userId) { sendUserAction("unblock", userId); }

    private void sendSimple(String type) {
        if (webSocket != null) webSocket.send("{\"type\":\"" + type + "\"}");
    }

    private void sendUserAction(String type, String userId) {
        try {
            JSONObject obj = new JSONObject(); obj.put("type", type); obj.put("userId", userId);
            if (webSocket != null) webSocket.send(obj.toString());
        } catch (Exception e) { Log.e(TAG, "Failed to send " + type, e); }
    }

    public void sendMessage(String text) {
        if (webSocket == null || text == null || text.trim().isEmpty()) return;
        try {
            JSONObject obj = new JSONObject();
            obj.put("type", "message");
            obj.put("text", text.trim());
            webSocket.send(obj.toString());
        } catch (Exception e) {
            Log.e(TAG, "Failed to send message", e);
        }
    }

    public void sendReaction(String reaction, String trackId) {
        if (webSocket == null) return;
        try {
            JSONObject obj = new JSONObject();
            obj.put("type", "react");
            obj.put("reaction", reaction);
            obj.put("trackId", trackId != null ? trackId : "allthings140");
            webSocket.send(obj.toString());
        } catch (Exception e) {
            Log.e(TAG, "Failed to send reaction", e);
        }
    }

    private void handleIncomingJson(String jsonText) {
        try {
            JSONObject data = new JSONObject(jsonText);
            String type = data.optString("type", "");

            mainHandler.post(() -> {
                if (listener == null) return;

                if ("history".equals(type)) {
                    JSONArray arr = data.optJSONArray("messages");
                    List<ChatMessage> list = new ArrayList<>();
                    if (arr != null) {
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject m = arr.optJSONObject(i);
                            if (m != null) {
                                list.add(parseMessage(m));
                            }
                        }
                    }
                    int count = data.optInt("count", 0);
                    String assignedName = data.optString("name", "");
                    listener.onHistoryLoaded(list, count, assignedName);
                } else if ("auth_state".equals(type)) {
                    listener.onAuthenticated(data.optString("userId", ""), data.optString("username", ""));
                } else if ("message".equals(type)) {
                    JSONObject m = data.optJSONObject("message");
                    if (m != null) {
                        listener.onNewMessage(parseMessage(m));
                    }
                } else if ("presence".equals(type)) {
                    listener.onPresenceUpdate(data.optInt("count", 0));
                } else if ("reactions".equals(type)) {
                    String trackId = data.optString("trackId", "");
                    JSONObject reacts = data.optJSONObject("reactions");
                    Map<String, Integer> map = new HashMap<>();
                    if (reacts != null) {
                        java.util.Iterator<String> keys = reacts.keys();
                        while (keys.hasNext()) {
                            String key = keys.next();
                            map.put(key, reacts.optInt(key, 0));
                        }
                    }
                    listener.onReactionsUpdate(trackId, map);
                } else if ("cleared".equals(type)) {
                    listener.onChatCleared();
                } else if ("deleted".equals(type)) {
                    listener.onMessageDeleted(data.optString("id", ""));
                } else if ("expired".equals(type)) {
                    listener.onMessageDeleted(data.optString("id", ""));
                } else if ("error".equals(type)) {
                    String message = data.optString("message", "Error");
                    if (message.contains("Accept the current Green Room Terms")) listener.onTermsRequired();
                    listener.onErrorNotice(message);
                }
            });
        } catch (Exception e) {
            Log.w(TAG, "JSON parse error in chat message", e);
        }
    }

    private ChatMessage parseMessage(JSONObject m) {
        return new ChatMessage(
                m.optString("id", ""),
                m.optString("name", "Listener"),
                m.optString("text", ""),
                m.optLong("ts", System.currentTimeMillis()),
                m.optString("color", "purple"),
                m.optBoolean("verified", false),
                m.optString("senderId", ""),
                false
        );
    }

    private void scheduleReconnect() {
        if (isExplicitlyClosed) return;
        cancelReconnect();
        reconnectRunnable = this::connect;
        mainHandler.postDelayed(reconnectRunnable, reconnectDelayMs);
        reconnectDelayMs = Math.min(reconnectDelayMs * 2, 15000L);
    }

    private void cancelReconnect() {
        if (reconnectRunnable != null) {
            mainHandler.removeCallbacks(reconnectRunnable);
            reconnectRunnable = null;
        }
    }

    private void notifyState(String stateText, boolean isOnline) {
        if (listener != null) {
            listener.onConnectionState(stateText, isOnline);
        }
    }
}
