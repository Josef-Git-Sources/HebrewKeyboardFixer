"""
One-time helper: downloads the Hunspell Hebrew dictionary,
parses it into a clean word-per-line text file, and saves it
as hebrew_words.txt in the project root for bundling into the EXE.
"""

import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/he/index.dic"
OUT = Path(__file__).parent / "hebrew_words.txt"

print(f"Downloading {URL} ...")
req = urllib.request.Request(URL, headers={"User-Agent": "KeyboardFixer/1.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    content = resp.read().decode("utf-8", errors="ignore")

words = set()
for line in content.splitlines()[1:]:   # line 0 is the word count
    word = line.split("/")[0].strip()
    if word and not word.isdigit():
        words.add(word)

OUT.write_text("\n".join(sorted(words)), encoding="utf-8")
print(f"Saved {len(words):,} words → {OUT}")
