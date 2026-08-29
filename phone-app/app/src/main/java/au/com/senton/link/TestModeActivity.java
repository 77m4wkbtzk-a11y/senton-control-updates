package com.senton.link;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

public class TestModeActivity extends Activity {
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(dp(18), dp(28), dp(18), dp(24));
        root.setBackgroundColor(Color.rgb(5, 8, 13));

        TextView brand = text("SENTON LINK", 30, Color.WHITE, true);
        brand.setGravity(Gravity.CENTER);
        root.addView(brand, full());

        TextView connected = text("● TEST MODE ACTIVE", 15, Color.rgb(58, 210, 84), true);
        connected.setGravity(Gravity.CENTER);
        root.addView(connected, mt(8));

        LinearLayout warning = new LinearLayout(this);
        warning.setOrientation(LinearLayout.VERTICAL);
        warning.setGravity(Gravity.CENTER);
        warning.setPadding(dp(18), dp(24), dp(18), dp(24));
        warning.setBackgroundColor(Color.rgb(185, 22, 22));

        TextView title = text("⚠  UNDER TESTING  ⚠", 28, Color.WHITE, true);
        title.setGravity(Gravity.CENTER);
        warning.addView(title, full());

        TextView main = text("DO NOT MOVE OR TURN OFF THIS PHONE", 24, Color.YELLOW, true);
        main.setGravity(Gravity.CENTER);
        warning.addView(main, mt(20));

        TextView body = text("SENTON LINK IS RUNNING AUTOMATED TESTS\n\nDO NOT LOCK THE SCREEN\nDO NOT MOVE THIS PHONE\nDO NOT TURN OFF THIS PHONE\nKEEP USB CONNECTED", 17, Color.WHITE, true);
        body.setGravity(Gravity.CENTER);
        warning.addView(body, mt(22));

        TextView progress = text("TESTING IN PROGRESS\nPLEASE WAIT…", 20, Color.WHITE, true);
        progress.setGravity(Gravity.CENTER);
        warning.addView(progress, mt(24));

        root.addView(warning, weightedPanel());

        TextView locks = text("🔒 DRIVE CONTROL LOCKED     🔒 SOLAR CHARGE LOCKED\nSafe Mode Active", 15, Color.rgb(160, 190, 225), true);
        locks.setGravity(Gravity.CENTER);
        root.addView(locks, mt(18));

        TextView footer = text("Screen will stay on while Senton Link Test Mode is active.", 13, Color.rgb(130, 150, 175), false);
        footer.setGravity(Gravity.CENTER);
        root.addView(footer, mt(14));

        setContentView(root);
    }

    private TextView text(String s, int size, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(size);
        t.setTextColor(color);
        if (bold) t.setTypeface(t.getTypeface(), android.graphics.Typeface.BOLD);
        return t;
    }

    private LinearLayout.LayoutParams full() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams mt(int top) {
        LinearLayout.LayoutParams lp = full();
        lp.topMargin = dp(top);
        return lp;
    }

    private LinearLayout.LayoutParams weightedPanel() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        lp.topMargin = dp(22);
        return lp;
    }

    private int dp(int v) {
        return (int)(v * getResources().getDisplayMetrics().density + 0.5f);
    }
}
