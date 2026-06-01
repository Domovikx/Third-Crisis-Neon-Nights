---
name: translate-batch
description: Пакетный перевод непереведённых строк с английского на русский через Google Translate API
license: MIT
compatibility: opencode
---

## Описание
Пакетный перевод непереведённых строк из `translations/ru/` (все `*.ndjson` в подпапках).
Ищет записи с пустым переводом, переводит через Google Translate API, сохраняет прямо в NDJSON.

## Когда использовать
- Когда нужно быстро перевести большой объём непереведённых строк
- После добавления новых строк через `extractor.mjs --merge translations/ru/`
- Или вручную — добавил строки в NDJSON, запустил batch

## Скрипт
```bash
node .opencode/skills/translate-batch/batch.mjs              # перевести всё непереведённое
node .opencode/skills/translate-batch/batch.mjs --dry-run     # тестовый прогон (без записи)
```

## Что делает
1. Рекурсивно обходит `translations/ru/` — ищет все `*.ndjson`
2. Собирает все записи с пустым переводом (третье поле)
3. Переводит пачками по 25 строк с паузой 1с
4. Сохраняет перевод обратно в те же NDJSON-файлы (idempotent)

## Важно
- Переводит пачками по 25 строк с паузой 1с между пакетами
- Использует бесплатный Google Translate (без API ключа)
- Уже переведённые строки не трогает
