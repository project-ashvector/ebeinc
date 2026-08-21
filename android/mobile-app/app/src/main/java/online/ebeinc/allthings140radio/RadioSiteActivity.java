package online.ebeinc.allthings140radio;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;

/**
 * Secure secondary WebView for optional station pages. The app's core radio player is native.
 */
public final class RadioSiteActivity extends Activity {
    public static final String EXTRA_URL = "station_url";
    public static final String EXTRA_TITLE = "station_title";
    private static final String STATION_HOST = "allthings140radio.online";

    private LinearLayout rootLayout;
    private LinearLayout topBar;
    private WebView web;
    private ProgressBar progress;
    private OnBackInvokedCallback backCallback;
    private String allowedPathPrefix = "/visuals/";

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);

        String initialUrl = getIntent().getStringExtra(EXTRA_URL);
        if (!isStationUrl(initialUrl)) initialUrl = "https://allthings140radio.online/";
        Uri initialUri = Uri.parse(initialUrl);
        String initialPath = initialUri.getPath();
        if (initialPath != null && !initialPath.isEmpty() && !"/".equals(initialPath)) {
            allowedPathPrefix = initialPath.endsWith("/") ? initialPath : initialPath + "/";
        }
        String sectionTitle = getIntent().getStringExtra(EXTRA_TITLE);
        if (sectionTitle == null || sectionTitle.trim().isEmpty()) sectionTitle = getString(R.string.web_default_title);

        rootLayout = new LinearLayout(this);
        rootLayout.setOrientation(LinearLayout.VERTICAL);
        rootLayout.setBackgroundColor(getColor(R.color.dark_bg));

        topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        int padH = dpToPx(8);
        int padV = dpToPx(8);
        topBar.setPadding(padH, padV, dpToPx(16), padV);
        topBar.setBackgroundColor(getColor(R.color.top_bar));
        topBar.setMinimumHeight(dpToPx(64));

        ImageButton backBtn = new ImageButton(this);
        backBtn.setImageResource(R.drawable.ic_back);
        backBtn.setBackgroundResource(android.R.drawable.list_selector_background);
        backBtn.setContentDescription(getString(R.string.go_back));
        backBtn.setPadding(dpToPx(12), dpToPx(12), dpToPx(12), dpToPx(12));
        int btnSize = dpToPx(48);
        backBtn.setLayoutParams(new LinearLayout.LayoutParams(btnSize, btnSize));
        backBtn.setOnClickListener(v -> handleBack());
        topBar.addView(backBtn);

        TextView title = new TextView(this);
        title.setText(sectionTitle.toUpperCase(java.util.Locale.ROOT));
        title.setTextColor(getColor(R.color.white));
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        title.setTypeface(Typeface.create("sans-serif-black", Typeface.BOLD));
        title.setLetterSpacing(0.08f);
        title.setSingleLine(true);
        title.setPadding(dpToPx(6), 0, 0, 0);
        topBar.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));

        TextView badge = new TextView(this);
        badge.setText("140");
        badge.setTextColor(getColor(R.color.purple_neon));
        badge.setTextSize(TypedValue.COMPLEX_UNIT_SP, 10);
        badge.setTypeface(Typeface.DEFAULT_BOLD);
        badge.setBackgroundResource(R.drawable.live_badge);
        badge.setPadding(dpToPx(9), dpToPx(4), dpToPx(9), dpToPx(4));
        topBar.addView(badge);

        rootLayout.addView(topBar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setIndeterminate(false);
        rootLayout.addView(progress, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dpToPx(3)));

        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        rootLayout.addView(web, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1.0f));
        setContentView(rootLayout);

        applyWindowInsets();
        configureWebView();
        registerPredictiveBack();
        web.loadUrl(initialUrl);
    }

    private void configureWebView() {
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(false);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setGeolocationEnabled(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setSupportMultipleWindows(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        if (Build.VERSION.SDK_INT >= 26) settings.setSafeBrowsingEnabled(true);
        settings.setUserAgentString(settings.getUserAgentString()
                + " AllThings140RadioAndroid/" + BuildConfig.VERSION_NAME);

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(web, false);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);

        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
                progress.setVisibility(value >= 100 ? View.GONE : View.VISIBLE);
            }
        });

        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (isAllowedInApp(uri)) return false;
                openExternal(uri);
                return true;
            }

            @SuppressWarnings("deprecation")
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {
                Uri uri = Uri.parse(url);
                if (isAllowedInApp(uri)) return false;
                openExternal(uri);
                return true;
            }
        });
    }

    private void openExternal(Uri uri) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (Exception ignored) {
            Toast.makeText(this, R.string.unable_to_open_link, Toast.LENGTH_SHORT).show();
        }
    }

    private static boolean isStationUrl(String value) {
        if (value == null || value.trim().isEmpty()) return false;
        try {
            return isStationUri(Uri.parse(value));
        } catch (Exception ignored) {
            return false;
        }
    }

    private static boolean isStationUri(Uri uri) {
        if (uri == null || !"https".equalsIgnoreCase(uri.getScheme())) return false;
        String host = uri.getHost();
        return host != null && (host.equalsIgnoreCase(STATION_HOST)
                || host.toLowerCase(java.util.Locale.ROOT).endsWith("." + STATION_HOST));
    }

    private boolean isAllowedInApp(Uri uri) {
        if (!isStationUri(uri)) return false;
        String path = uri.getPath();
        if (path == null) return false;
        return path.equals(allowedPathPrefix.substring(0, allowedPathPrefix.length() - 1))
                || path.startsWith(allowedPathPrefix);
    }

    private void registerPredictiveBack() {
        if (Build.VERSION.SDK_INT >= 33) {
            backCallback = this::handleBack;
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT, backCallback);
        }
    }

    private void handleBack() {
        if (web != null && web.canGoBack()) web.goBack();
        else finish();
    }

    @android.annotation.SuppressLint("GestureBackNavigation")
    @SuppressWarnings("deprecation")
    @Override public void onBackPressed() {
        if (Build.VERSION.SDK_INT < 33) handleBack();
    }

    private void applyWindowInsets() {
        final int barLeft = topBar.getPaddingLeft();
        final int barTop = topBar.getPaddingTop();
        final int barRight = topBar.getPaddingRight();
        final int barBottom = topBar.getPaddingBottom();
        rootLayout.setOnApplyWindowInsetsListener((v, insets) -> {
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
            topBar.setPadding(barLeft + left, barTop + top, barRight + right, barBottom);
            web.setPadding(left, 0, right, bottom);
            return insets;
        });
        rootLayout.requestApplyInsets();
    }

    private int dpToPx(int dp) {
        return (int) TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP, dp, getResources().getDisplayMetrics());
    }

    @Override protected void onDestroy() {
        if (Build.VERSION.SDK_INT >= 33 && backCallback != null) {
            getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(backCallback);
            backCallback = null;
        }
        if (web != null) {
            web.loadUrl("about:blank");
            web.stopLoading();
            web.setWebChromeClient(null);
            web.setWebViewClient(null);
            web.removeAllViews();
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
