"""Извлечение текста из PDF-документов."""
import pdfplumber
from pathlib import Path

_DEFAULT_DOCS_DIR = Path(__file__).parent.parent / "documents"


def extract_text(pdf_path: Path) -> str:
    if pdf_path.suffix.lower() in (".txt", ".csv"):
        return pdf_path.read_text(encoding="utf-8", errors="ignore")
    try:
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    except Exception:
        return ""


def all_pdfs(data_dir: Path | None = None) -> list[Path]:
    docs_dir = (data_dir or _DEFAULT_DOCS_DIR.parent) / "documents"
    # принимаем PDF и любые текстовые форматы (иногда .txt в датасете)
    return sorted(docs_dir.glob("*.pdf")) + sorted(docs_dir.glob("*.txt"))


def extract_account_id(text: str) -> str | None:
    """Ищет ACC-XXXX в тексте документа."""
    import re
    m = re.search(r"ACC-\d+", text)
    return m.group(0) if m else None
