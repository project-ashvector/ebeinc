package online.ebeinc.allthings140radio;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Rect;
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
import android.widget.EditText;
import android.widget.CheckBox;
import android.widget.ScrollView;
import android.text.method.HideReturnsTransformationMethod;
import android.text.method.PasswordTransformationMethod;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;

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
    private SupabaseAuthClient authClient;
    private TextView accountState;
    private TextView accountIntro;
    private TextView roleBadge;
    private Button moderationButton;
    private Button adminButton;
    private EditText accountEmail;
    private EditText accountPassword;
    private EditText accountConfirmPassword;
    private CheckBox accountShowPassword;
    private ScrollView settingsScroll;
    private View accountAuthTabs;
    private TextView authModeIntro;
    private Button authModeSignIn;
    private Button authModeCreate;
    private EditText accountUsername;
    private View accountAvatar;
    private View accountSaveProfile;
    private View accountSignIn;
    private View accountSignUp;
    private View accountReset;
    private View accountSignOut;
    private View accountDelete;
    private TextView accountType;
    private TextView alertAds;
    private View alertPreferenceControl;
    private Button alertAdsOff;
    private Button alertAdsOn;
    private enum AuthMode { SIGN_IN, CREATE, RESET }
    private AuthMode authMode = AuthMode.SIGN_IN;

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
        authClient = new SupabaseAuthClient(this);
        accountState = findViewById(R.id.txtAccountState);
        accountIntro = findViewById(R.id.txtAccountIntro);
        roleBadge = findViewById(R.id.txtAccountRoleBadge);
        moderationButton = findViewById(R.id.btnModeration);
        adminButton = findViewById(R.id.btnAdminControls);
        accountEmail = findViewById(R.id.editAccountEmail);
        accountPassword = findViewById(R.id.editAccountPassword);
        accountConfirmPassword = findViewById(R.id.editAccountConfirmPassword);
        accountShowPassword = findViewById(R.id.checkAccountShowPassword);
        settingsScroll = findViewById(R.id.settingsScroll);
        accountAuthTabs = findViewById(R.id.accountAuthTabs);
        authModeIntro = findViewById(R.id.txtAuthModeIntro);
        authModeSignIn = findViewById(R.id.btnAuthModeSignIn);
        authModeCreate = findViewById(R.id.btnAuthModeCreate);
        accountUsername = findViewById(R.id.editAccountUsername);
        accountAvatar = findViewById(R.id.btnAccountAvatar);
        accountSaveProfile = findViewById(R.id.btnAccountSaveProfile);
        accountSignIn = findViewById(R.id.btnAccountSignIn);
        accountSignUp = findViewById(R.id.btnAccountSignUp);
        accountReset = findViewById(R.id.btnAccountReset);
        accountSignOut = findViewById(R.id.btnAccountSignOut);
        accountDelete = findViewById(R.id.btnAccountDelete);
        accountType = findViewById(R.id.txtAccountType);
        alertAds = findViewById(R.id.txtAlertAds);
        alertPreferenceControl = findViewById(R.id.alertPreferenceControl);
        alertAdsOff = findViewById(R.id.btnAlertAdsOff);
        alertAdsOn = findViewById(R.id.btnAlertAdsOn);
        ImageButton back = findViewById(R.id.btnBack);
        Button privacy = findViewById(R.id.btnPrivacy);
        Button website = findViewById(R.id.btnWebsiteSettings);
        Button terms = findViewById(R.id.btnTerms);
        Button deleteWeb = findViewById(R.id.btnDeleteAccountWeb);

        applyWindowInsets();
        displayAppMetadata();

        back.setOnClickListener(v -> finish());
        checkUpdates.setOnClickListener(v -> performUpdateCheck());
        openPlay.setOnClickListener(v -> openGooglePlay());
        privacy.setOnClickListener(v -> startActivity(new Intent(this, PrivacyActivity.class)));
        terms.setOnClickListener(v -> openExternal("https://allthings140radio.online/terms/"));
        deleteWeb.setOnClickListener(v -> openExternal("https://allthings140radio.online/delete-account/"));
        website.setOnClickListener(v -> openExternal("https://allthings140radio.online/"));
        authModeSignIn.setOnClickListener(v -> showAuthMode(AuthMode.SIGN_IN));
        authModeCreate.setOnClickListener(v -> showAuthMode(AuthMode.CREATE));
        accountShowPassword.setOnCheckedChangeListener((button, checked) -> {
            int passwordCursor = accountPassword.getSelectionStart();
            int confirmCursor = accountConfirmPassword.getSelectionStart();
            accountPassword.setTransformationMethod(checked ? HideReturnsTransformationMethod.getInstance() : PasswordTransformationMethod.getInstance());
            accountConfirmPassword.setTransformationMethod(checked ? HideReturnsTransformationMethod.getInstance() : PasswordTransformationMethod.getInstance());
            accountPassword.setSelection(Math.max(0, passwordCursor));
            accountConfirmPassword.setSelection(Math.max(0, confirmCursor));
        });
        View.OnFocusChangeListener keepActionVisible = (view, focused) -> {
            if (focused) view.postDelayed(this::scrollAuthActionIntoView, 300);
        };
        accountEmail.setOnFocusChangeListener(keepActionVisible);
        accountPassword.setOnFocusChangeListener(keepActionVisible);
        accountConfirmPassword.setOnFocusChangeListener(keepActionVisible);
        findViewById(R.id.btnAccountSignIn).setOnClickListener(v -> authenticate(false));
        findViewById(R.id.btnAccountSignUp).setOnClickListener(v -> authenticate(true));
        findViewById(R.id.btnAccountReset).setOnClickListener(v -> {
            if (authMode != AuthMode.RESET) { showAuthMode(AuthMode.RESET); return; }
            String email = ((EditText) findViewById(R.id.editAccountEmail)).getText().toString().trim();
            if (email.isEmpty()) { Toast.makeText(this, "Enter your email first.", Toast.LENGTH_SHORT).show(); return; }
            authClient.resetPassword(email, (ok, msg) -> mainHandler.post(() -> Toast.makeText(this, msg, Toast.LENGTH_LONG).show()));
        });
        findViewById(R.id.btnAccountSignOut).setOnClickListener(v -> { authClient.signOut(); refreshAccountState(); });
        findViewById(R.id.btnAccountDelete).setOnClickListener(v -> confirmDelete());
        findViewById(R.id.btnAccountAvatar).setOnClickListener(v -> {
            if (!authClient.signedIn()) { Toast.makeText(this, "Sign in first.", Toast.LENGTH_SHORT).show(); return; }
            Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            pick.addCategory(Intent.CATEGORY_OPENABLE);
            pick.setType("image/*");
            startActivityForResult(pick, 1401);
        });
        findViewById(R.id.btnAccountSaveProfile).setOnClickListener(v -> {
            if (!authClient.signedIn()) { Toast.makeText(this, "Sign in first.", Toast.LENGTH_SHORT).show(); return; }
            String username = ((EditText) findViewById(R.id.editAccountUsername)).getText().toString().trim();
            authClient.updateUsername(username, (ok, msg) -> mainHandler.post(() -> {
                Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
                if (ok) refreshAccountState();
            }));
        });
        moderationButton.setOnClickListener(v -> openRoleConsole(false));
        adminButton.setOnClickListener(v -> openRoleConsole(true));
        alertAdsOff.setOnClickListener(v -> saveAlertPreference("off"));
        alertAdsOn.setOnClickListener(v -> saveAlertPreference("on"));
        refreshAccountState();
    }

    @Override protected void onResume() {
        super.onResume();
        refreshAccountState();
        if (authClient != null && authClient.signedIn()) authClient.refreshSession((ok, message) -> mainHandler.post(this::refreshRole));
    }

    private void openRoleConsole(boolean admin) {
        Intent intent = new Intent(this, RoleConsoleActivity.class);
        intent.putExtra(RoleConsoleActivity.EXTRA_ADMIN, admin);
        startActivity(intent);
    }

    private void refreshRole() {
        if (!authClient.signedIn()) {
            roleBadge.setVisibility(View.GONE); moderationButton.setVisibility(View.GONE); adminButton.setVisibility(View.GONE); return;
        }
        authClient.loadRole((ok, role, status, email, accountClass, visibleType, alertAdsPreference, alertAdsEnabled) -> mainHandler.post(() -> {
            String safeRole = ok ? role : "user";
            boolean moderator = "moderator".equals(safeRole) || "admin".equals(safeRole);
            boolean admin = "admin".equals(safeRole);
            String label = "partner_sponsor".equals(visibleType) ? "PARTNER / SPONSOR" : visibleType.toUpperCase();
            roleBadge.setText(label);
            roleBadge.setVisibility("regular".equals(visibleType) ? View.GONE : View.VISIBLE);
            moderationButton.setVisibility(moderator ? View.VISIBLE : View.GONE);
            adminButton.setVisibility(admin ? View.VISIBLE : View.GONE);
            accountState.setText("SIGNED IN — " + (email.isEmpty() ? authClient.userId() : email) + " • " + status.toUpperCase());
            accountType.setText("ACCOUNT TYPE\n" + label);
            String benefit = "plus".equals(visibleType) ? "Included with Plus" : "resident".equals(visibleType) ? "ALLTHINGS140 Resident benefit" : "partner_sponsor".equals(visibleType) ? "Partner benefit" : "moderator".equals(visibleType) ? "Staff account" : "admin".equals(visibleType) ? "Administrator account" : "Included in the shared station stream";
            alertAds.setText("ALERT ADS\n" + (alertAdsEnabled ? "ON\n" + benefit : "OFF\n" + benefit + " — account-aware delivery is in testing"));
            boolean eligible = !"regular".equals(visibleType);
            alertPreferenceControl.setVisibility(eligible ? View.VISIBLE : View.GONE);
            alertAdsOff.setText(alertAdsEnabled ? "OFF" : "✓ OFF");
            alertAdsOn.setText(alertAdsEnabled ? "✓ ON" : "ON");
            alertAdsOff.setAlpha(alertAdsEnabled ? 0.72f : 1f);
            alertAdsOn.setAlpha(alertAdsEnabled ? 1f : 0.72f);
            accountType.setVisibility(View.VISIBLE); alertAds.setVisibility(View.VISIBLE);
        }));
    }

    private void saveAlertPreference(String preference) {
        alertAdsOff.setEnabled(false);
        alertAdsOn.setEnabled(false);
        authClient.setAlertAdsPreference(preference, (ok, message) -> mainHandler.post(() -> {
            Toast.makeText(this, message, Toast.LENGTH_LONG).show();
            alertAdsOff.setEnabled(true);
            alertAdsOn.setEnabled(true);
            if (ok) refreshRole();
        }));
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != 1401 || resultCode != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        String mime = getContentResolver().getType(uri);
        authClient.uploadAvatar(() -> {
            try (InputStream in = getContentResolver().openInputStream(uri); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                if (in == null) return new byte[0];
                byte[] buf = new byte[8192]; int n;
                while ((n = in.read(buf)) != -1) out.write(buf, 0, n);
                return out.toByteArray();
            }
        }, mime, (ok, msg) -> mainHandler.post(() -> Toast.makeText(this, msg, Toast.LENGTH_LONG).show()));
    }

    private void authenticate(boolean signUp) {
        String email = ((EditText) findViewById(R.id.editAccountEmail)).getText().toString().trim();
        String password = ((EditText) findViewById(R.id.editAccountPassword)).getText().toString();
        if (email.isEmpty() || password.length() < 8) { Toast.makeText(this, "Enter a valid email and 8+ character password.", Toast.LENGTH_SHORT).show(); return; }
        if (signUp && !password.equals(accountConfirmPassword.getText().toString())) { Toast.makeText(this, "Passwords do not match.", Toast.LENGTH_SHORT).show(); return; }
        SupabaseAuthClient.Callback callback = (ok, message) -> mainHandler.post(() -> { Toast.makeText(this, message, Toast.LENGTH_LONG).show(); if (ok) refreshAccountState(); });
        if (signUp) authClient.signUp(email, password, callback); else authClient.signIn(email, password, callback);
    }

    private void confirmDelete() {
        if (!authClient.signedIn()) { Toast.makeText(this, "Sign in first.", Toast.LENGTH_SHORT).show(); return; }
        new android.app.AlertDialog.Builder(this).setTitle("Delete account?")
                .setMessage("This permanently removes your ALLTHINGS140 account and profile.")
                .setNegativeButton("CANCEL", null)
                .setPositiveButton("DELETE", (d, w) -> authClient.deleteAccount((ok, msg) -> mainHandler.post(() -> { Toast.makeText(this, msg, Toast.LENGTH_LONG).show(); refreshAccountState(); }))).show();
    }

    private void refreshAccountState() {
        boolean signedIn = authClient.signedIn();
        setVisible(accountType, signedIn);
        setVisible(alertAds, signedIn);
        if (!signedIn) setVisible(alertPreferenceControl, false);
        if (accountState != null) accountState.setText(signedIn ? "YOUR ALLTHINGS140 ACCOUNT" : "SIGN IN TO ALLTHINGS140");
        if (accountIntro != null) accountIntro.setText(signedIn
                ? "Manage your profile, membership, community access, and account security."
                : "Sign in to manage your profile and join the Green Room. Listening always works without an account.");
        setVisible(accountEmail, !signedIn);
        setVisible(accountShowPassword, !signedIn && authMode != AuthMode.RESET);
        setVisible(accountAuthTabs, !signedIn);
        setVisible(authModeIntro, !signedIn);
        if (!signedIn) showAuthMode(authMode);
        else { setVisible(accountPassword, false); setVisible(accountConfirmPassword, false); setVisible(accountShowPassword, false); setVisible(accountSignIn, false); setVisible(accountSignUp, false); setVisible(accountReset, false); }
        setVisible(accountUsername, signedIn);
        setVisible(accountAvatar, signedIn);
        setVisible(accountSaveProfile, signedIn);
        setVisible(accountSignOut, signedIn);
        setVisible(accountDelete, signedIn);
        refreshRole();
        if (signedIn) authClient.loadProfile((ok, username, avatarPath) -> mainHandler.post(() -> {
            if (ok && accountUsername != null && !username.isEmpty()) accountUsername.setText(username);
        }));
    }

    private static void setVisible(View view, boolean visible) {
        if (view != null) view.setVisibility(visible ? View.VISIBLE : View.GONE);
    }

    private void scrollAuthActionIntoView() {
        View action = authMode == AuthMode.CREATE ? accountSignUp : authMode == AuthMode.RESET ? accountReset : accountSignIn;
        if (settingsScroll == null || action == null || action.getVisibility() != View.VISIBLE) return;
        Rect target = new Rect();
        action.getDrawingRect(target);
        settingsScroll.offsetDescendantRectToMyCoords(action, target);
        int desired = Math.max(0, target.bottom - settingsScroll.getHeight() + dp(20));
        settingsScroll.smoothScrollTo(0, desired);
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void showAuthMode(AuthMode mode) {
        authMode = mode;
        boolean signIn = mode == AuthMode.SIGN_IN, create = mode == AuthMode.CREATE, reset = mode == AuthMode.RESET;
        authModeIntro.setText(signIn ? "Welcome back\nContinue your ALLTHINGS140 identity." : create ? "Create your account\nBuild your profile and join the Green Room." : "Reset your password\nEnter your account email and we’ll send a recovery link.");
        authModeSignIn.setTextColor(getColor(signIn ? R.color.white : R.color.muted));
        authModeCreate.setTextColor(getColor(create ? R.color.white : R.color.muted));
        setVisible(accountPassword, !reset);
        setVisible(accountConfirmPassword, create);
        setVisible(accountShowPassword, !reset);
        setVisible(accountSignIn, signIn);
        setVisible(accountSignUp, create);
        setVisible(accountReset, signIn || reset);
        ((Button) accountReset).setText(reset ? "SEND RESET LINK" : "FORGOT PASSWORD?");
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
