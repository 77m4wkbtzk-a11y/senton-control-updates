package com.senton.link;

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
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

public class MainActivity extends Activity {
    private static final String UPDATE_URL = "https://raw.githubusercontent.com/77m4wkbtzk-a11y/senton-control-updates/main/phone-update.json";
    private TextView updateStatus;
    private TextView pcStatus;
    private TextView telemetry;
    private EditText pcAddress;
    private long downloadId = -1;
    private String expectedSha = "";

    private final BroadcastReceiver downloadReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1);
            if (id == downloadId) handleDownloadedUpdate();
        }
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE));
        }

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(7, 12, 22));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(22), dp(18), dp(28));
        scroll.addView(root);

        root.addView(text("SENTON LINK", 30, Color.WHITE, true));
        root.addView(text("v" + BuildConfig.VERSION_NAME, 13, Color.rgb(38,139,255), true));
        root.addView(text("● SENTON PI DISCONNECTED — SAFE MODE", 15, Color.rgb(255,190,70), true), mt(16));

        updateStatus = text("Wi-Fi updates: checking…", 13, Color.rgb(135,166,196), false);
        root.addView(updateStatus, mt(8));

        root.addView(panel("WINDOWS LINK\nConnect Senton Link to Senton Control on this PC."), mt(16));
        pcAddress = new EditText(this);
        pcAddress.setText("http://127.0.0.1:8765");
        pcAddress.setTextColor(Color.WHITE);
        pcAddress.setHintTextColor(Color.GRAY);
        pcAddress.setSingleLine(true);
        root.addView(pcAddress, mt(8));

        LinearLayout pcButtons = row();
        Button connect = button("CONNECT", true);
        connect.setOnClickListener(v -> connectToPc());
        pcButtons.addView(connect, weight());
        Button test = button("SEND TEST", true);
        test.setOnClickListener(v -> sendTestMessage());
        pcButtons.addView(test, weight());
        root.addView(pcButtons, mt(8));

        pcStatus = panel("PC link: disconnected\nSafe mode active");
        root.addView(pcStatus, mt(10));

        root.addView(panel("MY SENTON\nReady for vehicle pairing\n\nVehicle controls remain disabled until Senton Pi pairing is complete."), mt(18));
        telemetry = panel("DASHBOARD\n\nSpeed          0 km/h\nMotor temp     -- °C\nBattery        -- V\nSignal         -- dBm");
        root.addView(telemetry, mt(12));

        LinearLayout actions = row();
        actions.addView(button("DRIVE", false), weight());
        actions.addView(button("TEST", false), weight());
        Button update = button("UPDATE", true);
        update.setOnClickListener(v -> checkForUpdateAutomatically());
        actions.addView(update, weight());
        root.addView(actions, mt(12));

        root.addView(panel("SOLAR CHARGE\n\nSolar input     --\nCharging        OFF\nBattery level   --\nCharge timer    --\n\nCharge controls remain locked until the Pi/car link is authenticated."), mt(16));
        LinearLayout charge = row();
        charge.addView(button("START CHARGE", false), weight());
        charge.addView(button("STOP CHARGE", false), weight());
        root.addView(charge, mt(8));

        root.addView(panel("SYSTEM\n\nApp status      OK\nUpdate channel  Beta\nVehicle link    Disconnected\nSafety mode     Active"), mt(16));
        TextView footer = text("Senton Link " + BuildConfig.VERSION_NAME + " • com.senton.link", 12, Color.rgb(90,115,140), false);
        footer.setGravity(Gravity.CENTER);
        root.addView(footer, mt(22));

        setContentView(scroll);
        checkForUpdateAutomatically();
        connectToPc();
    }

    private String baseUrl() {
        String value = pcAddress.getText().toString().trim();
        while (value.endsWith("/")) value = value.substring(0, value.length() - 1);
        return value;
    }

    private void connectToPc() {
        pcStatus.setText("PC link: connecting…");
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(baseUrl() + "/senton/status").openConnection();
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);
                conn.setUseCaches(false);
                String body = readAll(conn.getInputStream());
                JSONObject json = new JSONObject(body);
                String service = json.optString("service", "Senton Control");
                boolean safe = json.optBoolean("safe_mode", true);
                double speed = json.optDouble("speed_kmh", 0);
                String battery = json.isNull("battery_v") ? "--" : json.optString("battery_v", "--");
                String signal = json.isNull("signal") ? "--" : json.optString("signal", "--");
                String message = json.optString("message", "Windows link ready");
                runOnUiThread(() -> {
                    pcStatus.setText("PC link: CONNECTED\n" + service + "\n" + message + "\nSafe mode: " + (safe ? "ON" : "OFF"));
                    telemetry.setText("DASHBOARD\n\nSpeed          " + speed + " km/h\nMotor temp     -- °C\nBattery        " + battery + " V\nSignal         " + signal + " dBm");
                });
            } catch (Exception e) {
                runOnUiThread(() -> pcStatus.setText("PC link: disconnected\nCheck Senton Control and PC address\nSafe mode active"));
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    private void sendTestMessage() {
        pcStatus.setText("PC link: sending test…");
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(baseUrl() + "/senton/test-message").openConnection();
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json");
                byte[] data = "{\"message\":\"Senton Link phone test received\"}".getBytes(StandardCharsets.UTF_8);
                try (OutputStream out = conn.getOutputStream()) { out.write(data); }
                JSONObject json = new JSONObject(readAll(conn.getInputStream()));
                String echo = json.optString("echo", "Phone test received");
                runOnUiThread(() -> pcStatus.setText("PC link: CONNECTED\nTest successful\nPC echoed: " + echo + "\nSafe mode: ON"));
            } catch (Exception e) {
                runOnUiThread(() -> pcStatus.setText("PC link test failed\nSafe mode active"));
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    private String readAll(InputStream in) throws Exception {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(in))) {
            StringBuilder body = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) body.append(line);
            return body.toString();
        }
    }

    private void checkForUpdateAutomatically() {
        updateStatus.setText("Wi-Fi updates: checking…");
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(UPDATE_URL + "?t=" + System.currentTimeMillis()).openConnection();
                conn.setConnectTimeout(10000);
                conn.setReadTimeout(10000);
                conn.setUseCaches(false);
                JSONObject json = new JSONObject(readAll(conn.getInputStream()));
                String remoteVersion = json.getString("version");
                String apkUrl = json.getString("download_url");
                expectedSha = json.optString("sha256", "");
                if (isNewer(remoteVersion, BuildConfig.VERSION_NAME)) {
                    runOnUiThread(() -> updateStatus.setText("Update " + remoteVersion + " found — downloading…"));
                    startUpdateDownload(apkUrl, remoteVersion);
                } else {
                    runOnUiThread(() -> updateStatus.setText("Wi-Fi updates: current (" + BuildConfig.VERSION_NAME + ")"));
                }
            } catch (Exception e) {
                runOnUiThread(() -> updateStatus.setText("Wi-Fi updates: check failed — tap UPDATE to retry"));
            } finally { if (conn != null) conn.disconnect(); }
        }).start();
    }

    private void startUpdateDownload(String apkUrl, String version) {
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        DownloadManager.Request request = new DownloadManager.Request(Uri.parse(apkUrl));
        request.setTitle("Senton Link " + version);
        request.setDescription("Downloading verified update");
        request.setMimeType("application/vnd.android.package-archive");
        request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
        request.setDestinationInExternalFilesDir(this, null, "Senton-Link-update.apk");
        downloadId = dm.enqueue(request);
    }

    private void handleDownloadedUpdate() {
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        try (Cursor cursor = dm.query(new DownloadManager.Query().setFilterById(downloadId))) {
            if (cursor == null || !cursor.moveToFirst()) return;
            int idx = cursor.getColumnIndex(DownloadManager.COLUMN_STATUS);
            if (idx < 0 || cursor.getInt(idx) != DownloadManager.STATUS_SUCCESSFUL) return;
        }
        Uri uri = dm.getUriForDownloadedFile(downloadId);
        if (uri == null) return;
        new Thread(() -> {
            try {
                if (!expectedSha.isEmpty() && !expectedSha.equalsIgnoreCase(sha256(uri))) {
                    runOnUiThread(() -> updateStatus.setText("Update blocked: SHA-256 verification failed"));
                    return;
                }
                runOnUiThread(() -> launchInstaller(uri));
            } catch (Exception e) {
                runOnUiThread(() -> updateStatus.setText("Update verification failed"));
            }
        }).start();
    }

    private void launchInstaller(Uri uri) {
        updateStatus.setText("Update verified — opening Android installer…");
        Intent install = new Intent(Intent.ACTION_VIEW);
        install.setDataAndType(uri, "application/vnd.android.package-archive");
        install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(install);
    }

    private String sha256(Uri uri) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) throw new IllegalStateException("APK unavailable");
            byte[] buf = new byte[8192]; int n;
            while ((n = in.read(buf)) > 0) digest.update(buf, 0, n);
        }
        StringBuilder out = new StringBuilder();
        for (byte b : digest.digest()) out.append(String.format("%02x", b));
        return out.toString();
    }

    private boolean isNewer(String remote, String local) {
        String[] r = remote.split("\\."); String[] l = local.split("\\.");
        int count = Math.max(r.length, l.length);
        for (int i=0; i<count; i++) {
            int rv = i<r.length ? num(r[i]) : 0; int lv = i<l.length ? num(l[i]) : 0;
            if (rv != lv) return rv > lv;
        }
        return false;
    }

    private int num(String s) {
        try { String c = s.replaceAll("[^0-9].*$", ""); return c.isEmpty()?0:Integer.parseInt(c); }
        catch (Exception e) { return 0; }
    }

    @Override protected void onDestroy() {
        try { unregisterReceiver(downloadReceiver); } catch (Exception ignored) {}
        super.onDestroy();
    }

    private TextView panel(String s) { TextView t=text(s,14,Color.rgb(220,232,244),false); t.setPadding(dp(16),dp(16),dp(16),dp(16)); t.setBackgroundColor(Color.rgb(18,29,43)); return t; }
    private Button button(String label, boolean enabled) { Button b=new Button(this); b.setText(label); b.setTextSize(12); b.setAllCaps(false); b.setEnabled(enabled); b.setMinHeight(dp(48)); return b; }
    private LinearLayout row() { LinearLayout r=new LinearLayout(this); r.setOrientation(LinearLayout.HORIZONTAL); return r; }
    private LinearLayout.LayoutParams weight() { LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1f); lp.setMargins(dp(4),0,dp(4),0); return lp; }
    private TextView text(String s,int size,int color,boolean bold) { TextView t=new TextView(this); t.setText(s); t.setTextSize(size); t.setTextColor(color); if (bold) t.setTypeface(t.getTypeface(),android.graphics.Typeface.BOLD); return t; }
    private LinearLayout.LayoutParams mt(int top) { LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT); lp.topMargin=dp(top); return lp; }
    private int dp(int v) { return (int)(v*getResources().getDisplayMetrics().density+0.5f); }
}
