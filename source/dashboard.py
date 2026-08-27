from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTextEdit, QProgressBar, QMessageBox
)

from pi_client import PiClient
from updater import check_for_update, download_update, install_update_to_main_desktop


class UpdateDownloadThread(QThread):
    downloaded = Signal(object)
    failed = Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            self.downloaded.emit(download_update(self.url))
        except Exception as exc:
            self.failed.emit(str(exc))


class SentonDashboard(QMainWindow):
    def __init__(self, version="1.2.1"):
        super().__init__()
        self.version = version
        self.setWindowTitle(f"Senton Control v{version}")
        self.resize(1400, 880)

        self.pi = PiClient()
        self.auto_armed = False
        self.remote_connected = True
        self.takeover_seconds = 10
        self.session_seconds = 0
        self.session_limit = 30 * 60
        self.update_url = ""
        self.update_thread = None

        self.takeover_timer = QTimer(self)
        self.takeover_timer.timeout.connect(self._tick_takeover)
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._tick_ui)
        self.ui_timer.start(1000)

        self._build_ui()
        self._set_mode("MANUAL")
        self._log(f"Senton Control v{version} started")
        self._log("SIMULATION MODE active")

    def _card(self):
        f = QFrame()
        f.setStyleSheet("QFrame{background:#171a1f;border:1px solid #30343b;border-radius:10px;} QLabel{color:#f2f2f2;}")
        return f

    def _heading(self, text):
        x = QLabel(text)
        x.setStyleSheet("font-size:16px;font-weight:bold;")
        return x

    def _value_box(self, name, value="--"):
        f = QFrame()
        f.setStyleSheet("QFrame{background:#111419;border:1px solid #30343b;border-radius:8px;}")
        l = QVBoxLayout(f)
        n = QLabel(name)
        n.setAlignment(Qt.AlignCenter)
        v = QLabel(value)
        v.setAlignment(Qt.AlignCenter)
        v.setStyleSheet("font-size:20px;font-weight:bold;")
        l.addWidget(n)
        l.addWidget(v)
        return {"frame": f, "value": v}

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet("""
            QWidget{background:#0f1115;color:#f2f2f2;font-size:14px;}
            QPushButton{min-height:44px;border-radius:8px;padding:8px 12px;background:#20242a;border:1px solid #3b414a;color:white;}
            QPushButton:hover{background:#292e35;}
            QPushButton#stop{background:#7f1d1d;border:1px solid #ef4444;font-weight:bold;}
            QPushButton#auto{background:#18351f;border:1px solid #22c55e;}
            QPushButton#demo{background:#3d3210;border:1px solid #eab308;}
            QPushButton#update{background:#16233c;border:1px solid #3b82f6;}
            QTextEdit{background:#0c0e11;border:1px solid #30343b;color:#b8f5b8;}
            QProgressBar{background:#20242a;border:1px solid #30343b;border-radius:6px;text-align:center;}
            QProgressBar::chunk{background:#3b82f6;border-radius:5px;}
        """)
        self.setCentralWidget(root)
        main = QVBoxLayout(root)

        header = QHBoxLayout()
        title = QLabel("SENTON CONTROL")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        self.version_label = QLabel(f"Version {self.version}")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.version_label)
        main.addLayout(header)

        strip = QFrame()
        strip.setStyleSheet("QFrame{background:#111419;border:1px solid #30343b;border-radius:8px;}")
        st = QHBoxLayout(strip)
        self.status_sim = QLabel("SIMULATION: ON")
        self.status_pi = QLabel("PI: DISCONNECTED")
        self.status_remote = QLabel("REMOTE: CONNECTED")
        self.status_failsafe = QLabel("FAILSAFE: READY")
        for label in (self.status_sim, self.status_pi, self.status_remote, self.status_failsafe):
            label.setStyleSheet("font-weight:bold;")
            st.addWidget(label)
        st.addStretch(1)
        main.addWidget(strip)

        top = QGridLayout()
        main.addLayout(top, 4)

        camera = self._card()
        cl = QVBoxLayout(camera)
        cl.addWidget(self._heading("FRONT CAMERA"))
        self.camera_view = QLabel("LIVE CAMERA FEED\n\nSimulation placeholder — real Pi camera comes later")
        self.camera_view.setAlignment(Qt.AlignCenter)
        self.camera_view.setMinimumHeight(390)
        self.camera_view.setStyleSheet("QLabel{background:#111827;border:1px solid #374151;border-radius:8px;font-size:22px;color:#9ca3af;}")
        cl.addWidget(self.camera_view, 1)
        sr = QHBoxLayout()
        self.left_sensor = self._value_box("LEFT", "--")
        self.center_sensor = self._value_box("CENTRE", "--")
        self.right_sensor = self._value_box("RIGHT", "--")
        for x in (self.left_sensor, self.center_sensor, self.right_sensor):
            sr.addWidget(x["frame"])
        cl.addLayout(sr)
        top.addWidget(camera, 0, 0, 2, 2)

        controls = self._card()
        c = QVBoxLayout(controls)
        c.addWidget(self._heading("CONTROL PANEL"))
        row = QHBoxLayout()
        self.manual_btn = QPushButton("MANUAL")
        self.auto_btn = QPushButton("ARM AUTO")
        self.auto_btn.setObjectName("auto")
        row.addWidget(self.manual_btn)
        row.addWidget(self.auto_btn)
        c.addLayout(row)
        self.demo_btn = QPushButton("DEMO MODE")
        self.demo_btn.setObjectName("demo")
        self.stop_btn = QPushButton("EMERGENCY STOP")
        self.stop_btn.setObjectName("stop")
        self.mode_label = QLabel("Current Mode: --")
        self.mode_label.setStyleSheet("font-size:18px;font-weight:bold;")
        c.addWidget(self.demo_btn)
        c.addWidget(self.stop_btn)
        c.addWidget(self.mode_label)
        self.manual_btn.clicked.connect(self.manual_mode)
        self.auto_btn.clicked.connect(self.arm_auto)
        self.demo_btn.clicked.connect(self.demo_mode)
        self.stop_btn.clicked.connect(self.emergency_stop)
        top.addWidget(controls, 0, 2)

        status = self._card()
        sl = QVBoxLayout(status)
        sl.addWidget(self._heading("REMOTE / FAILSAFE"))
        self.remote_label = QLabel("Remote: CONNECTED")
        self.pi_label = QLabel("Pi: NOT CONNECTED (SIM)")
        self.failsafe_label = QLabel("Failsafe: READY")
        self.takeover_label = QLabel("Takeover countdown: inactive")
        for w in (self.remote_label, self.pi_label, self.failsafe_label, self.takeover_label):
            sl.addWidget(w)
        self.remote_test = QPushButton("Simulate Remote OFF")
        self.remote_test.clicked.connect(self.simulate_remote_loss)
        sl.addWidget(self.remote_test)
        top.addWidget(status, 1, 2)

        lower = QGridLayout()
        main.addLayout(lower, 2)

        telemetry = self._card()
        tl = QGridLayout(telemetry)
        tl.addWidget(self._heading("VEHICLE TELEMETRY"), 0, 0, 1, 3)
        self.speed = self._value_box("Speed", "0.0 km/h")
        self.car_batt = self._value_box("Car Battery", "-- V")
        self.pi_batt = self._value_box("Pi Supply", "-- V")
        self.steering = self._value_box("Steering", "CENTRE")
        self.throttle = self._value_box("Throttle", "NEUTRAL")
        self.object_state = self._value_box("Objects", "CLEAR")
        for i, item in enumerate((self.speed, self.car_batt, self.pi_batt, self.steering, self.throttle, self.object_state)):
            tl.addWidget(item["frame"], 1 + i // 3, i % 3)
        lower.addWidget(telemetry, 0, 0, 1, 2)

        session = self._card()
        se = QVBoxLayout(session)
        se.addWidget(self._heading("SESSION / RETURN HOME"))
        self.session_label = QLabel("Session: 00:00 / 30:00")
        self.return_label = QLabel("Return home: INACTIVE")
        self.session_bar = QProgressBar()
        self.session_bar.setRange(0, self.session_limit)
        self.return_btn = QPushButton("RETURN HOME NOW")
        self.return_btn.clicked.connect(self.return_home)
        se.addWidget(self.session_label)
        se.addWidget(self.return_label)
        se.addWidget(self.session_bar)
        se.addWidget(self.return_btn)
        lower.addWidget(session, 0, 2)

        updates = self._card()
        ul = QVBoxLayout(updates)
        ul.addWidget(self._heading("APP UPDATES"))
        self.update_status = QLabel("Ready to check for updates.")
        self.update_status.setWordWrap(True)
        self.check_update_btn = QPushButton("CHECK FOR UPDATES")
        self.check_update_btn.setObjectName("update")
        self.install_update_btn = QPushButton("DOWNLOAD & INSTALL UPDATE")
        self.install_update_btn.setEnabled(False)
        self.check_update_btn.clicked.connect(self.check_updates)
        self.install_update_btn.clicked.connect(self.install_update)
        ul.addWidget(self.update_status)
        ul.addWidget(self.check_update_btn)
        ul.addWidget(self.install_update_btn)
        lower.addWidget(updates, 0, 3)

        log_card = self._card()
        ll = QVBoxLayout(log_card)
        ll.addWidget(self._heading("SYSTEM LOG"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(135)
        ll.addWidget(self.log_box)
        main.addWidget(log_card, 1)

    def _set_mode(self, mode):
        self.mode_label.setText(f"Current Mode: {mode}")

    def _log(self, text):
        self.log_box.append(text)

    def manual_mode(self):
        self.auto_armed = False
        self.takeover_timer.stop()
        self.takeover_label.setText("Takeover countdown: inactive")
        self._set_mode("MANUAL")
        self.pi.send_command("manual")
        self._log("Manual mode selected")

    def arm_auto(self):
        self.auto_armed = True
        self._set_mode("AUTO ARMED")
        self.pi.send_command("arm_auto")
        self._log("Autonomous mode armed")

    def demo_mode(self):
        self.auto_armed = True
        self._set_mode("DEMO MODE")
        self.pi.send_command("demo")
        self._log("Demo Mode selected")

    def emergency_stop(self):
        self.auto_armed = False
        self.takeover_timer.stop()
        self._set_mode("EMERGENCY STOP")
        self.throttle["value"].setText("NEUTRAL")
        self.status_failsafe.setText("FAILSAFE: STOPPED")
        self.pi.send_command("stop")
        self._log("EMERGENCY STOP")

    def simulate_remote_loss(self):
        self.remote_connected = False
        self.remote_label.setText("Remote: LOST")
        self.status_remote.setText("REMOTE: LOST")
        self._log("Remote signal lost")
        if not self.auto_armed:
            self.emergency_stop()
            self.takeover_label.setText("No takeover: Auto not armed")
            return
        self.takeover_seconds = 10
        self.takeover_label.setText(f"Takeover in: {self.takeover_seconds}s")
        self.takeover_timer.start(1000)

    def _tick_takeover(self):
        self.takeover_seconds -= 1
        if self.takeover_seconds <= 0:
            self.takeover_timer.stop()
            self._set_mode("AUTONOMOUS")
            self.takeover_label.setText("Raspberry Pi has control")
            self.pi.send_command("takeover")
            self._log("10-second takeover complete")
            return
        self.takeover_label.setText(f"Takeover in: {self.takeover_seconds}s")

    def return_home(self):
        self.return_label.setText("Return home: ACTIVE")
        self._set_mode("RETURN HOME")
        self.pi.send_command("return_home")
        self._log("Return Home requested")

    def _tick_ui(self):
        self.session_seconds = min(self.session_seconds + 1, self.session_limit)
        m, s = divmod(self.session_seconds, 60)
        self.session_label.setText(f"Session: {m:02d}:{s:02d} / 30:00")
        self.session_bar.setValue(self.session_seconds)

        data = self.pi.get_status()
        if data:
            sim = data.get("simulation", True)
            self.status_sim.setText("SIMULATION: ON" if sim else "SIMULATION: OFF")
            self.status_pi.setText("PI: SIMULATED" if sim else "PI: CONNECTED")
            self.left_sensor["value"].setText(f'{data.get("left_m", 0):.2f} m')
            self.center_sensor["value"].setText(f'{data.get("center_m", 0):.2f} m')
            self.right_sensor["value"].setText(f'{data.get("right_m", 0):.2f} m')
            self.speed["value"].setText(f'{data.get("speed_kmh", 0):.1f} km/h')
            self.car_batt["value"].setText(f'{data.get("car_battery_v", 0):.2f} V')
            self.pi_batt["value"].setText(f'{data.get("pi_supply_v", 0):.2f} V')
            self.steering["value"].setText(data.get("steering", "CENTRE"))
            self.throttle["value"].setText(data.get("throttle", "NEUTRAL"))
            self.object_state["value"].setText(data.get("object_state", "CLEAR"))

        if self.session_seconds >= self.session_limit and self.return_label.text() != "Return home: ACTIVE":
            self.return_home()
            self._log("30-minute limit reached: Return Home activated")

    def check_updates(self):
        result = check_for_update(self.version)
        if not result.get("ok"):
            self.update_status.setText("Update check unavailable: " + result.get("reason", "Unknown error"))
            self.install_update_btn.setEnabled(False)
            return

        latest = result.get("latest_version", "?")
        if result.get("update_available"):
            self.update_url = result.get("download_url", "")
            notes = result.get("notes", "")
            text = f"Update available: v{latest}"
            if notes:
                text += "\n" + notes
            self.update_status.setText(text)
            self.install_update_btn.setEnabled(bool(self.update_url))
        else:
            self.update_status.setText(f"You're up to date. Latest version: v{latest}")
            self.install_update_btn.setEnabled(False)

    def install_update(self):
        if not self.update_url or (self.update_thread and self.update_thread.isRunning()):
            return
        answer = QMessageBox.question(
            self,
            "Install Senton Control update",
            "Download and install the new Senton Control version now?\n\nThe current Senton Control EXE will be backed up before replacement."
        )
        if answer != QMessageBox.Yes:
            return

        self.update_status.setText("Downloading and verifying update… You can keep using Senton Control.")
        self.install_update_btn.setEnabled(False)
        self.check_update_btn.setEnabled(False)
        self._log("Secure update download started")

        self.update_thread = UpdateDownloadThread(self.update_url, self)
        self.update_thread.downloaded.connect(self._update_downloaded)
        self.update_thread.failed.connect(self._update_download_failed)
        self.update_thread.start()

    def _update_downloaded(self, path):
        self.update_status.setText("Update verified. Restarting Senton Control to install…")
        self._log("Update downloaded and verified; closing app for replacement")
        try:
            install_update_to_main_desktop(path)
            QApplication.quit()
        except Exception as exc:
            self._update_download_failed(str(exc))

    def _update_download_failed(self, message):
        self.update_status.setText("Update failed. You can try again.")
        self.install_update_btn.setEnabled(bool(self.update_url))
        self.check_update_btn.setEnabled(True)
        self._log("Update failed: " + message)
        QMessageBox.critical(self, "Update Failed", message)
