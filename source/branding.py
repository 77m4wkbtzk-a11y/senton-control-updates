from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox


def _branded_question(parent, title, text, *args, **kwargs):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Senton Control Update")
    dialog.setModal(True)
    dialog.setMinimumWidth(520)
    dialog.setStyleSheet("""
        QDialog { background:#0f1115; color:#f2f2f2; }
        QLabel { color:#f2f2f2; }
        QPushButton { min-height:44px; border-radius:8px; padding:8px 14px;
                      background:#20242a; border:1px solid #3b414a; color:white; }
        QPushButton#install { background:#16233c; border:1px solid #3b82f6; font-weight:bold; }
    """)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(14)

    logo = QLabel("SENTON CONTROL")
    logo.setAlignment(Qt.AlignCenter)
    logo.setStyleSheet("font-size:34px;font-weight:900;letter-spacing:3px;padding:18px;")
    layout.addWidget(logo)

    sub = QLabel("OFFICIAL UPDATE")
    sub.setAlignment(Qt.AlignCenter)
    sub.setStyleSheet("font-size:16px;font-weight:bold;color:#93c5fd;")
    layout.addWidget(sub)

    message = QLabel(text)
    message.setWordWrap(True)
    message.setAlignment(Qt.AlignCenter)
    layout.addWidget(message)

    install = QPushButton("DOWNLOAD & INSTALL")
    install.setObjectName("install")
    later = QPushButton("REMIND ME LATER")

    install.clicked.connect(dialog.accept)
    later.clicked.connect(dialog.reject)

    layout.addWidget(install)
    layout.addWidget(later)

    footer = QLabel("Senton Control secure update channel")
    footer.setAlignment(Qt.AlignCenter)
    footer.setStyleSheet("color:#86efac;")
    layout.addWidget(footer)

    return QMessageBox.Yes if dialog.exec() == QDialog.Accepted else QMessageBox.No


def install_branded_update_ui():
    """Use the Senton-branded update confirmation screen across the desktop app."""
    QMessageBox.question = staticmethod(_branded_question)
