---
name: extract-text
description: Извлечение диалогов, UI-текста и имён персонажей из Unity serialized файлов игры (resources.assets, level, .bundle) через extractor.py
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

### `translations/dialogues.{path_id}.yaml`
```yaml
# Dialogues (path_id=73203): [text, translation, speaker]

- ["Yesss...!~", "", "Zoey"]
- ["Fhaaa..!!", "", "Zoey"]
```

### `translations/speakers.yaml`
```yaml
# Speakers: [name, translation, gender]

- ["Zoey", "Зои", "female"]
```

### `translations/settings_keys.yaml`
```yaml
# Settings keys: [key, translation]

- ["Fullscreen", "Полный экран"]
```

## Источники данных

- **dialogues** — из `"dialogues"` поля MonoBehaviour объектов в чанках (автопоиск, 1793 записи в 4 источниках)
- **speakers** — уникальные спикеры из dialogues (23, без пустых/Narration)
- **settings_keys** — только `settings_keys.display` из summary JSON (55 UI-строк, реальный display-текст из бинарника)

Формат YAML позволяет писать комментарии `#` прямо в файлах переводов.

## REMOVED: parser.py

Удалён. Вместо него — `extractor.py` + `dump_assets.py`.
Старый `parser.py` сканировал бинарники напрямую с шумными эвристиками,
генерировал мусорные all-caps строки и непредсказуемые display-имена.

## Тесты

```bash
python .opencode/skills/extract-text/extractor.test.py
```

14 тестов: диалоги, спикеры, UI, YAML, пустой дамп, спецсимволы, дедупликация, read_yaml, merge, idempotent, real_dump.
