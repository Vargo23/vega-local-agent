from pathlib import Path

p = Path("scripts/check_v030.py")

if not p.exists():
    raise FileNotFoundError("scripts/check_v030.py not found")

text = p.read_text(encoding="utf-8", errors="replace")

old = 'add("desktop launcher VEGA.cmd exists", exists(Path.home() / "Desktop" / "VEGA.cmd"))'

new = '''desktop_candidates = [
    Path.home() / "Desktop" / "VEGA.cmd",
    Path.home() / "OneDrive" / "Desktop" / "VEGA.cmd",
    Path.home() / "OneDrive" / "Рабочий стол" / "VEGA.cmd",
]
desktop_ok = any(x.exists() for x in desktop_candidates)
desktop_details = "; ".join(str(x) for x in desktop_candidates if x.exists()) or "; ".join(str(x) for x in desktop_candidates)
add("desktop launcher VEGA.cmd exists", desktop_ok, desktop_details)'''

if old in text:
    text = text.replace(old, new)
else:
    print("Desktop check line was not found or already patched.")

p.write_text(text, encoding="utf-8")

print("OK: v0.3.0 missing files fixed")
