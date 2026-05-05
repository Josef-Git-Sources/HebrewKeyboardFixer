"""
Hebrew/English Keyboard Auto-Switcher
Detects when typing in wrong language using dictionary lookup and auto-corrects.

Logic:
  - User typed "טקד" with Hebrew layout active
    → "טקד" is not a real Hebrew word
    → Convert via mapping → "yes"
    → "yes" IS a real English word → FIX ✅

  - User typed "kt" with English layout active
    → "kt" is not a real English word
    → Convert via mapping → "לא"
    → "לא" IS a real Hebrew word → FIX ✅
"""

import threading
import time
import ctypes
import ctypes.wintypes
import sys
import os
import winsound
import winreg
from pathlib import Path
from pynput import keyboard as pynput_keyboard

# ─── Keyboard Layout Mappings ────────────────────────────────────────────────

# Physical key position → Hebrew character (when Hebrew layout active)
ENG_TO_HEB = {
    'a': 'ש', 'b': 'נ', 'c': 'ב', 'd': 'ג', 'e': 'ק', 'f': 'כ',
    'g': 'ע', 'h': 'י', 'i': 'ן', 'j': 'ח', 'k': 'ל', 'l': 'ך',
    'm': 'צ', 'n': 'מ', 'o': 'ם', 'p': 'פ', 'q': '/', 'r': 'ר',
    's': 'ד', 't': 'א', 'u': 'ו', 'v': 'ה', 'w': "'", 'x': 'ס',
    'y': 'ט', 'z': 'ז', ',': 'ת', '.': 'ץ', ';': 'ף', "'": ',',
    '/': '.', '[': ']', ']': '[', '`': ';',
}

# Reverse: Hebrew character → physical key (English letter)
HEB_TO_ENG = {v: k for k, v in ENG_TO_HEB.items() if v.isalpha()}

# Character sets
HEBREW_CHARS = set('אבגדהוזחטיכלמנסעפצקרשתךםןףץ')
ENGLISH_CHARS = set('abcdefghijklmnopqrstuvwxyz')

# ─── Windows API ──────────────────────────────────────────────────────────────

LANG_HEBREW  = 0x040D
LANG_ENGLISH = 0x0409

KEYEVENTF_KEYUP = 0x0002
VK_LMENU    = 0xA4   # Left Alt
VK_LSHIFT   = 0xA0   # Left Shift
VK_LCONTROL = 0xA2   # Left Ctrl

user32 = ctypes.WinDLL('user32', use_last_error=True)

GWL_STYLE   = -16
ES_PASSWORD = 0x0020

class _RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize',        ctypes.c_uint),
        ('flags',         ctypes.c_uint),
        ('hwndActive',    ctypes.wintypes.HWND),
        ('hwndFocus',     ctypes.wintypes.HWND),
        ('hwndCapture',   ctypes.wintypes.HWND),
        ('hwndMenuOwner', ctypes.wintypes.HWND),
        ('hwndMoveSize',  ctypes.wintypes.HWND),
        ('hwndCaret',     ctypes.wintypes.HWND),
        ('rcCaret',       _RECT),
    ]

def get_current_layout():
    hwnd = user32.GetForegroundWindow()
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    return user32.GetKeyboardLayout(tid)

def is_hebrew_layout():
    return (get_current_layout() & 0xFFFF) == LANG_HEBREW

def get_layout_for(hwnd):
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    return user32.GetKeyboardLayout(tid) & 0xFFFF

def _get_toggle_vkeys():
    """Read registry to find the configured language-switch hotkey."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Keyboard Layout\Toggle")
        val = winreg.QueryValueEx(key, "Language Hotkey")[0]
        winreg.CloseKey(key)
    except Exception:
        val = "1"
    if val == "2":               # Ctrl+Shift
        return VK_LCONTROL, VK_LSHIFT
    return VK_LMENU, VK_LSHIFT  # default: Alt+Shift

def _simulate_toggle():
    """Send the system keyboard-layout toggle shortcut via keybd_event."""
    mod, second = _get_toggle_vkeys()
    ke = ctypes.windll.user32.keybd_event
    ke(mod,    0, 0,               0)
    ke(second, 0, 0,               0)
    ke(second, 0, KEYEVENTF_KEYUP, 0)
    ke(mod,    0, KEYEVENTF_KEYUP, 0)

def switch_to_english():
    for _ in range(5):
        if not is_hebrew_layout():
            return
        _simulate_toggle()
        time.sleep(0.15)

def switch_to_hebrew():
    for _ in range(5):
        if is_hebrew_layout():
            return
        _simulate_toggle()
        time.sleep(0.15)

def switch_to_english_for(hwnd):
    """Switch target window to English, checking its layout (not foreground)."""
    for _ in range(5):
        if get_layout_for(hwnd) != LANG_HEBREW:
            return
        _simulate_toggle()
        time.sleep(0.2)

def switch_to_hebrew_for(hwnd):
    """Switch target window to Hebrew, checking its layout (not foreground)."""
    for _ in range(5):
        if get_layout_for(hwnd) == LANG_HEBREW:
            return
        _simulate_toggle()
        time.sleep(0.2)

# ─── Dictionary Loading ───────────────────────────────────────────────────────

def _try_windows_spell_api(lang_tag):
    """Use Windows built-in Spell Checking API (Windows 8+, via COM)."""
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()

        factory = win32com.client.Dispatch("{7AB36653-1796-484B-BDFA-E74F1DB7C1DC}")

        if not factory.IsSupported(lang_tag):
            print(f"[Dict] Windows spell checker: {lang_tag} not installed as language pack")
            return None

        checker = factory.CreateSpellChecker(lang_tag)

        def check_word(word):
            try:
                enum_errors = checker.Check(word)
                try:
                    error = enum_errors.Next()
                    return error is None
                except Exception:
                    return len(list(enum_errors)) == 0
            except Exception:
                return False

        # Sanity test
        test = "hello" if "en" in lang_tag.lower() else "שלום"
        if check_word(test):
            print(f"[Dict] Using Windows Spell Checker ({lang_tag})")
            return check_word

        print(f"[Dict] Windows Spell Checker ({lang_tag}) sanity test failed")
        return None

    except Exception as e:
        print(f"[Dict] Windows Spell Checker unavailable: {e}")
        return None


def load_english_dict():
    # 1. pyspellchecker — comprehensive offline English dictionary (82k+ words)
    try:
        from spellchecker import SpellChecker
        spell = SpellChecker()
        print("[Dict] Using pyspellchecker (82k+ words)")
        return lambda word: bool(spell.known([word.lower()]))
    except Exception:
        pass

    # 2. Windows Spell Checking API
    checker = _try_windows_spell_api("en-US")
    if checker:
        return checker

    # 3. pyenchant
    try:
        import enchant
        d = enchant.Dict("en_US")
        print("[Dict] Using pyenchant en_US")
        return lambda word: d.check(word.lower())
    except Exception:
        pass

    # 4. Local wordlist file
    wordlist_path = Path(__file__).parent / 'data' / 'english_words.txt'
    if wordlist_path.exists():
        with open(wordlist_path, 'r', encoding='utf-8') as f:
            words = set(line.strip().lower() for line in f if line.strip())
        print(f"[Dict] Loaded {len(words):,} English words from file")
        return lambda word: word.lower() in words

    print("[Dict] Using built-in minimal English word list")
    COMMON_ENGLISH = set("""
    a able about above across act actually add after again against age ago agree
    ahead all allow almost alone along already also always am among an and another
    any anything appear are area around as ask at away
    back bad be because become been before behind being believe below best better
    between big both bring build but buy by
    call came can cannot care change check city click close code come coming
    computer could create current cut
    data date day days did different do does done down during
    each edit else end enough enter error even every example
    far feel few file files find first follow for form found free from full
    get give go good got group
    had has have he head help her here high him his home how
    id if image in info input into is it its
    job just
    keep key know
    large last later learn left let like list little live load local long look love
    made main make many may me menu message mode more most move much must my
    name need never new next no none not note notes nothing now null
    of off often on once one only open option or order other our out over own
    page pages part pass pay people place plan play post press print put
    read ready reply report right run
    said same save say search second see select send set she should show sign
    since site size so some sort start state stay step still stop such support sure
    take test text than that the their them then there these they thing think
    this those through time to today too top total true try two type types
    under update use user users
    value version very view
    want was way we web what when where which while who why will with word words work would write
    year yes yet you your
    add check close confirm create delete edit find get help home info list load
    login logout menu mode open save search send show start stop submit update upload
    back cancel click enter error form next pass reset return sort submit success view
    """.split())
    return lambda word: word.lower() in COMMON_ENGLISH


def load_hebrew_dict():
    # 1. Windows Spell Checking API (requires Hebrew language pack installed)
    checker = _try_windows_spell_api("he-IL")
    if checker:
        return checker

    # 2. pyenchant
    try:
        import enchant
        d = enchant.Dict("he_IL")
        print("[Dict] Using pyenchant he_IL")
        return lambda word: d.check(word)
    except Exception:
        pass

    # 3. Local wordlist file
    wordlist_path = Path(__file__).parent / 'data' / 'hebrew_words.txt'
    if wordlist_path.exists():
        with open(wordlist_path, 'r', encoding='utf-8') as f:
            words = set(line.strip() for line in f if line.strip())
        print(f"[Dict] Loaded {len(words):,} Hebrew words from file")
        return lambda word: word in words

    print("[Dict] Using built-in minimal Hebrew word list")
    COMMON_HEBREW = set("""
    אני את אתה הוא היא אנחנו אתם הם
    כן לא אולי
    של עם על אל מה איך מתי איפה מי למה
    זה זאת זו אלה אלו
    יש אין היה הייתה היו יהיה תהיה
    רוצה רוצים צריך צריכה אפשר
    טוב טובה יפה גדול קטן חדש ישן
    בית עבודה אוכל מים שמש יום לילה זמן
    אחד שניים שלושה ארבעה חמישה
    שלום תודה בבקשה סליחה ברוך
    ללכת לבוא לראות לדעת לעשות לקחת לתת לדבר לקנות
    הולך בא רואה יודע עושה קונה אומר
    היום מחר אתמול עכשיו כבר עוד
    כי אבל אם גם רק אז כש
    לי לו לה לנו להם לך
    שלי שלך שלו שלה שלנו שלהם
    ממש מאוד קצת הרבה יותר פחות
    כלב חתול ילד ילדה אמא אבא
    כסף עיר רחוב ספר
    חדר שולחן כיסא דלת חלון
    אוהב אוהבת יכול יכולה רוצה
    """.split())
    return lambda word: word in COMMON_HEBREW


# ─── Word Checker ─────────────────────────────────────────────────────────────

class WordChecker:
    def __init__(self):
        print("[Dict] Loading dictionaries...")
        self.check_english = load_english_dict()
        self.check_hebrew = load_hebrew_dict()
        print("[Dict] Dictionaries ready.")

    def is_english_word(self, word):
        if not word:
            return False
        return self.check_english(word)

    def is_hebrew_word(self, word):
        if not word:
            return False
        return self.check_hebrew(word)

    def convert_heb_to_eng(self, text):
        """Hebrew chars that were typed on Hebrew keyboard → what English keys were pressed"""
        return ''.join(HEB_TO_ENG.get(c, c) for c in text)

    def convert_eng_to_heb(self, text):
        """English chars that were typed on English keyboard → what Hebrew chars those keys map to"""
        return ''.join(ENG_TO_HEB.get(c.lower(), c) for c in text)

    def all_hebrew(self, text):
        return bool(text) and all(c in HEBREW_CHARS for c in text if not c.isspace())

    def all_english(self, text):
        return bool(text) and all(c.lower() in ENGLISH_CHARS for c in text if not c.isspace())

    def analyze(self, text):
        """
        Given typed text, determine if a fix is needed.
        Returns (fix_type, original, corrected) or None.

        Case A: All Hebrew characters typed
          → Is it a real Hebrew word? No fix needed.
          → Convert to English via key mapping → is it a real English word? Fix!

        Case B: All English characters typed
          → Is it a real English word? No fix needed.
          → Convert to Hebrew via key mapping → is it a real Hebrew word? Fix!
        """
        if not text or len(text) < 2:
            return None

        # Case A: all Hebrew chars on screen
        if self.all_hebrew(text):
            if self.is_hebrew_word(text):
                return None  # legitimate Hebrew word, no fix
            converted = self.convert_heb_to_eng(text)
            if self.all_english(converted) and self.is_english_word(converted):
                return ('hebrew_is_actually_english', text, converted)
            return None

        # Case B: all English chars on screen
        if self.all_english(text):
            if self.is_english_word(text):
                return None  # legitimate English word, no fix
            converted = self.convert_eng_to_heb(text)
            if self.all_hebrew(converted) and self.is_hebrew_word(converted):
                return ('english_is_actually_hebrew', text, converted)
            return None

        return None  # mixed content — don't touch


# ─── Keyboard Fixer ───────────────────────────────────────────────────────────

# How many word-boundaries (space/enter) to check before giving up in a window session
SESSION_MAX_WORDS = 2

class KeyboardFixer:
    def __init__(self, config, tray_icon=None):
        self.config = config
        self.tray_icon = tray_icon
        self.buffer = []
        self.enabled = True
        self.listener = None
        self.controller = pynput_keyboard.Controller()
        self._lock = threading.Lock()
        self._checker = WordChecker()
        self._fixing = False

        self._current_window = None
        self._session_done = True
        self._session_words = 0
        self._stop_monitor = threading.Event()
        self._last_keypress_time = 0.0
        self._last_layout = None

    def is_password_field(self):
        """Return True if the focused control has the ES_PASSWORD style."""
        try:
            hwnd = user32.GetForegroundWindow()
            tid = user32.GetWindowThreadProcessId(hwnd, None)
            info = _GUITHREADINFO(cbSize=ctypes.sizeof(_GUITHREADINFO))
            if not user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
                return False
            if not info.hwndFocus:
                return False
            style = user32.GetWindowLongW(info.hwndFocus, GWL_STYLE)
            return bool(style & ES_PASSWORD)
        except Exception:
            return False

    def _reset_session(self):
        self._session_done = False
        self._session_words = 0
        with self._lock:
            self.buffer.clear()

    def _window_monitor(self):
        """Background thread: resets session when foreground window changes (debounced)."""
        pending_hwnd = None
        pending_since = 0.0
        STABLE_MS = 0.25  # HWND must be stable for 250ms before triggering reset

        while not self._stop_monitor.is_set():
            try:
                if not self._fixing:
                    hwnd = user32.GetForegroundWindow()
                    now = time.time()

                    if hwnd and hwnd != self._current_window:
                        if hwnd != pending_hwnd:
                            pending_hwnd = hwnd
                            pending_since = now
                        elif now - pending_since >= STABLE_MS:
                            print(f"[Monitor] new window (stable)")
                            self._current_window = hwnd
                            pending_hwnd = None
                            self._reset_session()
                    else:
                        pending_hwnd = None
            except Exception:
                pass
            time.sleep(0.1)

    def _get_char(self, key):
        """Return the char pynput captured, corrected for listener-thread layout mismatch.

        pynput's hook thread keeps its own layout (HKL).  When we toggle the
        foreground window via Alt+Shift, the foreground window's HKL changes but
        pynput's thread HKL does not.  So pynput may translate 'a' → 'ש' even
        though the user's cursor is in an English-layout window and the screen
        shows 'a'.  We compare pynput's char script against the foreground
        window's actual layout and convert if they disagree.
        """
        try:
            ch = key.char
            if ch is None:
                return None
            is_heb = ch in HEBREW_CHARS
            is_eng = ch.lower() in ENGLISH_CHARS
            if not is_heb and not is_eng:
                return ch  # digit / symbol — leave as-is
            hwnd = user32.GetForegroundWindow()
            win_is_heb = (get_layout_for(hwnd) == LANG_HEBREW)
            if is_heb and not win_is_heb:
                # pynput used Hebrew layout, window is English → back to eng key
                return HEB_TO_ENG.get(ch, ch)
            if is_eng and win_is_heb:
                # pynput used English layout, window is Hebrew → Hebrew char
                return ENG_TO_HEB.get(ch.lower(), ch)
            return ch
        except AttributeError:
            return None

    def check_buffer(self):
        text = ''.join(self.buffer)
        return self._checker.analyze(text)

    def apply_fix(self, fix_type, original, corrected, delimiter=None):
        # Capture target window BEFORE any action — Alt+Shift temporarily shifts focus
        target_hwnd = user32.GetForegroundWindow()
        self._fixing = True
        try:
            time.sleep(0.05)  # let the OS deliver the physical delimiter before we start editing
            if self.config.get('action_play_beep', True):
                winsound.MessageBeep(winsound.MB_OK)

            if self.config.get('action_replace_text', True):
                # Delete the word + the delimiter that triggered the fix
                delete_count = len(original) + (1 if delimiter is not None else 0)
                print(f"[Fix] deleting {delete_count} chars, typing '{corrected}'")
                for _ in range(delete_count):
                    self.controller.press(pynput_keyboard.Key.backspace)
                    self.controller.release(pynput_keyboard.Key.backspace)
                    time.sleep(0.01)

                self.controller.type(corrected)

                with self._lock:
                    self.buffer.clear()

                # Re-type the delimiter so the word is properly terminated
                if delimiter is not None:
                    self.controller.press(delimiter)
                    self.controller.release(delimiter)

                time.sleep(0.05)
            else:
                # No text replacement — just clear our internal buffer
                with self._lock:
                    self.buffer.clear()

            if self.config.get('action_switch_layout', True):
                if fix_type == 'hebrew_is_actually_english':
                    switch_to_english_for(target_hwnd)
                elif fix_type == 'english_is_actually_hebrew':
                    switch_to_hebrew_for(target_hwnd)
                print(f"[Fix] layout after switch: {get_layout_for(target_hwnd):#06x}")

            # Anchor to target window so monitor doesn't re-reset the session
            self._current_window = target_hwnd

            if self.tray_icon and self.config.get('notify', True):
                self.tray_icon.notify("תוקן!", f'"{original}" → "{corrected}"')

        finally:
            self._fixing = False

    def on_press(self, key):
        if not self.enabled or self._fixing:
            return

        # Never log or process keystrokes in a password field
        if self.is_password_field():
            with self._lock:
                self.buffer.clear()
            return

        # Modifier / navigation keys invalidate the buffer (cursor may have moved)
        _BUFFER_RESET_KEYS = {
            pynput_keyboard.Key.ctrl,     pynput_keyboard.Key.ctrl_l,
            pynput_keyboard.Key.ctrl_r,   pynput_keyboard.Key.alt,
            pynput_keyboard.Key.alt_l,    pynput_keyboard.Key.alt_r,
            pynput_keyboard.Key.alt_gr,   pynput_keyboard.Key.cmd,
            pynput_keyboard.Key.cmd_l,    pynput_keyboard.Key.cmd_r,
            pynput_keyboard.Key.up,       pynput_keyboard.Key.down,
            pynput_keyboard.Key.left,     pynput_keyboard.Key.right,
            pynput_keyboard.Key.home,     pynput_keyboard.Key.end,
            pynput_keyboard.Key.page_up,  pynput_keyboard.Key.page_down,
            pynput_keyboard.Key.esc,      pynput_keyboard.Key.delete,
        }
        if key in _BUFFER_RESET_KEYS:
            with self._lock:
                self.buffer.clear()
            return

        # Reset session after 15s idle
        now = time.time()
        if self._session_done and (now - self._last_keypress_time) > 15:
            print("[Idle] reset session after idle")
            self._reset_session()
        self._last_keypress_time = now

        # Safety fallback: detect window change
        hwnd = user32.GetForegroundWindow()
        if hwnd and hwnd != self._current_window:
            print(f"[Window] new hwnd={hwnd}, resetting session")
            self._current_window = hwnd
            self._reset_session()

        if self._session_done:
            return

        # ── Word-boundary keys: check buffer and apply fix if needed ──────────
        if key in (pynput_keyboard.Key.space,
                   pynput_keyboard.Key.enter,
                   pynput_keyboard.Key.tab):
            min_chars = self.config.get('min_chars', 2)
            result = None
            if len(self.buffer) >= min_chars:
                result = self.check_buffer()
                print(f"[Check] '{''.join(self.buffer)}' → {result}")

            if result:
                fix_type, original, corrected = result
                if not self.config.get('continue_checking_window', False):
                    self._session_done = True
                threading.Thread(
                    target=self.apply_fix,
                    args=(fix_type, original, corrected, key),
                    daemon=True
                ).start()
                return  # apply_fix handles deletion + re-type of delimiter

            # Clean word — count toward session limit
            with self._lock:
                had_content = len(self.buffer) > 0
                self.buffer.clear()
            if had_content:
                self._session_words += 1
                print(f"[Word] clean word #{self._session_words}")
                if (not self.config.get('continue_checking_window', False)
                        and self._session_words >= SESSION_MAX_WORDS):
                    self._session_done = True
            return

        # ── Backspace: trim buffer ─────────────────────────────────────────────
        if key == pynput_keyboard.Key.backspace:
            with self._lock:
                if self.buffer:
                    self.buffer.pop()
            return

        # ── Regular character keys ─────────────────────────────────────────────
        ch = self._get_char(key)
        if ch is None:
            return

        with self._lock:
            self.buffer.append(ch)

        print(f"[Buffer] '{''.join(self.buffer)}'")

    def start(self):
        self.listener = pynput_keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        self._stop_monitor.clear()
        threading.Thread(target=self._window_monitor, daemon=True).start()

    def stop(self):
        self._stop_monitor.set()
        if self.listener:
            self.listener.stop()

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled
