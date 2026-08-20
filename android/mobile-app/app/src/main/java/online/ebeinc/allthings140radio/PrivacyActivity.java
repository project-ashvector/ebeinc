package online.ebeinc.allthings140radio;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.widget.ImageButton;
import android.widget.TextView;

public final class PrivacyActivity extends Activity {
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_privacy);
        View root = findViewById(R.id.privacyRoot);
        View topBar = findViewById(R.id.privacyTopBar);
        TextView policy = findViewById(R.id.txtPrivacyPolicy);
        ImageButton back = findViewById(R.id.btnPrivacyBack);

        policy.setText(R.string.privacy_policy_body);
        back.setOnClickListener(v -> finish());
        applyInsets(root, topBar);
    }

    private void applyInsets(View root, View topBar) {
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
            v.setPadding(left, 0, right, bottom);
            return insets;
        });
        root.requestApplyInsets();
    }
}
