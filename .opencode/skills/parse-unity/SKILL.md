---
name: parse-unity
description: Чистый парсер Unity serialized файлов (level, sharedassets, DLL) — бинарник → NDJSON. Без фильтрации.
---

# parse-unity — Pure binary parser

## Описание

Чистый парсер Unity serialized format (версия 22, Unity 2022+).
Читает заголовок файла и извлекает null-terminated ASCII строки из data-секции.

Выдаёт **только сырые данные** — без классификации, без фильтрации, без NOISE_SET/COMMON_WORDS.
Вся фильтрация: `.opencode/skills/extractor/extractor.mjs`

## Когда использовать

- Первичное извлечение всех строк для анализа
- После обновления игры — получить свежие NDJSON файлы
- Когда нужен полный контроль над парсингом
- Входные данные для extractor-а

## Скрипт

```bash
node .opencode/skills/parse-unity/parser.mjs                       # все файлы
node .opencode/skills/parse-unity/parser.mjs --level 3             # только level3
node .opencode/skills/parse-unity/parser.mjs --file example.dll --type raw
node .opencode/skills/parse-unity/parser.mjs --min-len 8           # строки от 8 символов
node .opencode/skills/parse-unity/parser.mjs --out output/parser/  # явная директория
```

## Результат

```
output/parser/
  manifest.json     — метаданные (headers, stats, timestamp)
  level0.ndjson     — [offset,"raw"]
  level3.ndjson
  sharedassets0.ndjson
  assembly-csharp.ndjson
```

### manifest.json

```json
{
  "parser": "parse-unity v3",
  "totalStrings": 649663,
  "files": [
    { "name": "level0", "type": "unity", "header": {...}, "stats": {"totalStrings": 533} },
    ...
  ]
}
```

### NDJSON format

```
[offset,"raw_string"]
[1131336,"In final Room Location Nova"]
[341810,"CONTINUE"]
```

## Тесты

```bash
node .opencode/skills/parse-unity/test.mjs
```
