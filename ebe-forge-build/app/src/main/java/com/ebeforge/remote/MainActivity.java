package com.ebeforge.remote;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.view.Gravity;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Locale;

public class MainActivity extends Activity implements TextToSpeech.OnInitListener {
    private static final int AUDIO_PERMISSION = 2001;
    private static final int FILE_CHOOSER = 2002;
    private static final String PREFS = "ebe_forge";
    private static final int BG = Color.rgb(9, 10, 16);
    private static final int PANEL = Color.rgb(17, 19, 29);
    private static final int PANEL_TWO = Color.rgb(24, 27, 40);
    private static final int TEXT = Color.rgb(247, 248, 251);
    private static final int MUTED = Color.rgb(146, 152, 170);
    private static final int PURPLE = Color.rgb(118, 80, 255);
    private static final int PURPLE_LIGHT = Color.rgb(157, 124, 255);
    private static final int GREEN = Color.rgb(105, 230, 180);

    private WebView webView;
    private SpeechRecognizer speechRecognizer;
    private TextToSpeech tts;
    private ValueCallback<Uri[]> fileCallback;
    private String pendingUrl;
    private String pendingToken;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        tts = new TextToSpeech(this, this);
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        String url = prefs.getString("url", "");
        String token = prefs.getString("token", "");
        if (url.isEmpty()) showSetup(url, token); else showWeb(url, token);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable rounded(int color, int radius, int strokeColor, int stroke) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radius));
        if (stroke > 0) drawable.setStroke(dp(stroke), strokeColor);
        return drawable;
    }

    private GradientDrawable gradient(int startColor, int endColor, int radius) {
        GradientDrawable drawable = new GradientDrawable(GradientDrawable.Orientation.TL_BR, new int[]{startColor, endColor});
        drawable.setCornerRadius(dp(radius));
        return drawable;
    }

    private TextView text(String value, float size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        if (bold) view.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        return view;
    }

    private TextView label(String value) {
        TextView view = text(value.toUpperCase(Locale.US), 11, MUTED, true);
        view.setLetterSpacing(0.08f);
        view.setPadding(0, dp(18), 0, dp(7));
        return view;
    }

    private EditText field(String value, String hint) {
        EditText edit = new EditText(this);
        edit.setText(value);
        edit.setHint(hint);
        edit.setTextColor(TEXT);
        edit.setHintTextColor(Color.rgb(104, 110, 128));
        edit.setTextSize(15);
        edit.setSingleLine(true);
        edit.setBackground(rounded(PANEL_TWO, 14, Color.rgb(45, 49, 68), 1));
        edit.setPadding(dp(16), dp(14), dp(16), dp(14));
        return edit;
    }

    private void showSetup(String currentUrl, String currentToken) {
        pendingUrl = currentUrl;
        pendingToken = currentToken;
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setGravity(Gravity.CENTER_HORIZONTAL);
        page.setPadding(dp(22), dp(28), dp(22), dp(32));
        scroll.addView(page, new ScrollView.LayoutParams(-1, -1));

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.VERTICAL);
        header.setGravity(Gravity.CENTER);
        header.setPadding(dp(20), dp(20), dp(20), dp(20));
        header.setBackground(gradient(Color.rgb(31, 25, 55), Color.rgb(16, 24, 38), 24));
        LinearLayout.LayoutParams headerParams = new LinearLayout.LayoutParams(-1, -2);
        headerParams.setMargins(0, 0, 0, dp(20));
        page.addView(header, headerParams);

        TextView mark = text("✦", 38, PURPLE_LIGHT, true);
        mark.setGravity(Gravity.CENTER);
        mark.setBackground(rounded(Color.argb(55, 157, 124, 255), 20, Color.argb(90, 157, 124, 255), 1));
        mark.setPadding(dp(18), dp(10), dp(18), dp(10));
        header.addView(mark, new LinearLayout.LayoutParams(dp(78), dp(78)));

        TextView title = text("EBE Forge", 29, TEXT, true);
        title.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(-1, -2);
        titleParams.setMargins(0, dp(15), 0, 0);
        header.addView(title, titleParams);

        TextView subtitle = text("Your private AI development system", 14, MUTED, false);
        subtitle.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams subtitleParams = new LinearLayout.LayoutParams(-1, -2);
        subtitleParams.setMargins(0, dp(5), 0, dp(14));
        header.addView(subtitle, subtitleParams);

        TextView secure = text("●  TAILSCALE PRIVATE", 10, GREEN, true);
        secure.setLetterSpacing(0.08f);
        secure.setGravity(Gravity.CENTER);
        secure.setPadding(dp(12), dp(7), dp(12), dp(7));
        secure.setBackground(rounded(Color.argb(24, 105, 230, 180), 20, Color.argb(55, 105, 230, 180), 1));
        header.addView(secure);

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(19), dp(20), dp(19), dp(20));
        card.setBackground(rounded(PANEL, 20, Color.rgb(39, 42, 57), 1));
        page.addView(card, new LinearLayout.LayoutParams(-1, -2));

        card.addView(text("Connect to your Zorin workstation", 19, TEXT, true));
        TextView help = text("Keep EBE Forge running on Zorin, connect both devices to the same Tailscale account, then enter the private address and pairing token shown by the desktop app.", 13, MUTED, false);
        help.setLineSpacing(0, 1.18f);
        LinearLayout.LayoutParams helpParams = new LinearLayout.LayoutParams(-1, -2);
        helpParams.setMargins(0, dp(8), 0, 0);
        card.addView(help, helpParams);

        card.addView(label("Private server address"));
        EditText url = field(currentUrl, "https://your-zorin-name.tailnet.ts.net");
        card.addView(url, new LinearLayout.LayoutParams(-1, -2));
        card.addView(label("Pairing token"));
        EditText token = field(currentToken, "Paste the token from Zorin");
        card.addView(token, new LinearLayout.LayoutParams(-1, -2));

        Button save = new Button(this);
        save.setText("Connect to EBE Forge   →");
        save.setTextColor(Color.WHITE);
        save.setTextSize(15);
        save.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        save.setAllCaps(false);
        save.setGravity(Gravity.CENTER);
        save.setBackground(gradient(PURPLE_LIGHT, PURPLE, 14));
        save.setPadding(dp(14), dp(14), dp(14), dp(14));
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(-1, -2);
        buttonParams.setMargins(0, dp(24), 0, 0);
        card.addView(save, buttonParams);

        TextView note = text("The phone stores only the private address and pairing token. Gemini keys and project files stay on your Zorin computer.", 11, Color.rgb(105, 111, 129), false);
        note.setGravity(Gravity.CENTER);
        note.setLineSpacing(0, 1.15f);
        LinearLayout.LayoutParams noteParams = new LinearLayout.LayoutParams(-1, -2);
        noteParams.setMargins(dp(10), dp(17), dp(10), 0);
        page.addView(note, noteParams);

        save.setOnClickListener(v -> {
            String cleanUrl = url.getText().toString().trim().replaceAll("/+$", "");
            String cleanToken = token.getText().toString().trim();
            if (cleanUrl.isEmpty() || cleanToken.isEmpty()) {
                Toast.makeText(this, "Enter the private server address and pairing token", Toast.LENGTH_LONG).show();
                return;
            }
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("url", cleanUrl).putString("token", cleanToken).apply();
            showWeb(cleanUrl, cleanToken);
        });
        setContentView(scroll);
    }

    private void showWeb(String url, String token) {
        pendingUrl = url;
        pendingToken = token;
        webView = new WebView(this);
        webView.setBackgroundColor(BG);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(false);
        settings.setTextZoom(100);
        settings.setUserAgentString(settings.getUserAgentString() + " EBEForgeAndroid/0.2.0");
        webView.addJavascriptInterface(new VoiceBridge(), "AndroidVoice");
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, String nextUrl) {
                Uri next = Uri.parse(nextUrl);
                Uri expected = Uri.parse(pendingUrl);
                if (next.getHost() != null && expected.getHost() != null && next.getHost().equals(expected.getHost())) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, next));
                return true;
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) Toast.makeText(MainActivity.this, "Cannot reach the Zorin workstation. Check Tailscale and EBE Forge.", Toast.LENGTH_LONG).show();
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, false);
                startActivityForResult(intent, FILE_CHOOSER);
                return true;
            }
        });
        setContentView(webView);
        webView.loadUrl(url + "/?token=" + Uri.encode(token), new HashMap<>());
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack(); else super.onBackPressed();
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER && fileCallback != null) {
            Uri[] result = null;
            if (resultCode == RESULT_OK && data != null && data.getData() != null) result = new Uri[]{data.getData()};
            fileCallback.onReceiveValue(result);
            fileCallback = null;
        }
    }

    private void startSpeech() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, AUDIO_PERMISSION);
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            sendVoiceError("Speech recognition is unavailable on this phone");
            return;
        }
        if (speechRecognizer != null) speechRecognizer.destroy();
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
        speechRecognizer.setRecognitionListener(new RecognitionListener() {
            public void onReadyForSpeech(Bundle params) {}
            public void onBeginningOfSpeech() {}
            public void onRmsChanged(float rmsdB) {}
            public void onBufferReceived(byte[] buffer) {}
            public void onEndOfSpeech() {}
            public void onPartialResults(Bundle partialResults) {}
            public void onEvent(int eventType, Bundle params) {}
            public void onError(int error) { sendVoiceError("Voice recognition error " + error); }
            public void onResults(Bundle results) {
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (matches == null || matches.isEmpty()) sendVoiceError("I did not hear anything clearly"); else sendVoiceResult(matches.get(0));
            }
        });
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault());
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false);
        speechRecognizer.startListening(intent);
    }

    private void sendVoiceResult(String value) {
        runOnUiThread(() -> { if (webView != null) webView.evaluateJavascript("window.ebeForgeVoiceResult(" + JSONObject.quote(value) + ")", null); });
    }

    private void sendVoiceError(String value) {
        runOnUiThread(() -> {
            if (webView != null) webView.evaluateJavascript("window.ebeForgeVoiceError(" + JSONObject.quote(value) + ")", null);
            else Toast.makeText(this, value, Toast.LENGTH_LONG).show();
        });
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == AUDIO_PERMISSION && grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) startSpeech();
        else if (requestCode == AUDIO_PERMISSION) sendVoiceError("Microphone permission was denied");
    }

    public class VoiceBridge {
        @JavascriptInterface public void startListening() { runOnUiThread(() -> startSpeech()); }
        @JavascriptInterface public void speak(String value) { runOnUiThread(() -> { if (tts != null) tts.speak(value, TextToSpeech.QUEUE_FLUSH, null, "ebe-forge"); }); }
        @JavascriptInterface public void openConnectionSettings() { runOnUiThread(() -> showSetup(pendingUrl, pendingToken)); }
    }

    @Override public void onInit(int status) { if (status == TextToSpeech.SUCCESS) tts.setLanguage(Locale.US); }
    @Override protected void onDestroy() {
        if (speechRecognizer != null) speechRecognizer.destroy();
        if (tts != null) tts.shutdown();
        if (webView != null) webView.destroy();
        super.onDestroy();
    }
}
