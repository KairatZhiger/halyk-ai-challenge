"""Вычисляет actual и status для каждого ковенанта по данным леджера."""
import pandas as pd
from openai import OpenAI
import json
import re


def _filter_period(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    return df[(df["date"] >= start) & (df["date"] <= end)]


def _keyword_filter(df: pd.DataFrame, hint: str) -> pd.DataFrame:
    """Фильтрует строки, где description содержит хотя бы одно ключевое слово."""
    if not hint:
        return df
    keywords = [k.strip().lower() for k in hint.split(",") if k.strip()]
    if not keywords:
        return df
    mask = df["description"].str.lower().apply(
        lambda d: any(k in d for k in keywords)
    )
    return df[mask]


def evaluate_covenant_with_llm(
    covenant: dict,
    txns: pd.DataFrame,
    client: OpenAI,
    model: str = "gpt-4o",
    context_docs: list[str] | None = None,
) -> dict:
    """
    Использует LLM для вычисления actual.
    context_docs — тексты других документов заёмщика (аудит, KYC и т.д.).
    """
    period_txns = _filter_period(txns, covenant["period_start"], covenant["period_end"])
    csv_sample = period_txns.to_csv(index=False)

    # собираем контекст из других документов (первые 3000 символов каждого)
    doc_context = ""
    if context_docs:
        snippets = [d[:3000] for d in context_docs if d.strip()]
        doc_context = "\n\n---\n".join(snippets[:4])  # максимум 4 документа

    system = """You are a financial compliance analyst. Compute the covenant value precisely.

STEP 1 — Extract from supporting documents:
a) RECLASSIFICATIONS: Auditors may state that a transaction "belongs to" or "relates to" a different period.
   Any transaction reclassified OUT of the covenant period must be EXCLUDED from all calculations.
   Example: "TXN-XXX-0045 (invoice dated 2025-08-12) relates to services rendered in 2026" → exclude TXN-XXX-0045.
b) RELATED PARTIES: From KYC documents, list counterparty names that meet the ownership threshold (usually ≥20%).
   Only these names are "related parties" for section 6.3 type covenants.
c) REVENUE / CAPEX / OPEX categories: Use any audit classification notes to identify which transactions belong to each category.

STEP 2 — Filter the transaction CSV:
- Apply reclassifications: remove any transaction moved to a different period by the auditor.
- Keep only transactions within the covenant period_start to period_end dates.

STEP 3 — Compute the value:
- ratio: numerator_sum / denominator_sum. BREACH if direction="max" and ratio > limit.
- sum/max: abs(negative amounts) for expense totals. BREACH if total > limit.
- sum/min: positive amounts only for revenue totals. BREACH if total < limit.
- single_txn: find the one transaction exceeding the limit. evidence_txn_id = that txn_id.

STEP 4 — Output ONLY this JSON (no markdown):
{"actual": <positive number, 2 decimal places>, "status": "COMPLIANT"|"BREACH", "evidence_txn_id": <string|null>}"""

    user_parts = [f"Covenant:\n{json.dumps(covenant, ensure_ascii=False, indent=2)}"]
    if doc_context:
        user_parts.append(f"Supporting documents (audit reports, KYC, etc.):\n{doc_context}")
    user_parts.append(f"Transactions CSV:\n{csv_sample[:8000]}")

    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    result = json.loads(raw)
    result["actual"] = round(float(result["actual"]), 2)
    return result
