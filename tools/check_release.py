import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "venv", "runs", "outputs", "build", "dist", "__pycache__",
        ".pytest_cache", ".ruff_cache", "validation"}
SECRET = re.compile(r"(?:sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)")
FORBIDDEN_SUFFIXES = {".xlsx", ".xls", ".docx", ".pdf", ".db", ".sqlite", ".pkl", ".pickle", ".fig"}


def main() -> int:
    errors = []
    count = 0
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in SKIP or part.endswith(".egg-info") for part in relative.parts):
            continue
        count += 1
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or (path.name.startswith(".env") and path.name != ".env.example"):
            errors.append(f"excluded artifact: {relative}")
        if relative.parts[0] == "data" and relative.parts[1] != "demo":
            errors.append(f"non-demo data path: {relative}")
        text = path.read_text(encoding="utf-8", errors="replace")
        if SECRET.search(text):
            errors.append(f"credential-like content: {relative}")
    print(json.dumps({"files_checked": count, "errors": errors}, indent=2))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
