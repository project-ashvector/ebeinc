package online.ebeinc.allthings140radio;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.ImageButton;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class SettingsActivity extends Activity {
    private static final String STATUS_API_URL = "https://status.ebeinc.online/api/public/status";
    private static final String FALLBACK_STATUS_URL = "https://allthings140radio.online/api/public/status";

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private View root;
    private View topBar;
    private TextView appVersion;
    private TextView buildTarget;
    private TextView updateStatus;
    private TextView updateDetails;
    private ProgressBar updateProgress;
    private Button checkUpdates;
    private Button openPlay;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        root = findViewById(R.id.settingsRoot);
        topBar = findViewById(R.id.settingsTopBar);
        appVersion = findViewById(R.id.txtAppVersion);
        buildTarget = findViewById(R.id.txtBuildTarget);
        updateStatus = findViewById(R.id.txtUpdateStatus);
        updateDetails = findViewById(R.id.txtUpdateDetails);
        updateProgress = findViewById(R.id.progressUpdate);
        checkUpdates = findViewById(R.id.btnCheckUpdates);
        openPlay = findViewById(R.id.btnOpenPlay);
        ImageButton back = findViewById(R.id.btnBack);
        Button privacy = findViewById(R.id.btnPrivacy);
        Button website = findViewById(R.id.btnWebsiteSettings);

        applyWindowInsets();
        displayAppMetadata();

        back.setOnClickListener(v -> finish());
        checkUpdates.setOnClickListener(v -> performUpdateCheck());
        openPlay.setOnClickListener(v -> openGooglePlay());
        privacy.setOnClickListener(v -> startActivity(new Intent(this, PrivacyActivity.class)));
        website.setOnClickListener(v -> openExternal("https://allthings140radio.online/"));
    }

    private void displayAppMetadata() {
        appVersion.setText(getString(R.string.version_format, BuildConfig.VERSION_NAME, BuildConfig.VERSION_CODE));
        int target = getApplicationInfo().targetSdkVersion;
        buildTarget.setText(getString(R.string.target_sdk_format, target));
    }

    private void performUpdateCheck() {
        checkUpdates.setEnabled(false);
        updateProgress.setVisibility(View.VISIBLE);
        updateStatus.setText(R.string.update_checking);
        updateStatus.setTextColor(getColor(R.color.white));
        updateDetails.setVisibility(View.GONE);
        openPlay.setVisibility(View.GONE);

        executor.execute(() -> {
            String json = fetchUrl(STATUS_API_URL);
            if (json == null) json = fetchUrl(FALLBACK_STATUS_URL);
            String response = json;
            mainHandler.post(() -> {
                if (!isFinishing() && !isDestroyed()) processUpdateResponse(response);
            });
        });
    }

    private String fetchUrl(String endpoint) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(endpoint + "?t=" + System.currentTimeMillis());
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(6000);
            connection.setReadTimeout(6000);
            connection.setUseCaches(false);
            connection.setRequestProperty("User-Agent", "AllThings140RadioAndroid/" + BuildConfig.VERSION_NAME);
            connection.setRequestProperty("Accept", "application/json");
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) return null;
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                    connection.getInputStream(), StandardCharsets.UTF_8))) {
                StringBuilder result = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) result.append(line);
                return result.toString();
            }
        } catch (Exception ignored) {
            return null;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private void processUpdateResponse(String response) {
        checkUpdates.setEnabled(true);
        updateProgress.setVisibility(View.GONE);

        if (response == null || response.trim().isEmpty()) {
            updateStatus.setText(R.string.update_unavailable);
            updateStatus.setTextColor(getColor(R.color.orange));
            return;
        }

        try {
            JSONObject data = new JSONObject(response);
            String remoteVersion = data.optString("android_app_version", "").trim();
            String releaseNotes = data.optString("android_app_notes", "").trim();

            if (remoteVersion.isEmpty()) {
                updateStatus.setText(R.string.update_feed_not_configured);
                updateStatus.setTextColor(getColor(R.color.muted));
                updateDetails.setText(R.string.update_play_store_delivery);
                updateDetails.setVisibility(View.VISIBLE);
                return;
            }

            int comparison = VersionUtils.compare(remoteVersion, BuildConfig.VERSION_NAME);
            if (comparison > 0) {
                updateStatus.setText(getString(R.string.update_available, remoteVersion));
                updateStatus.setTextColor(getColor(R.color.green_neon));
                String details = getString(R.string.update_versions,
                        BuildConfig.VERSION_NAME, remoteVersion);
                if (!releaseNotes.isEmpty()) details += "\n\n" + releaseNotes;
                updateDetails.setText(details);
                updateDetails.setVisibility(View.VISIBLE);
                openPlay.setVisibility(View.VISIBLE);
            } else if (comparison == 0) {
                updateStatus.setText(R.string.update_current);
                updateStatus.setTextColor(getColor(R.color.green_neon));
                updateDetails.setText(getString(R.string.update_current_version, BuildConfig.VERSION_NAME));
                updateDetails.setVisibility(View.VISIBLE);
            } else {
                updateStatus.setText(R.string.update_newer_than_feed);
                updateStatus.setTextColor(getColor(R.color.purple_neon));
                updateDetails.setText(getString(R.string.update_versions,
                        BuildConfig.VERSION_NAME, remoteVersion));
                updateDetails.setVisibility(View.VISIBLE);
            }
        } catch (Exception ignored) {
            updateStatus.setText(R.string.update_feed_invalid);
            updateStatus.setTextColor(getColor(R.color.orange));
        }
    }

    private void openGooglePlay() {
        String packageName = getPackageName().replace(".debug", "");
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + packageName)));
        } catch (Exception marketUnavailable) {
            openExternal("https://play.google.com/store/apps/details?id=" + packageName);
        }
    }

    private void openExternal(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception ignored) {
            Toast.makeText(this, R.string.unable_to_open_link, Toast.LENGTH_SHORT).show();
        }
    }

    private void applyWindowInsets() {
        final int rootBottom = root.getPaddingBottom();
        final int barLeft = topBar.getPaddingLeft();
        final int barTop = topBar.getPaddingTop();
        final int barRight = topBar.getPaddingRight();
        final int barBottom = topBar.getPaddingBottom();
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            int left;
            int top;
            int right;
            int bottom;
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(
                        WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars() | WindowInsets.Type.displayCutout());
                left = bars.left;
                top = bars.top;
                right = bars.right;
                bottom = bars.bottom;
            } else {
                left = insets.getSystemWindowInsetLeft();
                top = insets.getSystemWindowInsetTop();
                right = insets.getSystemWindowInsetRight();
                bottom = insets.getSystemWindowInsetBottom();
            }
            topBar.setPadding(barLeft, barTop + top, barRight, barBottom);
            v.setPadding(left, 0, right, rootBottom + bottom);
            return insets;
        });
        root.requestApplyInsets();
    }

    @Override protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
