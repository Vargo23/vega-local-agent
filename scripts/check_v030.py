from pathlib import Path
from datetime import datetime
import subprocess
import shutil

ROOT = Path.cwd()
REPORT_DIR = ROOT / "logs" / "checks"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

report_path = REPORT_DIR / f"vega_v030_check_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

checks = []

def add(name, ok, details=""):
    checks.append((name, ok, details))

def exists(path):
    return Path(path).exists()

def run_cmd(cmd):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 999, "", str(e)

# v0.2.2 stability checks
add("scripts/vega.py exists", exists(ROOT / "scripts" / "vega.py"))
add("root launcher vega.cmd exists", exists(ROOT / "vega.cmd"))
desktop_candidates = [
    Path.home() / "Desktop" / "VEGA.cmd",
    Path.home() / "OneDrive" / "Desktop" / "VEGA.cmd",
    Path.home() / "OneDrive" / "Рабочий стол" / "VEGA.cmd",
]
desktop_ok = any(x.exists() for x in desktop_candidates)
desktop_details = "; ".join(str(x) for x in desktop_candidates if x.exists()) or "; ".join(str(x) for x in desktop_candidates)
add("desktop launcher VEGA.cmd exists", desktop_ok, desktop_details)
add("global launcher exists", exists(Path.home() / "vega-bin" / "vega.cmd"))
add("logs/sessions exists", exists(ROOT / "logs" / "sessions"))

vega_py = ROOT / "scripts" / "vega.py"
if vega_py.exists():
    text = vega_py.read_text(encoding="utf-8", errors="replace")
    add("startup banner marker exists", "VEGA_ASCII_BANNER" in text or "VEGA_ASCII_BANNER_START" in text)
    add("vega-core referenced", "vega-core" in text)
else:
    add("startup banner marker exists", False, "scripts/vega.py not found")
    add("vega-core referenced", False, "scripts/vega.py not found")

add("python executable found", shutil.which("python") is not None, shutil.which("python") or "")
code, out, err = run_cmd("python --version")
add("python version works", code == 0, out or err)

add("ollama executable found", shutil.which("ollama") is not None, shutil.which("ollama") or "")
code, out, err = run_cmd("ollama list")
add("ollama list works", code == 0, out or err)
add("ollama model vega-core exists", "vega-core" in out, out)

# v0.3.0 scaffold checks
add("data/documents exists", exists(ROOT / "data" / "documents"))
add("data/index exists", exists(ROOT / "data" / "index"))
add("rag folder exists", exists(ROOT / "rag"))
add("docs folder exists", exists(ROOT / "docs"))
add("RAG architecture doc exists", exists(ROOT / "docs" / "VEGA_V030_RAG_ARCHITECTURE.md"))
add("rag README exists", exists(ROOT / "rag" / "README.md"))
add("data/documents .gitkeep exists", exists(ROOT / "data" / "documents" / ".gitkeep"))
add("data/index .gitkeep exists", exists(ROOT / "data" / "index" / ".gitkeep"))

passed = sum(1 for _, ok, _ in checks if ok)
failed = sum(1 for _, ok, _ in checks if not ok)

lines = []
lines.append("VEGA v0.3.0 SCAFFOLD CHECK")
lines.append("=" * 42)
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
    lines.append("RESULT: v0.3.0 scaffold is ready. Next patch: v0.3.1 document ingestion.")
else:
    lines.append("RESULT: Fix failed checks before implementing v0.3.1.")

report_path.write_text("\n".join(lines), encoding="utf-8")

print("\n".join(lines))
print("")
print(f"Report saved to: {report_path}")
