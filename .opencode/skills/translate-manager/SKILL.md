---
name: translate-manager
description: Пакетный перевод Third Crisis Neon Nights — группировка файлов в batch'и, запуск translate-game на каждый batch.
---

# translate-manager — Пакетный перевод диалогов

## Назначение

Найти файлы с непереведёнными строками, сгруппировать в batch'и для параллельного перевода, передать в translate-game.

## Формат batch.yaml

```yaml
created: 2026-06-19 17:25:38
params:
  max_lines: 250
total_files: 1050
total_untranslated: 0

batches:
  - id: 1
    untranslated: 687
    file_count: 1
    files:
      - translations/dialogues/73203.yaml: 687
  - id: 2
    untranslated: 45
    file_count: 1
    files:
      - translations/dialogues/4839.yaml: 45
```

- `total_files` — всего файлов
- `total_untranslated` — сумма непереведённых строк
- `batches` — группы файлов для task(general)
- batch'и отсортированы по urgency (самые проблемные первыми)
- файлы с `untranslated: 0` НЕ попадают в batches

## Workflow

### 1. Сканирование

```bash
python .opencode/skills/scan-translations/scan_translations.py
```

`report.yaml` — сводка: всего файлов, переведено, непереведено.

### 2. Группировка

```bash
python .opencode/skills/translate-manager/group_files.py [--max-lines 250]
```

- `group_files.py` сканирует все YAML файлы
- файлы с непереведёнными строками попадают в batch'и
- большие файлы (>= max_lines) — в отдельный batch
- маленькие — группами
- результат: `batch.yaml`

### 3. Перевод batch'ей

На каждый batch из `batch.yaml` запустить `task(general)`:

```
Загрузи скил translate-game и переведи файлы:
translations/dialogues/73203.yaml
translations/dialogues/4839.yaml

Переводи последовательно. После каждого файла проверь качество.
```

task(general) читает `batch.yaml` — берёт файлы из нужного batch.

### 4. Результат

После перевода всех batch'ей — повторить цикл:
1. scan_translations → обновить сводку
2. group_files → пересобрать batch'и (могут появиться новые непереведённые)

## Команды

```bash
# Сканировать что нужно перевести
python .opencode/skills/scan-translations/scan_translations.py

# Сгруппировать в batch'и
python .opencode/skills/translate-manager/group_files.py --max-lines 250

# JSON вывод (для автоматизации)
python .opencode/skills/translate-manager/group_files.py --json
```

## Как работает определение "непереведённого"

Строка считается непереведённой если:
- `translation` пуст ИЛИ
- `rich_text` присутствует, но `rich_translation` пуст

Поля `speaker`, `gender`, `notes` — не учитываются.

## Ограничения

- batch.yaml перезаписывается при каждом запуске group_files.py
- translate-game получает список файлов, не batch.yaml напрямую
- параллельно запускаются только batch'и, файлы в одном batch — последовательно
