---
name: neon-translator-deploy
description: Деплой NeonTranslatorRuntime — сборка DLL, прокси, обновление словаря
license: MIT
compatibility: opencode
---

## Описание

Деплой рантайм-переводчика в игру. Включает:

1. Компиляцию C# → DLL
2. Компиляцию нативного прокси dwmapi.dll
3. Копирование DLL в Managed/
4. Обновление словаря перевода

## Команды

### Полный деплой (всё сразу)

```bash
node .opencode/skills/neon-translator-runtime/build.mjs
cp runtime/NeonTranslatorRuntime.dll "Third Crisis Neon Nights_Data/Managed/"
```

### Прокси (dwmapi.dll) — только при первом запуске или изменении прокси

```bash
node .opencode/skills/neon-translator-runtime/build_proxy.mjs
```

### Обновление словаря

Словарь редактируется напрямую:

```
Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime_Data.ndjson
```

После изменений **не нужна** пересборка DLL — словарь читается при старте игры.

### Проверка после деплоя

```bash
ls -la "Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll"
cat "Third Crisis Neon Nights_Data/Managed/NeonTranslator.log"
```

## Файлы

| Файл                                                                      | Назначение                               |
| ------------------------------------------------------------------------- | ---------------------------------------- |
| `runtime/NeonTranslatorRuntime.dll`                                       | Скомпилированная DLL (build.mjs)         |
| `runtime/NeonTranslatorRuntime_Data.ndjson`                               | Копия словаря (редактируется в Managed/) |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll`         | Установленная DLL                        |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime_Data.ndjson` | Словарь (141+ записей)                   |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslator.log`                | Лог рантайма                             |
| `dwmapi.dll`                                                              | Native proxy (корень игры)               |
| `dwmapi_real.dll`                                                         | Форвардер (копия системной dwmapi.dll)   |

## После деплоя

- Перезапустить игру
- Проверить лог: `NeonTranslator.log`
- Лог создаётся в `Third Crisis Neon Nights_Data/Managed/`
