# Third Crisis Neon Nights — Локализация

## Структура проекта

- Unity 2022.3.62f3 + BepInEx 5.4
- Основной код: Assembly-CSharp.dll (фреймворк ANToolkit) + PlayMaker FSM
- Текст диалогов и UI: scan-and-replace через NeonTranslatorRuntime
- Парсер: `parser.py` — извлекает диалоги и UI-текст из бинарников Unity

## Извлечение текста

parser.py — Python-парсер Unity serialized-файлов. Три режима, все с **merge-логикой**: существующие переводы сохраняются, добавляются только новые ключи.

### `--dialogue`
Извлекает структурированные диалоги (Speaker/Text) из ресурса DialogueHistory в `resources.assets`. Читает существующий `dialogue.ndjson`, сохраняет переводы.
```
python .opencode/skills/extract-text/parser.py --dialogue
```
→ `translations/dialogs/dialogue.ndjson` — `["eng", "rus", "speaker"]` (1544 записи)

### `--texts`
Извлекает UI-строки (настройки, меню) из Settings-ключей и all-caps строк. Читает существующий `ui.ndjson`, сохраняет переводы.
```
python .opencode/skills/extract-text/parser.py --texts
```
→ `translations/texts/ui.ndjson` — `["eng", "rus"]`

### `--characters`
Извлекает уникальные имена персонажей из `dialogue.ndjson` (3-й айтем). Читает существующий `characters.ndjson`, сохраняет переводы и гендер.
```
python .opencode/skills/extract-text/parser.py --characters
```
→ `translations/characters.ndjson` — `["eng", "rus", "gender"]`

### По умолчанию (без `--dialogue`/`--texts`)
Полный скан всех файлов игры для исследовательских целей:
```
python .opencode/skills/extract-text/parser.py ./output/
```

## Формат перевода

```
translations/
  dialogs/
    dialogue.ndjson    — ["eng", "rus", "speaker"]     → диалоги
  texts/
    ui.ndjson          — ["eng", "rus"]                 → UI/меню
  characters.ndjson    — ["eng", "rus", "gender"]       → персонажи
```

Пустой `""` → не переведено. При перезапуске парсера существующие переводы НЕ затираются.

## Сборка рантайма

```bash
python .opencode/skills/build-translator/build.py
python .opencode/skills/build-translator/build_proxy.py
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

- `python .opencode/skills/extract-text/parser.py --dialogue` — диалоги
- `python .opencode/skills/extract-text/parser.py --texts` — UI + настройки
- `python .opencode/skills/extract-text/parser.py --characters` — персонажи
- `python .opencode/skills/extract-text/parser.py output/` — полный скан
- `python .opencode/skills/extract-text/parser.test.py` — тесты парсера (50)
- `python .opencode/skills/build-translator/build.py` — сборка DLL
- `python .opencode/skills/build-translator/build_proxy.py` — сборка прокси
- `python .opencode/skills/build-translator/build.test.py` — тесты сборки

## Важные пути

- Корень игры: `C:\Program Files (x86)\Steam\steamapps\common\Third Crisis Neon Nights`
- Переводы: `translations/`
- Парсер: `.opencode/skills/extract-text/parser.py`
- Рантайм: `.opencode/skills/build-translator/`
- Сборка DLL: `runtime/NeonTranslatorRuntime.dll`
- Прокси: `dwmapi.dll` (корень игры), `dwmapi_real.dll` (форвардер)
- Лог: `Third Crisis Neon Nights_Data/Managed/NeonTranslator.log`
