from __future__ import annotations

import py_compile
import re
import shutil
from pathlib import Path


ROOT = Path.cwd()
TARGET = ROOT / "scripts" / "vega.py"
BACKUP = ROOT / "scripts" / "vega.py.bak_v033"
DEBUG = ROOT / "scripts" / "vega_v033_patch_debug.txt"

if not TARGET.exists():
    raise FileNotFoundError(f"File not found: {TARGET}")

original = TARGET.read_text(encoding="utf-8", errors="replace")
BACKUP.write_text(original, encoding="utf-8")

text = original

# Remove old v0.3.3 block if patch was already applied
text = re.sub(
    r"(?ms)^[ \t]*# \[VEGA_DOCS_COMMANDS_CALL_START\]\n.*?^[ \t]*# \[VEGA_DOCS_COMMANDS_CALL_END\]\n?",
    "",
    text,
)

lines = text.splitlines(keepends=True)

candidate_index = None
candidate_var = None

# Prefer the input line that belongs to the VEGA prompt
for i, line in enumerate(lines):
    if "input(" not in line or "=" not in line:
        continue

    if "VEGA" not in line and "prompt" not in line.lower():
        continue

    match = re.match(r"^(?P<indent>[ \t]*)(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*input\(.*$", line)

    if match:
        candidate_index = i
        candidate_var = match.group("var")
        break

# Fallback: first input assignment
if candidate_index is None:
    for i, line in enumerate(lines):
        if "input(" not in line or "=" not in line:
            continue

        match = re.match(r"^(?P<indent>[ \t]*)(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*input\(.*$", line)

        if match:
            candidate_index = i
            candidate_var = match.group("var")
            break

if candidate_index is None or candidate_var is None:
    DEBUG.write_text(
        "".join(f"{n + 1}: {line}" for n, line in enumerate(lines[:260])),
        encoding="utf-8",
    )
    raise RuntimeError(
        "Could not find CLI input assignment in scripts/vega.py. "
        "Debug file created: scripts/vega_v033_patch_debug.txt"
    )

indent = re.match(r"^[ \t]*", lines[candidate_index]).group(0)

insert_block = (
    f"{indent}# [VEGA_DOCS_COMMANDS_CALL_START]\n"
    f"{indent}if str({candidate_var}).strip().startswith('/docs'):\n"
    f"{indent}    try:\n"
    f"{indent}        from pathlib import Path as _VegaPath\n"
    f"{indent}        from rag.commands import handle_docs_command as _vega_handle_docs_command\n"
    f"{indent}        _vega_handle_docs_command(str({candidate_var}), _VegaPath(__file__).resolve().parents[1])\n"
    f"{indent}    except Exception as _vega_docs_error:\n"
    f"{indent}        print(f'VEGA docs command error: {{_vega_docs_error}}')\n"
    f"{indent}    continue\n"
    f"{indent}# [VEGA_DOCS_COMMANDS_CALL_END]\n"
)

lines.insert(candidate_index + 1, insert_block)

patched = "".join(lines)
TARGET.write_text(patched, encoding="utf-8")

try:
    py_compile.compile(str(TARGET), doraise=True)
except Exception as exc:
    shutil.copyfile(BACKUP, TARGET)
    raise RuntimeError(
        "Patched scripts/vega.py failed Python syntax check. "
        "Original file restored from backup."
    ) from exc

print("OK: /docs commands patched into scripts/vega.py")
print(f"Changed file: {TARGET}")
print(f"Backup file: {BACKUP}")
print(f"Input variable detected: {candidate_var}")
print(f"Inserted after line: {candidate_index + 1}")
