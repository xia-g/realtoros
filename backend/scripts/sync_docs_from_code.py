"""sync_docs_from_code.py — автоматическая генерация docs/ из backend-кода."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if "__file__" in dir() else Path.cwd()
OUTPUT = ROOT / "docs" / "generated"


def get(path_pattern):
    for f in sorted(ROOT.glob(path_pattern)):
        if f.is_file() and not f.name.startswith("_") and "__pycache__" not in str(f):
            yield f


def sync_models():
    rows = []
    for f in get("backend/models/*.py"):
        content = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'class (\w+)\(', content):
            rows.append(f"| {m.group(1)} | {f.stem} |")
    text = "# Generated Models\n\n| Class | File |\n|-------|------|\n" + "\n".join(sorted(set(rows)))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "models.md").write_text(text)
    print(f"✅ models.md: {len(set(rows))} models")


def sync_apis():
    rows = []
    for f in get("backend/api/routes/*.py"):
        content = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'@router\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]', content):
            rows.append(f"| {m.group(1).upper()} | {m.group(2)} | {f.stem} |")
    text = "# Generated API Endpoints\n\n| Method | Path | Router |\n|--------|------|--------|\n" + "\n".join(rows)
    (OUTPUT / "api.md").write_text(text)
    print(f"✅ api.md: {len(rows)} endpoints")


def sync_events():
    declared, emitted = set(), set()
    for f in Path(ROOT).rglob("*.py"):
        if "__pycache__" in str(f) or "test_" in f.name: continue
        try:
            c = f.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'EVENT_\w+\s*=\s*["\']([^"\']+)["\']', c): declared.add(m.group(1))
            for m in re.finditer(r'event_type=["\']([^"\']+)["\']', c): emitted.add(m.group(1))
        except: pass
    dead = declared - emitted
    text = f"# Event Bus\n\nDeclared: {len(declared)}\nEmitted: {len(emitted)}\nDead: {len(dead)}\n\n## Dead\n" + "\n".join(f"- {e}" for e in sorted(dead)) + "\n\n## Active\n" + "\n".join(f"- {e}" for e in sorted(emitted))
    (OUTPUT / "events.md").write_text(text)
    print(f"✅ events.md: {len(declared)} declared, {len(emitted)} emitted")


def sync_services():
    rows = []
    for f in sorted((ROOT / "backend" / "services").rglob("*.py")):  # rglob for recursive
        if f.name.startswith("_") or "__pycache__" in str(f): continue
        c = f.read_text(encoding="utf-8", errors="ignore")
        classes = re.findall(r'class (\w+)\(', c)
        for cls in classes:
            methods = re.findall(r'def (\w+)', c)
            rows.append(f"| {cls} | {f.relative_to(ROOT)} | {', '.join(methods[:5])} |")
    text = "# Generated Services\n\n| Service | File | Methods |\n|--------|------|---------|\n" + "\n".join(rows)
    (OUTPUT / "services.md").write_text(text)
    print(f"✅ services.md: {len(rows)} services")


def sync_tests():
    total, files = 0, 0
    for f in sorted((ROOT / "backend" / "tests").rglob("*.py")):
        if "__pycache__" in str(f): continue
        c = f.read_text(encoding="utf-8", errors="ignore")
        n = len(re.findall(r'def test_', c))
        if n > 0: total += n; files += 1
    (OUTPUT / "tests.md").write_text(f"# Tests\n\n{total} tests in {files} files")
    print(f"✅ tests.md: {total} tests")


if __name__ == "__main__":
    sync_models(); sync_apis(); sync_services(); sync_events(); sync_tests()
    print(f"Done: {len(list(OUTPUT.glob('*.md')))} files")
