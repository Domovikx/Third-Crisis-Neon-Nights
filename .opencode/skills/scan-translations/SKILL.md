---
name: scan-translations
description: Сканирует translations/, выводит сводку и пишет report.yaml
  с датой последнего сканирования. По каждому файлу — done или
  количество непереведённых строк. Фильтр по --files, JSON через --json.
---

# scan-translations

Сканирую YAML-переводы Third Crisis Neon Nights, пишу отчёт и вывожу сводку.

## Формат вызова

```bash
python .opencode/skills/scan-translations/scan_translations.py [--json] [--files file1.yaml file2.yaml ...]
```

- Без флагов — пишет `report.yaml` + сводка в консоль.
- `--json` — в дополнение печатает детальный JSON.
- `--files a.yaml b.yaml` — сканировать только указанные файлы (относительно `translations/dialogues/`).

## Формат report.yaml

```yaml
last_scan: 2026-06-18 14:30:00

dialogues/73203.yaml: 24
dialogues/4839.yaml: 2
settings_keys.yaml: 27167
speakers.yaml: 10
```

- `last_scan` — дата запуска.
- Только файлы с непереведёнными строками.
- `<число>` — сколько строк не переведено.
