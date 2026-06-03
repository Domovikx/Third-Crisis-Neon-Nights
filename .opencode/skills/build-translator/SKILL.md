---
name: build-translator
description: Компиляция NeonTranslatorRuntime (C# → DLL) и нативного прокси dwmapi.dll (C → dll) для рантайм-перевода Unity-игр
---

# build-translator — Сборка рантайм-переводчика

Компилирует NeonTranslatorRuntime.dll (C#) и dwmapi.dll (C native proxy).
Scan-and-replace переводчик через NeonLateUpdate + Canvas.willRenderCanvases.

## Архитектура сборки

```
┌──────────────────────────┐     ┌──────────────────────────────┐
│  build.py                │     │  build_proxy.py              │
│  csc.exe → .dll          │     │  cl.exe → .dll              │
│                          │     │                              │
│  source/*.cs             │     │  source/dwmapi_proxy.c       │
│  + Unity refs.dll        │     │  + MSVC + Windows SDK        │
│  → NeonTranslatorRuntime │     │  → dwmapi.dll (native proxy) │
└──────────┬───────────────┘     └──────────┬───────────────────┘
           │                                │
           ▼                                ▼
   runtime/NeonTranslatorRuntime.dll  dwmapi.dll (корень игры)
```

## Файлы

| Файл                              | Назначение                                             |
| --------------------------------- | ------------------------------------------------------ |
| `source/NativeMethods.cs`         | P/Invoke kernel32 (VirtualProtect, GetProcAddress)     |
| `source/TranslationLoader.cs`     | Читает NDJSON, строит Dictionary (рекурсивно по папке) |
| `source/MethodPatcher.cs`         | VirtualProtect + JMP hook (DEACTIVATED)                |
| `source/NeonLateUpdate.cs`        | MonoBehaviour exec order 10000 — вызывает Populate     |
| `source/TranslatorPlugin.cs`      | Точка входа [RuntimeInitializeOnLoadMethod]            |
| `source/dwmapi_proxy.c`           | Native proxy DLL (32 forward + 2 intercepts)           |
| `build.py`                        | Компиляция C# → DLL через csc.exe                      |
| `build_proxy.py`                  | Компиляция dwmapi_proxy.c → dwmapi.dll                 |
| `build.test.py`                   | Тест сборки + проверка DLL                             |

## Сборка

```bash
python .opencode/skills/build-translator/build.py
```

Результат: `runtime/NeonTranslatorRuntime.dll`

## Установка

```bash
cp runtime/NeonTranslatorRuntime.dll "Third Crisis Neon Nights_Data/Managed/"
cp translations/**/*.ndjson "Third Crisis Neon Nights_Data/Managed/"
```

Словарь загружается рекурсивно из всех `*.ndjson` в `Managed/`. Пересборка DLL не требуется.

## Прокси (dwmapi.dll) — только один раз

```bash
python .opencode/skills/build-translator/build_proxy.py
```

Собирает `dwmapi.dll` + `dwmapi_real.dll` в корне игры.

## Формат данных (NDJSON)

```ndjson
["Resolution Scaling","Масштабирование разрешения"]
["I don't know...","Я не знаю...","Zoey"]
```

Первый элемент — оригинал (ключ), второй — перевод. Третий опционален (speaker).
Пустой второй элемент = не переведено.
