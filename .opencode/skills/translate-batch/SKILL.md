---
name: translate-batch
description: Пакетный перевод непереведённых строк с английского на русский через Google Translate API
license: MIT
compatibility: opencode
---

## Описание
Пакетный перевод непереведённых строк из `translations/NeonTranslatorRuntime_Data.json`.
Ищет записи с пустым переводом, переводит через Google Translate API, сохраняет прямо в JSON.

## Когда использовать
- Когда нужно быстро перевести большой объём непереведённых строк
- После добавления новых строк вручную в JSON

## Скрипт
```bash
node .opencode/skills/translate-batch/batch.mjs              # перевести всё непереведённое
node .opencode/skills/translate-batch/batch.mjs --dry-run     # тестовый прогон (без записи)
```

## Что делает
1. Читает `translations/NeonTranslatorRuntime_Data.json`
2. Собирает все записи с пустым переводом (значение)
3. Переводит пачками по 25 строк с паузой 1с
4. Сохраняет перевод обратно (idempotent)

## Важно
- Переводит пачками по 25 строк с паузой 1с между пакетами
- Использует бесплатный Google Translate (без API ключа)
- Уже переведённые строки не трогает
