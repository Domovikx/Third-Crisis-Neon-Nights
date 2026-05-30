---
name: parse-unity
description: Парсинг бинарных Unity serialized файлов (level, sharedassets) — чтение заголовка, ObjectTable, извлечение length-prefixed строк для перевода
license: MIT
compatibility: opencode
---

## Описание

Структурный парсер Unity serialized format (версия 22, Unity 2022+).
Читает заголовок, метаданные, ObjectTable и извлекает строки для перевода
из data-блоков MonoBehaviour, PlayMakerFSM, TextMeshPro.

В отличие от `find-strings` и `extract`:
- Парсит заголовок файла (header + metadata)
- Извлекает строки только из data-секции (без шума метаданных)
- Читает length-prefixed строки (основной формат Unity), а не только null-terminated
- Группирует результат: dialogue / ui / unknown
- Собирает статистику по объектам

## Когда использовать

- Первичное извлечение всех строк игры для перевода
- После обновления игры — найти новый текст
- Для точного извлечения (минимум шума)

## Скрипт

```bash
node .opencode/skills/parse-unity/parse.mjs
node .opencode/skills/parse-unity/parse.mjs --level 3       # только level3
node .opencode/skills/parse-unity/parse.mjs --min 20        # строки от 20 символов
node .opencode/skills/parse-unity/parse.mjs --detailed      # подробный вывод
node .opencode/skills/parse-unity/parse.mjs --json          # вывод в JSON
```

## Результат

Файлы в `output/raw/`:
| Файл | Описание |
|------|----------|
| `parsed-dialogue.txt` | Диалоговые строки |
| `parsed-ui.txt` | UI-элементы |
| `parsed-all.txt` | Все найденные строки |

## Тесты

```bash
node .opencode/skills/parse-unity/test.mjs
```
