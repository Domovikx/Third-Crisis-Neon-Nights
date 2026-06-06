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
│  csc.exe → .dll          │     │  cl.exe → .dll               │
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

| Файл                          | Назначение                                           |
| ----------------------------- | ---------------------------------------------------- |
| `source/NativeMethods.cs`     | P/Invoke kernel32 (VirtualProtect, GetProcAddress)   |
| `source/TranslationLoader.cs` | Читает YAML, строит Dictionary (рекурсивно по папке) |
| `source/MethodPatcher.cs`     | VirtualProtect + JMP hook (DEACTIVATED)              |
| `source/NeonLateUpdate.cs`    | MonoBehaviour exec order 10000 — вызывает Populate   |
| `source/TranslatorPlugin.cs`  | Точка входа [RuntimeInitializeOnLoadMethod]          |
| `source/dwmapi_proxy.c`       | Native proxy DLL (32 forward + 2 intercepts)         |
| `build.py`                    | Компиляция C# → DLL через csc.exe                    |
| `build_proxy.py`              | Компиляция dwmapi_proxy.c → dwmapi.dll               |
| `build.test.py`               | Тест сборки + проверка DLL                           |

## Сборка

```bash
python .opencode/skills/build-translator/build.py
```

Результат: `runtime/NeonTranslatorRuntime.dll`

## Установка

```bash
cp runtime/NeonTranslatorRuntime.dll "Third Crisis Neon Nights_Data/Managed/"
cp translations/**/*.yaml "Third Crisis Neon Nights_Data/Managed/"
```

Словарь загружается рекурсивно из всех `*.yaml` в `Managed/`. Пересборка DLL не требуется.

## Прокси (dwmapi.dll) — только один раз

```bash
python .opencode/skills/build-translator/build_proxy.py
```

Собирает `dwmapi.dll` + `dwmapi_real.dll` в корне игры.

## Формат данных (YAML)

```yaml
# Dialogues (path_id=73203): text, translation, speaker, rich_text, rich_translation
- text: "Yesss...!~"
  translation: "Да-а-а...!~"
  speaker: "Zoey"
  rich_text: ""
  rich_translation: ""
- text: "Fhaaa..!!"
  translation: "Ахха..!!"
  speaker: "Zoey"
  rich_text: ""
  rich_translation: ""

# Settings keys: text, translation
- text: "Fullscreen"
  translation: "Полный экран"

# Speakers: text, translation, gender, notes
- text: "Zoey"
  translation: "Зои"
  gender: "female"
  notes: ""

Поля: `text` — оригинал (ключ), `translation` — перевод. Для диалогов также `speaker`, `rich_text`, `rich_translation`.
Пустая строка `""` на месте перевода → не переведено.
```
