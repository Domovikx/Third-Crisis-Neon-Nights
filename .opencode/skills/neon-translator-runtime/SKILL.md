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
│    │   ├── FindObjectsOfType(TMP/UI.Text)             │
│    │   ├── замена по словарю                          │
│    │   └── перерегистрация FastScan                   │
│    │                                                  │
│    ├── willRenderCanvases → FastScan (last handler)   │
│    │   └── замена после перестроения Canvas           │
│    │                                                  │
│    └── OnPreRenderObject → PostRebuildHandler         │
│        └── SetAllDirty() для заменённых               │
│                          │                            │
│              ┌───────────┴───────────┐                │
│              │  TranslationLoader   │                 │
│              │  Dictionary<str,str> │                 │
│              │  "Resolution" →      │                 │
│              │  "Разрешение экрана" │                 │
│              └──────────────────────┘                 │
│                          │                            │
│                          ▼                            │
│               На экране: любая длина!                 │
└───────────────────────────────────────────────────────┘
```

## Файлы

| Файл                          | Назначение                                             |
| ----------------------------- | ------------------------------------------------------ |
| `source/NativeMethods.cs`     | P/Invoke kernel32 (VirtualProtect, GetProcAddress)     |
| `source/TranslationLoader.cs` | Читает NDJSON, строит Dictionary                       |
| `source/MethodPatcher.cs`     | VirtualProtect + JMP hook (DEACTIVATED — повреждал UI) |
| `source/NeonLateUpdate.cs`    | MonoBehaviour exec order 10000 — три фиксера           |
| `source/TranslatorPlugin.cs`  | Точка входа [RuntimeInitializeOnLoadMethod]            |
| `build.mjs`                   | Компиляция C# → DLL через csc.exe                      |
| `build.test.mjs`              | Тест сборки + проверка DLL                             |

## Сборка

```bash
node .opencode/skills/neon-translator-runtime/build.mjs
```

Результат: `output/runtime/NeonTranslatorRuntime.dll`

## Установка

```bash
cp output/runtime/NeonTranslatorRuntime.dll \
   "Third Crisis Neon Nights_Data/Managed/"
cp output/translations/ui/resources.ndjson \
   "Third Crisis Neon Nights_Data/Managed/NeonTranslatorRuntime_Data.ndjson"
```

## Формат данных (NDJSON)

```ndjson
["source_seq","Resolution Scaling","Масштабирование разрешения","2355047"]
```
