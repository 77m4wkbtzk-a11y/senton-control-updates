package com.senton.link;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final String PREFS = "senton_link";
    private static final String KEY_UPDATE_STAGE = "update_stage";
    private TextView updateStatus;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(7, 12, 22));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(22), dp(18), dp(28));
        scroll.addView(root);

        root.addView(text("SENTON LINK", 30, Color.WHITE, true));
        root.addView(text("v" + BuildConfig.VERSION_NAME, 13, Color.rgb(38, 139, 255), true));
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

        root.addView(panel("SYSTEM\n\nApp status      OK\nUpdate channel  Beta\nVehicle link    Disconnected\nSafety mode     Active"), mt(16));
        TextView footer = text("Senton Link " + BuildConfig.VERSION_NAME + " • com.senton.link", 12, Color.rgb(90, 115, 140), false);
        footer.setGravity(Gravity.CENTER);
        root.addView(footer, mt(22));
        setContentView(scroll);
    }

    @Override protected void onResume() {
        super.onResume();
        updateStatus.setText(getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_UPDATE_STAGE, "Wi-Fi updates: open UPDATE for status"));
    }

    private TextView panel(String s) { TextView t=text(s,14,Color.rgb(220,232,244),false); t.setPadding(dp(16),dp(16),dp(16),dp(16)); t.setBackgroundColor(Color.rgb(18,29,43)); return t; }
    private Button button(String label, boolean enabled) { Button b=new Button(this); b.setText(label); b.setTextSize(12); b.setAllCaps(false); b.setEnabled(enabled); b.setMinHeight(dp(48)); return b; }
    private LinearLayout row() { LinearLayout r=new LinearLayout(this); r.setOrientation(LinearLayout.HORIZONTAL); return r; }
    private LinearLayout.LayoutParams weight() { LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1f); lp.setMargins(dp(4),0,dp(4),0); return lp; }
    private TextView text(String s,int size,int color,boolean bold) { TextView t=new TextView(this); t.setText(s); t.setTextSize(size); t.setTextColor(color); if(bold)t.setTypeface(t.getTypeface(),android.graphics.Typeface.BOLD); return t; }
    private LinearLayout.LayoutParams mt(int top) { LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT); lp.topMargin=dp(top); return lp; }
    private int dp(int v) { return (int)(v*getResources().getDisplayMetrics().density+0.5f); }
}
