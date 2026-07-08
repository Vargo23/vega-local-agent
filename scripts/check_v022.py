from pathlib import Path
from datetime import datetime
import os
import shutil
import subprocess
import sys

ROOT = Path.cwd()
REPORT_DIR = ROOT / "logs" / "checks"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

report_path = REPORT_DIR / f"vega_v022_check_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

checks = []

def add_check(name, ok, details=""):
    checks.append((name, ok, details))

def exists(path):
    return Path(path).exists()

def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 999, "", str(e)

# 1. Core files
add_check("Project root exists", ROOT.exists(), str(ROOT))
add_check("scripts/vega.py exists", exists(ROOT / "scripts" / "vega.py"))
add_check("ollama/Modelfile exists", exists(ROOT / "ollama" / "Modelfile"))
add_check("root launcher vega.cmd exists", exists(ROOT / "vega.cmd"))

# 2. Banner check
vega_py = ROOT / "scripts" / "vega.py"
if vega_py.exists():
    text = vega_py.read_text(encoding="utf-8", errors="replace")
    add_check("Startup banner marker exists", "VEGA_ASCII_BANNER" in text or "VEGA_ASCII_BANNER_START" in text)
    add_check("Startup text exists", "VEGA v" in text)
    add_check("Model name vega-core referenced", "vega-core" in text)
else:
    add_check("Startup banner marker exists", False, "scripts/vega.py not found")
    add_check("Startup text exists", False, "scripts/vega.py not found")
    add_check("Model name vega-core referenced", False, "scripts/vega.py not found")

# 3. Launcher check
user_bin = Path.home() / "vega-bin" / "vega.cmd"
desktop_launcher = Path.home() / "Desktop" / "VEGA.cmd"

add_check("Global launcher exists", user_bin.exists(), str(user_bin))
add_check("Desktop launcher exists", desktop_launcher.exists(), str(desktop_launcher))

path_env = os.environ.get("PATH", "")
add_check("vega-bin in PATH", str(Path.home() / "vega-bin") in path_env, str(Path.home() / "vega-bin"))

# 4. Python check
add_check("Python executable found", shutil.which("python") is not None, shutil.which("python") or "")

code, out, err = run_cmd("python --version")
add_check("Python version command works", code == 0, out or err)

# 5. Ollama check
add_check("Ollama executable found", shutil.which("ollama") is not None, shutil.which("ollama") or "")

code, out, err = run_cmd("ollama list")
add_check("ollama list works", code == 0, out or err)
add_check("Ollama model vega-core exists", "vega-core" in out, out)

# 6. Logs check
sessions_dir = ROOT / "logs" / "sessions"
add_check("logs/sessions exists", sessions_dir.exists(), str(sessions_dir))

if sessions_dir.exists():
    logs = sorted(sessions_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    add_check("At least one session log exists", len(logs) > 0, logs[0].name if logs else "")
else:
    add_check("At least one session log exists", False, "logs/sessions not found")

# 7. Backups check
backup_files = list((ROOT / "scripts").glob("*.bak*")) if (ROOT / "scripts").exists() else []
add_check("Backup files exist", len(backup_files) > 0, ", ".join(p.name for p in backup_files[:10]))

# Report
passed = sum(1 for _, ok, _ in checks if ok)
failed = sum(1 for _, ok, _ in checks if not ok)

lines = []
lines.append("VEGA v0.2.2 COMPLEX CHECK")
lines.append("=" * 40)
lines.append(f"Project: {ROOT}")
lines.append(f"Passed: {passed}")
lines.append(f"Failed: {failed}")
lines.append("")

for name, ok, details in checks:
    status = "PASS" if ok else "FAIL"
    lines.append(f"[{status}] {name}")
    if details:
        lines.append(f"       {details}")

lines.append("")
if failed == 0:
    lines.append("RESULT: v0.2.2 is stable enough to move to v0.3.")
else:
    lines.append("RESULT: Fix failed checks before moving to v0.3.")

report_path.write_text("\n".join(lines), encoding="utf-8")

print("\n".join(lines))
print("")
print(f"Report saved to: {report_path}")
