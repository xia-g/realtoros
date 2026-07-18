from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOCS_DIR = ROOT / "docs"


def read_doc(relative_path: str) -> str:
    file_path = DOCS_DIR / relative_path

    if not file_path.exists():
        return f"Document not found: {relative_path}"

    return file_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

def search_docs(query: str):
    result = []

    for file in DOCS_DIR.rglob("*.md"):

        try:
            text = file.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            if query.lower() in text.lower():

                result.append(
                    str(file.relative_to(DOCS_DIR))
                )

        except Exception:
            pass

    return result
