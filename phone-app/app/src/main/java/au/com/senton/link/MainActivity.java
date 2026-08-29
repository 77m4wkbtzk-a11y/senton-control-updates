package au.com.senton.link;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public class MainActivity extends Activity {
    private TextView status;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.rgb(7, 12, 22));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(24), dp(20), dp(28));
        scroll.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = text("SENTON LINK", 30, Color.WHITE, true);
        root.addView(title);
        TextView subtitle = text("Vehicle control companion", 15, Color.rgb(135, 166, 196), false);
        root.addView(subtitle, marginTop(4));

        status = text("●  DISCONNECTED — safe mode", 16, Color.rgb(255, 190, 70), true);
        root.addView(status, marginTop(22));

        root.addView(section("VEHICLE", "Waiting for Senton car connection\nSpeed: 0 km/h   •   Battery: --   •   Signal: --"), marginTop(16));
        root.addView(section("SOLAR CHARGE", "Solar input: --\nCharging: OFF\nBattery level: --\nCharge controls remain locked until the Pi/car link is authenticated."), marginTop(14));

        Button start = button("START CHARGE");
        start.setEnabled(false);
        root.addView(start, marginTop(14));

        Button stop = button("STOP CHARGE");
        stop.setEnabled(false);
        root.addView(stop, marginTop(10));

        LinearLayout timers = new LinearLayout(this);
        timers.setOrientation(LinearLayout.HORIZONTAL);
        timers.setGravity(Gravity.CENTER_HORIZONTAL);
        String[] labels = {"30 MIN", "1 HOUR", "2 HOURS"};
        for (String label : labels) {
            Button b = button(label);
            b.setEnabled(false);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(48), 1f);
            lp.setMargins(dp(4), 0, dp(4), 0);
            timers.addView(b, lp);
        }
        root.addView(timers, marginTop(10));

        root.addView(section("SAFETY", "Senton Link only grants or removes charge permission. The dedicated charger/BMS remains responsible for battery voltage, current, balancing and thermal protection."), marginTop(18));

        TextView footer = text("Senton Link beta 0.1.0", 13, Color.rgb(100, 125, 150), false);
        footer.setGravity(Gravity.CENTER);
        root.addView(footer, marginTop(24));

        setContentView(scroll);
    }

    private TextView section(String heading, String body) {
        TextView box = text(heading + "\n\n" + body, 15, Color.rgb(220, 232, 244), false);
        box.setPadding(dp(16), dp(16), dp(16), dp(16));
        box.setBackgroundColor(Color.rgb(18, 29, 43));
        return box;
    }

    private Button button(String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(15);
        b.setAllCaps(false);
        b.setMinHeight(dp(50));
        return b;
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(size);
        t.setTextColor(color);
        if (bold) t.setTypeface(t.getTypeface(), android.graphics.Typeface.BOLD);
        return t;
    }

    private LinearLayout.LayoutParams marginTop(int top) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(top);
        return lp;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
