---
name: neon-translator-deploy
description: Деплой NeonTranslatorRuntime — сборка DLL, прокси, обновление словаря
license: MIT
compatibility: opencode
---

## Описание

Деплой рантайм-переводчика в игру. Включает:

1. Компиляцию C# → DLL
2. Компиляцию нативного прокси dwmapi.dll (только при первом запуске или изменении C-кода)
3. Копирование DLL в Managed/

## Команды

### Полный деплой (всё сразу)

```bash
python .opencode/skills/neon-translator-runtime/build.py
cp runtime/NeonTranslatorRuntime.dll "Third Crisis Neon Nights_Data/Managed/"
```

### Прокси (dwmapi.dll) — только при первом запуске или изменении прокси

```bash
python .opencode/skills/neon-translator-runtime/build_proxy.py
```

### Обновление словаря

Словарь редактируется напрямую — все `*.json` и `*.ndjson` из `translations/` читаются рекурсивно.

### Проверка после деплоя

```bash
ls -la "Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll"
cat "Third Crisis Neon Nights_Data/Managed/NeonTranslator.log"
```

## Формат

```
translations/
  dialogs/
    dialogue.ndjson  — ["speaker", "eng", "rus"]
  texts/
    ui.ndjson        — ["eng", "rus"]
```

## Файлы

| Файл                                                              | Назначение                             |
| ----------------------------------------------------------------- | -------------------------------------- |
| `runtime/NeonTranslatorRuntime.dll`                               | Скомпилированная DLL (build.py)        |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll` | Установленная DLL                      |
| `translations/dialogs/dialogue.ndjson`                            | Диалоги (источник)                     |
| `translations/texts/ui.ndjson`                                    | UI-текст (источник)                    |
| `translations/texts/settings.ndjson`                              | Настройки (источник)                   |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslator.log`        | Лог рантайма                           |
| `dwmapi.dll`                                                      | Native proxy (корень игры)             |
| `dwmapi_real.dll`                                                 | Форвардер (копия системной dwmapi.dll) |

## После деплоя

- Перезапустить игру
- Проверить лог: `NeonTranslator.log`
- Лог создаётся в `Third Crisis Neon Nights_Data/Managed/`
