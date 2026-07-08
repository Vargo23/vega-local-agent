from pathlib import Path
from datetime import datetime
import json
import subprocess


ROOT = Path.cwd()
REPORT_DIR = ROOT / "logs" / "checks"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

report_path = REPORT_DIR / f"vega_v031_check_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

checks = []


def add(name, ok, details=""):
    checks.append((name, ok, details))


def run_cmd(cmd):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as exc:
        return 999, "", str(exc)


add("rag/__init__.py exists", (ROOT / "rag" / "__init__.py").exists())
add("rag/store.py exists", (ROOT / "rag" / "store.py").exists())
add("rag/ingest.py exists", (ROOT / "rag" / "ingest.py").exists())
add("data/documents exists", (ROOT / "data" / "documents").exists())
add("data/index exists", (ROOT / "data" / "index").exists())
add("test document exists", (ROOT / "data" / "documents" / "vega_v031_test.md").exists())

code, out, err = run_cmd("python .\\rag\\ingest.py")
add("ingest command works", code == 0, out or err)

index_path = ROOT / "data" / "index" / "documents_index.json"
add("documents_index.json exists", index_path.exists(), str(index_path))

if index_path.exists():
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))

        add("index schema is valid", index.get("schema") == "vega.documents_index.v1", index.get("schema", ""))
        add("index has documents list", isinstance(index.get("documents"), list))
        add("index has chunks list", isinstance(index.get("chunks"), list))
        add("at least one document indexed", index.get("documents_count", 0) >= 1, str(index.get("documents_count")))
        add("at least one chunk created", index.get("chunks_count", 0) >= 1, str(index.get("chunks_count")))

        chunks = index.get("chunks", [])
        has_source = bool(chunks and chunks[0].get("source_path"))
        has_text = bool(chunks and chunks[0].get("text"))

        add("chunk has source_path", has_source)
        add("chunk has text", has_text)

    except Exception as exc:
        add("index can be parsed as JSON", False, str(exc))
else:
    add("index schema is valid", False, "index not found")
    add("index has documents list", False, "index not found")
    add("index has chunks list", False, "index not found")
    add("at least one document indexed", False, "index not found")
    add("at least one chunk created", False, "index not found")
    add("chunk has source_path", False, "index not found")
    add("chunk has text", False, "index not found")

passed = sum(1 for _, ok, _ in checks if ok)
failed = sum(1 for _, ok, _ in checks if not ok)

lines = []
lines.append("VEGA v0.3.1 DOCUMENT INGESTION CHECK")
lines.append("=" * 46)
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
    lines.append("RESULT: v0.3.1 document ingestion is ready. Next patch: v0.3.2 keyword search.")
else:
    lines.append("RESULT: Fix failed checks before implementing v0.3.2.")

report_path.write_text("\n".join(lines), encoding="utf-8")

print("\n".join(lines))
print("")
print(f"Report saved to: {report_path}")
