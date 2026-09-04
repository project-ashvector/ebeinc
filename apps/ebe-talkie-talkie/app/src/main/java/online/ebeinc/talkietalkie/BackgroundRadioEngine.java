package online.ebeinc.talkietalkie;

import android.content.Context;
import android.util.Base64;

import org.json.JSONObject;
import org.webrtc.AudioTrack;
import org.webrtc.DataChannel;
import org.webrtc.IceCandidate;
import org.webrtc.MediaConstraints;
import org.webrtc.MediaStream;
import org.webrtc.MediaStreamTrack;
import org.webrtc.PeerConnection;
import org.webrtc.PeerConnectionFactory;
import org.webrtc.RtpReceiver;
import org.webrtc.RtpTransceiver;
import org.webrtc.SdpObserver;
import org.webrtc.SessionDescription;
import org.webrtc.audio.AudioDeviceModule;
import org.webrtc.audio.JavaAudioDeviceModule;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.PBEKeySpec;
import javax.crypto.spec.SecretKeySpec;

import okio.ByteString;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * Receive-only native WebRTC engine used while the Activity is not visible.
 *
 * The visible Activity keeps the existing proven WebView PTT implementation.
 * When Android stops the Activity, the app tears that connection down and this
 * engine takes over the same device ID and room code. No microphone capture is
 * started here, so Android's background microphone restrictions do not apply.
 */
public final class BackgroundRadioEngine {
    public interface Listener {
        void onReady();
        void onDisconnected(String reason);
        void onTalker(String name);
        void onTalkerStopped();
        void onPeerCount(int count);
    }

    private static final String BROKER = "wss://test.mosquitto.org:8081/mqtt";
    private static final String ROOM_SALT = "EBE-Talkie-Talkie-v1";
    private static final int ROOM_KEY_ITERATIONS = 150_000;
    private static final SecureRandom RANDOM = new SecureRandom();

    private static final Object INIT_LOCK = new Object();
    private static volatile boolean WEBRTC_INITIALIZED = false;

    private final Context context;
    private final Listener listener;
    private final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor();
    private final OkHttpClient http = new OkHttpClient.Builder()
            .pingInterval(0, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build();
    private final Map<String, PeerState> peers = new HashMap<>();

    private String roomCode;
    private String myId;
    private String myName;
    private String topic;
    private SecretKey roomKey;

    private PeerConnectionFactory factory;
    private AudioDeviceModule audioDeviceModule;
    private WebSocket socket;
    private volatile boolean running;
    private volatile boolean mqttReady;
    private int packetId = 1;
    private int reconnectAttempt;
    private ScheduledFuture<?> keepAliveTask;
    private ScheduledFuture<?> helloTask;
    private ScheduledFuture<?> reapTask;
    private ScheduledFuture<?> reconnectTask;

    public BackgroundRadioEngine(Context context, Listener listener) {
        this.context = context.getApplicationContext();
        this.listener = listener;
    }

    public synchronized void start(String roomCode, String myId, String myName) {
        if (running && roomCode != null && roomCode.equals(this.roomCode)
                && myId != null && myId.equals(this.myId)) {
            return;
        }
        stopInternal(false);
        try {
            this.roomCode = roomCode == null ? "" : roomCode.trim().toUpperCase(Locale.US);
            this.myId = myId == null ? "" : myId.trim();
            this.myName = myName == null || myName.trim().isEmpty() ? "Radio" : myName.trim();
            if (this.roomCode.length() < 8 || this.myId.isEmpty()) {
                listener.onDisconnected("No active room");
                return;
            }
            this.topic = "ebe-talkie-talkie/v1/" + sha256Hex(this.roomCode).substring(0, 40);
            this.roomKey = deriveRoomKey(this.roomCode);
            running = true;
            initWebRtc();
            connectBroker();
        } catch (Exception e) {
            running = false;
            listener.onDisconnected("Background radio init failed");
        }
    }

    public synchronized void stop() {
        stopInternal(true);
    }

    public synchronized boolean isRunning() {
        return running;
    }

    private void stopInternal(boolean sendBye) {
        boolean wasRunning = running;
        running = false;
        mqttReady = false;
        cancel(reconnectTask);
        cancel(keepAliveTask);
        cancel(helloTask);
        cancel(reapTask);
        reconnectTask = keepAliveTask = helloTask = reapTask = null;

        if (sendBye && wasRunning) {
            try { publishSignal(new JSONObject().put("type", "bye")); } catch (Exception ignored) {}
        }

        if (socket != null) {
            try { socket.send(ByteString.of(new byte[]{(byte) 0xE0, 0x00})); } catch (Exception ignored) {}
            try { socket.close(1000, "handoff"); } catch (Exception ignored) {}
            socket = null;
        }

        synchronized (peers) {
            for (PeerState peer : peers.values()) {
                try { peer.pc.close(); } catch (Exception ignored) {}
                try { peer.pc.dispose(); } catch (Exception ignored) {}
            }
            peers.clear();
        }

        if (factory != null) {
            try { factory.dispose(); } catch (Exception ignored) {}
            factory = null;
        }
        if (audioDeviceModule != null) {
            try { audioDeviceModule.release(); } catch (Exception ignored) {}
            audioDeviceModule = null;
        }
        if (wasRunning) listener.onPeerCount(0);
    }

    public void shutdown() {
        stop();
        executor.shutdownNow();
        http.dispatcher().executorService().shutdown();
        http.connectionPool().evictAll();
    }

    private void initWebRtc() {
        synchronized (INIT_LOCK) {
            if (!WEBRTC_INITIALIZED) {
                PeerConnectionFactory.initialize(
                        PeerConnectionFactory.InitializationOptions.builder(context)
                                .setEnableInternalTracer(false)
                                .createInitializationOptions()
                );
                WEBRTC_INITIALIZED = true;
            }
        }

        audioDeviceModule = JavaAudioDeviceModule.builder(context)
                .setUseHardwareAcousticEchoCanceler(true)
                .setUseHardwareNoiseSuppressor(true)
                .createAudioDeviceModule();

        factory = PeerConnectionFactory.builder()
                .setAudioDeviceModule(audioDeviceModule)
                .createPeerConnectionFactory();
    }

    private void connectBroker() {
        if (!running) return;
        cancel(reconnectTask);

        Request request = new Request.Builder()
                .url(BROKER)
                .header("Sec-WebSocket-Protocol", "mqtt")
                .build();

        socket = http.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket webSocket, Response response) {
                executor.execute(() -> sendRaw(mqttConnectPacket()));
            }

            @Override
            public void onMessage(WebSocket webSocket, ByteString bytes) {
                byte[] raw = bytes.toByteArray();
                executor.execute(() -> parseMqtt(raw));
            }

            @Override
            public void onClosing(WebSocket webSocket, int code, String reason) {
                webSocket.close(code, reason);
            }

            @Override
            public void onClosed(WebSocket webSocket, int code, String reason) {
                executor.execute(() -> handleSocketDown("Signaling reconnecting"));
            }

            @Override
            public void onFailure(WebSocket webSocket, Throwable t, Response response) {
                executor.execute(() -> handleSocketDown("Signaling reconnecting"));
            }
        });
    }

    private void handleSocketDown(String reason) {
        if (!running) return;
        mqttReady = false;
        cancel(keepAliveTask);
        cancel(helloTask);
        keepAliveTask = helloTask = null;
        listener.onDisconnected(reason);
        scheduleReconnect();
    }

    private void scheduleReconnect() {
        if (!running) return;
        cancel(reconnectTask);
        long delay = Math.min(30_000L, 1_000L * (1L << Math.min(reconnectAttempt, 5)));
        reconnectAttempt++;
        reconnectTask = executor.schedule(this::connectBroker, delay, TimeUnit.MILLISECONDS);
    }

    private void onMqttReady() {
        if (!running || mqttReady) return;
        mqttReady = true;
        reconnectAttempt = 0;
        listener.onReady();

        cancel(keepAliveTask);
        cancel(helloTask);
        cancel(reapTask);

        keepAliveTask = executor.scheduleAtFixedRate(
                () -> sendRaw(new byte[]{(byte) 0xC0, 0x00}),
                18, 18, TimeUnit.SECONDS
        );
        helloTask = executor.scheduleAtFixedRate(
                this::sendHello,
                0, 8, TimeUnit.SECONDS
        );
        reapTask = executor.scheduleAtFixedRate(
                this::reapPeers,
                5, 5, TimeUnit.SECONDS
        );
    }

    private void sendHello() {
        try { publishSignal(new JSONObject().put("type", "hello")); } catch (Exception ignored) {}
    }

    private void reapPeers() {
        long cutoff = System.currentTimeMillis() - 28_000L;
        List<String> stale = new ArrayList<>();
        synchronized (peers) {
            for (Map.Entry<String, PeerState> entry : peers.entrySet()) {
                if (entry.getValue().lastSeen < cutoff) stale.add(entry.getKey());
            }
        }
        for (String id : stale) removePeer(id);
    }

    private void parseMqtt(byte[] data) {
        try {
            int i = 0;
            while (i < data.length) {
                int header = data[i++] & 0xFF;
                int multiplier = 1;
                int remaining = 0;
                int digit;
                do {
                    if (i >= data.length) return;
                    digit = data[i++] & 0xFF;
                    remaining += (digit & 127) * multiplier;
                    multiplier *= 128;
                } while ((digit & 128) != 0);

                int end = i + remaining;
                if (end > data.length) return;
                int type = header >> 4;

                if (type == 2) {
                    sendRaw(mqttSubscribePacket(topic));
                } else if (type == 3) {
                    if (i + 2 > end) return;
                    int topicLen = ((data[i] & 0xFF) << 8) | (data[i + 1] & 0xFF);
                    i += 2;
                    if (i + topicLen > end) return;
                    String incomingTopic = new String(data, i, topicLen, StandardCharsets.UTF_8);
                    i += topicLen;
                    String payload = new String(data, i, end - i, StandardCharsets.UTF_8);
                    if (topic.equals(incomingTopic)) onBrokerPayload(payload);
                } else if (type == 9) {
                    onMqttReady();
                }
                i = end;
            }
        } catch (Exception ignored) {
        }
    }

    private void onBrokerPayload(String payload) {
        try {
            JSONObject msg = decryptSignal(payload);
            if (msg == null) return;
            String from = msg.optString("from", "");
            if (from.isEmpty() || from.equals(myId)) return;
            String to = msg.optString("to", "");
            if (!to.isEmpty() && !to.equals(myId)) return;

            String type = msg.optString("type", "");
            String name = msg.optString("name", "Radio");
            PeerState peer = peers.get(from);

            if ("hello".equals(type)) {
                peer = ensurePeer(from, name);
                peer.lastSeen = System.currentTimeMillis();
                peer.name = name;
                if (myId.compareTo(from) < 0) createOffer(peer);
            } else if ("bye".equals(type)) {
                removePeer(from);
            } else if ("offer".equals(type)) {
                peer = ensurePeer(from, name);
                peer.lastSeen = System.currentTimeMillis();
                JSONObject d = msg.optJSONObject("description");
                if (d != null) receiveOffer(peer, d);
            } else if ("answer".equals(type)) {
                peer = ensurePeer(from, name);
                peer.lastSeen = System.currentTimeMillis();
                JSONObject d = msg.optJSONObject("description");
                if (d != null) receiveAnswer(peer, d);
            } else if ("ice".equals(type)) {
                peer = ensurePeer(from, name);
                peer.lastSeen = System.currentTimeMillis();
                JSONObject c = msg.optJSONObject("candidate");
                if (c != null) receiveIce(peer, c);
            } else if ("ptt-start".equals(type)) {
                peer = ensurePeer(from, name);
                peer.lastSeen = System.currentTimeMillis();
                listener.onTalker(name);
            } else if ("ptt-heartbeat".equals(type)) {
                peer = ensurePeer(from, name);
                peer.lastSeen = System.currentTimeMillis();
            } else if ("ptt-stop".equals(type)) {
                listener.onTalkerStopped();
            }
        } catch (Exception ignored) {
        }
    }

    private PeerState ensurePeer(String id, String name) {
        synchronized (peers) {
            PeerState existing = peers.get(id);
            if (existing != null) {
                existing.lastSeen = System.currentTimeMillis();
                if (name != null && !name.isEmpty()) existing.name = name;
                return existing;
            }

            List<PeerConnection.IceServer> iceServers = Arrays.asList(
                    PeerConnection.IceServer.builder("stun:stun.l.google.com:19302").createIceServer(),
                    PeerConnection.IceServer.builder("stun:stun1.l.google.com:19302").createIceServer(),
                    PeerConnection.IceServer.builder("turn:openrelay.metered.ca:80")
                            .setUsername("openrelayproject").setPassword("openrelayproject").createIceServer(),
                    PeerConnection.IceServer.builder("turn:openrelay.metered.ca:443")
                            .setUsername("openrelayproject").setPassword("openrelayproject").createIceServer(),
                    PeerConnection.IceServer.builder("turns:openrelay.metered.ca:443")
                            .setUsername("openrelayproject").setPassword("openrelayproject").createIceServer()
            );

            PeerConnection.RTCConfiguration config = new PeerConnection.RTCConfiguration(iceServers);
            config.sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN;

            PeerState peer = new PeerState(id, name);
            PeerConnection pc = factory.createPeerConnection(config, new PeerConnection.Observer() {
                @Override public void onSignalingChange(PeerConnection.SignalingState state) {}
                @Override public void onIceConnectionChange(PeerConnection.IceConnectionState state) {}
                @Override public void onIceConnectionReceivingChange(boolean receiving) {}
                @Override public void onIceGatheringChange(PeerConnection.IceGatheringState state) {}

                @Override
                public void onIceCandidate(IceCandidate candidate) {
                    try {
                        JSONObject c = new JSONObject()
                                .put("candidate", candidate.sdp)
                                .put("sdpMid", candidate.sdpMid)
                                .put("sdpMLineIndex", candidate.sdpMLineIndex);
                        JSONObject m = new JSONObject()
                                .put("type", "ice")
                                .put("to", id)
                                .put("candidate", c);
                        publishSignal(m);
                    } catch (Exception ignored) {}
                }

                @Override public void onIceCandidatesRemoved(IceCandidate[] candidates) {}
                @Override public void onAddStream(MediaStream stream) {}
                @Override public void onRemoveStream(MediaStream stream) {}
                @Override public void onDataChannel(DataChannel dataChannel) {}

                @Override
                public void onRenegotiationNeeded() {
                    if (myId.compareTo(id) < 0) executor.execute(() -> {
                        PeerState p = peers.get(id);
                        if (p != null) createOffer(p);
                    });
                }

                @Override
                public void onAddTrack(RtpReceiver receiver, MediaStream[] mediaStreams) {
                    MediaStreamTrack track = receiver.track();
                    if (track instanceof AudioTrack) {
                        track.setEnabled(true);
                    }
                }

                @Override
                public void onConnectionChange(PeerConnection.PeerConnectionState state) {
                    if (state == PeerConnection.PeerConnectionState.FAILED
                            || state == PeerConnection.PeerConnectionState.CLOSED) {
                        executor.schedule(() -> restartPeer(id), 700, TimeUnit.MILLISECONDS);
                    }
                }
            });

            if (pc == null) throw new IllegalStateException("Unable to create peer connection");
            peer.pc = pc;
            peers.put(id, peer);

            try {
                RtpTransceiver.RtpTransceiverInit init =
                        new RtpTransceiver.RtpTransceiverInit(
                                RtpTransceiver.RtpTransceiverDirection.RECV_ONLY
                        );
                pc.addTransceiver(MediaStreamTrack.MediaType.MEDIA_TYPE_AUDIO, init);
            } catch (Exception ignored) {
            }

            listener.onPeerCount(peers.size());
            return peer;
        }
    }

    private void restartPeer(String id) {
        if (!running) return;
        PeerState old;
        synchronized (peers) {
            old = peers.remove(id);
        }
        if (old == null) return;
        String name = old.name;
        try { old.pc.close(); old.pc.dispose(); } catch (Exception ignored) {}
        PeerState fresh = ensurePeer(id, name);
        if (myId.compareTo(id) < 0) createOffer(fresh);
    }

    private void removePeer(String id) {
        PeerState peer;
        synchronized (peers) {
            peer = peers.remove(id);
        }
        if (peer != null) {
            try { peer.pc.close(); } catch (Exception ignored) {}
            try { peer.pc.dispose(); } catch (Exception ignored) {}
        }
        listener.onPeerCount(peers.size());
    }

    private void createOffer(PeerState peer) {
        if (!running || !mqttReady || peer == null || peer.offering) return;
        peer.offering = true;
        peer.pc.createOffer(new SimpleSdpObserver() {
            @Override
            public void onCreateSuccess(SessionDescription description) {
                peer.pc.setLocalDescription(new SimpleSdpObserver() {
                    @Override
                    public void onSetSuccess() {
                        peer.offering = false;
                        try {
                            JSONObject d = new JSONObject()
                                    .put("type", description.type.canonicalForm())
                                    .put("sdp", description.description);
                            publishSignal(new JSONObject()
                                    .put("type", "offer")
                                    .put("to", peer.id)
                                    .put("description", d));
                        } catch (Exception ignored) {}
                    }

                    @Override
                    public void onSetFailure(String error) {
                        peer.offering = false;
                    }
                }, description);
            }

            @Override
            public void onCreateFailure(String error) {
                peer.offering = false;
            }
        }, new MediaConstraints());
    }

    private void receiveOffer(PeerState peer, JSONObject d) {
        try {
            SessionDescription remote = new SessionDescription(
                    SessionDescription.Type.fromCanonicalForm(d.optString("type", "offer")),
                    d.optString("sdp", "")
            );
            peer.pc.setRemoteDescription(new SimpleSdpObserver() {
                @Override
                public void onSetSuccess() {
                    peer.remoteSet = true;
                    flushIce(peer);
                    peer.pc.createAnswer(new SimpleSdpObserver() {
                        @Override
                        public void onCreateSuccess(SessionDescription answer) {
                            peer.pc.setLocalDescription(new SimpleSdpObserver() {
                                @Override
                                public void onSetSuccess() {
                                    try {
                                        JSONObject out = new JSONObject()
                                                .put("type", answer.type.canonicalForm())
                                                .put("sdp", answer.description);
                                        publishSignal(new JSONObject()
                                                .put("type", "answer")
                                                .put("to", peer.id)
                                                .put("description", out));
                                    } catch (Exception ignored) {}
                                }
                            }, answer);
                        }
                    }, new MediaConstraints());
                }

                @Override
                public void onSetFailure(String error) {
                    restartPeer(peer.id);
                }
            }, remote);
        } catch (Exception e) {
            restartPeer(peer.id);
        }
    }

    private void receiveAnswer(PeerState peer, JSONObject d) {
        try {
            SessionDescription remote = new SessionDescription(
                    SessionDescription.Type.fromCanonicalForm(d.optString("type", "answer")),
                    d.optString("sdp", "")
            );
            peer.pc.setRemoteDescription(new SimpleSdpObserver() {
                @Override
                public void onSetSuccess() {
                    peer.remoteSet = true;
                    flushIce(peer);
                }
            }, remote);
        } catch (Exception ignored) {
        }
    }

    private void receiveIce(PeerState peer, JSONObject c) {
        try {
            IceCandidate candidate = new IceCandidate(
                    c.optString("sdpMid", null),
                    c.optInt("sdpMLineIndex", 0),
                    c.optString("candidate", "")
            );
            if (peer.remoteSet) {
                peer.pc.addIceCandidate(candidate);
            } else {
                peer.pendingIce.add(candidate);
            }
        } catch (Exception ignored) {
        }
    }

    private void flushIce(PeerState peer) {
        List<IceCandidate> pending = new ArrayList<>(peer.pendingIce);
        peer.pendingIce.clear();
        for (IceCandidate candidate : pending) {
            try { peer.pc.addIceCandidate(candidate); } catch (Exception ignored) {}
        }
    }

    private void publishSignal(JSONObject msg) {
        if (!running || !mqttReady || socket == null || roomKey == null) return;
        try {
            msg.put("from", myId);
            msg.put("name", myName);
            msg.put("ts", System.currentTimeMillis());
            String encrypted = encryptSignal(msg);
            sendRaw(mqttPublishPacket(topic, encrypted));
        } catch (Exception ignored) {
        }
    }

    private String encryptSignal(JSONObject msg) throws Exception {
        byte[] iv = new byte[12];
        RANDOM.nextBytes(iv);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, roomKey, new GCMParameterSpec(128, iv));
        byte[] encrypted = cipher.doFinal(msg.toString().getBytes(StandardCharsets.UTF_8));
        return new JSONObject()
                .put("v", 1)
                .put("iv", Base64.encodeToString(iv, Base64.NO_WRAP))
                .put("data", Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .toString();
    }

    private JSONObject decryptSignal(String text) {
        try {
            JSONObject box = new JSONObject(text);
            if (box.optInt("v", 0) != 1) return null;
            byte[] iv = Base64.decode(box.getString("iv"), Base64.DEFAULT);
            byte[] data = Base64.decode(box.getString("data"), Base64.DEFAULT);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, roomKey, new GCMParameterSpec(128, iv));
            byte[] plain = cipher.doFinal(data);
            return new JSONObject(new String(plain, StandardCharsets.UTF_8));
        } catch (Exception e) {
            return null;
        }
    }

    private static SecretKey deriveRoomKey(String roomCode) throws Exception {
        PBEKeySpec spec = new PBEKeySpec(
                roomCode.toCharArray(),
                ROOM_SALT.getBytes(StandardCharsets.UTF_8),
                ROOM_KEY_ITERATIONS,
                256
        );
        SecretKeyFactory factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
        byte[] raw = factory.generateSecret(spec).getEncoded();
        spec.clearPassword();
        return new SecretKeySpec(raw, "AES");
    }

    private static String sha256Hex(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256")
                .digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder out = new StringBuilder();
        for (byte b : digest) out.append(String.format(Locale.US, "%02x", b & 0xFF));
        return out.toString();
    }

    private void sendRaw(byte[] data) {
        WebSocket ws = socket;
        if (!running || ws == null) return;
        ws.send(ByteString.of(data));
    }

    private byte[] mqttConnectPacket() {
        try {
            byte[] variable = concat(
                    mqttString("MQTT"),
                    new byte[]{4, 2, 0, 30}
            );
            String clientId = "ebe-bg-" + myId.replace("-", "");
            if (clientId.length() > 22) clientId = clientId.substring(0, 22);
            return mqttPacket(0x10, concat(variable, mqttString(clientId)));
        } catch (Exception e) {
            return new byte[0];
        }
    }

    private byte[] mqttSubscribePacket(String topic) {
        packetId = (packetId % 65535) + 1;
        byte[] id = new byte[]{(byte) ((packetId >> 8) & 0xFF), (byte) (packetId & 0xFF)};
        return mqttPacket(0x82, concat(id, mqttString(topic), new byte[]{0}));
    }

    private byte[] mqttPublishPacket(String topic, String payload) {
        return mqttPacket(0x30, concat(mqttString(topic), payload.getBytes(StandardCharsets.UTF_8)));
    }

    private static byte[] mqttString(String text) {
        byte[] body = text.getBytes(StandardCharsets.UTF_8);
        ByteBuffer out = ByteBuffer.allocate(2 + body.length);
        out.put((byte) ((body.length >> 8) & 0xFF));
        out.put((byte) (body.length & 0xFF));
        out.put(body);
        return out.array();
    }

    private static byte[] mqttPacket(int type, byte[] body) {
        return concat(new byte[]{(byte) type}, remainingLength(body.length), body);
    }

    private static byte[] remainingLength(int value) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int n = value;
        do {
            int digit = n % 128;
            n /= 128;
            if (n > 0) digit |= 0x80;
            out.write(digit);
        } while (n > 0);
        return out.toByteArray();
    }

    private static byte[] concat(byte[]... parts) {
        int len = 0;
        for (byte[] p : parts) len += p.length;
        byte[] out = new byte[len];
        int offset = 0;
        for (byte[] p : parts) {
            System.arraycopy(p, 0, out, offset, p.length);
            offset += p.length;
        }
        return out;
    }

    private static void cancel(ScheduledFuture<?> task) {
        if (task != null) task.cancel(false);
    }

    private static final class PeerState {
        final String id;
        final List<IceCandidate> pendingIce = new ArrayList<>();
        String name;
        PeerConnection pc;
        long lastSeen = System.currentTimeMillis();
        boolean remoteSet;
        boolean offering;

        PeerState(String id, String name) {
            this.id = id;
            this.name = name == null || name.isEmpty() ? "Radio" : name;
        }
    }

    private static class SimpleSdpObserver implements SdpObserver {
        @Override public void onCreateSuccess(SessionDescription sessionDescription) {}
        @Override public void onSetSuccess() {}
        @Override public void onCreateFailure(String error) {}
        @Override public void onSetFailure(String error) {}
    }
}
