package online.ebeinc.allthings140radio;

import android.app.PendingIntent;
import android.content.Intent;
import android.net.Uri;
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

import java.util.List;

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
    private static final long RETRY_DELAY_MS = 5_000L;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private ExoPlayer player;
    private MediaLibrarySession session;

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
        mainHandler.removeCallbacksAndMessages(null);
        if (player == null || !player.getPlayWhenReady()) return;
        mainHandler.postDelayed(() -> {
            if (player == null || !player.getPlayWhenReady()) return;
            Log.i(TAG, "Retrying continuous stream after bounded delay");
            player.seekToDefaultPosition();
            player.prepare();
            player.play();
        }, RETRY_DELAY_MS);
    }

    @Override public MediaLibrarySession onGetSession(MediaSession.ControllerInfo controllerInfo) {
        return session;
    }

    @Override public void onTaskRemoved(Intent rootIntent) {
        if (player == null || !player.getPlayWhenReady()) stopSelf();
    }

    @Override public void onDestroy() {
        mainHandler.removeCallbacksAndMessages(null);
        if (session != null) session.release();
        if (player != null) player.release();
        session = null;
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
