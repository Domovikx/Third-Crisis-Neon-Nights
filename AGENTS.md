# Third Crisis Neon Nights — Локализация

## Структура проекта

- Unity 2022.3.62f3 + BepInEx 5.4
- Основной код: Assembly-CSharp.dll (фреймворк ANToolkit) + PlayMaker FSM
- Текст диалогов и UI: scan-and-replace через NeonTranslatorRuntime
- Все `*.json` из `translations/` рекурсивно — DLL мержит их сама

## Формат перевода

```
{"original":"translated"}
{"Fullscreen":"Полноэкранный режим"}
{"Load Game":"Загрузить игру"}
```

Каждая строка — независимая JSON-запись. `translated` пустой (`""`) → не переведено.
**Ключи регистрозависимые** — `"Load Game"` и `"LOAD GAME"` — разные записи, но merge.mjs дедупит case-insensitive (первое вхождение побеждает).

## Доступные скилы (в .opencode/skills/)

- `translate-analysis` — анализ файлов перевода, статистика, поиск непереведённого
- `translate-batch` — пакетный перевод через Google Translate API
- `find-strings` — извлечение английских строк из бинарных файлов Unity
- `parse-unity` — чистый парсер Unity serialized + bundle парсер (binary → NDJSON, без фильтрации)
  - `parser.mjs` — .assets/level файлы (aligned + null-terminated + UTF-16 строки)
  - `bundle-parser.mjs` — .bundle файлы (LZ4HC, raw ASCII scanning)
- `extractor` — классификация и фильтрация строк из NDJSON (dialogue / UI / noise)
- `neon-translator-runtime` — рантайм-переводчик (C# DLL, scan-and-replace + native proxy dwmapi.dll)
- `neon-translator-deploy` — деплой: сборка DLL, копирование в Managed, обновление словаря

## Команды

- `node .opencode/skills/translate-analysis/analyze.mjs` — запустить анализ
- `node .opencode/skills/translate-batch/batch.mjs` — пакетный перевод непереведённого
- `node .opencode/skills/translate-batch/batch.mjs --dry-run` — тестовый прогон
- `node .opencode/skills/translate-batch/merge.mjs` — дедупликация + деплой в Managed/
- `node .opencode/skills/translate-batch/merge.mjs --dry-run` — тестовый прогон
- `node .opencode/skills/translate-batch/batch.test.mjs` — тесты batch (7 тестов)
- `node .opencode/skills/translate-batch/merge.test.mjs` — тесты merge (12 тестов)
- `node .opencode/skills/find-strings/find.mjs` — извлечь строки
- `node .opencode/skills/parse-unity/parser.mjs` — парсер (binary → NDJSON)
- `node .opencode/skills/parse-unity/bundle-parser.mjs` — парсер бандлов (LZ4HC → NDJSON)
- `node .opencode/skills/extractor/extractor.mjs` — экстрактор (NDJSON → диалоги/UI)
- `node .opencode/skills/parse-unity/parser.test.mjs` — тесты парсера (80 тестов)
- `node .opencode/skills/neon-translator-runtime/build.mjs` — сборка рантайм-переводчика (→ runtime/NeonTranslatorRuntime.dll)
- `node .opencode/skills/neon-translator-runtime/build.test.mjs` — тесты сборки
- `node .opencode/skills/neon-translator-runtime/build_proxy.mjs` — сборка нативного прокси (→ dwmapi.dll)
- `python C:\Users\Domo\AppData\Local\Temp\opencode\search_bundles.py` — поиск строк в сырых бандлах

## Структура файлов перевода

```
translations/
  ui.json                            — UI переводы (137 строк, Fullscreen, Load Game…)
  resources.json                     — диалоги по исходным файлам
  level3.json
  level7.json
  sharedassets.json
  ...                              (~4900 диалоговых строк)
```

## Пайплайн

```
извлечение:
  parser.mjs → extractor.mjs → split_sources.mjs  (извлекает диалоги в translations/)

перевод:
  редактировать translations/*.json (flat, никакой вложенности)
         │
         └── DLL сама читает все *.json из translations/ рекурсивно
```

## Команды (дополнительные)

- `node C:\Users\Domo\AppData\Local\Temp\opencode\split_sources.mjs` — разделить экстракт по исходным файлам в `translations/`

## Формат NDJSON

```
["original","translated"]
["Fullscreen","Полноэкранный режим"]
["Load Game","Загрузить игру"]
["Ultra",""]                       ← не переведено
```

## Ключевые находки

- **Data area бандлов не сжата** — только LZ4-заголовок, raw ASCII scanning работает напрямую
- **Settings.\* ключи** — ANToolkit локализация: `Settings.Fullscreen → Fullscreen` (58 ключей в resources.assets)
- **Из 97 бандлов только 4 с UI текстом:** level-cartelhideout, level-glowinghole, 3dsuitcasescene, releasenotesui
- **"Enable VSync"** — не "VSYNC": `Settings.EnableVSync → Enable VSync`
- **4 missing settings найдены** в Assembly-CSharp.dll как UTF-16 LE строки
- **MonoBehaviour.Update работает** через `[RuntimeInitializeOnLoadMethod]` + `new GameObject().AddComponent<>()`
- **NeonLateUpdate** с `[DefaultExecutionOrder(10000)]` — срабатывает ПОСЛЕ всех игровых LateUpdate
- **Два фиксера:** PopulateAllTextPublic (LateUpdate — использует кэш), willRenderCanvases (OnPreRender — инвалидирует кэш + заменяет)
- **Два бага найдены и исправлены:** (1) exact type check → IsAssignableFrom (2) "m_Text" → "m_text" (camelCase)
- **SetTextFieldDirect** теперь также ставит `m_havePropertiesChanged = true` + `SetVerticesDirty()` для TMP
- **141 перевод** UI (было 117, добавлено 24)
- **Текст стабилен** — мерцание устранено через кэш
- **dwmapi.dll proxy** — 32 forward + 2 интерсепта, 13.5 KB
- **MethodPatcher (JMP detour) DEACTIVATED** — повреждал UI

## Рантайм-переводчик

- **dwmapi.dll proxy** в корне игры — загружается Unity при старте
- Бутстрапит NeonTranslatorRuntime.dll в Managed/ через mono_domain_assembly_open
- **NeonTranslatorRuntime.dll** — сканирует текст каждый кадр через LateUpdate + willRenderCanvases
- **Словарь перевода** — все `*.json` из `translations/` рекурсивно (141 запись UI + ~4900 диалогов)
- Формат NDJSON: `{"original":"translated"}`

## Ключевые находки (диалоги)

- **Диалоги извлекаются** через пайплайн parser → extractor → split_sources.mjs
- **4200+ диалоговых строк** найдено во всех level-файлах, resources.assets, sharedassets и бандлах
- **Реальные диалоги** — длинные фразы с пунктуацией, эмоциональной окраской, диалоговыми маркерами (`>`, `<`, `<>`)
- **FSM шум** (20K строк) — отфильтрован: `Wait for trigger`, `Top left of Zoey`, `Check to enable` и т.д.
- **Unity API docs** — отфильтрованы: строки с префиксом `a `, `b `, `eUpdate`, `Returns a rotation` и т.д.
- **UI (137 строк)** — хранятся отдельно в `translations/ui.json`, не смешиваются с диалогами
- Формат per-source — каждый файл в `translations/` соответствует исходному файлу игры
- **~130K UI кандидатов** в экстракторе — большинство тех.шум (имена объектов, шейдеров)
- **Google Translate 429** — бесплатное API блокирует пакетный перевод 3700+ строк

## Важные пути

- Корень игры: `C:\Program Files (x86)\Steam\steamapps\common\Third Crisis Neon Nights`
- Переводы: `translations/`
- Лог: `Third Crisis Neon Nights_Data/Managed/NeonTranslator.log`
- Прокси: `dwmapi.dll` (корень игры)
- Исходники: `.opencode/skills/neon-translator-runtime/source/`
- Сборка: `runtime/NeonTranslatorRuntime.dll`
