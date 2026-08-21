package online.ebeinc.allthings140radio;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

import java.io.IOException;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/** Small client-safe Supabase Auth/profile adapter. Privileged keys never belong here. */
public final class SupabaseAuthClient {
    public interface Callback { void complete(boolean ok, String message); }
    public static final String TERMS_VERSION = "green-room-2026-08-21-v1";
    private static final String URL = "https://dtvnlpgtmrbnpecsapsv.supabase.co";
    private static final String KEY = "sb_publishable_rSf3FiaFsk2zZ37GU0zmzA_2cNQmVJQ";
    private static final String PREFS = "allthings140_supabase";
    private final SharedPreferences prefs;
    private final OkHttpClient client = new OkHttpClient.Builder().callTimeout(15, TimeUnit.SECONDS).build();

    public SupabaseAuthClient(Context context) { prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE); }
    public String accessToken() { return prefs.getString("access_token", ""); }
    public String userId() { return prefs.getString("user_id", ""); }
    public String username() { return prefs.getString("username", ""); }
    public boolean signedIn() { return !accessToken().isEmpty(); }

    public void signIn(String email, String password, Callback callback) { auth("token?grant_type=password", email, password, callback); }
    public void signUp(String email, String password, Callback callback) { auth("signup", email, password, callback); }
    public void resetPassword(String email, Callback callback) {
        new Thread(() -> {
            try {
                JSONObject body = new JSONObject().put("email", email);
                Request request = new Request.Builder().url(URL + "/auth/v1/recover")
                        .post(RequestBody.create(body.toString(), MediaType.parse("application/json")))
                        .header("apikey", KEY).header("Content-Type", "application/json").build();
                try (Response response = client.newCall(request).execute()) { callback.complete(response.isSuccessful(), response.isSuccessful() ? "Recovery email requested." : "Recovery request failed."); }
            } catch (Exception e) { callback.complete(false, "Recovery request failed."); }
        }).start();
    }

    private void auth(String path, String email, String password, Callback callback) {
        new Thread(() -> {
            try {
                JSONObject body = new JSONObject().put("email", email).put("password", password);
                Request request = new Request.Builder().url(URL + "/auth/v1/" + path)
                        .post(RequestBody.create(body.toString(), MediaType.parse("application/json")))
                        .header("apikey", KEY).header("Content-Type", "application/json").build();
                try (Response response = client.newCall(request).execute()) {
                    String text = response.body() == null ? "" : response.body().string();
                    if (!response.isSuccessful()) { callback.complete(false, error(text)); return; }
                    JSONObject data = new JSONObject(text);
                    String token = data.optString("access_token", "");
                    if (token.isEmpty()) { callback.complete(true, "Check your email to confirm your account."); return; }
                    JSONObject user = data.optJSONObject("user");
                    prefs.edit().putString("access_token", token).putString("refresh_token", data.optString("refresh_token", ""))
                            .putString("user_id", user == null ? "" : user.optString("id", "")).apply();
                    callback.complete(true, "Signed in.");
                }
            } catch (Exception e) { callback.complete(false, "Network error. Please try again."); }
        }).start();
    }

    public void updateUsername(String username, Callback callback) {
        new Thread(() -> {
            try {
                JSONObject body = new JSONObject().put("username", username.trim());
                Request request = new Request.Builder().url(URL + "/rest/v1/profiles?id=eq." + userId())
                        .patch(RequestBody.create(body.toString(), MediaType.parse("application/json")))
                        .header("apikey", KEY).header("Authorization", "Bearer " + accessToken())
                        .header("Prefer", "return=minimal").build();
                try (Response response = client.newCall(request).execute()) {
                    if (response.isSuccessful()) { prefs.edit().putString("username", username.trim()).apply(); callback.complete(true, "Profile saved."); }
                    else callback.complete(false, "Username was rejected by the server.");
                }
            } catch (Exception e) { callback.complete(false, "Profile update failed."); }
        }).start();
    }

    /** Uploads one user-owned avatar object at the canonical UUID/avatar path. */
    public void uploadAvatar(UriSource source, String mimeType, Callback callback) {
        new Thread(() -> {
            try {
                byte[] bytes = source.read();
                if (bytes.length == 0 || bytes.length > 2 * 1024 * 1024) { callback.complete(false, "Avatar must be a non-empty image under 2 MiB."); return; }
                String type = mimeType == null ? "" : mimeType.toLowerCase(java.util.Locale.US);
                if (!("image/jpeg".equals(type) || "image/png".equals(type) || "image/webp".equals(type))) { callback.complete(false, "Choose a JPEG, PNG, or WebP image."); return; }
                String path = userId() + "/avatar";
                Request upload = new Request.Builder().url(URL + "/storage/v1/object/avatars/" + path)
                        .put(RequestBody.create(bytes, MediaType.parse(type)))
                        .header("apikey", KEY).header("Authorization", "Bearer " + accessToken())
                        .header("x-upsert", "true").build();
                try (Response response = client.newCall(upload).execute()) {
                    if (!response.isSuccessful()) { callback.complete(false, "Avatar upload was rejected."); return; }
                }
                JSONObject profile = new JSONObject().put("avatar_path", path);
                Request update = new Request.Builder().url(URL + "/rest/v1/profiles?id=eq." + userId())
                        .patch(RequestBody.create(profile.toString(), MediaType.parse("application/json")))
                        .header("apikey", KEY).header("Authorization", "Bearer " + accessToken())
                        .header("Prefer", "return=minimal").build();
                try (Response response = client.newCall(update).execute()) {
                    callback.complete(response.isSuccessful(), response.isSuccessful() ? "Avatar saved." : "Avatar profile update failed.");
                }
            } catch (Exception e) { callback.complete(false, "Avatar upload failed."); }
        }).start();
    }

    public interface UriSource { byte[] read() throws Exception; }

    public void deleteAccount(Callback callback) {
        new Thread(() -> {
            try {
                Request request = new Request.Builder().url(URL + "/functions/v1/delete-account")
                        .post(RequestBody.create("{}", MediaType.parse("application/json")))
                        .header("apikey", KEY).header("Authorization", "Bearer " + accessToken()).build();
                try (Response response = client.newCall(request).execute()) {
                    if (response.isSuccessful()) { signOut(); callback.complete(true, "Account deleted."); }
                    else callback.complete(false, "Account deletion was not completed.");
                }
            } catch (IOException e) { callback.complete(false, "Account deletion failed."); }
        }).start();
    }

    public void signOut() { prefs.edit().clear().apply(); }
    private static String error(String text) { try { return new JSONObject(text).optString("msg", new JSONObject(text).optString("error_description", "Authentication failed.")); } catch (Exception ignored) { return "Authentication failed."; } }
}
