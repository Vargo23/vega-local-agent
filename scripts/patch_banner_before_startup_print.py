from pathlib import Path
import re

target = Path("scripts/vega.py")
backup = Path("scripts/vega.py.bak_banner_v3")

if not target.exists():
    raise FileNotFoundError(f"File not found: {target}")

text = target.read_text(encoding="utf-8-sig")
backup.write_text(text, encoding="utf-8")

# Удаляем старый баннер, если он уже был вставлен
text = re.sub(
    r"(?ms)^[ \t]*# \[VEGA_ASCII_BANNER_START\]\n.*?^[ \t]*# \[VEGA_ASCII_BANNER_END\]\n*",
    "",
    text
)

banner = """██╗   ██╗███████╗ ██████╗  █████╗
██║   ██║██╔════╝██╔════╝ ██╔══██╗
██║   ██║█████╗  ██║  ███╗███████║
╚██╗ ██╔╝██╔══╝  ██║   ██║██╔══██║
 ╚████╔╝ ███████╗╚██████╔╝██║  ██║
  ╚═══╝  ╚══════╝ ╚═════╝ ╚═╝  ╚═╝"""

startup_markers = [
    "VEGA v",
    "Local Project",
    "Coding-Agent",
    "Status: Ready",
    "Type /help",
]

lines = text.splitlines(keepends=True)

insert_index = None

for i, line in enumerate(lines):
    if "print(" in line and any(marker in line for marker in startup_markers):
        insert_index = i
        break

if insert_index is None:
    debug_path = Path("scripts/vega_startup_debug.txt")
    debug_path.write_text(
        "".join(f"{n+1}: {line}" for n, line in enumerate(lines[:160])),
        encoding="utf-8"
    )
    raise RuntimeError(
        "Не нашёл startup print в scripts/vega.py. "
        "Создал debug-файл: scripts/vega_startup_debug.txt"
    )

indent = re.match(r"^[ \t]*", lines[insert_index]).group(0)

banner_block = (
    f"{indent}# [VEGA_ASCII_BANNER_START]\n"
    f"{indent}print({banner!r})\n"
    f"{indent}# [VEGA_ASCII_BANNER_END]\n"
)

lines.insert(insert_index, banner_block)

target.write_text("".join(lines), encoding="utf-8")

print("OK: banner inserted before startup print")
print(f"Changed file: {target}")
print(f"Backup file: {backup}")
