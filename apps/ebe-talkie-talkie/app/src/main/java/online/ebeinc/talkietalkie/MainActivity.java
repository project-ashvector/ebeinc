package online.ebeinc.talkietalkie;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int MIC_PERMISSION_REQUEST = 140;
    private static final int NOTIFICATION_PERMISSION_REQUEST = 141;
    private static final int PREFERRED_PORT = 17777;
    private static final String PREFS = "ebe_talkie_talkie";
    private static final String DEFAULT_ROOM = "EBE-9WEN-F9H9-8EP3";

    private WebView webView;
    private LocalAssetServer localServer;
    private SharedPreferences prefs;
    private AudioManager audioManager;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(0xFF0A0710);
        getWindow().setNavigationBarColor(0xFF0A0710);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        audioManager = (AudioManager) getSystemService(Context.AUDIO_SERVICE);

        webView = new WebView(this);
        webView.setBackgroundColor(0xFF0A0710);
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
        setContentView(webView);

        configureWebView();
        startLocalPage();
        requestMicrophonePermissionIfNeeded();
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString() + " EBE-Talkie-Talkie/0.2.1");

        webView.addJavascriptInterface(new AndroidBridge(), "EBEAndroid");
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> {
                    String origin = request.getOrigin() == null ? "" : request.getOrigin().toString();
                    if (!origin.startsWith("http://127.0.0.1:") && !origin.startsWith("http://localhost:")) {
                        request.deny();
                        return;
                    }

                    boolean wantsAudio = false;
                    for (String resource : request.getResources()) {
                        if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) {
                            wantsAudio = true;
                            break;
                        }
                    }

                    if (wantsAudio && checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                        request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                    } else {
                        request.deny();
                        if (wantsAudio) requestMicrophonePermissionIfNeeded();
                    }
                });
            }
        });
    }

    private void startLocalPage() {
        try {
            localServer = new LocalAssetServer(this, PREFERRED_PORT);
            localServer.start();
            webView.loadUrl("http://127.0.0.1:" + localServer.getPort() + "/");
        } catch (IOException first) {
            try {
                localServer = new LocalAssetServer(this, 0);
                localServer.start();
                webView.loadUrl("http://127.0.0.1:" + localServer.getPort() + "/");
            } catch (IOException second) {
                Toast.makeText(this, "Unable to start EBE Talkie Talkie", Toast.LENGTH_LONG).show();
            }
        }
    }

    private void requestMicrophonePermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M &&
                checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, MIC_PERMISSION_REQUEST);
        }
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFICATION_PERMISSION_REQUEST);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == MIC_PERMISSION_REQUEST) {
            boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
            if (!granted) {
                Toast.makeText(this, "Microphone permission is required to talk.", Toast.LENGTH_LONG).show();
            } else if (webView != null) {
                webView.evaluateJavascript("window.ebeMicPermissionChanged && window.ebeMicPermissionChanged(true);", null);
            }
        }
    }

    @Override
    protected void onDestroy() {
        setCommunicationAudio(false);
        if (localServer != null) localServer.stop();
        if (webView != null) {
            webView.removeJavascriptInterface("EBEAndroid");
            webView.destroy();
        }
        super.onDestroy();
    }

    private void setCommunicationAudio(boolean enabled) {
        if (audioManager == null) return;
        try {
            if (enabled) {
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
            } else {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    audioManager.clearCommunicationDevice();
                } else {
                    audioManager.setSpeakerphoneOn(false);
                }
                audioManager.setMode(AudioManager.MODE_NORMAL);
            }
        } catch (Exception ignored) {
        }
    }

    private void startListeningService() {
        requestNotificationPermissionIfNeeded();
        Intent intent = new Intent(this, TalkieListeningService.class).setAction(TalkieListeningService.ACTION_ARM);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent);
        else startService(intent);
    }

    private void stopListeningService() {
        stopService(new Intent(this, TalkieListeningService.class));
    }

    public final class AndroidBridge {
        @JavascriptInterface
        public String getDeviceId() {
            String id = prefs.getString("device_id", null);
            if (id == null) {
                id = UUID.randomUUID().toString();
                prefs.edit().putString("device_id", id).apply();
            }
            return id;
        }

        @JavascriptInterface
        public String getDefaultRoom() {
            return prefs.getString("room", DEFAULT_ROOM);
        }

        @JavascriptInterface
        public void saveRoom(String room) {
            if (room == null) return;
            room = room.trim().toUpperCase();
            if (room.length() >= 8 && room.length() <= 64) {
                prefs.edit().putString("room", room).apply();
            }
        }

        @JavascriptInterface
        public String getSavedName() {
            return prefs.getString("name", "");
        }

        @JavascriptInterface
        public void saveName(String name) {
            if (name == null) return;
            name = name.trim();
            if (name.length() > 32) name = name.substring(0, 32);
            prefs.edit().putString("name", name).apply();
        }

        @JavascriptInterface
        public boolean shouldAutoConnect() {
            return prefs.getBoolean("auto_connect", false);
        }

        @JavascriptInterface
        public void setAutoConnect(boolean enabled) {
            prefs.edit().putBoolean("auto_connect", enabled).apply();
        }

        @JavascriptInterface
        public boolean hasMicPermission() {
            return checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
        }

        @JavascriptInterface
        public void requestMicPermission() {
            runOnUiThread(MainActivity.this::requestMicrophonePermissionIfNeeded);
        }

        @JavascriptInterface
        public void setCommunicationMode(boolean enabled) {
            runOnUiThread(() -> setCommunicationAudio(enabled));
        }

        @JavascriptInterface
        public void startBackgroundListening() {
            runOnUiThread(() -> {
                prefs.edit().putBoolean("auto_connect", true).apply();
                startListeningService();
            });
        }

        @JavascriptInterface
        public void stopBackgroundListening() {
            runOnUiThread(() -> {
                prefs.edit().putBoolean("auto_connect", false).apply();
                stopListeningService();
            });
        }

        @JavascriptInterface
        public void shareRoom(String room) {
            final String safeRoom = room == null ? DEFAULT_ROOM : room.trim().toUpperCase();
            runOnUiThread(() -> {
                Intent send = new Intent(Intent.ACTION_SEND);
                send.setType("text/plain");
                send.putExtra(Intent.EXTRA_SUBJECT, "EBE Talkie Talkie family channel");
                send.putExtra(Intent.EXTRA_TEXT,
                        "Join me on EBE Talkie Talkie. Use family room code: " + safeRoom +
                                "\nInstall the EBE Talkie Talkie APK, enter your name, use this code, and connect.");
                startActivity(Intent.createChooser(send, "Share EBE Talkie Talkie room"));
            });
        }

        @JavascriptInterface
        public void buzz(int millis) {
            int duration = Math.max(10, Math.min(250, millis));
            Vibrator vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            if (vibrator == null || !vibrator.hasVibrator()) return;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(duration, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                vibrator.vibrate(duration);
            }
        }

        @JavascriptInterface
        public void beep(int kind) {
            final int tone = kind == 2 ? ToneGenerator.TONE_PROP_ACK : ToneGenerator.TONE_PROP_BEEP;
            final int duration = kind == 2 ? 70 : 45;
            runOnUiThread(() -> {
                ToneGenerator generator = new ToneGenerator(AudioManager.STREAM_MUSIC, 55);
                generator.startTone(tone, duration);
                webView.postDelayed(generator::release, duration + 80L);
            });
        }
    }

    private static final class LocalAssetServer {
        private final Context context;
        private final ServerSocket serverSocket;
        private final ExecutorService executor = Executors.newCachedThreadPool();
        private volatile boolean running;

        LocalAssetServer(Context context, int port) throws IOException {
            this.context = context.getApplicationContext();
            this.serverSocket = new ServerSocket(port, 8, InetAddress.getByName("127.0.0.1"));
        }

        int getPort() {
            return serverSocket.getLocalPort();
        }

        void start() {
            running = true;
            executor.execute(() -> {
                while (running) {
                    try {
                        Socket socket = serverSocket.accept();
                        executor.execute(() -> handle(socket));
                    } catch (IOException e) {
                        if (running) e.printStackTrace();
                    }
                }
            });
        }

        void stop() {
            running = false;
            try { serverSocket.close(); } catch (IOException ignored) {}
            executor.shutdownNow();
        }

        private void handle(Socket socket) {
            try (Socket client = socket;
                 BufferedInputStream in = new BufferedInputStream(client.getInputStream());
                 BufferedOutputStream out = new BufferedOutputStream(client.getOutputStream())) {

                readRequestHead(in);
                byte[] body = readAsset("index.html");
                String headers = "HTTP/1.1 200 OK\r\n" +
                        "Content-Type: text/html; charset=utf-8\r\n" +
                        "Content-Length: " + body.length + "\r\n" +
                        "Cache-Control: no-store\r\n" +
                        "X-Content-Type-Options: nosniff\r\n" +
                        "Connection: close\r\n\r\n";
                out.write(headers.getBytes(StandardCharsets.US_ASCII));
                out.write(body);
                out.flush();
            } catch (IOException ignored) {
            }
        }

        private void readRequestHead(InputStream in) throws IOException {
            int previous = -1;
            int current;
            int matched = 0;
            while ((current = in.read()) != -1) {
                if ((previous == '\r' && current == '\n') || current == '\n') {
                    matched++;
                    if (matched >= 2) break;
                } else if (current != '\r') {
                    matched = 0;
                }
                previous = current;
            }
        }

        private byte[] readAsset(String name) throws IOException {
            try (InputStream asset = context.getAssets().open(name);
                 ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
                byte[] chunk = new byte[8192];
                int read;
                while ((read = asset.read(chunk)) != -1) {
                    buffer.write(chunk, 0, read);
                }
                return buffer.toByteArray();
            }
        }
    }
}
