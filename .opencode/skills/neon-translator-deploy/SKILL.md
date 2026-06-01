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
4. Дедупликацию словаря через merge.mjs

## Команды

### Полный деплой (всё сразу)

```bash
node .opencode/skills/neon-translator-runtime/build.mjs
cp runtime/NeonTranslatorRuntime.dll "Third Crisis Neon Nights_Data/Managed/"
node .opencode/skills/translate-batch/merge.mjs
```

### Прокси (dwmapi.dll) — только при первом запуске или изменении прокси

```bash
node .opencode/skills/neon-translator-runtime/build_proxy.mjs
```

### Обновление словаря

Словарь редактируется напрямую:

```
translations/ru/NeonTranslatorRuntime_Data.json
```

После изменений запустить `merge.mjs` для дедупликации и копирования в Managed/.

### Проверка после деплоя

```bash
ls -la "Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll"
cat "Third Crisis Neon Nights_Data/Managed/NeonTranslator.log"
```

## Формат

```
{"original":"translated"}
{"Fullscreen":"Полноэкранный режим"}
{"Load Game":"Загрузить игру"}
{"Ultra":""}                       ← не переведено
```

## Файлы

| Файл                                                                      | Назначение                             |
| ------------------------------------------------------------------------- | -------------------------------------- |
| `runtime/NeonTranslatorRuntime.dll`                                       | Скомпилированная DLL (build.mjs)       |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime.dll`         | Установленная DLL                      |
| `translations/ru/NeonTranslatorRuntime_Data.json`                        | Словарь (источник, версионируется)     |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime_Data.json`   | Словарь (копия для игры)              |
| `Third Crisis Neon Nights_Data/Managed/NeonTranslator.log`                | Лог рантайма                           |
| `dwmapi.dll`                                                              | Native proxy (корень игры)             |
| `dwmapi_real.dll`                                                         | Форвардер (копия системной dwmapi.dll) |

## После деплоя

- Перезапустить игру
- Проверить лог: `NeonTranslator.log`
- Лог создаётся в `Third Crisis Neon Nights_Data/Managed/`
