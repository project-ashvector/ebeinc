package online.ebeinc.talkietalkie;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.os.Build;
import android.os.IBinder;

import org.json.JSONObject;

import java.io.IOException;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;

/**
 * Long-lived room service.
 *
 * The service is deliberately receive-only while the UI is not visible. The
 * visible Activity owns the microphone/PTT connection. When the Activity goes
 * away, it hands the same room/device identity to BackgroundRadioEngine.
 */
public class TalkieListeningService extends Service implements BackgroundRadioEngine.Listener {
    private static final String PREFS = "ebe_talkie_talkie";
    private static final String CHANNEL_ID = "ebe_talkie_listening";
    private static final String ALERT_CHANNEL_ID = "ebe_talkie_talk_alerts";
    private static final int NOTIFICATION_ID = 1401;
    private static final int TALK_ALERT_ID = 1411;

    public static final String ACTION_ARM = "online.ebeinc.talkietalkie.ARM_LISTENING";
    public static final String ACTION_ACTIVITY_BACKGROUND = "online.ebeinc.talkietalkie.ACTIVITY_BACKGROUND";
    public static final String ACTION_ACTIVITY_FOREGROUND = "online.ebeinc.talkietalkie.ACTIVITY_FOREGROUND";
    public static final String ACTION_LEAVE_ROOM = "online.ebeinc.talkietalkie.LEAVE_ROOM";

    private SharedPreferences prefs;
    private NotificationManager notifications;
    private ConnectivityManager connectivity;
    private AudioManager audioManager;
    private BackgroundRadioEngine engine;
    private ConnectivityManager.NetworkCallback networkCallback;

    private final ScheduledExecutorService worker = Executors.newSingleThreadScheduledExecutor();
    private ScheduledFuture<?> presenceTask;
    private final OkHttpClient http = new OkHttpClient.Builder()
            .connectTimeout(12, TimeUnit.SECONDS)
            .readTimeout(12, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build();

    private volatile boolean ownsAudioRoute;

    @Override
    public void onCreate() {
        super.onCreate();
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        notifications = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        connectivity = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        audioManager = (AudioManager) getSystemService(Context.AUDIO_SERVICE);

        createChannels();
        engine = new BackgroundRadioEngine(this, this);
        registerNetworkCallback();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIFICATION_ID, buildStatusNotification("Room armed · waiting in background"));

        // START_STICKY can recreate the service with a null Intent after Android
        // kills the process. The old Activity cannot still be visible in that
        // case, so discard a stale ui_visible flag and recover the armed room.
        if (intent == null) {
            prefs.edit().putBoolean("ui_visible", false).apply();
            if (prefs.getBoolean("auto_connect", false)) {
                worker.schedule(this::startBackgroundEngine, 250, TimeUnit.MILLISECONDS);
            }
            return START_STICKY;
        }

        String action = intent.getAction();
        if (ACTION_LEAVE_ROOM.equals(action)) {
            leaveRoomAndStop();
            return START_NOT_STICKY;
        }

        if (ACTION_ACTIVITY_FOREGROUND.equals(action)) {
            prefs.edit().putBoolean("ui_visible", true).apply();
            stopBackgroundEngine();
            updateStatus("Room connected · app is open");
            return START_STICKY;
        }

        if (ACTION_ACTIVITY_BACKGROUND.equals(action)) {
            prefs.edit().putBoolean("ui_visible", false).apply();
            if (prefs.getBoolean("auto_connect", false)) {
                worker.schedule(this::startBackgroundEngine, 500, TimeUnit.MILLISECONDS);
            }
            return START_STICKY;
        }

        if (ACTION_ARM.equals(action)) {
            prefs.edit().putBoolean("auto_connect", true).apply();
        }

        boolean visible = prefs.getBoolean("ui_visible", false);
        if (prefs.getBoolean("auto_connect", false) && !visible) {
            startBackgroundEngine();
        }
        return START_STICKY;
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        prefs.edit().putBoolean("ui_visible", false).apply();
        if (prefs.getBoolean("auto_connect", false)) {
            worker.schedule(this::startBackgroundEngine, 550, TimeUnit.MILLISECONDS);
        }
        super.onTaskRemoved(rootIntent);
    }

    private void startBackgroundEngine() {
        if (!prefs.getBoolean("auto_connect", false)) return;
        String room = prefs.getString("room", "");
        String deviceId = prefs.getString("device_id", "");
        String name = prefs.getString("name", "");
        if (room == null || room.trim().length() < 8 || deviceId == null || deviceId.trim().isEmpty()) {
            updateStatus("No active room");
            return;
        }

        prepareAudioRoute();
        engine.start(room, deviceId, name);
        startPresenceLoop();
        String roomName = prefs.getString("active_room_name", "room");
        updateStatus("Connecting to " + safeLabel(roomName));
    }

    private void stopBackgroundEngine() {
        stopPresenceLoop();
        if (engine != null) engine.stop();
        restoreAudioRoute();
    }

    private void leaveRoomAndStop() {
        stopPresenceLoop();
        if (engine != null) engine.stop();
        restoreAudioRoute();
        prefs.edit()
                .putBoolean("auto_connect", false)
                .putBoolean("ui_visible", false)
                .remove("active_social_room_id")
                .remove("active_room_name")
                .remove("active_room_owner")
                .apply();
        stopForeground(true);
        stopSelf();
    }

    private void prepareAudioRoute() {
        if (audioManager == null || ownsAudioRoute) return;
        try {
            if (audioManager.getMode() != AudioManager.MODE_NORMAL) return;
            ownsAudioRoute = true;
            audioManager.setMode(AudioManager.MODE_IN_COMMUNICATION);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                AudioDeviceInfo speaker = null;
                for (AudioDeviceInfo device : audioManager.getAvailableCommunicationDevices()) {
                    if (device.getType() == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) {
                        speaker = device;
                        break;
                    }
                }
                if (speaker != null) audioManager.setCommunicationDevice(speaker);
            } else {
                audioManager.setSpeakerphoneOn(true);
            }
        } catch (Exception ignored) {
            ownsAudioRoute = false;
        }
    }

    private void restoreAudioRoute() {
        if (audioManager == null || !ownsAudioRoute) return;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                audioManager.clearCommunicationDevice();
            } else {
                audioManager.setSpeakerphoneOn(false);
            }
            audioManager.setMode(AudioManager.MODE_NORMAL);
        } catch (Exception ignored) {
        } finally {
            ownsAudioRoute = false;
        }
    }

    private void startPresenceLoop() {
        stopPresenceLoop();
        presenceTask = worker.scheduleAtFixedRate(this::sendPresence, 1, 12, TimeUnit.SECONDS);
    }

    private void stopPresenceLoop() {
        if (presenceTask != null) {
            presenceTask.cancel(false);
            presenceTask = null;
        }
    }

    private void sendPresence() {
        if (!prefs.getBoolean("auto_connect", false) || prefs.getBoolean("ui_visible", false)) return;
        String token = prefs.getString("social_auth_token", "");
        String roomId = prefs.getString("active_social_room_id", "");
        if (token == null || token.isEmpty() || roomId == null || roomId.isEmpty()) return;

        try {
            JSONObject body = new JSONObject().put("roomId", roomId);
            Request request = new Request.Builder()
                    .url(BuildConfig.TALKIE_API_URL + "/v1/presence")
                    .header("Authorization", "Bearer " + token)
                    .post(RequestBody.create(
                            body.toString(),
                            MediaType.get("application/json; charset=utf-8")
                    ))
                    .build();
            try (okhttp3.Response ignored = http.newCall(request).execute()) {
                // Presence is best-effort. The radio transport keeps running even
                // if the social session expires or the API is temporarily down.
            }
        } catch (Exception ignored) {
        }
    }

    private void registerNetworkCallback() {
        if (connectivity == null || Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return;
        networkCallback = new ConnectivityManager.NetworkCallback() {
            @Override
            public void onAvailable(Network network) {
                if (prefs.getBoolean("auto_connect", false)
                        && !prefs.getBoolean("ui_visible", false)) {
                    worker.schedule(TalkieListeningService.this::startBackgroundEngine, 400, TimeUnit.MILLISECONDS);
                }
            }
        };
        try {
            connectivity.registerDefaultNetworkCallback(networkCallback);
        } catch (Exception ignored) {
            networkCallback = null;
        }
    }

    private void createChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || notifications == null) return;

        NotificationChannel status = new NotificationChannel(
                CHANNEL_ID,
                "Always-on room listening",
                NotificationManager.IMPORTANCE_LOW
        );
        status.setDescription("Keeps the selected EBE Talkie Talkie room connected while the app is closed.");
        status.setShowBadge(false);
        notifications.createNotificationChannel(status);

        NotificationChannel talk = new NotificationChannel(
                ALERT_CHANNEL_ID,
                "Talk alerts",
                NotificationManager.IMPORTANCE_HIGH
        );
        talk.setDescription("Alerts when someone starts talking while EBE Talkie Talkie is in the background or another call is active.");
        talk.setShowBadge(false);
        talk.enableVibration(true);
        talk.setVibrationPattern(new long[]{0, 80, 60, 120});
        talk.setSound(null, null);
        notifications.createNotificationChannel(talk);
    }

    private Notification buildStatusNotification(String text) {
        Intent openIntent = new Intent(this, PersistentMainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent openPending = PendingIntent.getActivity(
                this, 1401, openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Intent leaveIntent = new Intent(this, TalkieListeningService.class)
                .setAction(ACTION_LEAVE_ROOM);
        PendingIntent leavePending = PendingIntent.getService(
                this, 1402, leaveIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);

        return builder
                .setSmallIcon(R.drawable.ic_stat_talkie)
                .setContentTitle("EBE Talkie Talkie")
                .setContentText(text)
                .setContentIntent(openPending)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setCategory(Notification.CATEGORY_SERVICE)
                .addAction(new Notification.Action.Builder(
                        R.drawable.ic_stat_talkie,
                        "Leave room",
                        leavePending
                ).build())
                .build();
    }

    private void updateStatus(String text) {
        if (notifications != null) notifications.notify(NOTIFICATION_ID, buildStatusNotification(text));
    }

    private void postTalkAlert(String talker) {
        if (notifications == null) return;
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;
        }

        Intent openIntent = new Intent(this, PersistentMainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent openPending = PendingIntent.getActivity(
                this, TALK_ALERT_ID, openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, ALERT_CHANNEL_ID)
                : new Notification.Builder(this);

        String roomName = safeLabel(prefs.getString("active_room_name", "your room"));
        builder.setSmallIcon(R.drawable.ic_stat_talkie)
                .setContentTitle(safeLabel(talker) + " is talking")
                .setContentText(roomName + " · tap to open EBE Talkie Talkie")
                .setContentIntent(openPending)
                .setAutoCancel(true)
                .setOnlyAlertOnce(false)
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setTimeoutAfter(7_000L);

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            builder.setPriority(Notification.PRIORITY_HIGH)
                    .setDefaults(Notification.DEFAULT_VIBRATE);
        }
        notifications.notify(TALK_ALERT_ID, builder.build());
    }

    private String safeLabel(String value) {
        if (value == null || value.trim().isEmpty()) return "Room";
        String safe = value.trim().replace('\n', ' ').replace('\r', ' ');
        return safe.length() > 40 ? safe.substring(0, 40) : safe;
    }

    @Override
    public void onReady() {
        String roomName = safeLabel(prefs.getString("active_room_name", "room"));
        updateStatus("Always listening in " + roomName);
    }

    @Override
    public void onDisconnected(String reason) {
        String roomName = safeLabel(prefs.getString("active_room_name", "room"));
        updateStatus("Reconnecting to " + roomName);
    }

    @Override
    public void onTalker(String name) {
        String roomName = safeLabel(prefs.getString("active_room_name", "room"));
        updateStatus(safeLabel(name) + " is talking · " + roomName);
        postTalkAlert(name);
    }

    @Override
    public void onTalkerStopped() {
        String roomName = safeLabel(prefs.getString("active_room_name", "room"));
        updateStatus("Always listening in " + roomName);
    }

    @Override
    public void onPeerCount(int count) {
        if (count <= 0) return;
        String roomName = safeLabel(prefs.getString("active_room_name", "room"));
        updateStatus("Always listening in " + roomName + " · " + (count + 1) + " connected");
    }

    @Override
    public void onDestroy() {
        stopPresenceLoop();
        if (networkCallback != null && connectivity != null) {
            try { connectivity.unregisterNetworkCallback(networkCallback); } catch (Exception ignored) {}
        }
        if (engine != null) engine.shutdown();
        restoreAudioRoute();
        worker.shutdownNow();
        http.dispatcher().executorService().shutdown();
        http.connectionPool().evictAll();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
