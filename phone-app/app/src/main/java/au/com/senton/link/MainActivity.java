package com.senton.link;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final String PREFS = "senton_link";
    private static final String KEY_UPDATE_STAGE = "update_stage";
    private static final String EXTRA_TEST_MODE = "senton_test_mode";

    private TextView updateStatus;
    private TextView testBanner;
    private TextView systemPanel;
    private boolean testMode;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        testMode = getIntent() != null && getIntent().getBooleanExtra(EXTRA_TEST_MODE, false);
        if (testMode) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
        applyImmersiveLauncherUi();

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(7, 12, 22));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(22), dp(18), dp(28));
        scroll.addView(root);

        root.addView(text("SENTON LINK", 30, Color.WHITE, true));
        root.addView(text("v" + BuildConfig.VERSION_NAME + " • Launcher Mode", 13, Color.rgb(38, 139, 255), true));

        testBanner = text("⚠ UNDER TESTING ⚠\nTEMPORARY HARD-TEST SESSION\nVEHICLE CONTROLS LOCKED", 18, Color.WHITE, true);
        testBanner.setGravity(Gravity.CENTER);
        testBanner.setPadding(dp(14), dp(14), dp(14), dp(14));
        testBanner.setBackgroundColor(Color.rgb(180, 35, 35));
        testBanner.setVisibility(testMode ? View.VISIBLE : View.GONE);
        root.addView(testBanner, mt(14));

        root.addView(text("● SENTON PI DISCONNECTED — SAFE MODE", 15, Color.rgb(255, 190, 70), true), mt(16));

        updateStatus = text(prefs.getString(KEY_UPDATE_STAGE, "Wi-Fi updates: open UPDATE for status"), 13, Color.rgb(135, 166, 196), false);
        root.addView(updateStatus, mt(8));

        root.addView(panel("MY SENTON\nReady for vehicle pairing\n\nVehicle controls remain disabled until Senton Pi pairing is complete."), mt(18));
        root.addView(panel("DASHBOARD\n\nSpeed          0 km/h\nMotor temp     -- °C\nBattery        -- V\nSignal         -- dBm"), mt(12));

        LinearLayout actions = row();
        actions.addView(button("DRIVE", false), weight());
        actions.addView(button("TEST", false), weight());
        Button update = button("UPDATE", true);
        update.setOnClickListener(v -> startActivity(new Intent(this, UpdateProgressActivity.class)));
        actions.addView(update, weight());
        root.addView(actions, mt(12));

        root.addView(panel("SOLAR CHARGE\n\nSolar input     --\nCharging        OFF\nBattery level   --\nCharge timer    --\n\nCharge controls remain locked until the Pi/car link is authenticated."), mt(16));
        LinearLayout charge = row();
        charge.addView(button("START CHARGE", false), weight());
        charge.addView(button("STOP CHARGE", false), weight());
        root.addView(charge, mt(8));

        systemPanel = panel(systemText());
        root.addView(systemPanel, mt(16));

        Button maintenance = button("HOLD FOR ANDROID MAINTENANCE", true);
        maintenance.setOnClickListener(v -> { });
        maintenance.setOnLongClickListener(v -> {
            Intent settings = new Intent(Settings.ACTION_SETTINGS);
            startActivity(settings);
            return true;
        });
        root.addView(maintenance, mt(16));
        TextView maintenanceHint = text("Long-press only. Opens Android settings for Wi-Fi, USB debugging, recovery and maintenance.", 12, Color.rgb(135, 166, 196), false);
        maintenanceHint.setGravity(Gravity.CENTER);
        root.addView(maintenanceHint, mt(6));

        TextView footer = text("Senton Link " + BuildConfig.VERSION_NAME + " • com.senton.link", 12, Color.rgb(90, 115, 140), false);
        footer.setGravity(Gravity.CENTER);
        root.addView(footer, mt(22));
        setContentView(scroll);
    }

    @Override protected void onResume() {
        super.onResume();
        applyImmersiveLauncherUi();
        if (testMode) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            if (testBanner != null) testBanner.setVisibility(View.VISIBLE);
        }
        if (systemPanel != null) systemPanel.setText(systemText());
        updateStatus.setText(getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_UPDATE_STAGE, "Wi-Fi updates: open UPDATE for status"));
    }

    @Override protected void onPause() {
        if (testMode) {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
        super.onPause();
    }

    @Override public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) applyImmersiveLauncherUi();
    }

    private void applyImmersiveLauncherUi() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY |
                View.SYSTEM_UI_FLAG_FULLSCREEN |
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }

    private String systemText() {
        return "SYSTEM\n\nApp status      " + (testMode ? "TESTING" : "OK") +
                "\nLauncher mode   Ready" +
                "\nUpdate channel  Beta\nVehicle link    Disconnected\nSafety mode     Active";
    }

    private TextView panel(String s) { TextView t=text(s,14,Color.rgb(220,232,244),false); t.setPadding(dp(16),dp(16),dp(16),dp(16)); t.setBackgroundColor(Color.rgb(18,29,43)); return t; }
    private Button button(String label, boolean enabled) { Button b=new Button(this); b.setText(label); b.setTextSize(12); b.setAllCaps(false); b.setEnabled(enabled); b.setMinHeight(dp(48)); return b; }
    private LinearLayout row() { LinearLayout r=new LinearLayout(this); r.setOrientation(LinearLayout.HORIZONTAL); return r; }
    private LinearLayout.LayoutParams weight() { LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1f); lp.setMargins(dp(4),0,dp(4),0); return lp; }
    private TextView text(String s,int size,int color,boolean bold) { TextView t=new TextView(this); t.setText(s); t.setTextSize(size); t.setTextColor(color); if(bold)t.setTypeface(t.getTypeface(),android.graphics.Typeface.BOLD); return t; }
    private LinearLayout.LayoutParams mt(int top) { LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT); lp.topMargin=dp(top); return lp; }
    private int dp(int v) { return (int)(v*getResources().getDisplayMetrics().density+0.5f); }
}
