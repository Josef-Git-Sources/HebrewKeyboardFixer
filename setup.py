"""
Setup and installer for Hebrew Keyboard Fixer
Run this once to install dependencies and create a shortcut
"""

import subprocess
import sys
import os
from pathlib import Path

def install_deps():
    print("מתקין חבילות Python נדרשות...")

    # Core packages
    packages = ['pynput', 'pystray', 'pillow']
    for pkg in packages:
        print(f"  מתקין {pkg}...")
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', pkg, '--quiet'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  ✅ {pkg}")
        else:
            print(f"  ❌ שגיאה: {result.stderr.strip()}")
            return False

    # Try pyenchant (best dictionary quality) — optional
    print("\n  מנסה להתקין מילון מקצועי (pyenchant)...")
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', 'pyenchant', '--quiet'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("  ✅ pyenchant — מילון מלא הותקן!")
    else:
        print("  ⚠️  pyenchant לא הותקן — התוכנה תשתמש במילון מובנה מצומצם.")
        print("     (זה בסדר, התוכנה תעבוד גם כך)")

    return True

def create_data_dir():
    """Create data directory for word lists"""
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)
    readme = data_dir / 'README.txt'
    with open(readme, 'w', encoding='utf-8') as f:
        f.write("""תיקיית מילונים
==============
ניתן להוסיף כאן קבצי מילונים לשיפור הזיהוי:

english_words.txt  — מילון אנגלי (מילה אחת בכל שורה)
hebrew_words.txt   — מילון עברי (מילה אחת בכל שורה)

מקורות מומלצים:
- אנגלית: https://github.com/dwyl/english-words (words_alpha.txt)
- עברית:  https://github.com/eyaler/hebrew_wordlists
""")
    print(f"✅ נוצרה תיקיית מילונים: {data_dir}")

def create_shortcut():
    script_dir = Path(__file__).parent.absolute()
    bat_path = script_dir / 'start_keyboard_fixer.bat'

    bat_content = f'@echo off\ncd /d "{script_dir}"\nstart "" pythonw "{script_dir}\\tray_app.py"\n'
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)
    print(f"✅ קובץ הפעלה: {bat_path}")

    desktop = Path(os.environ.get('USERPROFILE', '~')) / 'Desktop'
    shortcut_path = desktop / 'Hebrew Keyboard Fixer.lnk'
    ps_script = f'''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{bat_path}"
$Shortcut.WorkingDirectory = "{script_dir}"
$Shortcut.Description = "Hebrew Keyboard Auto-Switcher"
$Shortcut.Save()
'''
    result = subprocess.run(['powershell', '-Command', ps_script], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ קיצור דרך בשולחן העבודה נוצר")
    else:
        print(f"⚠️  לא הצלחנו ליצור קיצור דרך. הפעל ידנית: {bat_path}")

    return bat_path

def main():
    print("=" * 55)
    print("  Hebrew Keyboard Fixer - התקנה")
    print("=" * 55)

    if sys.platform != 'win32':
        print("❌ תוכנה זו פועלת רק על Windows!")
        input("לחץ Enter לסגירה...")
        sys.exit(1)

    if not install_deps():
        print("\n❌ ההתקנה נכשלה.")
        input("לחץ Enter לסגירה...")
        sys.exit(1)

    create_data_dir()
    bat_path = create_shortcut()

    print("\n" + "=" * 55)
    print("✅ ההתקנה הושלמה!")
    print()
    print("💡 טיפ לשיפור הזיהוי:")
    print("   הורד מילונים גדולים יותר לתיקיית data/")
    print("   (ראה data/README.txt להסבר)")
    print()
    print(f"הפעלה: לחץ פעמיים על 'Hebrew Keyboard Fixer' בשולחן העבודה")
    print("=" * 55)

    ans = input("\nהאם להפעיל את התוכנה עכשיו? (y/n): ").strip().lower()
    if ans == 'y':
        subprocess.Popen([sys.executable, str(Path(__file__).parent / 'tray_app.py')])
        print("✅ התוכנה הופעלה! חפש אותה במגש המערכת.")

    input("\nלחץ Enter לסגירה...")

if __name__ == '__main__':
    main()
