import sys
import os
import json
import winreg
from datetime import datetime
from PIL import Image, ImageDraw

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QDialog, QPushButton, QTextBrowser, QSpacerItem, QSizePolicy
)
import pystray
from pystray import MenuItem as item

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".tuxclock_config.json")
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "TuxClock"

def load_config():
    default_config = {
        "digit_size": 100,
        "text_color": "White",
        "font_family": "Courier New",
        "always_on_top": True,
        "is_locked": False,
        "autostart": False,
        "pos_x": None,
        "pos_y": None
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                default_config.update(config)
        except Exception as e:
            print(f"Chyba při načítání konfigurace: {e}")
    return default_config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Chyba při ukládání konfigurace: {e}")

def get_asset_path(filename):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)

def get_executable_command():
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
    else:
        exe_path = sys.executable.replace("python.exe", "pythonw.exe")
        script_path = os.path.abspath(__file__)
        return f'"{exe_path}" "{script_path}"'
    return f'"{exe_path}"'

def set_autostart_registry(enable: bool):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            cmd = get_executable_command()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Chyba nastavení registrů: {e}")

class TraySignals(QObject):
    change_size = pyqtSignal(int)
    change_color = pyqtSignal(str)
    change_font = pyqtSignal(str)
    toggle_top = pyqtSignal(bool)
    toggle_lock = pyqtSignal(bool)
    toggle_autostart = pyqtSignal(bool)
    show_about = pyqtSignal()
    quit_app = pyqtSignal()

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.setStyleSheet("""
            QDialog {
                background-color: #000000;
                border: 3px solid #FFFFFF;
            }
            QTextBrowser {
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-family: 'Courier New';
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #000000;
                color: #FFFFFF;
                border: 2px solid #FFFFFF;
                font-family: 'Courier New';
                font-weight: bold;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #FFFFFF;
                color: #000000;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        about_text = (
            "<p style='text-align: center; margin: 0;'><b>JXD VibeLabs</b></p>"
            "<p style='text-align: center; margin: 5px 0;'><b># Penguin TUXCLOCK by JXD VibeLabs #</b></p>"
            "<p style='text-align: center; margin: 5px 0;'>Stoned penguin is watching you!</p>"
            "<p style='text-align: center; margin: 5px 0;'>Tux &copy; Larry Ewing</p>"
            "<p style='text-align: center; margin: 5px 0;'>Software &copy; Jiri X. Dolezal</p>"
            "<p style='text-align: center; margin: 5px 0;'>Questions: <a style='color: #00FFFF;' href='mailto:jxd@jxd.cz'>jxd@jxd.cz</a></p>"
            "<p style='text-align: center; margin: 5px 0;'><a style='color: #00FFFF;' href='https://jxd.cz/'>https://jxd.cz/</a></p>"
            "<br>"
            "<p style='text-align: center; margin: 5px 0;'>VIBE coding is poetry.</p>"
            "<p style='text-align: center; margin: 5px 0;'>Fear the penguin!</p>"
        )

        browser = QTextBrowser()
        browser.setHtml(about_text)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)

        btn_close = QPushButton("CLOSE")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

        self.resize(420, 320)

class TuxClock(QWidget):
    def __init__(self, signals: TraySignals, config: dict):
        super().__init__()
        self.signals = signals
        self.config = config

        self.digit_size = self.config.get("digit_size", 100)
        self.text_color = self.config.get("text_color", "White")
        self.font_family = self.config.get("font_family", "Courier New")
        self.always_on_top = self.config.get("always_on_top", True)
        self.is_locked = self.config.get("is_locked", False)
        self.autostart = self.config.get("autostart", False)

        self.init_ui()
        self.connect_signals()

        if self.config.get("pos_x") is not None and self.config.get("pos_y") is not None:
            self.move(self.config["pos_x"], self.config["pos_y"])

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(200)

        self.update_time()

    def init_ui(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_time = QLabel(self)
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.day_layout = QHBoxLayout()
        self.day_layout.setContentsMargins(0, 0, 0, 0)
        self.day_layout.setSpacing(0)

        self.lbl_tux = QLabel(self)
        self.lbl_day = QLabel(self)

        tux_path = get_asset_path("tux.png")
        if os.path.exists(tux_path):
            self.tux_pixmap = QPixmap(tux_path)
        else:
            self.tux_pixmap = QPixmap(32, 32)
            self.tux_pixmap.fill(QColor(0, 0, 0, 0))

        self.left_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.right_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.day_layout.addItem(self.left_spacer)
        self.day_layout.addWidget(self.lbl_tux, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.day_layout.addSpacing(30)
        self.day_layout.addWidget(self.lbl_day, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.day_layout.addItem(self.right_spacer)

        self.main_layout.addWidget(self.lbl_time)
        self.main_layout.addLayout(self.day_layout)

        self.apply_styles()

    def connect_signals(self):
        self.signals.change_size.connect(self.set_digit_size)
        self.signals.change_color.connect(self.set_color)
        self.signals.change_font.connect(self.set_font_family)
        self.signals.toggle_top.connect(self.set_always_on_top)
        self.signals.toggle_lock.connect(self.set_lock_position)
        self.signals.toggle_autostart.connect(self.set_autostart_state)
        self.signals.show_about.connect(self.open_about)
        self.signals.quit_app.connect(QApplication.quit)

    def apply_styles(self):
        time_font = QFont(self.font_family, int(self.digit_size * 0.75), QFont.Weight.Bold)
        day_font = QFont(self.font_family, int((self.digit_size * 0.75) / 2), QFont.Weight.Bold)

        color_hex = "#FFFFFF" if self.text_color == "White" else "#000000"

        style = f"color: {color_hex}; background: transparent;"
        self.lbl_time.setFont(time_font)
        self.lbl_time.setStyleSheet(style)

        self.lbl_day.setFont(day_font)
        self.lbl_day.setStyleSheet(style)

        self.main_layout.setSpacing(int(-self.digit_size * 0.15))

        tux_h = max(16, int((self.digit_size * 0.75) / 2))
        scaled_tux = self.tux_pixmap.scaledToHeight(
            tux_h, Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_tux.setPixmap(scaled_tux)

        self.adjustSize()

    def update_time(self):
        now = datetime.now()
        self.lbl_time.setText(now.strftime("%H:%M:%S"))
        self.lbl_day.setText(now.strftime("%A"))
        self.adjustSize()

    def save_current_state(self):
        self.config["digit_size"] = self.digit_size
        self.config["text_color"] = self.text_color
        self.config["font_family"] = self.font_family
        self.config["always_on_top"] = self.always_on_top
        self.config["is_locked"] = self.is_locked
        self.config["autostart"] = self.autostart
        self.config["pos_x"] = self.pos().x()
        self.config["pos_y"] = self.pos().y()
        save_config(self.config)

    def set_digit_size(self, size: int):
        self.digit_size = size
        self.apply_styles()
        self.save_current_state()

    def set_color(self, color: str):
        self.text_color = color
        self.apply_styles()
        self.save_current_state()

    def set_font_family(self, font_name: str):
        self.font_family = font_name
        self.apply_styles()
        self.save_current_state()

    def set_always_on_top(self, state: bool):
        self.always_on_top = state
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if state:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self.save_current_state()

    def set_lock_position(self, state: bool):
        self.is_locked = state
        self.save_current_state()

    def set_autostart_state(self, state: bool):
        self.autostart = state
        set_autostart_registry(state)
        self.save_current_state()

    def open_about(self):
        dlg = AboutDialog(self)
        dlg.exec()

    def mousePressEvent(self, event):
        if not self.is_locked and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.save_current_state()

    def mouseMoveEvent(self, event):
        if not self.is_locked and event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

def setup_tray(signals: TraySignals, config: dict):
    ico_path = get_asset_path("TIME.ico")
    if os.path.exists(ico_path):
        icon_img = Image.open(ico_path)
    else:
        icon_img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))

    def on_size(size):
        return lambda icon, item: signals.change_size.emit(size)

    def on_color(color):
        return lambda icon, item: signals.change_color.emit(color)

    def on_font(font_name):
        return lambda icon, item: signals.change_font.emit(font_name)

    def on_autostart(icon, item):
        global current_autostart
        current_autostart = not current_autostart
        signals.toggle_autostart.emit(current_autostart)

    def on_top(icon, item):
        global current_top
        current_top = not current_top
        signals.toggle_top.emit(current_top)

    def on_lock(icon, item):
        global current_lock
        current_lock = not current_lock
        signals.toggle_lock.emit(current_lock)

    global current_top, current_lock, current_autostart
    current_top = config.get("always_on_top", True)
    current_lock = config.get("is_locked", False)
    current_autostart = config.get("autostart", False)

    menu = pystray.Menu(
        item('Size', pystray.Menu(
            item('50 pix', on_size(50)),
            item('100 pix', on_size(100)),
            item('200 pix', on_size(200)),
            item('300 pix', on_size(300)),
            item('500 pix', on_size(500)),
        )),
        item('Color', pystray.Menu(
            item('Black', on_color('Black')),
            item('White', on_color('White')),
        )),
        item('Font', pystray.Menu(
            item('Courier New', on_font('Courier New')),
            item('Arial Black', on_font('Arial Black')),
        )),
        item('Start with Windows', on_autostart, checked=lambda item: current_autostart),
        item('Always on the top', on_top, checked=lambda item: current_top),
        item('Lock position', on_lock, checked=lambda item: current_lock),
        pystray.Menu.SEPARATOR,
        item('About', lambda icon, item: signals.show_about.emit()),
        item('Exit', lambda icon, item: (icon.stop(), signals.quit_app.emit()))
    )

    tray_icon = pystray.Icon("TUXCLOCK", icon_img, "TUXCLOCK", menu)
    tray_icon.run()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = load_config()

    signals = TraySignals()
    clock = TuxClock(signals, config)
    clock.show()

    import threading
    tray_thread = threading.Thread(target=setup_tray, args=(signals, config), daemon=True)
    tray_thread.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()