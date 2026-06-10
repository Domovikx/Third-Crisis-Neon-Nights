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
# Dialogues (path_id=73203): text, translation, speaker, rich_text, rich_translation

- text: "Yesss...!~"
  translation: "Да-а...!~"
  speaker: "Zoey"
  rich_text: "<color=#B867FF><font=\"Roboto-Condensed_DialogueUI\" material=\"Roboto-Condensed_DialogueUI_Perversion\">Yesss...!~</font></color>"
  rich_translation: "<color=#B867FF><font=\"Roboto-Condensed_DialogueUI\" material=\"Roboto-Condensed_DialogueUI_Perversion\">Да-а...!~</font></color>"

- text: "Fhaaa..!!"
  translation: ""
  speaker: "Zoey"
  rich_text: "<color=#B867FF><font=\"Roboto-Condensed_DialogueUI\" material=\"Roboto-Condensed_DialogueUI_Perversion\">Fhaaa..!!</font></color>"
  rich_translation: ""
```

### `translations/speakers.yaml`
```yaml
# Speakers: text, translation, gender, notes

- text: "Zoey"
  translation: "Зои"
  gender: "female"
```

### `translations/settings_keys.yaml`
```yaml
# Settings keys: text, translation

- text: "Fullscreen"
  translation: "Полный экран"
```

## Источники данных

- **dialogues** — из `"dialogues"` поля MonoBehaviour объектов в чанках (автопоиск, 1085+97 источников)
- **dialogues.bundle_*** — из `raw_strings` с `line_X` маркерами (дубликаты с ANToolkit отфильтрованы экстрактором; по 1 файлу на актив)
- **speakers** — уникальные спикеры из обоих источников (67, без пустых/Narration)
- **settings_keys** — только `settings_keys.display` из summary JSON (55 UI-строк, реальный display-текст из бинарника)

Экстрактор авто-генерирует `rich_translation` из `rich_text` + `translation` при записи.
Bundle-записи, уже присутствующие в dialogue-файлах, отфильтровываются (DRY).

**Named colors resolution:** Экстрактор загружает `color_parser_list` из дампов
(динамически, через `_load_color_parser_list()`) и заменяет `<color=perversion>` →
`<color=#EB83FF>` во всех rich_text/rich_translation. При апдейте игры перезапуск
dump_assets.py + extractor.py автоматически подхватит новые цвета.

Формат YAML: объектный `{text, translation, ...}`. Поля опциональны.  
Рантайм использует fallback: `rich_translation` > `translation` > `rich_text` > `text`.
Неизвестные поля игнорируются рантаймом, но сохраняются через merge при перезапуске экстрактора.

**Форматирование вывода:**
- `text` и `translation` — всегда (обязательные поля)
- `speaker` — только если непустой
- `rich_text` — только если непустой
- `rich_translation` — всегда, если есть `rich_text` (даже пустой, как подсказка переводчику)
- Между записями — пустая строка для читабельности

## REMOVED: parser.py

Удалён. Вместо него — `extractor.py` + `dump_assets.py`.
Старый `parser.py` сканировал бинарники напрямую с шумными эвристиками,
генерировал мусорные all-caps строки и непредсказуемые display-имена.

## Тесты

```bash
python .opencode/skills/extract-text/extractor.test.py
```

15 тестов: диалоги, спикеры, UI, YAML, пустой дамп, спецсимволы, дедупликация, read_yaml, merge, idempotent, real_dump.
