---
name: extract-text
description: Извлечение диалогов, UI-текста и имён персонажей из Unity serialized файлов игры (resources.assets, level, .bundle) через parser.py
---

# extract-text — Извлечение текста из Unity

## Описание

`parser.py` — Python-парсер Unity serialized format (версия 22, Unity 2022+).
Читает напрямую сериализованные Unity-объекты. Три режима:

### `--dialogue` — извлечение диалогов

Читает массив `DialogueHistory` из `resources.assets`:
Speaker + Text + color. 1544 записи, 24 спикера.

```bash
python .opencode/skills/extract-text/parser.py --dialogue
```
→ `translations/dialogs/dialogue.ndjson` — `["eng", "", "speaker"]`

### `--texts` — извлечение UI

Читает TMP_Text компоненты, Settings-ключи, названия сцен
из всех level и .bundle файлов. 102 UI строки.

```bash
python .opencode/skills/extract-text/parser.py --texts
```
→ `translations/texts/ui.ndjson` — `["eng", ""]`

### `--characters` — извлечение персонажей

Извлекает уникальные имена спикеров из DialogueHistory.

```bash
python .opencode/skills/extract-text/parser.py --characters
```
→ `translations/characters.ndjson` — `["eng", "", "gender"]`

### Полный скан (без флагов)

Сканирует все файлы игры для исследовательских целей (raw ASCII-поиск):

```bash
python .opencode/skills/extract-text/parser.py ./output/
```

## Формат NDJSON

**Диалоги:**
```ndjson
["I don't know... I murmur, fidgeting.","","Zoey"]
```

**UI:**
```ndjson
["Resolution Scaling",""]
```

**Персонажи:**
```ndjson
["Zoey","","ж"]
```

Пустой `""` → не переведено.

## Тесты

```bash
python .opencode/skills/extract-text/parser.test.py
```

43 теста: заголовок, metadata, stringPool, aligned strings, диалоги, UI, персонажи.
