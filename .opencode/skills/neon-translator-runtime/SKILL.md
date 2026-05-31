---
name: neon-translator-runtime
description: NeonTranslatorRuntime — самописный рантайм-переводчик для Unity игр. Method hooking через VirtualProtect + JMP. Zero сторонних библиотек.
---

# NeonTranslatorRuntime

Самописный аналог BepInEx/XUnity.AutoTranslator для дипломной работы.
Перехватывает `TMP_Text.set_text()` в рантайме и заменяет текст на перевод
из NDJSON-словаря. **Ноль сторонних библиотек** — только C# + Win32 API.

## Архитектура

```
┌─────────────────────────────────────────────────┐
│                  Игра (Unity)                   │
│   TMP_Text.text = "Resolution"                  │
│                         │                       │
│              ┌──────────┴──────────┐            │
│              │  MethodPatcher.cs   │            │
│              │  jmp → Translator   │            │
│              └──────────┬──────────┘            │
│                         ▼                       │
│              ┌──────────────────────┐           │
│              │  TranslationLoader   │           │
│              │  Dictionary<str,str> │           │
│              │  "Resolution" →      │           │
│              │  "Разрешение экрана" │           │
│              └──────────────────────┘           │
│                         │                       │
│                         ▼                       │
│              На экране: любая длина!            │
└─────────────────────────────────────────────────┘
```

## Файлы

| Файл                          | Назначение                                                  |
| ----------------------------- | ----------------------------------------------------------- |
| `source/NativeMethods.cs`     | P/Invoke kernel32 (VirtualProtect, GetProcAddress)          |
| `source/TranslationLoader.cs` | Читает NDJSON, строит Dictionary                            |
| `source/MethodPatcher.cs`     | VirtualProtect + JMP hook                                   |
| `source/TranslatorPlugin.cs`  | MonoBehaviour — точка входа [RuntimeInitializeOnLoadMethod] |
| `build.mjs`                   | Компиляция C# → DLL через csc.exe                           |
| `build.test.mjs`              | Тест сборки + проверка DLL                                  |

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
