---
name: extract-text
description: Извлечение диалогов, UI-текста и имён персонажей из Unity serialized файлов игры (resources.assets, level, .bundle) через parser.py
---

# extract-text — Извлечение текста из Unity

## Описание

**`extractor.py`** — читает JSON-дампы из `dump_assets/` и собирает 3 YAML-файла.
Никакого парсинга бинарников — работает через данные, уже извлечённые `dump_assets.py`.

```bash
# 1. Свежий дамп ассетов
python .opencode/skills/dump-assets/dump_assets.py

# 2. Извлечение переводов
python .opencode/skills/extract-text/extractor.py
```

## Выходные файлы

### `translations/dialogues.yaml`
```yaml
# Dialogues: [text, speaker]

- {text: "Hello there!", speaker: "Zoey"}
- {text: "Hi Zoey!", speaker: "Sarah"}
```

### `translations/speakers.yaml`
```yaml
# Speakers: [name, gender]

- {name: "Zoey", gender: ""}
- {name: "Sarah", gender: ""}
```

### `translations/global_strings.yaml`
```yaml
# Global strings (UI): [key]

- {key: "Fullscreen"}
- {key: "Music Volume"}
```

## Источники данных

- **dialogues** — из `"dialogues"` поля MonoBehaviour объектов в чанках (автопоиск, 1544 записи)
- **speakers** — уникальные спикеры из dialogues (23, без пустых/Narration)
- **global_strings** — только `settings_keys.display` из summary JSON (55 UI-строк, реальный display-текст из бинарника)

Формат YAML позволяет писать комментарии `#` прямо в файлах переводов.

## DEPRECATED: parser.py

Старый `parser.py` — не использовать. Он сканировал бинарники напрямую с шумными эвристиками,
генерировал мусорные all-caps строки и непредсказуемые display-имена.
Вместо него — `extractor.py` + `dump_assets.py`.

## Тесты

```bash
python .opencode/skills/extract-text/extractor.test.py
```

9 тестов: диалоги, спикеры, UI, YAML, пустой дамп, спецсимволы, дедупликация.
