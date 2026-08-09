"""Загрузка и индексирование леджера транзакций."""
import pandas as pd
from pathlib import Path

_DEFAULT_DIR = Path(__file__).parent.parent


def load_ledger(data_dir: Path | None = None) -> pd.DataFrame:
    base = data_dir or _DEFAULT_DIR
    # ищем первый CSV с "ledger" в имени, иначе берём любой CSV
    candidates = list(base.glob("*ledger*.csv")) or list(base.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"Ledger CSV not found in {base}")
    df = pd.read_csv(candidates[0], parse_dates=["date"])
    df["scenario_key"] = df["txn_id"].str.extract(r"TXN-(\w+)-\d+")
    return df


def get_account_map(df: pd.DataFrame) -> dict[str, str]:
    """Возвращает {account_id: scenario_key}."""
    return df.groupby("account_id")["scenario_key"].first().to_dict()


def transactions_for(df: pd.DataFrame, account_id: str) -> pd.DataFrame:
    return df[df["account_id"] == account_id].copy()
