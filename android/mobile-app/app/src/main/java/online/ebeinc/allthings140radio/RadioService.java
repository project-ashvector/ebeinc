package online.ebeinc.allthings140radio;

import android.annotation.SuppressLint;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.session.LibraryResult;
import androidx.media3.session.MediaLibraryService;
import androidx.media3.session.MediaSession;
import androidx.media3.session.SessionError;

import com.google.common.collect.ImmutableList;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

/**
 * Single native playback authority for the phone UI, lock screen, Bluetooth,
 * Android Auto, and Android Automotive media browsing.
 */
@UnstableApi
public final class RadioService extends MediaLibraryService {
    private static final String TAG = "AT140Playback";
    private static final String ROOT_ID = "allthings140_root";
    private static final String LIVE_ID = "allthings140_live";
    private static final String STREAM_URL = "https://stream.ebeinc.online/live.mp3";
    private static final String ALERT_CATALOG_URL = BuildConfig.DEBUG
            ? "https://account-aware-alerts-vc19.ebeinc-uqt.pages.dev/api/public/alert-catalog"
            : "https://allthings140radio.online/api/public/alert-catalog";
    private static final long RETRY_DELAY_MS = 5_000L;
    private static final long POLICY_REFRESH_MS = 5 * 60_000L;
    private static final long ENTITLEMENT_GRACE_MS = 60 * 60_000L;
    private static final float ALERT_DUCK_GAIN = 0.34f;
    private static final String ALERT_PREFS = "allthings140_alert_scheduler";
    private static final String ACTION_ALERT_QA = "online.ebeinc.allthings140radio.ALERT_QA";

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final OkHttpClient http = new OkHttpClient.Builder().callTimeout(15, TimeUnit.SECONDS).build();
    private ExoPlayer player;
    private ExoPlayer alertPlayer;
    private MediaLibrarySession session;
    private SupabaseAuthClient authClient;
    private SharedPreferences alertPrefs;
    private final List<AlertItem> alerts = new ArrayList<>();
    private long alertIntervalMs = 900_000L;
    private boolean clientAlertsEnabled;
    private boolean alertPlaying;
    private boolean protectedAlertsEnabled = true;
    private boolean protectedStateKnown;
    private String protectedUserId = "";
    private long protectedStateAt;

    private static final class AlertItem {
        final String id;
        final String url;
        AlertItem(String id, String url) { this.id = id; this.url = url; }
    }

    private final Runnable recoveryRunnable = () -> {
        if (player == null || !player.getPlayWhenReady()) return;
        Log.i(TAG, "Retrying continuous stream after bounded delay");
        player.seekToDefaultPosition();
        player.prepare();
        player.play();
    };
    private final Runnable alertDueRunnable = this::playDueAlert;
    private final Runnable policyRefreshRunnable = new Runnable() {
        @Override public void run() {
            refreshAlertPolicy();
            mainHandler.postDelayed(this, POLICY_REFRESH_MS);
        }
    };
    private final BroadcastReceiver accountReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) { refreshAlertPolicy(); }
    };

    static MediaItem liveItem() {
        MediaMetadata metadata = new MediaMetadata.Builder()
                .setTitle("LIVE RADIO")
                .setArtist("ALLTHINGS140 — 24/7 HEAVY BASS")
                .setAlbumTitle("ALLTHINGS140 Radio")
                .setArtworkUri(Uri.parse("android.resource://" + BuildConfig.APPLICATION_ID + "/drawable/station_art"))
                .setIsPlayable(true)
                .setIsBrowsable(false)
                .setMediaType(MediaMetadata.MEDIA_TYPE_RADIO_STATION)
                .build();
        return new MediaItem.Builder()
                .setMediaId(LIVE_ID)
                .setUri(STREAM_URL)
                .setLiveConfiguration(new MediaItem.LiveConfiguration.Builder().build())
                .setMediaMetadata(metadata)
                .build();
    }

    private static MediaItem rootItem() {
        return new MediaItem.Builder()
                .setMediaId(ROOT_ID)
                .setMediaMetadata(new MediaMetadata.Builder()
                        .setTitle("ALLTHINGS140")
                        .setSubtitle("LIVE RADIO")
                        .setIsBrowsable(true)
                        .setIsPlayable(false)
                        .setMediaType(MediaMetadata.MEDIA_TYPE_FOLDER_RADIO_STATIONS)
                        .build())
                .build();
    }

    @SuppressLint("UnspecifiedRegisterReceiverFlag")
    @Override public void onCreate() {
        super.onCreate();
        player = new ExoPlayer.Builder(this).build();
        player.setAudioAttributes(new AudioAttributes.Builder()
                .setUsage(C.USAGE_MEDIA)
                .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
                .build(), true);
        player.setHandleAudioBecomingNoisy(true);
        player.setWakeMode(C.WAKE_MODE_NETWORK);
        player.setMediaItem(liveItem());
        player.addListener(new Player.Listener() {
            @Override public void onIsPlayingChanged(boolean isPlaying) {
                if (isPlaying) scheduleAlert();
                else mainHandler.removeCallbacks(alertDueRunnable);
            }

            @Override public void onPlayerError(PlaybackException error) {
                Log.w(TAG, "Stream error: " + error.getErrorCodeName());
                scheduleRecovery();
            }

            @Override public void onMediaMetadataChanged(MediaMetadata mediaMetadata) {
                if (mediaMetadata.title != null) {
                    Log.d(TAG, "Metadata: " + mediaMetadata.title);
                }
            }
        });

        // The stream remains the sole MediaSession authority. A second player
        // inside this same service provides short alerts without reconnecting
        // Icecast or creating a competing foreground service.
        alertPlayer = new ExoPlayer.Builder(this).build();
        alertPlayer.setAudioAttributes(new AudioAttributes.Builder()
                .setUsage(C.USAGE_MEDIA)
                .setContentType(C.AUDIO_CONTENT_TYPE_SPEECH)
                .build(), false);
        alertPlayer.addListener(new Player.Listener() {
            @Override public void onPlaybackStateChanged(int state) {
                if (state == Player.STATE_ENDED) finishAlert("complete");
            }
            @Override public void onPlayerError(PlaybackException error) {
                Log.w(TAG, "Client alert failed; stream continues: " + error.getErrorCodeName());
                finishAlert("media_failed");
            }
        });
        authClient = new SupabaseAuthClient(this);
        alertPrefs = getSharedPreferences(ALERT_PREFS, MODE_PRIVATE);
        IntentFilter filter = new IntentFilter(SupabaseAuthClient.ACTION_ACCOUNT_STATE_CHANGED);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(accountReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(accountReceiver, filter);
        fetchAlertCatalog();
        refreshAlertPolicy();
        mainHandler.postDelayed(policyRefreshRunnable, POLICY_REFRESH_MS);

        PendingIntent openApp = PendingIntent.getActivity(
                this,
                140,
                new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

        session = new MediaLibrarySession.Builder(this, player, new LibraryCallback())
                .setSessionActivity(openApp)
                .build();
        Log.i(TAG, "Media library service created");
    }

    private void scheduleRecovery() {
        mainHandler.removeCallbacks(recoveryRunnable);
        if (player == null || !player.getPlayWhenReady()) return;
        mainHandler.postDelayed(recoveryRunnable, RETRY_DELAY_MS);
    }

    private void fetchAlertCatalog() {
        new Thread(() -> {
            try (Response response = http.newCall(new Request.Builder().url(ALERT_CATALOG_URL).get().build()).execute()) {
                if (!response.isSuccessful() || response.body() == null) throw new IllegalStateException("HTTP " + response.code());
                JSONObject body = new JSONObject(response.body().string());
                JSONArray items = body.optJSONArray("alerts");
                ArrayList<AlertItem> loaded = new ArrayList<>();
                if (items != null) for (int i = 0; i < items.length(); i++) {
                    JSONObject item = items.optJSONObject(i);
                    if (item == null) continue;
                    String id = item.optString("id", "");
                    String url = item.optString("url", "");
                    if (!id.matches("[a-f0-9]{32}")) continue;
                    if (url.startsWith("/")) url = "https://status.ebeinc.online" + url;
                    if (url.startsWith("https://")) loaded.add(new AlertItem(id, url));
                }
                long interval = Math.max(60, body.optLong("interval_seconds", 900)) * 1000L;
                boolean enabled = body.optBoolean("client_account_alerts_enabled", false);
                mainHandler.post(() -> {
                    alerts.clear();
                    alerts.addAll(loaded);
                    boolean qaEnabled = BuildConfig.DEBUG && alertPrefs.getBoolean("qa_client_alerts", false);
                    alertIntervalMs = qaEnabled ? Math.min(interval, 60_000L) : interval;
                    clientAlertsEnabled = enabled || qaEnabled;
                    Log.i(TAG, "Alert catalog loaded: " + loaded.size()
                            + " items; client delivery " + (clientAlertsEnabled ? "enabled" : "disabled"));
                    scheduleAlert();
                });
            } catch (Exception error) {
                Log.w(TAG, "Alert catalog unavailable; stream continues", error);
                if (BuildConfig.DEBUG && alertPrefs.getBoolean("qa_client_alerts", false)) {
                    int resource = getResources().getIdentifier("at140_qa_alert", "raw", getPackageName());
                    if (resource != 0) mainHandler.post(() -> {
                        alerts.clear();
                        alerts.add(new AlertItem("00000000000000000000000000000000",
                                "android.resource://" + getPackageName() + "/" + resource));
                        alertIntervalMs = 60_000L;
                        clientAlertsEnabled = true;
                        scheduleAlert();
                    });
                }
            }
        }, "at140-alert-catalog").start();
    }

    private void refreshAlertPolicy() {
        String userId = authClient.userId();
        if (!authClient.signedIn()) {
            protectedUserId = "";
            protectedStateKnown = true;
            protectedAlertsEnabled = true;
            protectedStateAt = System.currentTimeMillis();
            cancelActiveAlert("signed_out");
            scheduleAlert();
            return;
        }
        if (!userId.equals(protectedUserId)) {
            protectedUserId = userId;
            protectedStateKnown = false;
            cancelActiveAlert("account_changed");
        }
        authClient.loadRole((ok, role, status, email, accountClass, accountType, alertAdsPreference, alertAdsEnabled) -> mainHandler.post(() -> {
            if (ok && userId.equals(authClient.userId())) {
                protectedAlertsEnabled = alertAdsEnabled;
                protectedStateKnown = true;
                protectedStateAt = System.currentTimeMillis();
                if (!alertAdsEnabled) cancelActiveAlert("entitlement_off");
                scheduleAlert();
            } else if (System.currentTimeMillis() - protectedStateAt > ENTITLEMENT_GRACE_MS) {
                // Never infer ad-free authority from editable local state.
                // While signed in but unvalidated, defer client alerts.
                protectedStateKnown = false;
                cancelActiveAlert("authority_unknown");
            }
        }));
    }

    private boolean shouldPlayAlerts() {
        return clientAlertsEnabled && protectedStateKnown && protectedAlertsEnabled;
    }

    private void scheduleAlert() {
        mainHandler.removeCallbacks(alertDueRunnable);
        if (player == null || !player.isPlaying() || !shouldPlayAlerts() || alerts.isEmpty()) return;
        long last = alertPrefs.getLong("last_alert_at", 0);
        if (last == 0) {
            last = System.currentTimeMillis();
            alertPrefs.edit().putLong("last_alert_at", last).apply();
        }
        long elapsed = Math.max(0, System.currentTimeMillis() - last);
        mainHandler.postDelayed(alertDueRunnable, Math.max(1000, alertIntervalMs - elapsed));
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (BuildConfig.DEBUG && intent != null && ACTION_ALERT_QA.equals(intent.getAction())) {
            boolean enabled = intent.getBooleanExtra("enabled", false);
            alertPrefs.edit().putBoolean("qa_client_alerts", enabled).apply();
            if (!enabled) {
                clientAlertsEnabled = false;
                alerts.clear();
                cancelActiveAlert("qa_disabled");
            }
            fetchAlertCatalog();
        }
        return super.onStartCommand(intent, flags, startId);
    }

    private void playDueAlert() {
        if (alertPlaying || player == null || !player.isPlaying() || !shouldPlayAlerts() || alerts.isEmpty()) {
            scheduleAlert();
            return;
        }
        ArrayList<AlertItem> choices = new ArrayList<>(alerts);
        String last = alertPrefs.getString("last_alert_id", "");
        if (choices.size() > 1) {
            for (int index = choices.size() - 1; index >= 0; index--) {
                if (choices.get(index).id.equals(last)) choices.remove(index);
            }
        }
        Collections.shuffle(choices);
        AlertItem selected = choices.get(0);
        alertPlaying = true;
        player.setVolume(ALERT_DUCK_GAIN);
        alertPlayer.setMediaItem(MediaItem.fromUri(selected.url));
        alertPlayer.prepare();
        alertPlayer.play();
        alertPrefs.edit().putLong("last_alert_at", System.currentTimeMillis()).putString("last_alert_id", selected.id).apply();
        Log.i(TAG, "Client alert started; stream remains connected");
    }

    private void finishAlert(String reason) {
        if (!alertPlaying) return;
        alertPlaying = false;
        alertPlayer.stop();
        alertPlayer.clearMediaItems();
        if (player != null) player.setVolume(1f);
        Log.i(TAG, "Client alert ended: " + reason);
        scheduleAlert();
    }

    private void cancelActiveAlert(String reason) {
        mainHandler.removeCallbacks(alertDueRunnable);
        if (alertPlaying) finishAlert(reason);
    }

    @Override public MediaLibrarySession onGetSession(MediaSession.ControllerInfo controllerInfo) {
        return session;
    }

    @Override public void onTaskRemoved(Intent rootIntent) {
        if (player == null || !player.getPlayWhenReady()) stopSelf();
    }

    @Override public void onDestroy() {
        mainHandler.removeCallbacksAndMessages(null);
        try { unregisterReceiver(accountReceiver); } catch (IllegalArgumentException ignored) {}
        if (session != null) session.release();
        if (alertPlayer != null) alertPlayer.release();
        if (player != null) player.release();
        session = null;
        alertPlayer = null;
        player = null;
        Log.i(TAG, "Media library service destroyed");
        super.onDestroy();
    }

    private static final class LibraryCallback implements MediaLibrarySession.Callback {
        @Override public ListenableFuture<LibraryResult<MediaItem>> onGetLibraryRoot(
                MediaLibrarySession session,
                MediaSession.ControllerInfo browser,
                LibraryParams params) {
            return Futures.immediateFuture(LibraryResult.ofItem(rootItem(), params));
        }

        @Override public ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> onGetChildren(
                MediaLibrarySession session,
                MediaSession.ControllerInfo browser,
                String parentId,
                int page,
                int pageSize,
                LibraryParams params) {
            if (!ROOT_ID.equals(parentId) || page > 0) {
                return Futures.immediateFuture(LibraryResult.ofItemList(ImmutableList.of(), params));
            }
            return Futures.immediateFuture(LibraryResult.ofItemList(ImmutableList.of(liveItem()), params));
        }

        @Override public ListenableFuture<LibraryResult<MediaItem>> onGetItem(
                MediaLibrarySession session,
                MediaSession.ControllerInfo browser,
                String mediaId) {
            if (LIVE_ID.equals(mediaId)) {
                return Futures.immediateFuture(LibraryResult.ofItem(liveItem(), null));
            }
            return Futures.immediateFuture(LibraryResult.ofError(SessionError.ERROR_BAD_VALUE));
        }

        @Override public ListenableFuture<List<MediaItem>> onAddMediaItems(
                MediaSession session,
                MediaSession.ControllerInfo controller,
                List<MediaItem> requested) {
            return Futures.immediateFuture(ImmutableList.of(liveItem()));
        }
    }
}
