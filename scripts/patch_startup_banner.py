from pathlib import Path
import re

root = Path.cwd()
target = root / "scripts" / "vega.py"
backup = root / "scripts" / "vega.py.bak_banner_v2"

if not target.exists():
    raise FileNotFoundError(f"File not found: {target}")

text = target.read_text(encoding="utf-8")
backup.write_text(text, encoding="utf-8")

block_start = "# [VEGA_ASCII_BANNER_START]"
block_end = "# [VEGA_ASCII_BANNER_END]"
call_marker = "# [VEGA_ASCII_BANNER_CALL]"

# Удаляем старую версию патча, если она уже была
text = re.sub(
    r"(?ms)^# \[VEGA_ASCII_BANNER_START\].*?^# \[VEGA_ASCII_BANNER_END\]\n*",
    "",
    text
)
text = re.sub(
    r"(?m)^[ \t]*print_startup_banner\(\)[ \t]*# \[VEGA_ASCII_BANNER_CALL\]\n?",
    "",
    text
)

banner_block = r'''
# [VEGA_ASCII_BANNER_START]
VEGA_ASCII_BANNER = r"""
██╗   ██╗███████╗ ██████╗  █████╗
██║   ██║██╔════╝██╔════╝ ██╔══██╗
██║   ██║█████╗  ██║  ███╗███████║
╚██╗ ██╔╝██╔══╝  ██║   ██║██╔══██║
 ╚████╔╝ ███████╗╚██████╔╝██║  ██║
  ╚═══╝  ╚══════╝ ╚═════╝ ╚═╝  ╚═╝
"""

def print_startup_banner():
    print(VEGA_ASCII_BANNER)
# [VEGA_ASCII_BANNER_END]

'''

lines = text.splitlines(keepends=True)

main_if_index = None
for i, line in enumerate(lines):
    if "__name__" in line and "__main__" in line:
        main_if_index = i
        break

if main_if_index is None:
    raise RuntimeError('Не найден блок if __name__ == "__main__". Нужно смотреть scripts\\vega.py вручную.')

# Вставляем функцию баннера перед if __name__ == "__main__"
lines.insert(main_if_index, banner_block)

# После вставки индекс if сместился
text = "".join(lines)
lines = text.splitlines(keepends=True)

main_if_index = None
for i, line in enumerate(lines):
    if "__name__" in line and "__main__" in line:
        main_if_index = i
        break

inserted_call = False

for i in range(main_if_index + 1, min(main_if_index + 12, len(lines))):
    line = lines[i]
    stripped = line.strip()

    if stripped.startswith("main(") or stripped == "main()":
        indent = re.match(r"^[ \t]*", line).group(0)
        lines.insert(i, f"{indent}print_startup_banner()  {call_marker}\n")
        inserted_call = True
        break

if not inserted_call:
    raise RuntimeError('Не найден вызов main() после if __name__ == "__main__". Нужно смотреть scripts\\vega.py вручную.')

target.write_text("".join(lines), encoding="utf-8")

print("OK: banner patch applied")
print(f"Changed file: {target}")
print(f"Backup file: {backup}")
