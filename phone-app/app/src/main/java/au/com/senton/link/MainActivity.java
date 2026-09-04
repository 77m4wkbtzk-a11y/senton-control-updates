package com.senton.link;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.security.MessageDigest;
import java.security.SecureRandom;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;

public class MainActivity extends Activity {
    private static final String PREFS = "senton_link";
    private static final String KEY_UPDATE_STAGE = "update_stage";
    private static final String EXTRA_TEST_MODE = "senton_test_mode";
    private static final String KEY_MAINT_PIN_SALT = "maintenance_pin_salt";
    private static final String KEY_MAINT_PIN_HASH = "maintenance_pin_hash";
    private static final String KEY_MAINT_PIN_FAILS = "maintenance_pin_fails";
    private static final String KEY_MAINT_PIN_LOCK_UNTIL = "maintenance_pin_lock_until";
    private static final String KEY_TEST_SMS_NUMBER = "test_sms_number";
    private static final int PIN_MIN_LENGTH = 4;
    private static final int PIN_MAX_LENGTH = 8;
    private static final int MAX_PIN_FAILURES = 5;
    private static final long PIN_LOCKOUT_MS = 60_000L;
    private static final int PBKDF2_ITERATIONS = 120_000;
    private static final int PBKDF2_KEY_BITS = 256;

    private TextView updateStatus;
    private TextView testBanner;
    private TextView systemPanel;
    private boolean testMode;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        testMode = getIntent() != null && getIntent().getBooleanExtra(EXTRA_TEST_MODE, false);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
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

        Button testSms = button("TEST SIGHTING SMS", true);
        testSms.setOnClickListener(v -> showTestSmsDialog());
        root.addView(testSms, mt(12));
        TextView smsHint = text("Test only — opens your SMS app with an unverified possible-sighting message. You review it before sending.", 12, Color.rgb(135, 166, 196), false);
        smsHint.setGravity(Gravity.CENTER);
        root.addView(smsHint, mt(6));

        systemPanel = panel(systemText());
        root.addView(systemPanel, mt(16));

        Button maintenance = button("HOLD FOR ANDROID MAINTENANCE", true);
        maintenance.setOnClickListener(v -> { });
        maintenance.setOnLongClickListener(v -> {
            requestMaintenanceAccess();
            return true;
        });
        root.addView(maintenance, mt(16));
        TextView maintenanceHint = text("Long-press only. Opens Android settings only after the local maintenance PIN is verified.", 12, Color.rgb(135, 166, 196), false);
        maintenanceHint.setGravity(Gravity.CENTER);
        root.addView(maintenanceHint, mt(6));

        TextView footer = text("Senton Link " + BuildConfig.VERSION_NAME + " • com.senton.link", 12, Color.rgb(90, 115, 140), false);
        footer.setGravity(Gravity.CENTER);
        root.addView(footer, mt(22));
        setContentView(scroll);
    }

    private void showTestSmsDialog() {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        EditText number = new EditText(this);
        number.setHint("Your mobile number");
        number.setSingleLine(true);
        number.setInputType(InputType.TYPE_CLASS_PHONE);
        number.setText(prefs.getString(KEY_TEST_SMS_NUMBER, ""));
        number.setSelection(number.getText().length());

        new AlertDialog.Builder(this)
                .setTitle("Test sighting SMS")
                .setMessage("Enter the phone number that should receive the test. Senton Link will open the SMS app with the message pre-filled; it will not send automatically.")
                .setView(number)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Open SMS", (dialog, which) -> {
                    String recipient = number.getText().toString().trim();
                    if (!validSmsRecipient(recipient)) {
                        Toast.makeText(this, "Enter a valid mobile number.", Toast.LENGTH_LONG).show();
                        return;
                    }
                    prefs.edit().putString(KEY_TEST_SMS_NUMBER, recipient).apply();
                    openTestSightingSms(recipient);
                }).show();
    }

    private boolean validSmsRecipient(String recipient) {
        if (recipient == null) return false;
        String compact = recipient.replace(" ", "").replace("-", "").replace("(", "").replace(")", "");
        return compact.matches("\\+?\\d{8,15}");
    }

    private void openTestSightingSms(String recipient) {
        String body = "Senton Link – TEST Possible Missing Person Sighting\n\n" +
                "Location: Near the petrol station on Main Rd, Hahndorf\n" +
                "Time: TEST MESSAGE\n\n" +
                "Notes: Saw someone who may match the missing-person description. Grey hoodie, black pants, walking toward the shops.\n\n" +
                "Photo: Unverified possible sighting photo would be attached in the full Missing Person Mode.\n\n" +
                "This is an unverified TEST sighting. Do not treat it as confirmed identification.";
        Intent sms = new Intent(Intent.ACTION_SENDTO);
        sms.setData(Uri.parse("smsto:" + Uri.encode(recipient)));
        sms.putExtra("sms_body", body);
        try {
            startActivity(sms);
        } catch (Exception e) {
            Toast.makeText(this, "No SMS app is available on this phone.", Toast.LENGTH_LONG).show();
        }
    }

    @Override protected void onResume() {
        super.onResume();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        applyImmersiveLauncherUi();
        if (testMode) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            if (testBanner != null) testBanner.setVisibility(View.VISIBLE);
        }
        if (systemPanel != null) systemPanel.setText(systemText());
        if (updateStatus != null) {
            updateStatus.setText(getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_UPDATE_STAGE, "Wi-Fi updates: open UPDATE for status"));
        }
    }

    @Override protected void onPause() {
        if (testMode) {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
        super.onPause();
    }

    @Override public void onBackPressed() {
        applyImmersiveLauncherUi();
    }

    @Override public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) applyImmersiveLauncherUi();
    }

    private void requestMaintenanceAccess() {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        long now = System.currentTimeMillis();
        long lockUntil = prefs.getLong(KEY_MAINT_PIN_LOCK_UNTIL, 0L);
        if (lockUntil > now) {
            long seconds = Math.max(1L, (lockUntil - now + 999L) / 1000L);
            Toast.makeText(this, "Maintenance PIN locked. Try again in " + seconds + " seconds.", Toast.LENGTH_LONG).show();
            return;
        }
        if (!prefs.contains(KEY_MAINT_PIN_HASH) || !prefs.contains(KEY_MAINT_PIN_SALT)) showCreatePinDialog();
        else showVerifyPinDialog();
    }

    private void showCreatePinDialog() {
        EditText first = pinEntry("Create 4–8 digit PIN");
        new AlertDialog.Builder(this)
                .setTitle("Create maintenance PIN")
                .setMessage("This PIN is required before leaving Senton Link for Android Home settings or maintenance. Keep it somewhere safe.")
                .setView(first)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Next", (dialog, which) -> {
                    String pin = first.getText().toString();
                    if (!validPin(pin)) {
                        Toast.makeText(this, "PIN must be 4–8 digits.", Toast.LENGTH_LONG).show();
                        return;
                    }
                    showConfirmPinDialog(pin);
                }).show();
    }

    private void showConfirmPinDialog(String firstPin) {
        EditText confirm = pinEntry("Confirm PIN");
        new AlertDialog.Builder(this)
                .setTitle("Confirm maintenance PIN")
                .setView(confirm)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", (dialog, which) -> {
                    if (!firstPin.equals(confirm.getText().toString())) {
                        Toast.makeText(this, "PINs did not match. Try again.", Toast.LENGTH_LONG).show();
                        return;
                    }
                    if (storePin(firstPin)) {
                        Toast.makeText(this, "Maintenance PIN saved.", Toast.LENGTH_SHORT).show();
                        openAndroidHomeSettings();
                    } else Toast.makeText(this, "Could not securely save the PIN.", Toast.LENGTH_LONG).show();
                }).show();
    }

    private void showVerifyPinDialog() {
        EditText entry = pinEntry("Maintenance PIN");
        new AlertDialog.Builder(this)
                .setTitle("PIN required")
                .setMessage("Enter the Senton maintenance PIN to access Android Home settings.")
                .setView(entry)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Unlock", (dialog, which) -> verifyEnteredPin(entry.getText().toString()))
                .show();
    }

    private void verifyEnteredPin(String pin) {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        if (verifyPin(pin)) {
            prefs.edit().putInt(KEY_MAINT_PIN_FAILS, 0).putLong(KEY_MAINT_PIN_LOCK_UNTIL, 0L).apply();
            openAndroidHomeSettings();
            return;
        }
        int failures = prefs.getInt(KEY_MAINT_PIN_FAILS, 0) + 1;
        SharedPreferences.Editor editor = prefs.edit().putInt(KEY_MAINT_PIN_FAILS, failures);
        if (failures >= MAX_PIN_FAILURES) {
            editor.putInt(KEY_MAINT_PIN_FAILS, 0).putLong(KEY_MAINT_PIN_LOCK_UNTIL, System.currentTimeMillis() + PIN_LOCKOUT_MS).apply();
            Toast.makeText(this, "Too many wrong PINs. Maintenance locked for 60 seconds.", Toast.LENGTH_LONG).show();
        } else {
            editor.apply();
            Toast.makeText(this, "Wrong PIN. " + (MAX_PIN_FAILURES - failures) + " attempts remaining.", Toast.LENGTH_LONG).show();
        }
    }

    private boolean storePin(String pin) {
        try {
            byte[] salt = new byte[16];
            new SecureRandom().nextBytes(salt);
            byte[] hash = derivePinHash(pin, salt);
            getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                    .putString(KEY_MAINT_PIN_SALT, Base64.encodeToString(salt, Base64.NO_WRAP))
                    .putString(KEY_MAINT_PIN_HASH, Base64.encodeToString(hash, Base64.NO_WRAP))
                    .putInt(KEY_MAINT_PIN_FAILS, 0)
                    .putLong(KEY_MAINT_PIN_LOCK_UNTIL, 0L).apply();
            return true;
        } catch (Exception e) { return false; }
    }

    private boolean verifyPin(String pin) {
        try {
            SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
            byte[] salt = Base64.decode(prefs.getString(KEY_MAINT_PIN_SALT, ""), Base64.NO_WRAP);
            byte[] expected = Base64.decode(prefs.getString(KEY_MAINT_PIN_HASH, ""), Base64.NO_WRAP);
            return MessageDigest.isEqual(expected, derivePinHash(pin, salt));
        } catch (Exception e) { return false; }
    }

    private byte[] derivePinHash(String pin, byte[] salt) throws Exception {
        PBEKeySpec spec = new PBEKeySpec(pin.toCharArray(), salt, PBKDF2_ITERATIONS, PBKDF2_KEY_BITS);
        try { return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded(); }
        finally { spec.clearPassword(); }
    }

    private boolean validPin(String pin) {
        return pin != null && pin.matches("\\d{" + PIN_MIN_LENGTH + "," + PIN_MAX_LENGTH + "}");
    }

    private EditText pinEntry(String hint) {
        EditText input = new EditText(this);
        input.setHint(hint);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        return input;
    }

    private void openAndroidHomeSettings() {
        try {
            startActivity(new Intent(Settings.ACTION_HOME_SETTINGS));
        } catch (Exception e) {
            startActivity(new Intent(Settings.ACTION_SETTINGS));
        }
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
        boolean pinSet = getSharedPreferences(PREFS, MODE_PRIVATE).contains(KEY_MAINT_PIN_HASH);
        return "SYSTEM\n\nApp status      " + (testMode ? "TESTING" : "OK") +
                "\nLauncher mode   Ready" +
                "\nHome escape     " + (pinSet ? "PIN protected" : "PIN setup required") +
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
