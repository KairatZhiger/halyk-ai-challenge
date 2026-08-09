# halyk-ai-challenge

AI-агент для проверки финансовых ковенантов по кредитным договорам (Halyk AI Challenge).

## Требования

- Python 3.11+
- OpenAI API key

## Установка

```bash
# 1. Клонируй репозиторий
git clone https://github.com/KairatZhiger/halyk-ai-challenge.git
cd halyk-ai-challenge

# 2. Создай виртуальное окружение
python -m venv venv
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows

# 3. Установи зависимости
pip install -r requirements.txt

# 4. Создай .env файл с API ключом
cp .env.example .env
# Открой .env и вставь свой OpenAI API key
```

## Структура данных

Ожидаемая структура папки с данными:

```
data_dir/
├── documents/          # PDF и TXT документы (кредитные договора, аудиты, KYC)
├── master_ledger_*.csv # Транзакционный леджер
├── submission_template.json
└── .env                # (опционально, если не в корне проекта)
```

## Запуск

### На публичных тренировочных данных (папка по умолчанию)

```bash
python -m agent.pipeline
```

### На отдельной папке с данными

```bash
python -m agent.pipeline path/to/data_dir
```

Результат сохраняется в `data_dir/submission.json`.

## Переменные окружения

| Переменная       | Описание                       |
|------------------|--------------------------------|
| `OPENAI_API_KEY` | Ключ OpenAI API (обязательно)  |
