"""Сопоставление PDF-документов с scenario_id через account_id."""
from pathlib import Path
from agent.ledger import load_ledger, get_account_map
from agent.pdf_reader import all_pdfs, extract_text, extract_account_id


def build_doc_index() -> dict[str, list[Path]]:
    """
    Возвращает {scenario_key: [список PDF этого заёмщика]}.
    Проходит по всем PDF, находит account_id, маппит на scenario_key через леджер.
    """
    df = load_ledger()
    account_map = get_account_map(df)  # {ACC-9001: "9001", ...}

    index: dict[str, list[Path]] = {}
    for pdf in all_pdfs():
        text = extract_text(pdf)
        acc_id = extract_account_id(text)
        if acc_id and acc_id in account_map:
            key = account_map[acc_id]
            index.setdefault(key, []).append(pdf)

    return index


if __name__ == "__main__":
    idx = build_doc_index()
    for scenario, docs in sorted(idx.items()):
        print(f"{scenario}: {len(docs)} документов")
        for d in docs:
            print(f"  {d.name}")
