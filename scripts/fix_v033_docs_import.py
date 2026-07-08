from pathlib import Path
import re
import py_compile
import shutil

target = Path("scripts/vega.py")
backup = Path("scripts/vega.py.bak_v033_import_fix")

if not target.exists():
    raise FileNotFoundError("scripts/vega.py not found")

text = target.read_text(encoding="utf-8", errors="replace")
backup.write_text(text, encoding="utf-8")

pattern = r"(?ms)^[ \t]*# \[VEGA_DOCS_COMMANDS_CALL_START\]\n.*?^[ \t]*# \[VEGA_DOCS_COMMANDS_CALL_END\]\n?"

match = re.search(pattern, text)

if not match:
    raise RuntimeError("VEGA_DOCS_COMMANDS_CALL block not found in scripts/vega.py")

old_block = match.group(0)

indent = re.match(r"^[ \t]*", old_block).group(0)

# Пытаемся понять имя переменной пользовательского ввода из старого блока
var_match = re.search(r"startswith\('/docs'\)", old_block)

# Более надёжно: ищем строку вида if str(USER_INPUT).strip().startswith('/docs'):
input_var_match = re.search(r"if str\((?P<var>[A-Za-z_][A-Za-z0-9_]*)\)\.strip\(\)\.startswith\('/docs'\):", old_block)

if not input_var_match:
    raise RuntimeError("Could not detect input variable in existing /docs block")

input_var = input_var_match.group("var")

new_block = (
    f"{indent}# [VEGA_DOCS_COMMANDS_CALL_START]\n"
    f"{indent}if str({input_var}).strip().startswith('/docs'):\n"
    f"{indent}    try:\n"
    f"{indent}        import sys as _vega_sys\n"
    f"{indent}        from pathlib import Path as _VegaPath\n"
    f"{indent}        _vega_project_root = _VegaPath(__file__).resolve().parents[1]\n"
    f"{indent}        if str(_vega_project_root) not in _vega_sys.path:\n"
    f"{indent}            _vega_sys.path.insert(0, str(_vega_project_root))\n"
    f"{indent}        from rag.commands import handle_docs_command as _vega_handle_docs_command\n"
    f"{indent}        _vega_handle_docs_command(str({input_var}), _vega_project_root)\n"
    f"{indent}    except Exception as _vega_docs_error:\n"
    f"{indent}        print(f'VEGA docs command error: {{_vega_docs_error}}')\n"
    f"{indent}    continue\n"
    f"{indent}# [VEGA_DOCS_COMMANDS_CALL_END]\n"
)

text = text[:match.start()] + new_block + text[match.end():]

target.write_text(text, encoding="utf-8")

try:
    py_compile.compile(str(target), doraise=True)
except Exception as exc:
    shutil.copyfile(backup, target)
    raise RuntimeError("Syntax check failed. Restored backup.") from exc

print("OK: /docs import path fixed")
print(f"Changed file: {target}")
print(f"Backup file: {backup}")
print(f"Input variable: {input_var}")
