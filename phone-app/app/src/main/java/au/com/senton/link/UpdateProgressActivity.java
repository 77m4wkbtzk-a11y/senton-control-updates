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
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

public class UpdateProgressActivity extends Activity {
    private static final String UPDATE_URL = "https://raw.githubusercontent.com/77m4wkbtzk-a11y/senton-control-updates/main/phone-update.json";
    private static final String PREFS = "senton_link";
    private static final String KEY_DOWNLOAD_ID = "update_download_id";
    private static final String KEY_EXPECTED_SHA = "update_expected_sha";
    private static final String KEY_UPDATE_STAGE = "update_stage";
    private static final String KEY_UPDATE_VERSION = "update_version";
    private static final int MAX_RESPONSE_CHARS = 65536;

    private TextView stage;
    private TextView detail;
    private TextView percent;
    private ProgressBar progress;
    private long downloadId = -1;
    private String expectedSha = "";
    private final AtomicBoolean updateCheckInFlight = new AtomicBoolean(false);
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean polling = false;

    private final Runnable progressPoll = new Runnable() {
        @Override public void run() {
            if (!polling) return;
            refreshDownloadProgress();
            handler.postDelayed(this, 1000);
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
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        if (Build.VERSION.SDK_INT >= 33) registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), RECEIVER_NOT_EXPORTED);
        else registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE));

        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        downloadId = prefs.getLong(KEY_DOWNLOAD_ID, -1);
        expectedSha = prefs.getString(KEY_EXPECTED_SHA, "");

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(7, 12, 22));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(28), dp(20), dp(28));
        scroll.addView(root);

        TextView title = text("SENTON LINK UPDATE", 28, Color.WHITE, true);
        title.setGravity(Gravity.CENTER);
        root.addView(title);

        TextView version = text("Installed: " + BuildConfig.VERSION_NAME, 13, Color.rgb(38, 139, 255), true);
        version.setGravity(Gravity.CENTER);
        root.addView(version, mt(8));

        TextView info = text("You can close this page and return to the dashboard.\nA queued Android download will continue in the background.", 14, Color.rgb(190, 210, 230), false);
        info.setGravity(Gravity.CENTER);
        root.addView(info, mt(20));

        stage = text(prefs.getString(KEY_UPDATE_STAGE, "Checking for updates…"), 22, Color.WHITE, true);
        stage.setGravity(Gravity.CENTER);
        stage.setPadding(dp(14), dp(18), dp(14), dp(18));
        stage.setBackgroundColor(Color.rgb(18, 29, 43));
        root.addView(stage, mt(24));

        detail = text("Preparing update status…", 14, Color.rgb(160, 185, 210), false);
        detail.setGravity(Gravity.CENTER);
        root.addView(detail, mt(16));

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setProgress(0);
        progress.setIndeterminate(true);
        root.addView(progress, mt(20));

        percent = text("", 15, Color.WHITE, true);
        percent.setGravity(Gravity.CENTER);
        root.addView(percent, mt(8));

        Button check = button("CHECK FOR UPDATE");
        check.setOnClickListener(v -> checkForUpdateAutomatically());
        root.addView(check, mt(24));

        Button close = button("BACK TO DASHBOARD");
        close.setOnClickListener(v -> finish());
        root.addView(close, mt(10));

        TextView footer = text("Closing this page does not cancel a queued update.", 12, Color.rgb(90, 115, 140), false);
        footer.setGravity(Gravity.CENTER);
        root.addView(footer, mt(22));

        setContentView(scroll);

        if (!resumePendingUpdateIfAny()) checkForUpdateAutomatically();
    }

    @Override protected void onResume() {
        super.onResume();
        polling = true;
        handler.removeCallbacks(progressPoll);
        handler.post(progressPoll);
    }

    @Override protected void onPause() {
        polling = false;
        handler.removeCallbacks(progressPoll);
        super.onPause();
    }

    private void setStage(String value) {
        stage.setText(value);
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_UPDATE_STAGE, value).apply();
    }

    private void checkForUpdateAutomatically() {
        if (!updateCheckInFlight.compareAndSet(false, true)) {
            setStage("Wi-Fi updates: check already running");
            return;
        }
        setStage("CHECKING FOR UPDATE");
        detail.setText("Contacting the Senton Link beta update channel…");
        progress.setIndeterminate(true);
        percent.setText("");

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
                    runOnUiThread(() -> {
                        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_UPDATE_VERSION, remoteVersion).apply();
                        if (downloadId != -1) {
                            setStage("Update in progress — download already queued");
                            detail.setText("Senton Link " + remoteVersion + " is already downloading.");
                        } else {
                            setStage("Update in progress — downloading Senton Link " + remoteVersion + "…");
                            detail.setText("Downloading the verified APK. You can return to the dashboard.");
                            startUpdateDownload(apkUrl, remoteVersion, sha);
                        }
                    });
                } else {
                    runOnUiThread(() -> {
                        setStage("UP TO DATE");
                        detail.setText("Senton Link " + BuildConfig.VERSION_NAME + " is the current beta build.");
                        progress.setIndeterminate(false);
                        progress.setProgress(100);
                        percent.setText("100%");
                    });
                }
            } catch (Exception e) {
                runOnUiThread(() -> {
                    setStage("UPDATE CHECK FAILED");
                    detail.setText("Could not reach or validate the update channel. Tap CHECK FOR UPDATE to retry.");
                    progress.setIndeterminate(false);
                    progress.setProgress(0);
                    percent.setText("");
                });
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
        progress.setIndeterminate(true);
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
                setStage("Update in progress — verifying downloaded update…");
                detail.setText("Download complete. Checking SHA-256 before installation.");
                handleDownloadedUpdate();
                return true;
            }
            if (status == DownloadManager.STATUS_PENDING || status == DownloadManager.STATUS_RUNNING || status == DownloadManager.STATUS_PAUSED) {
                setStage("Update in progress — download already queued");
                detail.setText("The Android download is still active in the background.");
                return true;
            }
        }
        setStage("UPDATE DOWNLOAD FAILED");
        detail.setText("The queued download failed. Tap CHECK FOR UPDATE to retry.");
        clearPendingDownloadState();
        return false;
    }

    private void refreshDownloadProgress() {
        if (downloadId == -1) return;
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        try (Cursor cursor = dm.query(new DownloadManager.Query().setFilterById(downloadId))) {
            if (cursor == null || !cursor.moveToFirst()) return;
            int statusIndex = cursor.getColumnIndex(DownloadManager.COLUMN_STATUS);
            int doneIndex = cursor.getColumnIndex(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR);
            int totalIndex = cursor.getColumnIndex(DownloadManager.COLUMN_TOTAL_SIZE_BYTES);
            if (statusIndex < 0) return;
            int status = cursor.getInt(statusIndex);
            if (status == DownloadManager.STATUS_SUCCESSFUL) {
                progress.setIndeterminate(false);
                progress.setProgress(100);
                percent.setText("100%");
                return;
            }
            if (doneIndex >= 0 && totalIndex >= 0) {
                long done = cursor.getLong(doneIndex);
                long total = cursor.getLong(totalIndex);
                if (total > 0) {
                    int p = (int) Math.min(100, (done * 100L) / total);
                    progress.setIndeterminate(false);
                    progress.setProgress(p);
                    percent.setText(p + "%");
                    detail.setText(String.format(Locale.US, "Downloading %.1f MB of %.1f MB", done / 1048576.0, total / 1048576.0));
                } else {
                    progress.setIndeterminate(true);
                    percent.setText("");
                }
            }
        } catch (Exception ignored) {}
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
                setStage("UPDATE VERIFICATION FAILED");
                detail.setText("Downloaded file could not be found.");
                clearPendingDownloadState();
                return;
            }
            int idx = cursor.getColumnIndex(DownloadManager.COLUMN_STATUS);
            if (idx < 0 || cursor.getInt(idx) != DownloadManager.STATUS_SUCCESSFUL) {
                setStage("Update download failed — tap UPDATE to retry");
                detail.setText("Android reported that the download did not complete successfully.");
                clearPendingDownloadState();
                return;
            }
        }

        Uri uri = dm.getUriForDownloadedFile(downloadId);
        if (uri == null) {
            setStage("Update downloaded but installer could not open");
            detail.setText("The downloaded APK URI is unavailable.");
            clearPendingDownloadState();
            return;
        }

        setStage("Update in progress — verifying downloaded update…");
        detail.setText("Checking SHA-256 integrity…");
        progress.setIndeterminate(true);
        percent.setText("");

        new Thread(() -> {
            try {
                if (!expectedSha.matches("[0-9a-f]{64}") || !expectedSha.equalsIgnoreCase(sha256(uri))) {
                    runOnUiThread(() -> {
                        setStage("Update blocked: SHA-256 verification failed");
                        detail.setText("The APK did not match the signed update manifest. Installation has been blocked.");
                        clearPendingDownloadState();
                    });
                    return;
                }
                runOnUiThread(() -> launchInstaller(uri));
            } catch (Exception e) {
                runOnUiThread(() -> {
                    setStage("Update verification failed");
                    detail.setText("The APK could not be verified.");
                    clearPendingDownloadState();
                });
            }
        }, "senton-update-verify").start();
    }

    private void launchInstaller(Uri uri) {
        setStage("Update in progress — verified, opening Android installer…");
        detail.setText("Verification passed. Android will ask you to confirm the installation.");
        progress.setIndeterminate(false);
        progress.setProgress(100);
        percent.setText("100%");
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

    private String cleanText(String value, int max) {
        if (value == null) return "";
        String clean = value.replace('\n', ' ').replace('\r', ' ').trim();
        return clean.length() <= max ? clean : clean.substring(0, max);
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
        } catch (Exception e) {
            return 0;
        }
    }

    @Override protected void onDestroy() {
        polling = false;
        handler.removeCallbacksAndMessages(null);
        try { unregisterReceiver(downloadReceiver); } catch (Exception ignored) {}
        super.onDestroy();
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(size);
        t.setTextColor(color);
        if (bold) t.setTypeface(t.getTypeface(), android.graphics.Typeface.BOLD);
        return t;
    }

    private Button button(String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(13);
        b.setAllCaps(false);
        b.setMinHeight(dp(52));
        return b;
    }

    private LinearLayout.LayoutParams mt(int top) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(top);
        return lp;
    }

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }
}
