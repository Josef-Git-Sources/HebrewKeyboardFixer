"""
System Tray Application for Hebrew/English Keyboard Auto-Switcher
"""

import sys
import os
import json
import threading
import ctypes
from pathlib import Path

if sys.platform != 'win32':
    print("This application only runs on Windows.")
    sys.exit(1)

try:
    import pystray
    from pystray import MenuItem as item, Menu
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Missing dependencies. Run: pip install pystray pillow pynput")
    sys.exit(1)

from keyboard_switcher import KeyboardFixer

# ─── Config ──────────────────────────────────────────────────────────────────

CONFIG_FILE = Path(os.environ.get('APPDATA', '.')) / 'HebrewKeyboardFixer' / 'config.json'

DEFAULT_CONFIG = {
    'enabled': True,
    'min_chars': 2,
    'notify': False,
    'continue_checking_window': False,
    'action_replace_text': True,
    'action_play_beep': True,
    'action_switch_layout': True,
    'start_with_windows': False,
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ─── Tray Icon Image ──────────────────────────────────────────────────────────

def make_icon(enabled=True):
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bg_color = (46, 160, 67) if enabled else (120, 120, 120)
    draw.ellipse([2, 2, 62, 62], fill=bg_color)
    try:
        font = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    text = "HE"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((64 - tw) / 2, (64 - th) / 2 - 2), text, fill="white", font=font)
    return img

# ─── Tray App ─────────────────────────────────────────────────────────────────

class TrayApp:
    def __init__(self):
        self.config = load_config()
        self.fixer = KeyboardFixer(self.config, tray_icon=self)
        self.icon = None

    def notify(self, title, message):
        if self.config.get('notify', False) and self.icon:
            try:
                self.icon.notify(message, title)
            except Exception:
                pass

    # ── menu builder ──────────────────────────────────────────────────────────

    def build_menu(self):
        cfg = self.config
        return Menu(
            # Header (non-clickable)
            item('מתקן מקלדת עברית/אנגלית', None, enabled=False),
            Menu.SEPARATOR,

            # Group 1: Enable / Disable
            item(
                'פעיל' if self.fixer.enabled else 'מושהה',
                self.toggle_enabled,
                checked=lambda i: self.fixer.enabled,
            ),
            Menu.SEPARATOR,

            # Group 2: Sensitivity
            item('רגישות: 2 תווים', lambda icon, it: self.set_min_chars(2),
                 checked=lambda i: cfg.get('min_chars') == 2),
            item('רגישות: 3 תווים', lambda icon, it: self.set_min_chars(3),
                 checked=lambda i: cfg.get('min_chars') == 3),
            item('רגישות: 4 תווים', lambda icon, it: self.set_min_chars(4),
                 checked=lambda i: cfg.get('min_chars') == 4),
            Menu.SEPARATOR,

            # Group 3: Actions
            item('החלף טקסט אוטומטית',
                 self.toggle_replace_text,
                 checked=lambda i: cfg.get('action_replace_text', True)),
            item('השמע צפצוף',
                 self.toggle_beep,
                 checked=lambda i: cfg.get('action_play_beep', True)),
            item('החלף שפת מקלדת',
                 self.toggle_switch_layout,
                 checked=lambda i: cfg.get('action_switch_layout', True)),
            Menu.SEPARATOR,

            # Group 4: Behaviour
            item('המשך בדיקה לאחר תיקון (באותו חלון)',
                 self.toggle_continue_checking,
                 checked=lambda i: cfg.get('continue_checking_window', False)),
            item('הודעות קופצות',
                 self.toggle_notify,
                 checked=lambda i: cfg.get('notify', False)),
            Menu.SEPARATOR,

            # Group 5: Startup / Exit
            item('הפעל עם Windows',
                 self.toggle_startup,
                 checked=lambda i: cfg.get('start_with_windows', False)),
            item('יציאה', self.quit_app),
        )

    # ── toggle handlers ───────────────────────────────────────────────────────

    def _refresh_menu(self, icon):
        icon.menu = self.build_menu()

    def toggle_enabled(self, icon, it):
        enabled = self.fixer.toggle()
        self.config['enabled'] = enabled
        save_config(self.config)
        icon.icon = make_icon(enabled)
        self._refresh_menu(icon)

    def set_min_chars(self, n):
        self.config['min_chars'] = n
        self.fixer.config['min_chars'] = n
        save_config(self.config)
        if self.icon:
            self._refresh_menu(self.icon)

    def toggle_replace_text(self, icon, it):
        self.config['action_replace_text'] = not self.config.get('action_replace_text', True)
        self.fixer.config['action_replace_text'] = self.config['action_replace_text']
        save_config(self.config)
        self._refresh_menu(icon)

    def toggle_beep(self, icon, it):
        self.config['action_play_beep'] = not self.config.get('action_play_beep', True)
        self.fixer.config['action_play_beep'] = self.config['action_play_beep']
        save_config(self.config)
        self._refresh_menu(icon)

    def toggle_switch_layout(self, icon, it):
        self.config['action_switch_layout'] = not self.config.get('action_switch_layout', True)
        self.fixer.config['action_switch_layout'] = self.config['action_switch_layout']
        save_config(self.config)
        self._refresh_menu(icon)

    def toggle_continue_checking(self, icon, it):
        self.config['continue_checking_window'] = not self.config.get('continue_checking_window', False)
        self.fixer.config['continue_checking_window'] = self.config['continue_checking_window']
        save_config(self.config)
        self._refresh_menu(icon)

    def toggle_notify(self, icon, it):
        self.config['notify'] = not self.config.get('notify', False)
        save_config(self.config)
        self._refresh_menu(icon)

    def toggle_startup(self, icon, it):
        val = not self.config.get('start_with_windows', False)
        self.config['start_with_windows'] = val
        save_config(self.config)
        self._set_startup(val)
        self._refresh_menu(icon)

    def _set_startup(self, enable):
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "HebrewKeyboardFixer"
        exe_path = sys.executable
        script_path = os.path.abspath(__file__)
        cmd = f'"{exe_path}" "{script_path}"'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Could not set startup: {e}")

    def quit_app(self, icon, it):
        self.fixer.stop()
        save_config(self.config)
        icon.stop()

    # ── entry point ───────────────────────────────────────────────────────────

    def run(self):
        self.fixer.start()
        enabled = self.config.get('enabled', True)
        self.fixer.enabled = enabled

        self.icon = pystray.Icon(
            name="HebrewKeyboardFixer",
            icon=make_icon(enabled),
            title="מתקן מקלדת עברית/אנגלית",
            menu=self.build_menu(),
        )
        self.icon.run()


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "HebrewKeyboardFixerMutex")
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(
            0,
            "התוכנה כבר רצה ברקע.\nחפש אותה במגש המערכת (שעון, פינה ימנית תחתונה).",
            "Hebrew Keyboard Fixer",
            0x40,
        )
        sys.exit(0)

    app = TrayApp()
    app.run()
