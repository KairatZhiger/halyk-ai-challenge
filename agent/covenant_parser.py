"""Находит кредитный договор среди PDF заёмщика и извлекает ковенанты через LLM."""
import re
import json
from pathlib import Path
from openai import OpenAI

_CREDIT_KEYWORDS = [
    "loan agreement", "credit agreement", "кредитный договор",
    "заёмщик обязуется", "borrower shall",
]


def find_credit_agreement(
    pdf_texts: dict[str, str],
    ledger_year: int | None = None,
) -> tuple[str, str] | None:
    """
    Из словаря {filename: full_text} возвращает (filename, text) кредитного договора.
    Если ledger_year задан — предпочитает договор с совпадающим годом периода.
    """
    candidates = []
    for name, text in pdf_texts.items():
        has_section6 = bool(re.search(r"\b6\.[123]\b", text))
        has_credit = any(kw in text.lower() for kw in _CREDIT_KEYWORDS)
        if has_section6 and has_credit:
            # извлекаем год периода из section 6
            year_match = re.search(r"за период с (\d{4})-\d{2}-\d{2}", text)
            period_year = int(year_match.group(1)) if year_match else 0
            year_score = 1 if (ledger_year and period_year == ledger_year) else 0
            candidates.append((name, text, year_score, len(text)))
    if not candidates:
        return None
    # сначала по совпадению года, потом по длине
    candidates.sort(key=lambda x: (x[2], x[3]), reverse=True)
    return candidates[0][0], candidates[0][1]


def extract_section6(text: str) -> str:
    """Вырезает раздел 6 из текста договора (от 6.1 до следующего раздела)."""
    # ищем от 6.1 до Статья/Раздел/Section/Article 7 (или конца)
    m = re.search(
        r"(6\.1.+?)(?=(?:Статья|Раздел|Section|Article)\s+[7-9]|\Z)",
        text, re.DOTALL | re.IGNORECASE,
    )
    if m:
        return m.group(0)[:6000]
    # fallback: от заголовка раздела 6
    m2 = re.search(r"(?:Статья|Раздел|Section|Article)\s+6\b.+", text, re.DOTALL | re.IGNORECASE)
    return m2.group(0)[:6000] if m2 else text[:6000]


def parse_covenants(section6_text: str, client: OpenAI, model: str = "gpt-4o") -> list[dict]:
    """
    Отправляет раздел 6 в LLM, получает список ковенантов в виде JSON.

    Возвращает список:
    [
      {
        "clause": "6.1",
        "type": "ratio" | "sum" | "single_txn",
        "description": "...",
        "limit": 1.17,
        "direction": "max" | "min",
        "period_start": "2024-01-01",
        "period_end": "2024-12-31",
        "filter_hint": "description keywords to identify transactions",
        "numerator_hint": "...",   // для ratio
        "denominator_hint": "..."  // для ratio
      },
      ...
    ]
    """
    system = """You are a financial analyst. Extract all financial covenants from section 6 of a loan agreement.
Return a JSON array. Each element must have:
- clause: string like "6.1", "6.2", "6.3"
- type: "ratio" (coefficient test), "sum" (aggregate monetary limit), or "single_txn" (limit per transaction)
- description: short English description
- limit: numeric threshold (positive number)
- direction: "max" (must not exceed) or "min" (must not fall below)
- period_start: ISO date string
- period_end: ISO date string
- filter_hint: comma-separated keywords from transaction descriptions to match relevant transactions
- numerator_hint: for ratio type, what to sum for numerator (empty string if not ratio)
- denominator_hint: for ratio type, what to sum for denominator (empty string if not ratio)

Return ONLY valid JSON array, no markdown fences."""

    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": section6_text},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    # убираем markdown если LLM всё же добавил
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)
