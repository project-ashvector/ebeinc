package online.ebeinc.allthings140radio;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

final class StationStatusClient {
    private static final String ICECAST_URL = "https://stream.ebeinc.online/status-json.xsl";
    private static final String STATUS_URL = "https://status.ebeinc.online/api/public/status";
    private static final String FALLBACK_STATUS_URL = "https://allthings140radio.online/api/public/status";

    static final class Status {
        final boolean online;
        final String title;
        final String artist;
        final int listeners;

        Status(boolean online, String title, String artist, int listeners) {
            this.online = online;
            this.title = clean(title);
            this.artist = clean(artist);
            this.listeners = listeners;
        }

        private static String clean(String value) {
            return value == null ? "" : value.trim();
        }
    }

    Status fetch() {
        String icecast = fetchText(ICECAST_URL);
        Status parsedIcecast = parseIcecast(icecast);
        if (parsedIcecast != null) return parsedIcecast;

        String status = fetchText(STATUS_URL);
        if (status == null) status = fetchText(FALLBACK_STATUS_URL);
        Status parsedStatus = parseStatusApi(status);
        return parsedStatus != null ? parsedStatus : new Status(false, "", "", -1);
    }

    private String fetchText(String endpoint) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(endpoint + (endpoint.contains("?") ? "&" : "?") + "t=" + System.currentTimeMillis());
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            connection.setUseCaches(false);
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("User-Agent", "AllThings140RadioAndroid/" + BuildConfig.VERSION_NAME);
            int responseCode = connection.getResponseCode();
            if (responseCode < 200 || responseCode >= 300) return null;
            try (InputStream stream = connection.getInputStream();
                 BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                StringBuilder body = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) body.append(line);
                return body.toString();
            }
        } catch (Exception ignored) {
            return null;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private Status parseIcecast(String body) {
        if (body == null || body.trim().isEmpty()) return null;
        try {
            JSONObject root = new JSONObject(body);
            JSONObject icestats = root.optJSONObject("icestats");
            if (icestats == null) return null;
            Object sourceNode = icestats.opt("source");
            JSONObject source = chooseLiveSource(sourceNode);
            if (source == null) return null;

            int listeners = source.optInt("listeners", -1);
            String title = source.optString("title", "");
            String artist = source.optString("artist", "");
            if (artist.isEmpty() && title.contains(" - ")) {
                int split = title.indexOf(" - ");
                artist = title.substring(0, split).trim();
                title = title.substring(split + 3).trim();
            }
            return new Status(true, title, artist, listeners);
        } catch (JSONException ignored) {
            return null;
        }
    }

    private JSONObject chooseLiveSource(Object node) {
        if (node instanceof JSONObject) return (JSONObject) node;
        if (!(node instanceof JSONArray)) return null;
        JSONArray array = (JSONArray) node;
        JSONObject first = null;
        for (int i = 0; i < array.length(); i++) {
            JSONObject source = array.optJSONObject(i);
            if (source == null) continue;
            if (first == null) first = source;
            String listenUrl = source.optString("listenurl", "");
            if (listenUrl.contains("live.mp3") || listenUrl.endsWith("/live")) return source;
        }
        return first;
    }

    private Status parseStatusApi(String body) {
        if (body == null || body.trim().isEmpty()) return null;
        try {
            JSONObject root = new JSONObject(body);
            boolean online = root.optBoolean("online", root.optBoolean("ok", true));
            int listeners = findInt(root, new String[]{"listeners", "listener_count", "listenerCount", "connected"}, -1);
            String artist = findString(root, new String[]{"artist", "current_artist", "currentArtist"});
            String title = findString(root, new String[]{"track_title", "current_title", "currentTitle", "song", "track"});

            JSONObject nowPlaying = findObject(root, new String[]{"now_playing", "nowPlaying", "current_track", "currentTrack"});
            if (nowPlaying != null) {
                String nestedArtist = findString(nowPlaying, new String[]{"artist", "artist_name", "artistName"});
                String nestedTitle = findString(nowPlaying, new String[]{"title", "song", "track", "name"});
                if (!nestedArtist.isEmpty()) artist = nestedArtist;
                if (!nestedTitle.isEmpty()) title = nestedTitle;
            }

            if (artist.isEmpty() && title.contains(" - ")) {
                int split = title.indexOf(" - ");
                artist = title.substring(0, split).trim();
                title = title.substring(split + 3).trim();
            }
            return new Status(online, title, artist, listeners);
        } catch (JSONException ignored) {
            return null;
        }
    }

    private static String findString(JSONObject object, String[] keys) {
        for (String key : keys) {
            Object value = object.opt(key);
            if (value instanceof String && !((String) value).trim().isEmpty()) return ((String) value).trim();
        }
        return "";
    }

    private static int findInt(JSONObject object, String[] keys, int fallback) {
        for (String key : keys) {
            if (object.has(key)) {
                int value = object.optInt(key, Integer.MIN_VALUE);
                if (value != Integer.MIN_VALUE) return value;
            }
        }
        return fallback;
    }

    private static JSONObject findObject(JSONObject object, String[] keys) {
        for (String key : keys) {
            JSONObject nested = object.optJSONObject(key);
            if (nested != null) return nested;
        }
        return null;
    }
}
