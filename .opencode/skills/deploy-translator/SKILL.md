---
name: deploy-translator
description: Деплой NeonTranslatorRuntime — сборка DLL, прокси, копирование словаря в Managed/
license: MIT
compatibility: opencode
---

# deploy-translator — Деплой переводчика в игру

## Описание

Деплой рантайм-переводчика в игру. Включает:

1. Компиляцию C# → DLL (через `build-translator/build.py`)
2. Компиляцию нативного прокси dwmapi.dll (только при первом запуске или изменении C-кода)
3. Копирование DLL + YAML словарей в `Managed/`

## Команды

### Полный деплой (всё сразу)

```bash
python .opencode/skills/build-translator/build.py
cp runtime/NeonTranslatorRuntime.dll "Third Crisis Neon Nights_Data/Managed/"
cp translations/*.yaml "Third Crisis Neon Nights_Data/Managed/"
cp fonts/RobotoCondensed-Regular.ttf "Third Crisis Neon Nights_Data/Managed/"
```

### Прокси (dwmapi.dll) — только при первом запуске или изменении прокси

```bash
python .opencode/skills/build-translator/build_proxy.py
```

### Обновление словаря

Словарь редактируется напрямую — все `*.yaml` из `translations/` читаются рекурсивно
рантаймом через `TranslationLoader.Load()`.

```bash
cp translations/*.yaml "Third Crisis Neon Nights_Data/Managed/"
```

### Проверка после деплоя

```bash
ls -la "Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll"
cat "Third Crisis Neon Nights_Data/Managed/NeonTranslator.log"
```

## Формат

```
translations/
  dialogues.73203.yaml  — диалоги (1503, text, translation, speaker, rich_text, rich_translation)
  dialogues.73262.yaml  — диалоги (93)
  dialogues.73263.yaml  — диалоги (97)
  dialogues.73264.yaml  — диалоги (100)
  dialogues.bundle_*.yaml — диалоги (952, дубликаты отфильтрованы, по активу)
  speakers.yaml         — персонажи (52, text, translation, gender, notes)
  settings_keys.yaml    — UI строки (55, text, translation)
```

## Файлы

| Файл                                                              | Назначение                             |
| ----------------------------------------------------------------- | -------------------------------------- |
| `runtime/NeonTranslatorRuntime.dll`                               | Скомпилированная DLL (build.py)        |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll` | Установленная DLL                      |
| `translations/dialogues.{path_id}.yaml`                           | Диалоги (источник, 4 файла)            |
| `translations/settings_keys.yaml`                                 | UI-текст (источник)                    |
| `translations/speakers.yaml`                                      | Имена персонажей (источник)            |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslator.log`        | Лог рантайма                           |
| `dwmapi.dll`                                                      | Native proxy (корень игры)             |
| `dwmapi_real.dll`                                                 | Форвардер (копия системной dwmapi.dll) |

## После деплоя

- Перезапустить игру
- Проверить лог: `NeonTranslator.log`
- Лог создаётся в `Third Crisis Neon Nights_Data/Managed/`

## Очистка старых NDJSON

Рантайм больше не читает `*.ndjson`. Удали старые файлы из `Managed/`:

```bash
rm "Third Crisis Neon Nights_Data/Managed/"*.ndjson
```
