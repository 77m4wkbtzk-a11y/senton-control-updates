package com.senton.link;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
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
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends Activity {
    private static final String UPDATE_URL = "https://raw.githubusercontent.com/77m4wkbtzk-a11y/senton-control-updates/main/phone-update.json";
    private static final String PREFS = "senton_link";
    private static final String KEY_PC_ADDRESS = "pc_address";
    private static final String KEY_DOWNLOAD_ID = "update_download_id";
    private static final String KEY_EXPECTED_SHA = "update_expected_sha";
    private static final String DEFAULT_PC_URL = "http://127.0.0.1:8765";
    private static final int SENTON_PROTOCOL = 1;
    private static final int MAX_RESPONSE_CHARS = 65536;

    private TextView updateStatus;
    private TextView pcStatus;
    private TextView telemetry;
    private EditText pcAddress;
    private long downloadId = -1;
    private String expectedSha = "";

    private final Handler pollHandler = new Handler(Looper.getMainLooper());
    private final AtomicBoolean pcRequestInFlight = new AtomicBoolean(false);
    private final AtomicBoolean updateCheckInFlight = new AtomicBoolean(false);
    private boolean polling = false;

    private final Runnable pcPoll = new Runnable() {
        @Override public void run() {
            if (!polling) return;
            connectToPc(false);
            pollHandler.postDelayed(this, 3000);
        }
    };

    private final BroadcastReceiver downloadReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1);
            if (id == downloadId) handleDownloadedUpdate();
        }
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (BuildConfig.TEST_MODE) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), RECEIVER_NOT_EXPORTED);
        else registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE));

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        downloadId = prefs.getLong(KEY_DOWNLOAD_ID, -1);
        expectedSha = prefs.getString(KEY_EXPECTED_SHA, "");
        if (downloadId == -1 || expectedSha == null || !expectedSha.matches("[0-9a-f]{64}")) {
            clearPendingDownloadState();
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

        TextView testing = text("⚠ UNDER TESTING ⚠\nDO NOT MOVE OR TURN OFF THIS PHONE\nKEEP USB CONNECTED", 18, Color.WHITE, true);
        testing.setGravity(Gravity.CENTER);
        testing.setPadding(dp(14), dp(14), dp(14), dp(14));
        testing.setBackgroundColor(Color.rgb(180, 35, 35));
        testing.setVisibility(BuildConfig.TEST_MODE ? View.VISIBLE : View.GONE);
        root.addView(testing, mt(14));

        root.addView(text("● SENTON PI DISCONNECTED — SAFE MODE", 15, Color.rgb(255,190,70), true), mt(16));
        updateStatus = text("Wi-Fi updates: checking…", 13, Color.rgb(135,166,196), false);
        root.addView(updateStatus, mt(8));

        root.addView(panel("WINDOWS LINK\nConnect Senton Link to Senton Control on this PC."), mt(16));
        pcAddress = new EditText(this);
        pcAddress.setText(prefs.getString(KEY_PC_ADDRESS, DEFAULT_PC_URL));
        pcAddress.setTextColor(Color.WHITE);
        pcAddress.setHintTextColor(Color.GRAY);
        pcAddress.setSingleLine(true);
        root.addView(pcAddress, mt(8));

        LinearLayout pcButtons = row();
        Button connect = button("CONNECT", true);
        connect.setOnClickListener(v -> connectToPc(true));
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

        String appStatus = BuildConfig.TEST_MODE ? "TESTING" : "OK";
        root.addView(panel("SYSTEM\n\nApp status      " + appStatus + "\nUpdate channel  Beta\nVehicle link    Disconnected\nSafety mode     Active"), mt(16));
        TextView footer = text("Senton Link " + BuildConfig.VERSION_NAME + " • com.senton.link", 12, Color.rgb(90,115,140), false);
        footer.setGravity(Gravity.CENTER);
        root.addView(footer, mt(22));

        setContentView(scroll);
        if (!resumePendingUpdateIfAny()) {
            checkForUpdateAutomatically();
        }
    }

    @Override protected void onResume() {
        super.onResume();
        polling = true;
        pollHandler.removeCallbacks(pcPoll);
        pollHandler.post(pcPoll);
    }

    @Override protected void onPause() {
        polling = false;
        pollHandler.removeCallbacks(pcPoll);
        super.onPause();
    }

    private String captureBaseUrl() {
        String value = pcAddress.getText().toString().trim();
        while (value.endsWith("/")) value = value.substring(0, value.length() - 1);
        if (value.length() < 8 || value.length() > 200 || !(value.startsWith("http://") || value.startsWith("https://"))) return "";
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_PC_ADDRESS, value).apply();
        return value;
    }

    private void connectToPc(boolean showConnecting) {
        if (!pcRequestInFlight.compareAndSet(false, true)) return;
        final String baseUrl = captureBaseUrl();
        if (baseUrl.isEmpty()) {
            pcRequestInFlight.set(false);
            setPcDisconnected("Invalid PC address");
            return;
        }
        if (showConnecting) pcStatus.setText("PC link: connecting…\nSafe mode active");

        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(baseUrl + "/senton/status").openConnection();
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);
                conn.setUseCaches(false);
                conn.setRequestProperty("Accept", "application/json");
                int code = conn.getResponseCode();
                if (code != 200) throw new IllegalStateException("PC status HTTP " + code);

                JSONObject json = new JSONObject(readAllLimited(conn.getInputStream(), MAX_RESPONSE_CHARS));
                if (!"Senton Control".equals(json.optString("service", "")) || json.optInt("protocol", -1) != SENTON_PROTOCOL || !json.optBoolean("safe_mode", false)) {
                    throw new SecurityException("Untrusted or unsafe PC response");
                }

                double speed = json.optDouble("speed_kmh", 0);
                if (!Double.isFinite(speed) || speed < 0 || speed > 1000) speed = 0;
                String battery = safeValue(json, "battery_v");
                String signal = safeValue(json, "signal");
                String message = cleanText(json.optString("message", "Windows link ready"), 120);
                final double finalSpeed = speed;
                runOnUiThread(() -> {
                    pcStatus.setText("PC link: CONNECTED\nSenton Control\n" + message + "\nSafe mode: ON");
                    telemetry.setText(String.format(Locale.US,
                            "DASHBOARD\n\nSpeed          %.1f km/h\nMotor temp     -- °C\nBattery        %s V\nSignal         %s dBm",
                            finalSpeed, battery, signal));
                });
            } catch (Exception e) {
                runOnUiThread(() -> setPcDisconnected("Check Senton Control and PC address"));
            } finally {
                if (conn != null) conn.disconnect();
                pcRequestInFlight.set(false);
            }
        }, "senton-pc-status").start();
    }

    private void setPcDisconnected(String reason) {
        pcStatus.setText("PC link: disconnected\n" + reason + "\nSafe mode active");
        telemetry.setText("DASHBOARD\n\nSpeed          0 km/h\nMotor temp     -- °C\nBattery        -- V\nSignal         -- dBm");
    }

    private void sendTestMessage() {
        final String baseUrl = captureBaseUrl();
        if (baseUrl.isEmpty()) {
            setPcDisconnected("Invalid PC address");
            return;
        }
        pcStatus.setText("PC link: sending test…\nSafe mode active");
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(baseUrl + "/senton/test-message").openConnection();
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setRequestProperty("Accept", "application/json");
                byte[] data = "{\"message\":\"Senton Link phone test received\"}".getBytes(StandardCharsets.UTF_8);
                conn.setFixedLengthStreamingMode(data.length);
                try (OutputStream out = conn.getOutputStream()) { out.write(data); }
                int code = conn.getResponseCode();
                if (code != 200) throw new IllegalStateException("PC test HTTP " + code);
                JSONObject json = new JSONObject(readAllLimited(conn.getInputStream(), MAX_RESPONSE_CHARS));
                if (!json.optBoolean("ok", false) || !json.optBoolean("safe_mode", false) || json.optInt("protocol", -1) != SENTON_PROTOCOL) {
                    throw new SecurityException("Unsafe PC test response");
                }
                String echo = cleanText(json.optString("echo", "Phone test received"), 120);
                runOnUiThread(() -> pcStatus.setText("PC link: CONNECTED\nTest successful\nPC echoed: " + echo + "\nSafe mode: ON"));
            } catch (Exception e) {
                runOnUiThread(() -> setPcDisconnected("PC link test failed"));
            } finally {
                if (conn != null) conn.disconnect();
            }
        }, "senton-pc-test").start();
    }

    private String safeValue(JSONObject json, String key) {
        if (json.isNull(key)) return "--";
        return cleanText(json.optString(key, "--"), 20);
    }

    private String cleanText(String value, int max) {
        if (value == null) return "";
        String clean = value.replace('\n', ' ').replace('\r', ' ').trim();
        return clean.length() <= max ? clean : clean.substring(0, max);
    }

    private String readAllLimited(InputStream in, int maxChars) throws Exception {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            StringBuilder body = new StringBuilder();
            char[] buffer = new char[1024];
            int n;
            while ((n = reader.read(buffer)) != -1) {
                body.append(buffer, 0, n);
                if (body.length() > maxChars) throw new IllegalStateException("Response too large");
            }
            return body.toString();
        }
    }

    private void checkForUpdateAutomatically() {
        if (!updateCheckInFlight.compareAndSet(false, true)) {
            updateStatus.setText("Wi-Fi updates: check already running");
            return;
        }
        updateStatus.setText("Wi-Fi updates: checking…");
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(UPDATE_URL + "?t=" + System.currentTimeMillis()).openConnection();
                conn.setConnectTimeout(10000);
                conn.setReadTimeout(10000);
                conn.setUseCaches(false);
                conn.setRequestProperty("Cache-Control", "no-cache");
                int code = conn.getResponseCode();
                if (code != 200) throw new IllegalStateException("Update HTTP " + code);
                JSONObject json = new JSONObject(readAllLimited(conn.getInputStream(), MAX_RESPONSE_CHARS));
                String remoteVersion = cleanText(json.getString("version"), 40);
                String apkUrl = json.getString("download_url").trim();
                String sha = json.optString("sha256", "").trim().toLowerCase(Locale.US);
                if (remoteVersion.isEmpty() || !apkUrl.startsWith("https://") || !sha.matches("[0-9a-f]{64}")) throw new SecurityException("Invalid update manifest");
                if (isNewer(remoteVersion, BuildConfig.VERSION_NAME)) {
                    if (downloadId != -1) runOnUiThread(() -> updateStatus.setText("Update in progress — download already queued"));
                    else {
                        runOnUiThread(() -> updateStatus.setText("Update in progress — downloading Senton Link " + remoteVersion + "…"));
                        startUpdateDownload(apkUrl, remoteVersion, sha);
                    }
                } else runOnUiThread(() -> updateStatus.setText("Wi-Fi updates: current (" + BuildConfig.VERSION_NAME + ")"));
            } catch (Exception e) {
                runOnUiThread(() -> updateStatus.setText("Wi-Fi updates: check failed — tap UPDATE to retry"));
            } finally {
                if (conn != null) conn.disconnect();
                updateCheckInFlight.set(false);
            }
        }, "senton-update-check").start();
    }

    private void startUpdateDownload(String apkUrl, String version, String sha) {
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        DownloadManager.Request request = new DownloadManager.Request(Uri.parse(apkUrl));
        request.setTitle("Senton Link " + version);
        request.setDescription("Downloading verified update");
        request.setMimeType("application/vnd.android.package-archive");
        request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
        String safeVersion = version.replaceAll("[^A-Za-z0-9._-]", "_");
        request.setDestinationInExternalFilesDir(this, null, "Senton-Link-" + safeVersion + "-" + System.currentTimeMillis() + ".apk");
        long id = dm.enqueue(request);
        savePendingDownloadState(id, sha);
    }

    private boolean resumePendingUpdateIfAny() {
        if (downloadId == -1 || expectedSha == null || !expectedSha.matches("[0-9a-f]{64}")) return false;
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        try (Cursor cursor = dm.query(new DownloadManager.Query().setFilterById(downloadId))) {
            if (cursor == null || !cursor.moveToFirst()) {
                clearPendingDownloadState();
                return false;
            }
            int idx = cursor.getColumnIndex(DownloadManager.COLUMN_STATUS);
            if (idx < 0) {
                clearPendingDownloadState();
                return false;
            }
            int status = cursor.getInt(idx);
            if (status == DownloadManager.STATUS_SUCCESSFUL) {
                updateStatus.setText("Update in progress — verifying downloaded update…");
                handleDownloadedUpdate();
                return true;
            }
            if (status == DownloadManager.STATUS_PENDING || status == DownloadManager.STATUS_RUNNING || status == DownloadManager.STATUS_PAUSED) {
                updateStatus.setText("Update in progress — download already queued");
                return true;
            }
        }
        updateStatus.setText("Update download failed — tap UPDATE to retry");
        clearPendingDownloadState();
        return false;
    }

    private void savePendingDownloadState(long id, String sha) {
        downloadId = id;
        expectedSha = sha;
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putLong(KEY_DOWNLOAD_ID, id)
                .putString(KEY_EXPECTED_SHA, sha)
                .apply();
    }

    private void clearPendingDownloadState() {
        downloadId = -1;
        expectedSha = "";
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .remove(KEY_DOWNLOAD_ID)
                .remove(KEY_EXPECTED_SHA)
                .apply();
    }

    private void handleDownloadedUpdate() {
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        try (Cursor cursor = dm.query(new DownloadManager.Query().setFilterById(downloadId))) {
            if (cursor == null || !cursor.moveToFirst()) {
                updateStatus.setText("Update download could not be verified");
                clearPendingDownloadState();
                return;
            }
            int idx = cursor.getColumnIndex(DownloadManager.COLUMN_STATUS);
            if (idx < 0 || cursor.getInt(idx) != DownloadManager.STATUS_SUCCESSFUL) {
                updateStatus.setText("Update download failed — tap UPDATE to retry");
                clearPendingDownloadState();
                return;
            }
        }
        Uri uri = dm.getUriForDownloadedFile(downloadId);
        if (uri == null) {
            updateStatus.setText("Update downloaded but installer could not open");
            clearPendingDownloadState();
            return;
        }
        updateStatus.setText("Update in progress — verifying downloaded update…");
        new Thread(() -> {
            try {
                if (!expectedSha.matches("[0-9a-f]{64}") || !expectedSha.equalsIgnoreCase(sha256(uri))) {
                    runOnUiThread(() -> { updateStatus.setText("Update blocked: SHA-256 verification failed"); clearPendingDownloadState(); });
                    return;
                }
                runOnUiThread(() -> launchInstaller(uri));
            } catch (Exception e) {
                runOnUiThread(() -> { updateStatus.setText("Update verification failed"); clearPendingDownloadState(); });
            }
        }, "senton-update-verify").start();
    }

    private void launchInstaller(Uri uri) {
        updateStatus.setText("Update in progress — verified, opening Android installer…");
        Intent install = new Intent(Intent.ACTION_VIEW);
        install.setDataAndType(uri, "application/vnd.android.package-archive");
        install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        clearPendingDownloadState();
        startActivity(install);
    }

    private String sha256(Uri uri) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) throw new IllegalStateException("APK unavailable");
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) digest.update(buf, 0, n);
        }
        StringBuilder out = new StringBuilder();
        for (byte b : digest.digest()) out.append(String.format(Locale.US, "%02x", b));
        return out.toString();
    }

    private boolean isNewer(String remote, String local) {
        String[] r = remote.split("\\.");
        String[] l = local.split("\\.");
        int count = Math.max(r.length, l.length);
        for (int i = 0; i < count; i++) {
            int rv = i < r.length ? num(r[i]) : 0;
            int lv = i < l.length ? num(l[i]) : 0;
            if (rv != lv) return rv > lv;
        }
        return false;
    }

    private int num(String s) {
        try {
            String c = s.replaceAll("[^0-9].*$", "");
            return c.isEmpty() ? 0 : Integer.parseInt(c);
        } catch (Exception e) { return 0; }
    }

    @Override protected void onDestroy() {
        polling = false;
        pollHandler.removeCallbacksAndMessages(null);
        try { unregisterReceiver(downloadReceiver); } catch (Exception ignored) {}
        super.onDestroy();
    }

    private TextView panel(String s) { TextView t=text(s,14,Color.rgb(220,232,244),false); t.setPadding(dp(16),dp(16),dp(16),dp(16)); t.setBackgroundColor(Color.rgb(18,29,43)); return t; }
    private Button button(String label, boolean enabled) { Button b=new Button(this); b.setText(label); b.setTextSize(12); b.setAllCaps(false); b.setEnabled(enabled); b.setMinHeight(dp(48)); return b; }
    private LinearLayout row() { LinearLayout r=new LinearLayout(this); r.setOrientation(LinearLayout.HORIZONTAL); return r; }
    private LinearLayout.LayoutParams weight() { LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1f); lp.setMargins(dp(4),0,dp(4),0); return lp; }
    private TextView text(String s,int size,int color,boolean bold) { TextView t=new TextView(this); t.setText(s); t.setTextSize(size); t.setTextColor(color); if(bold)t.setTypeface(t.getTypeface(),android.graphics.Typeface.BOLD); return t; }
    private LinearLayout.LayoutParams mt(int top) { LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT); lp.topMargin=dp(top); return lp; }
    private int dp(int v) { return (int)(v*getResources().getDisplayMetrics().density+0.5f); }
}
