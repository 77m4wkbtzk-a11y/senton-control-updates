package au.com.senton.link;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;

public class MainActivity extends Activity {
    private static final String UPDATE_URL = "https://raw.githubusercontent.com/77m4wkbtzk-a11y/senton-control-updates/main/phone-update.json";
    private TextView status;
    private TextView updateStatus;
    private long downloadId = -1;
    private String expectedSha = null;

    private final BroadcastReceiver downloadReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1);
            if (id == downloadId) handleDownloadedUpdate();
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE));
        }

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

        updateStatus = text("Updates: checking automatically…", 14, Color.rgb(135, 166, 196), false);
        root.addView(updateStatus, marginTop(10));

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

        TextView footer = text("Senton Link beta " + BuildConfig.VERSION_NAME, 13, Color.rgb(100, 125, 150), false);
        footer.setGravity(Gravity.CENTER);
        root.addView(footer, marginTop(24));

        setContentView(scroll);
        checkForUpdateAutomatically();
    }

    private void checkForUpdateAutomatically() {
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(UPDATE_URL).openConnection();
                conn.setConnectTimeout(10000);
                conn.setReadTimeout(10000);
                conn.setUseCaches(false);
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()))) {
                    StringBuilder jsonText = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) jsonText.append(line);
                    JSONObject json = new JSONObject(jsonText.toString());
                    String remoteVersion = json.getString("version");
                    String apkUrl = json.getString("download_url");
                    expectedSha = json.optString("sha256", "");
                    if (isNewer(remoteVersion, BuildConfig.VERSION_NAME)) {
                        runOnUiThread(() -> updateStatus.setText("Update " + remoteVersion + " found — downloading automatically…"));
                        startUpdateDownload(apkUrl, remoteVersion);
                    } else {
                        runOnUiThread(() -> updateStatus.setText("Updates: current (" + BuildConfig.VERSION_NAME + ")"));
                    }
                }
            } catch (Exception e) {
                runOnUiThread(() -> updateStatus.setText("Updates: check failed — will try next launch"));
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    private void startUpdateDownload(String apkUrl, String version) {
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        DownloadManager.Request request = new DownloadManager.Request(Uri.parse(apkUrl));
        request.setTitle("Senton Link " + version);
        request.setDescription("Downloading automatic update");
        request.setMimeType("application/vnd.android.package-archive");
        request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
        request.setDestinationInExternalFilesDir(this, null, "Senton-Link-update.apk");
        downloadId = dm.enqueue(request);
    }

    private void handleDownloadedUpdate() {
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        DownloadManager.Query query = new DownloadManager.Query().setFilterById(downloadId);
        try (Cursor cursor = dm.query(query)) {
            if (cursor == null || !cursor.moveToFirst()) return;
            int statusIndex = cursor.getColumnIndex(DownloadManager.COLUMN_STATUS);
            if (statusIndex < 0 || cursor.getInt(statusIndex) != DownloadManager.STATUS_SUCCESSFUL) {
                updateStatus.setText("Update download failed — will retry next launch");
                return;
            }
        }

        Uri uri = dm.getUriForDownloadedFile(downloadId);
        if (uri == null) {
            updateStatus.setText("Update downloaded but could not open installer");
            return;
        }

        new Thread(() -> {
            try {
                if (expectedSha != null && !expectedSha.isEmpty()) {
                    String actual = sha256(uri);
                    if (!expectedSha.equalsIgnoreCase(actual)) {
                        runOnUiThread(() -> updateStatus.setText("Update blocked: file verification failed"));
                        return;
                    }
                }
                runOnUiThread(() -> launchInstaller(uri));
            } catch (Exception e) {
                runOnUiThread(() -> updateStatus.setText("Update verification failed"));
            }
        }).start();
    }

    private void launchInstaller(Uri uri) {
        updateStatus.setText("Update ready — Android installer opening…");
        Intent install = new Intent(Intent.ACTION_VIEW);
        install.setDataAndType(uri, "application/vnd.android.package-archive");
        install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(install);
    }

    private String sha256(Uri uri) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) > 0) digest.update(buffer, 0, read);
        }
        StringBuilder out = new StringBuilder();
        for (byte b : digest.digest()) out.append(String.format("%02x", b));
        return out.toString();
    }

    private boolean isNewer(String remote, String local) {
        String[] r = remote.split("\\.");
        String[] l = local.split("\\.");
        int count = Math.max(r.length, l.length);
        for (int i = 0; i < count; i++) {
            int rv = i < r.length ? parseInt(r[i]) : 0;
            int lv = i < l.length ? parseInt(l[i]) : 0;
            if (rv != lv) return rv > lv;
        }
        return false;
    }

    private int parseInt(String value) {
        try { return Integer.parseInt(value.replaceAll("[^0-9].*$", "")); }
        catch (Exception e) { return 0; }
    }

    @Override
    protected void onDestroy() {
        try { unregisterReceiver(downloadReceiver); } catch (Exception ignored) {}
        super.onDestroy();
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
