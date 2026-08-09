"""Главный оркестратор: обходит всех заёмщиков, заполняет submission.json."""
import json
import sys
from pathlib import Path
from openai import OpenAI

from agent.ledger import load_ledger, get_account_map, transactions_for
from agent.pdf_reader import all_pdfs, extract_text, extract_account_id
from agent.covenant_parser import find_credit_agreement, extract_section6, parse_covenants
from agent.evaluator import evaluate_covenant_with_llm

_DEFAULT_BASE = Path(__file__).parent.parent


def build_pdf_index(account_map: dict[str, str], data_dir: Path) -> dict[str, dict[str, str]]:
    """Возвращает {scenario_key: {pdf_name: full_text}}."""
    index: dict[str, dict[str, str]] = {}
    for pdf in all_pdfs(data_dir):
        text = extract_text(pdf)
        acc_id = extract_account_id(text)
        if acc_id and acc_id in account_map:
            key = account_map[acc_id]
            index.setdefault(key, {})[pdf.name] = text
    return index


def run(
    openai_api_key: str,
    model: str = "gpt-5.6-sol",
    team: str = "",
    email: str = "",
    scenarios: list[str] | None = None,
    data_dir: Path | None = None,
) -> dict:
    base = data_dir or _DEFAULT_BASE
    client = OpenAI(api_key=openai_api_key)

    df = load_ledger(base)
    account_map = get_account_map(df)
    ledger_year = int(df["date"].dt.year.mode()[0])
    with open(base / "submission_template.json") as f:
        submission = json.load(f)

    submission["team"] = team
    submission["contact_email"] = email
    submission["model"] = model

    print("Индексируем PDF документы...")
    pdf_index = build_pdf_index(account_map, base)

    target_scenarios = scenarios or list(submission["answers"].keys())

    for scenario_key in target_scenarios:
        print(f"\n{'='*50}")
        print(f"Обрабатываем сценарий: {scenario_key}")

        pdf_texts = pdf_index.get(scenario_key, {})
        if not pdf_texts:
            print(f"  ⚠ PDF не найдены для {scenario_key}")
            continue

        # находим кредитный договор
        result = find_credit_agreement(pdf_texts, ledger_year=ledger_year)
        if not result:
            print(f"  ⚠ Кредитный договор не найден для {scenario_key}")
            continue
        contract_name, contract_text = result
        print(f"  Договор: {contract_name}")

        # извлекаем и парсим ковенанты
        section6 = extract_section6(contract_text)
        try:
            covenants = parse_covenants(section6, client, model)
        except Exception as e:
            print(f"  ⚠ Ошибка парсинга ковенантов: {e}")
            continue
        print(f"  Ковенантов найдено: {len(covenants)}")
        if not covenants:
            print(f"  ⚠ LLM вернул пустой список. Начало section6:\n{section6[:500]}")
            continue

        # транзакции заёмщика
        acc_ids = [acc for acc, sc in account_map.items() if sc == scenario_key]
        if not acc_ids:
            print(f"  ⚠ account_id не найден для {scenario_key}")
            continue
        account_id = acc_ids[0]
        txns = transactions_for(df, account_id)
        print(f"  account_id: {account_id}, транзакций: {len(txns)}")

        # тексты остальных документов (аудит, KYC и т.д.) для контекста
        context_docs = [t for n, t in pdf_texts.items() if n != contract_name]

        for covenant in covenants:
            clause = covenant.get("clause", "")
            if clause not in submission["answers"].get(scenario_key, {}):
                print(f"  Пропускаем {clause} — нет в шаблоне")
                continue
            print(f"  Вычисляем {clause}: {covenant.get('description','')[:60]}")
            try:
                answer = evaluate_covenant_with_llm(covenant, txns, client, model, context_docs=context_docs)
                submission["answers"][scenario_key][clause] = answer
                print(f"    → {answer['status']} | actual={answer['actual']} | txn={answer['evidence_txn_id']}")
            except Exception as e:
                print(f"    ⚠ Ошибка вычисления {clause}: {e}")

    return submission


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    if len(sys.argv) > 1:
        data_dir = Path(sys.argv[1])
        if not data_dir.is_absolute():
            data_dir = Path.cwd() / data_dir
    else:
        data_dir = _DEFAULT_BASE

    load_dotenv(data_dir / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        load_dotenv(_DEFAULT_BASE / ".env")

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("Установите OPENAI_API_KEY в .env файле")
        sys.exit(1)

    result = run(
        openai_api_key=api_key,
        model="gpt-4o",
        team="hilarious",
        email="sherizatk@gmail.com",
        data_dir=data_dir,
    )

    out_path = data_dir / "submission.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Сохранено в {out_path}")
