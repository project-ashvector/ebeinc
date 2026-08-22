package online.ebeinc.allthings140radio;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.content.ContextCompat;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * ALLTHINGS140 Radio — Native listener experience.
 * Primary audio is continuously managed by RadioService.
 * Navigation between Radio, Green Room Chat, and Settings never interrupts playback.
 */
@androidx.media3.common.util.UnstableApi
public final class MainActivity extends Activity {
    private static final String LIVE_MEDIA_ID = "allthings140_live";
    private static final long STATUS_REFRESH_MS = 15_000L;
    private static final String PREFS_NAME = "allthings140_app_prefs";
    private static final String PREF_CHAT_NAME = "chat_display_name";
    private static final String PREF_CHAT_COLOR = "chat_glow_color";
    private static final String PREF_BLOCKED_USERS = "chat_blocked_users";

    private enum Tab { RADIO, CHAT }
    private Tab currentTab = Tab.RADIO;

    // Root & Top Bar
    private View root;
    private View topBar;

    // Tabs & Navigation
    private ScrollView scrollRadio;
    private LinearLayout layoutChat;
    private LinearLayout navTabRadio;
    private LinearLayout navTabChat;
    private ImageView imgTabRadioIcon;
    private TextView txtTabRadioLabel;
    private ImageView imgTabChatIcon;
    private TextView txtTabChatLabel;

    // Radio Tab Views
    private TextView txtVisualTrackTitle;
    private TextView txtVisualStatus;
    private VisualsVideoView visualsVideoView;
    private TextView liveBadge;
    private TextView nowPlaying;
    private TextView artist;
    private TextView listeners;
    private TextView connectionStatus;
    private Button playPause;
    private Button retry;

    // Chat Tab Views
    private TextView txtChatStatus;
    private TextView txtChatUsersCount;
    private RecyclerView recyclerChatMessages;
    private EditText editChatMessage;
    private ImageButton btnSendMessage;
    private ChatAdapter chatAdapter;
    private ChatClient chatClient;
    private SupabaseAuthClient authClient;

    // Media & Status
    private ListenableFuture<MediaController> controllerFuture;
    private MediaController controller;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService statusExecutor = Executors.newSingleThreadExecutor();
    private final StationStatusClient statusClient = new StationStatusClient();
    private boolean pollingStatus;
    private boolean statusFetchInFlight;
    private boolean activityStarted;
    private String latestApiTitle = "";
    private String latestApiArtist = "";
    private String currentTrackId = "allthings140";
    private SharedPreferences prefs;

    private final Player.Listener playerListener = new Player.Listener() {
        @Override public void onIsPlayingChanged(boolean isPlaying) {
            updatePlaybackUi();
        }

        @Override public void onPlaybackStateChanged(int playbackState) {
            updatePlaybackUi();
        }

        @Override public void onMediaMetadataChanged(MediaMetadata mediaMetadata) {
            updateMetadata(mediaMetadata);
        }

        @Override public void onPlayerError(PlaybackException error) {
            if (!activityStarted) return;
            connectionStatus.setText(R.string.playback_reconnecting);
            retry.setVisibility(View.VISIBLE);
            updatePlaybackUi();
        }
    };

    private final Runnable statusPollRunnable = new Runnable() {
        @Override public void run() {
            if (!pollingStatus) return;
            if (!statusFetchInFlight) {
                statusFetchInFlight = true;
                statusExecutor.execute(() -> {
                    StationStatusClient.Status status = statusClient.fetch();
                    mainHandler.post(() -> {
                        statusFetchInFlight = false;
                        if (pollingStatus) applyStationStatus(status);
                    });
                });
            }
            mainHandler.postDelayed(this, STATUS_REFRESH_MS);
        }
    };

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        authClient = new SupabaseAuthClient(this);

        initViews();
        setupNavigation();
        setupRadioControls();
        setupChatControls();
        applyWindowInsets();

        playPause.setEnabled(false);
        updatePlaybackUi();
    }

    private void initViews() {
        root = findViewById(R.id.mainRoot);
        topBar = findViewById(R.id.mainTopBar);

        // Screens
        scrollRadio = findViewById(R.id.scrollRadio);
        layoutChat = findViewById(R.id.layoutChat);

        // Navigation
        navTabRadio = findViewById(R.id.navTabRadio);
        navTabChat = findViewById(R.id.navTabChat);
        imgTabRadioIcon = findViewById(R.id.imgTabRadioIcon);
        txtTabRadioLabel = findViewById(R.id.txtTabRadioLabel);
        imgTabChatIcon = findViewById(R.id.imgTabChatIcon);
        txtTabChatLabel = findViewById(R.id.txtTabChatLabel);

        // Visuals Video Card
        txtVisualTrackTitle = findViewById(R.id.txtVisualTrackTitle);
        txtVisualStatus = findViewById(R.id.txtVisualStatus);
        visualsVideoView = findViewById(R.id.visualsVideoView);

        // Live Station Info
        liveBadge = findViewById(R.id.txtLiveBadge);
        nowPlaying = findViewById(R.id.txtNowPlaying);
        artist = findViewById(R.id.txtArtist);
        listeners = findViewById(R.id.txtListeners);
        connectionStatus = findViewById(R.id.txtConnectionStatus);
        playPause = findViewById(R.id.btnPlayPause);
        retry = findViewById(R.id.btnRetryStream);

        // Chat
        txtChatStatus = findViewById(R.id.txtChatStatus);
        txtChatUsersCount = findViewById(R.id.txtChatUsersCount);
        recyclerChatMessages = findViewById(R.id.recyclerChatMessages);
        editChatMessage = findViewById(R.id.editChatMessage);
        btnSendMessage = findViewById(R.id.btnSendMessage);

        ImageButton btnSettings = findViewById(R.id.btnSettings);
        btnSettings.setOnClickListener(v -> startActivity(new Intent(this, SettingsActivity.class)));

        Button btnWebsite = findViewById(R.id.btnWebsite);
        btnWebsite.setOnClickListener(v -> openExternal("https://allthings140radio.online/"));

        Button btnVisuals = findViewById(R.id.btnVisuals);
        btnVisuals.setOnClickListener(v -> openStationPage(
                "https://allthings140radio.online/visuals/", getString(R.string.web_visuals)));
    }

    private void setupNavigation() {
        navTabRadio.setOnClickListener(v -> selectTab(Tab.RADIO));
        navTabChat.setOnClickListener(v -> selectTab(Tab.CHAT));
        selectTab(Tab.RADIO);
    }

    private void selectTab(Tab tab) {
        currentTab = tab;
        if (tab == Tab.RADIO) {
            scrollRadio.setVisibility(View.VISIBLE);
            layoutChat.setVisibility(View.GONE);

            navTabRadio.setSelected(true);
            navTabChat.setSelected(false);
            imgTabRadioIcon.setColorFilter(ContextCompat.getColor(this, R.color.orange));
            txtTabRadioLabel.setTextColor(ContextCompat.getColor(this, R.color.white));
            imgTabChatIcon.setColorFilter(ContextCompat.getColor(this, R.color.muted));
            txtTabChatLabel.setTextColor(ContextCompat.getColor(this, R.color.muted));

            if (activityStarted && visualsVideoView != null) {
                visualsVideoView.startPlayback();
            }
        } else {
            scrollRadio.setVisibility(View.GONE);
            layoutChat.setVisibility(View.VISIBLE);

            navTabRadio.setSelected(false);
            navTabChat.setSelected(true);
            imgTabRadioIcon.setColorFilter(ContextCompat.getColor(this, R.color.muted));
            txtTabRadioLabel.setTextColor(ContextCompat.getColor(this, R.color.muted));
            imgTabChatIcon.setColorFilter(ContextCompat.getColor(this, R.color.purple_neon));
            txtTabChatLabel.setTextColor(ContextCompat.getColor(this, R.color.white));

            if (visualsVideoView != null) {
                visualsVideoView.pausePlayback();
            }

            if (chatClient != null && !chatClient.isConnected()) {
                chatClient.connect();
            }
        }
    }

    private void setupRadioControls() {
        playPause.setOnClickListener(v -> togglePlayback());
        retry.setOnClickListener(v -> retryPlayback());
    }

    private void setupChatControls() {
        LinearLayoutManager lm = new LinearLayoutManager(this);
        lm.setStackFromEnd(true);
        recyclerChatMessages.setLayoutManager(lm);

        chatAdapter = new ChatAdapter(this);
        Set<String> blocked = prefs.getStringSet(PREF_BLOCKED_USERS, new HashSet<>());
        chatAdapter.setBlockedUsers(blocked);
        chatAdapter.setActionCallback(this::showMessageOptionsDialog);
        recyclerChatMessages.setAdapter(chatAdapter);

        chatClient = new ChatClient();
        chatClient.setAccessToken(authClient.accessToken());
        String savedName = prefs.getString(PREF_CHAT_NAME, "");
        String savedColor = prefs.getString(PREF_CHAT_COLOR, "purple");
        chatClient.setProfile(savedName, savedColor);

        chatClient.setListener(new ChatClient.Listener() {
            @Override
            public void onConnectionState(String stateText, boolean isOnline) {
                txtChatStatus.setText(stateText);
                txtChatStatus.setTextColor(ContextCompat.getColor(MainActivity.this,
                        isOnline ? R.color.green_neon : R.color.orange));
            }

            @Override
            public void onHistoryLoaded(List<ChatMessage> messages, int presenceCount, String assignedName) {
                chatAdapter.setMessages(messages);
                scrollChatToEndIfNeeded(false);
                updatePresenceUi(presenceCount);
                if (savedName.isEmpty() && !assignedName.isEmpty()) {
                    prefs.edit().putString(PREF_CHAT_NAME, assignedName).apply();
                    chatClient.setProfile(assignedName, savedColor);
                }
            }

            @Override
            public void onNewMessage(ChatMessage message) {
                chatAdapter.addMessage(message);
                scrollChatToEndIfNeeded(true);
            }

            @Override
            public void onPresenceUpdate(int count) {
                updatePresenceUi(count);
            }

            @Override
            public void onReactionsUpdate(String trackId, Map<String, Integer> reactions) {
            }

            @Override
            public void onChatCleared() {
                chatAdapter.clearMessages();
                chatAdapter.addMessage(ChatMessage.systemNotice(getString(R.string.chat_moderation_cleared)));
            }

            @Override
            public void onMessageDeleted(String messageId) {
                chatAdapter.removeMessage(messageId);
            }

            @Override
            public void onErrorNotice(String message) {
                Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show();
            }

            @Override public void onTermsRequired() { showTermsGate(); }
        });

        btnSendMessage.setOnClickListener(v -> submitChatMessage());
        editChatMessage.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                submitChatMessage();
                return true;
            }
            return false;
        });

        findViewById(R.id.btnChatProfile).setOnClickListener(v -> showProfileDialog());
        findViewById(R.id.btnChatRules).setOnClickListener(v -> showRulesDialog());

        // Quick reactions
        findViewById(R.id.btnReactFire).setOnClickListener(v -> sendQuickReaction("fire"));
        findViewById(R.id.btnReactSkull).setOnClickListener(v -> sendQuickReaction("skull"));
        findViewById(R.id.btnReactHeart).setOnClickListener(v -> sendQuickReaction("heart"));
        findViewById(R.id.btnReactBolt).setOnClickListener(v -> sendQuickReaction("bolt"));
        findViewById(R.id.btnReactBass).setOnClickListener(v -> sendQuickReaction("bass"));
    }

    private void scrollChatToEndIfNeeded(boolean smooth) {
        if (recyclerChatMessages == null || chatAdapter == null) return;
        int count = chatAdapter.getItemCount();
        if (count <= 0) return;
        int last = count - 1;
        if (smooth) recyclerChatMessages.smoothScrollToPosition(last);
        else recyclerChatMessages.scrollToPosition(last);
    }

    private void updatePresenceUi(int count) {
        if (txtChatUsersCount != null) {
            txtChatUsersCount.setText(getString(R.string.chat_users_count, Math.max(1, count)));
        }
    }

    private void submitChatMessage() {
        String text = editChatMessage.getText().toString().trim();
        if (text.isEmpty()) return;

        String currentName = prefs.getString(PREF_CHAT_NAME, "");
        if (currentName.isEmpty() && !chatClient.isAuthenticated()) {
            showProfileDialog();
            return;
        }

        if (!chatClient.isConnected()) {
            chatClient.connect();
        }

        chatClient.sendMessage(text);
        editChatMessage.setText("");
    }

    private void sendQuickReaction(String reaction) {
        if (!chatClient.isConnected()) chatClient.connect();
        chatClient.sendReaction(reaction, currentTrackId);
        Toast.makeText(this, "Sent " + reaction, Toast.LENGTH_SHORT).show();
    }

    private void showProfileDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        View view = LayoutInflater.from(this).inflate(R.layout.dialog_chat_profile, null);
        builder.setView(view);
        AlertDialog dialog = builder.create();

        EditText editName = view.findViewById(R.id.editProfileName);
        String currentName = prefs.getString(PREF_CHAT_NAME, "");
        String currentColor = prefs.getString(PREF_CHAT_COLOR, "purple");
        editName.setText(currentName);

        final String[] selectedColor = { currentColor };
        view.findViewById(R.id.btnColorPurple).setOnClickListener(v -> selectedColor[0] = "purple");
        view.findViewById(R.id.btnColorCyan).setOnClickListener(v -> selectedColor[0] = "cyan");
        view.findViewById(R.id.btnColorPink).setOnClickListener(v -> selectedColor[0] = "pink");
        view.findViewById(R.id.btnColorGreen).setOnClickListener(v -> selectedColor[0] = "green");
        view.findViewById(R.id.btnColorOrange).setOnClickListener(v -> selectedColor[0] = "orange");

        view.findViewById(R.id.btnProfileCancel).setOnClickListener(v -> dialog.dismiss());
        view.findViewById(R.id.btnProfileSave).setOnClickListener(v -> {
            String name = editName.getText().toString().trim();
            if (!name.isEmpty()) {
                prefs.edit()
                        .putString(PREF_CHAT_NAME, name)
                        .putString(PREF_CHAT_COLOR, selectedColor[0])
                        .apply();
                chatClient.setProfile(name, selectedColor[0]);
                dialog.dismiss();
            } else {
                Toast.makeText(this, "Please enter a display name", Toast.LENGTH_SHORT).show();
            }
        });

        dialog.show();
    }

    private void showRulesDialog() {
        new AlertDialog.Builder(this)
                .setTitle(R.string.chat_rules_title)
                .setMessage(R.string.chat_rules_body)
                .setPositiveButton(R.string.chat_close, (d, w) -> d.dismiss())
                .show();
    }

    private void showMessageOptionsDialog(ChatMessage msg) {
        if (msg.isNotice) return;

        CharSequence[] options = new CharSequence[] {
                getString(R.string.chat_copy),
                getString(R.string.chat_report),
                getString(R.string.chat_block)
        };

        new AlertDialog.Builder(this)
                .setTitle("Message from " + msg.name)
                .setItems(options, (dialog, which) -> {
                    if (which == 0) {
                        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                        ClipData clip = ClipData.newPlainText("Chat message", msg.text);
                        cm.setPrimaryClip(clip);
                        Toast.makeText(this, "Copied to clipboard", Toast.LENGTH_SHORT).show();
                    } else if (which == 1) {
                        chatClient.sendReport(msg.id, "other");
                        chatAdapter.reportMessage(msg.id);
                        Toast.makeText(this, R.string.chat_msg_reported, Toast.LENGTH_LONG).show();
                    } else if (which == 2) {
                        if (chatClient.isAuthenticated() && !msg.senderId.isEmpty()) chatClient.sendBlock(msg.senderId);
                        String lowerName = msg.name.trim().toLowerCase(java.util.Locale.ROOT);
                        Set<String> set = new HashSet<>(prefs.getStringSet(PREF_BLOCKED_USERS, new HashSet<>()));
                        set.add(lowerName);
                        prefs.edit().putStringSet(PREF_BLOCKED_USERS, set).apply();
                        chatAdapter.blockUser(msg.name);
                        chatAdapter.blockUserId(msg.senderId);
                        Toast.makeText(this, R.string.chat_user_blocked, Toast.LENGTH_LONG).show();
                    }
                })
                .show();
    }

    private void showTermsGate() {
        new AlertDialog.Builder(this)
                .setTitle("Green Room Terms")
                .setMessage("Read the current Community Rules before posting.")
                .setNegativeButton("NOT NOW", (d, w) -> d.dismiss())
                .setPositiveButton("I AGREE — ENTER GREEN ROOM", (d, w) -> chatClient.sendTermsAccept())
                .show();
    }

    @Override protected void onStart() {
        super.onStart();
        activityStarted = true;
        connectController();
        startStatusPolling();
        if (chatClient != null && currentTab == Tab.CHAT) {
            chatClient.connect();
        }
        if (visualsVideoView != null && currentTab == Tab.RADIO) {
            visualsVideoView.startPlayback();
        }
    }

    @Override protected void onResume() {
        super.onResume();
        if (authClient != null && authClient.signedIn()) {
            authClient.refreshSession((ok, message) -> {
                if (ok && chatClient != null) runOnUiThread(() -> {
                    chatClient.setAccessToken(authClient.accessToken());
                    chatClient.connect();
                });
            });
        }
        if (chatClient != null && !authClient.accessToken().equals(chatClient.getAccessToken())) {
            chatClient.setAccessToken(authClient.accessToken());
            if (chatClient.isConnected()) chatClient.disconnect();
            if (currentTab == Tab.CHAT) chatClient.connect();
        }
        if (visualsVideoView != null && currentTab == Tab.RADIO) {
            visualsVideoView.startPlayback();
        }
    }

    @Override protected void onPause() {
        if (visualsVideoView != null) {
            visualsVideoView.pausePlayback();
        }
        super.onPause();
    }

    @Override protected void onStop() {
        activityStarted = false;
        stopStatusPolling();
        if (visualsVideoView != null) {
            visualsVideoView.pausePlayback();
        }
        if (controller != null) controller.removeListener(playerListener);
        if (controllerFuture != null) {
            MediaController.releaseFuture(controllerFuture);
            controllerFuture = null;
        }
        controller = null;
        super.onStop();
    }

    private void connectController() {
        if (controllerFuture != null || controller != null) return;
        connectionStatus.setText(R.string.playback_connecting);
        SessionToken token = new SessionToken(this, new ComponentName(this, RadioService.class));
        ListenableFuture<MediaController> future = new MediaController.Builder(this, token).buildAsync();
        controllerFuture = future;
        Futures.addCallback(future, new FutureCallback<MediaController>() {
            @Override public void onSuccess(MediaController result) {
                if (!activityStarted || controllerFuture != future) {
                    MediaController.releaseFuture(future);
                    return;
                }
                controller = result;
                controller.addListener(playerListener);
                updateMetadata(controller.getMediaMetadata());
                updatePlaybackUi();
            }

            @Override public void onFailure(Throwable throwable) {
                if (controllerFuture == future) controllerFuture = null;
                if (!activityStarted) return;
                connectionStatus.setText(R.string.playback_unavailable);
                retry.setVisibility(View.VISIBLE);
                updatePlaybackUi();
            }
        }, command -> runOnUiThread(command));
    }

    private void togglePlayback() {
        if (controller == null) {
            connectController();
            return;
        }
        if (controller.isPlaying()) {
            controller.pause();
            return;
        }
        ensureLiveItem();
        controller.prepare();
        controller.play();
    }

    private void retryPlayback() {
        retry.setVisibility(View.GONE);
        if (controller == null) {
            connectController();
            return;
        }
        ensureLiveItem();
        controller.prepare();
        controller.play();
    }

    private void ensureLiveItem() {
        if (controller.getMediaItemCount() == 0) {
            controller.setMediaItem(new MediaItem.Builder().setMediaId(LIVE_MEDIA_ID).build());
        }
    }

    private void updatePlaybackUi() {
        boolean connected = controller != null && controller.isConnected();
        boolean isPlaying = connected && controller.isPlaying();
        int state = connected ? controller.getPlaybackState() : Player.STATE_IDLE;

        if (playPause == null) return;
        playPause.setEnabled(connected);
        playPause.setText(isPlaying ? R.string.pause_live : R.string.play_live);
        liveBadge.setText(isPlaying ? R.string.live_on_air : R.string.live_ready);
        liveBadge.setActivated(isPlaying);

        if (txtVisualStatus != null) {
            txtVisualStatus.setText(isPlaying ? R.string.live_transmission : R.string.ready_for_transmission);
            txtVisualStatus.setTextColor(ContextCompat.getColor(this, isPlaying ? R.color.green_neon : R.color.purple_neon));
        }

        if (!connected) {
            connectionStatus.setText(R.string.playback_connecting);
        } else if (state == Player.STATE_BUFFERING) {
            connectionStatus.setText(R.string.playback_buffering);
        } else if (isPlaying) {
            connectionStatus.setText(R.string.playback_live);
            retry.setVisibility(View.GONE);
        } else if (state == Player.STATE_READY) {
            connectionStatus.setText(R.string.playback_paused);
        } else {
            connectionStatus.setText(R.string.playback_ready);
        }
    }

    private void updateMetadata(MediaMetadata metadata) {
        if (nowPlaying == null) return;
        String title = metadata != null && metadata.title != null ? metadata.title.toString().trim() : "";
        String artistName = metadata != null && metadata.artist != null ? metadata.artist.toString().trim() : "";

        if (title.isEmpty() || title.equalsIgnoreCase("LIVE RADIO")) title = latestApiTitle;
        if (artistName.isEmpty() || artistName.startsWith("ALLTHINGS140")) artistName = latestApiArtist;
        if (title.isEmpty()) title = getString(R.string.default_track_title);
        if (artistName.isEmpty()) artistName = getString(R.string.default_track_artist);

        nowPlaying.setText(title);
        artist.setText(artistName);
        if (txtVisualTrackTitle != null) {
            txtVisualTrackTitle.setText(title);
        }
    }

    private void startStatusPolling() {
        if (pollingStatus) return;
        pollingStatus = true;
        mainHandler.post(statusPollRunnable);
    }

    private void stopStatusPolling() {
        pollingStatus = false;
        mainHandler.removeCallbacks(statusPollRunnable);
    }

    private void applyStationStatus(StationStatusClient.Status status) {
        if (status == null) return;
        if (!status.title.isEmpty()) {
            latestApiTitle = status.title;
            currentTrackId = status.title;
        }
        if (!status.artist.isEmpty()) latestApiArtist = status.artist;
        listeners.setText(status.listeners >= 0
                ? getResources().getQuantityString(R.plurals.listener_count, status.listeners, status.listeners)
                : getString(status.online ? R.string.station_online : R.string.station_status_unknown));
        if (controller != null) updateMetadata(controller.getMediaMetadata());
    }

    private void openExternal(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception ignored) {
            Toast.makeText(this, R.string.unable_to_open_link, Toast.LENGTH_SHORT).show();
        }
    }

    private void openStationPage(String url, String title) {
        Intent intent = new Intent(this, RadioSiteActivity.class);
        intent.putExtra(RadioSiteActivity.EXTRA_URL, url);
        intent.putExtra(RadioSiteActivity.EXTRA_TITLE, title);
        startActivity(intent);
    }

    private void applyWindowInsets() {
        final int barLeft = topBar.getPaddingLeft();
        final int barTop = topBar.getPaddingTop();
        final int barRight = topBar.getPaddingRight();
        final int barBottom = topBar.getPaddingBottom();
        final View bottomNav = findViewById(R.id.mainBottomNav);
        final int navBottom = bottomNav.getPaddingBottom();

        root.setOnApplyWindowInsetsListener((v, insets) -> {
            int left;
            int top;
            int right;
            int bottom;
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets systemBars = insets.getInsets(
                        WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars() | WindowInsets.Type.displayCutout());
                left = systemBars.left;
                top = systemBars.top;
                right = systemBars.right;
                bottom = systemBars.bottom;
            } else {
                left = insets.getSystemWindowInsetLeft();
                top = insets.getSystemWindowInsetTop();
                right = insets.getSystemWindowInsetRight();
                bottom = insets.getSystemWindowInsetBottom();
            }
            topBar.setPadding(barLeft + left, barTop + top, barRight + right, barBottom);
            bottomNav.setPadding(barLeft + left, bottomNav.getPaddingTop(), barRight + right, navBottom + bottom);
            return insets;
        });
        root.requestApplyInsets();
    }

    @Override protected void onDestroy() {
        stopStatusPolling();
        statusExecutor.shutdownNow();
        if (chatClient != null) {
            chatClient.disconnect();
            chatClient = null;
        }
        if (visualsVideoView != null) {
            visualsVideoView.releasePlayer();
        }
        super.onDestroy();
    }
}
