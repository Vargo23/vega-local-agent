from pathlib import Path
from datetime import datetime
import json
import subprocess


ROOT = Path.cwd()
REPORT_DIR = ROOT / "logs" / "checks"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

report_path = REPORT_DIR / f"vega_v032_check_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

checks = []


def add(name, ok, details=""):
    checks.append((name, ok, details))


def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return 999, "", str(exc)


add("rag/search.py exists", (ROOT / "rag" / "search.py").exists())
add("rag/ingest.py exists", (ROOT / "rag" / "ingest.py").exists())
add("rag/store.py exists", (ROOT / "rag" / "store.py").exists())

code, out, err = run_cmd("python .\\rag\\ingest.py")
add("ingest works before search", code == 0, out or err)

index_path = ROOT / "data" / "index" / "documents_index.json"
add("documents_index.json exists", index_path.exists(), str(index_path))

if index_path.exists():
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        add("index has chunks", data.get("chunks_count", 0) >= 1, str(data.get("chunks_count")))
    except Exception as exc:
        add("index has chunks", False, str(exc))
else:
    add("index has chunks", False, "index not found")

code, out, err = run_cmd('python .\\rag\\search.py "document ingestion"')
add("search command works", code == 0, out or err)
add("search returns test document", "vega_v031_test.md" in out, out)

code, out, err = run_cmd('python .\\rag\\search.py "query_that_should_not_exist_12345"')
add("empty search does not crash", code == 0, out or err)
add("empty search returns no matches", "No matching documents found." in out, out)

code, out, err = run_cmd('python .\\rag\\search.py "document ingestion" --json')
add("JSON search mode works", code == 0, out or err)

try:
    parsed = json.loads(out)
    add("JSON search output parses", isinstance(parsed, list), str(type(parsed)))
except Exception as exc:
    add("JSON search output parses", False, str(exc))

passed = sum(1 for _, ok, _ in checks if ok)
failed = sum(1 for _, ok, _ in checks if not ok)

lines = []
lines.append("VEGA v0.3.2 KEYWORD SEARCH CHECK")
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
    lines.append("RESULT: v0.3.2 keyword search is ready. Next patch: v0.3.3 CLI /docs commands.")
else:
    lines.append("RESULT: Fix failed checks before implementing v0.3.3.")

report_path.write_text("\n".join(lines), encoding="utf-8")

print("\n".join(lines))
print("")
print(f"Report saved to: {report_path}")
