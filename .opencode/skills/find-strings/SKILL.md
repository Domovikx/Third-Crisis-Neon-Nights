---
name: find-strings
description: Извлечение английских строк из бинарных файлов Unity (level сцены, shared assets) для поиска и анализа текста для перевода
license: MIT
compatibility: opencode
---

## Описание

Сканирует бинарные файлы Unity (level0-level15, sharedassets) и извлекает английские строки.
Полезно для обнаружения текста, который ещё не был переведён.

## Когда использовать

- Когда нужно найти новый непереведённый текст в свежем обновлении игры
- Для поиска текста, пропущенного при первичном извлечении
- Для составления полного словаря игры

## Скрипт

```bash
node .opencode/skills/find-strings/find.mjs
node .opencode/skills/find-strings/find.mjs --min 30   # строки от 30 символов
node .opencode/skills/find-strings/find.mjs --dir путь  # другая директория
```

## Результат

Сохраняет найденные строки в `.opencode/skills/find-strings/extracted.txt`
