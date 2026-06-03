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
3. Копирование DLL + NDJSON словарей в `Managed/`

## Команды

### Полный деплой (всё сразу)

```bash
python .opencode/skills/build-translator/build.py
cp runtime/NeonTranslatorRuntime.dll "Third Crisis Neon Nights_Data/Managed/"
```

### Прокси (dwmapi.dll) — только при первом запуске или изменении прокси

```bash
python .opencode/skills/build-translator/build_proxy.py
```

### Обновление словаря

Словарь редактируется напрямую — все `*.ndjson` из `translations/` читаются рекурсивно
рантаймом через `TranslationLoader.Load()`.

### Проверка после деплоя

```bash
ls -la "Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll"
cat "Third Crisis Neon Nights_Data/Managed/NeonTranslator.log"
```

## Формат

```
translations/
  dialogs/
    dialogue.ndjson  — ["eng", "rus", "speaker"]  (1544 диалога)
  texts/
    ui.ndjson        — ["eng", "rus"]             (102 UI строки)
```

## Файлы

| Файл                                                              | Назначение                             |
| ----------------------------------------------------------------- | -------------------------------------- |
| `runtime/NeonTranslatorRuntime.dll`                               | Скомпилированная DLL (build.py)        |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll` | Установленная DLL                      |
| `translations/dialogs/dialogue.ndjson`                            | Диалоги (источник)                     |
| `translations/texts/ui.ndjson`                                    | UI-текст (источник)                    |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslator.log`        | Лог рантайма                           |
| `dwmapi.dll`                                                      | Native proxy (корень игры)             |
| `dwmapi_real.dll`                                                 | Форвардер (копия системной dwmapi.dll) |

## После деплоя

- Перезапустить игру
- Проверить лог: `NeonTranslator.log`
- Лог создаётся в `Third Crisis Neon Nights_Data/Managed/`
