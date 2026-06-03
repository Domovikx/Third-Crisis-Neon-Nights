# Third Crisis Neon Nights — Локализация

## Структура проекта

- Unity 2022.3.62f3 + BepInEx 5.4
- Основной код: Assembly-CSharp.dll (фреймворк ANToolkit) + PlayMaker FSM
- Текст диалогов и UI: scan-and-replace через NeonTranslatorRuntime
- Парсер: `parser_v2.py` — извлекает диалоги и UI-текст из бинарников Unity

## Извлечение текста

parser_v2.py — Python-парсер Unity serialized-файлов. Три режима:

### `--dialogue`
Извлекает структурированные диалоги (Speaker/Text) из ресурса DialogueHistory в `resources.assets`.
```
python .opencode/skills/parse-unity/parser_v2.py --dialogue
```
→ `translations/dialogs/dialogue.ndjson` — `["speaker", "eng", ""]` (1544 записи)

### `--texts`
Извлекает UI-строки (настройки, меню) и Settings-ключи.
```
python .opencode/skills/parse-unity/parser_v2.py --texts
```
→ `translations/texts/ui.ndjson` — `["eng", ""]` (102 UI строки)

### По умолчанию (без `--dialogue`/`--texts`)
Полный скан всех файлов игры для исследовательских целей:
```
python .opencode/skills/parse-unity/parser_v2.py ./output/
```

## Формат перевода

```
translations/
  dialogs/
    dialogue.ndjson    — ["speaker", "eng", ""]     → диалоги
  texts/
    ui.ndjson          — ["eng", ""]                 → UI/меню
```

Пустой `""` → не переведено.

## Сборка рантайма

```bash
python .opencode/skills/neon-translator-runtime/build.py
python .opencode/skills/neon-translator-runtime/build_proxy.py
```
→ `runtime/NeonTranslatorRuntime.dll`
→ `dwmapi.dll` (нативный прокси, корень игры)

## Ключевые находки

- **Диалоги только в `resources.assets`** (DialogueHistory — Speaker + Text + color)
- **24 спикера**: Zoey (840), Sarah (107), Man (90), Max (78), Lio (51) и др.
- **Settings.* ключи** — ANToolkit локализация: `Settings.Fullscreen → Fullscreen` (57 ключей)
- **102 UI строки** — настройки, меню, интерфейс
- **Из 97 бандлов только 4 с UI текстом:** level-cartelhideout, level-glowinghole, 3dsuitcasescene, releasenotesui
- **NeonLateUpdate** с `[DefaultExecutionOrder(10000)]` — срабатывает ПОСЛЕ всех игровых LateUpdate
- **dwmapi.dll proxy** — 32 forward + 2 интерсепта, 13.5 KB

## Команды

- `python .opencode/skills/parse-unity/parser_v2.py --dialogue` — диалоги
- `python .opencode/skills/parse-unity/parser_v2.py --texts` — UI + настройки
- `python .opencode/skills/parse-unity/parser_v2.py output/` — полный скан
- `python .opencode/skills/parse-unity/parser_v2.test.py` — тесты парсера (43)
- `python .opencode/skills/neon-translator-runtime/build.py` — сборка DLL
- `python .opencode/skills/neon-translator-runtime/build_proxy.py` — сборка прокси
- `python .opencode/skills/neon-translator-runtime/build.test.py` — тесты сборки

## Важные пути

- Корень игры: `C:\Program Files (x86)\Steam\steamapps\common\Third Crisis Neon Nights`
- Переводы: `translations/`
- Парсер: `.opencode/skills/parse-unity/parser_v2.py`
- Рантайм: `.opencode/skills/neon-translator-runtime/`
- Сборка DLL: `runtime/NeonTranslatorRuntime.dll`
- Прокси: `dwmapi.dll` (корень игры), `dwmapi_real.dll` (форвардер)
- Лог: `Third Crisis Neon Nights_Data/Managed/NeonTranslator.log`
