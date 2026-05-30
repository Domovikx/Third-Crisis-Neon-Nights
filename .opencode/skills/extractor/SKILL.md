---
name: extractor
description: Классификация и фильтрация строк из NDJSON-вывода парсера. Отделяет диалоги от UI и шума.
---

# extractor — Dialogue & UI extractor

## Описание

Принимает NDJSON от `parser.mjs`, классифицирует строки (dialogue / UI / noise),
разбивает по source-файлам, выдаёт NDJSON для перевода.

## Использование

```bash
node .opencode/skills/extractor/extractor.mjs
node .opencode/skills/extractor/extractor.mjs --detailed
node .opencode/skills/extractor/extractor.mjs --show-noise
```

## Опции

| Флаг | По умолчанию | Описание |
|------|-------------|----------|
| `--input-dir <dir>` | `output/parser/` | Директория с NDJSON от парсера |
| `--out <dir>` | `output/extractor/` | Выходная директория |
| `--min-len <N>` | `10` | Минимальная длина строки |
| `--detailed` | — | Показать per-file breakdown + samples |
| `--show-noise` | — | Включить noise (FSM-состояния, имена) в вывод |

## Выходные файлы

```
output/extractor/
  dialogs/
    level3.ndjson
    level7.ndjson
    sharedassets0.ndjson
    ...
  ui/
    sharedassets0.ndjson
    ...
```

### Формат NDJSON

Каждая строка — JSON-массив:
```json
["{source}_{seq}","{original}","{translated}","{offset}"]
```

Где:
- `source_seq` — уникальный ID (level3_001, sharedassets0_042)
- `original` — оригинальная строка
- `translated` — пустая строка (заполняет LLM)
- `offset` — байтовый адрес в бинарнике (для восстановления)

### Пример

```json
["level3_001","And now hold still I'm not done yet.","","641239"]
["level3_002","(I hope she's okay.)","","642001"]
```

После перевода LLM заполняет третий элемент:

```json
["level3_001","And now hold still I'm not done yet.","А теперь замри, я ещё не закончила.","641239"]
```

## Методология

- `isDialogue()`: минимум 12 символов, 3+ слова, common English words, без noise-слов
- `isUI()`: ALL CAPS, длина 2-60
- Остальное → noise (PlayMaker FSM-состояния, имена объектов, метаданные)
