---
name: neon-translator-runtime
description: NeonTranslatorRuntime — самописный рантайм-переводчик для Unity игр. Scan-and-replace через NeonLateUpdate + Canvas.willRenderCanvases. Zero сторонних библиотек.
---

# NeonTranslatorRuntime

Самописный аналог BepInEx/XUnity.AutoTranslator для дипломной работы.
Сканирует TMP/UI.Text компоненты в LateUpdate и Canvas.willRenderCanvases,
заменяет текст на перевод из NDJSON-словаря. **Ноль сторонних библиотек**.

## Архитектура

```
┌───────────────────────────────────────────────────────┐
│                     Игра (Unity)                      │
│  TMP_Text.text = "Resolution" → "Resolution"          │
│                          │                            │
│  NeonLateUpdate (exec 10000)                          │
│    ├── LateUpdate → PopulateAllTextPublic()           │
│    │   └── итерация по кэшу → замена                  │
│    │                                                  │
│    └── willRenderCanvases → OnPreRender               │
│        ├── InvalidateCache()                          │
│        ├── ScanAllUiLocs() → ANToolkit словарь        │
│        └── PopulateAllText() → FindObjects + замена   │
│                          │                            │
│              ┌───────────┴───────────┐                │
│              │  TranslationLoader   │                 │
│              │  Dictionary<str,str> │                 │
│              │  "Resolution" →      │                 │
│              │  "Разрешение экрана" │                 │
│              └──────────────────────┘                 │
│                          │                            │
│                          ▼                            │
│               На экране: русский текст                │
└───────────────────────────────────────────────────────┘
```

## Файлы

| Файл                          | Назначение                                             |
| ----------------------------- | ------------------------------------------------------ |
| `source/NativeMethods.cs`     | P/Invoke kernel32 (VirtualProtect, GetProcAddress)     |
| `source/TranslationLoader.cs` | Читает NDJSON, строит Dictionary                       |
| `source/MethodPatcher.cs`     | VirtualProtect + JMP hook (DEACTIVATED — повреждал UI) |
| `source/NeonLateUpdate.cs`    | MonoBehaviour exec order 10000 — вызывает Populate     |
| `source/TranslatorPlugin.cs`  | Точка входа [RuntimeInitializeOnLoadMethod]            |
| `source/dwmapi_proxy.c`       | Native proxy DLL (32 forward + 2 intercepts)           |
| `build.mjs`                   | Компиляция C# → DLL через csc.exe                      |
| `build.test.mjs`              | Тест сборки + проверка DLL                             |
| `build_proxy.mjs`             | Компиляция dwmapi_proxy.c → dwmapi.dll                 |

## Сборка

```bash
node .opencode/skills/neon-translator-runtime/build.mjs
```

Результат: `runtime/NeonTranslatorRuntime.dll`

## Установка

```bash
cp runtime/NeonTranslatorRuntime.dll \
   "Third Crisis Neon Nights_Data/Managed/"
```

Словарь (`NeonTranslatorRuntime_Data.json`) редактируется напрямую в `translations/ru/`,
через `merge.mjs` копируется в `Managed/`. Пересборка DLL не требуется.

## Прокси (dwmapi.dll) — только один раз

```bash
node build_proxy.mjs
```

Собирает `dwmapi.dll` + `dwmapi_real.dll` в корне игры.

## Формат данных (NDJSON)

```ndjson
["source_seq","Resolution Scaling","Масштабирование разрешения","2355047"]
```
