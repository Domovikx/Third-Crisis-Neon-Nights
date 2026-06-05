# Third Crisis Neon Nights — Локализация

## Структура проекта

- Unity 2022.3.62f3 + BepInEx 5.4
- Основной код: Assembly-CSharp.dll (фреймворк ANToolkit) + PlayMaker FSM
- Текст диалогов и UI: scan-and-replace через NeonTranslatorRuntime
- Экстрактор текста: `extractor.py` — читает dump_assets/ и пишет YAML

## Извлечение текста

**`extractor.py`** — читает JSON-дампы из `dump_assets/` и собирает YAML-файлы в `translations/`.
Никакого парсинга бинарников — работает через данные, уже извлечённые `dump_assets.py`.

```
python .opencode/skills/extract-text/extractor.py
```

→ `translations/dialogues.{path_id}.yaml` — `[text, translation, speaker]` (1503+93+97+100, ANToolkit JSON)
→ `translations/dialogues.bundle.yaml` — `[text, translation, speaker]` (~992, PlayMaker FSM из .bundle)
→ `translations/speakers.yaml` — `[name, translation, gender, notes]` (52 спикера)
→ `translations/settings_keys.yaml` — `[key, translation]` (55 UI-строк)

### Источники данных

- **dialogues (path_id)** — из `"dialogues"` поля MonoBehaviour в чанках `.assets` (ANToolkit `Speaker/Text` JSON)
- **dialogues.bundle** — из `raw_strings` MonoBehaviour с `line_X` маркерами в чанках `.bundle` (PlayMaker FSM)
- **speakers** — уникальные спикеры из обоих источников (пустые/Narration исключены)
- **global_strings** — только `settings_keys.display` из summary JSON (реальный display-текст из бинарника)

Формат YAML: `[key, translation, ...extra]`. Экстра колонки (speaker, gender, notes) игнорируются C#-рантаймом,
но сохраняются через merge при перезапуске экстрактора.

### dump_assets

Перед запуском экстрактора нужен актуальный дамп. Обрабатывает как `.assets`, так и `.bundle` файлы:

```
python .opencode/skills/dump-assets/dump_assets.py
```

→ `dump_assets/` — summary + chunk файлы (UnityPy-объекты + raw-скан).
Сканирует `Third Crisis Neon Nights_Data/` на `.assets` и рекурсивно `StreamingAssets/` на `.bundle`.

### REMOVED: parser.py

Удалён. Вместо него — `extractor.py` + `dump_assets.py`.
Старый `parser.py` сканировал бинарники напрямую с шумными эвристиками,
генерировал мусорные all-caps строки и непредсказуемые display-имена.

## Сборка рантайма

```bash
python .opencode/skills/build-translator/build.py
python .opencode/skills/build-translator/build_proxy.py
```

→ `runtime/NeonTranslatorRuntime.dll`
→ `dwmapi.dll` (нативный прокси, корень игры)

## Команды

- `python .opencode/skills/extract-text/extractor.py` — извлечение переводов
- `python .opencode/skills/extract-text/extractor.test.py` — тесты (14)
- `python .opencode/skills/dump-assets/dump_assets.py` — дамп ассетов (+ .bundle)
- `python .opencode/skills/dump-assets/dump_assets.test.py` — тесты дампера (23)
- `python .opencode/skills/build-translator/build.py` — сборка DLL
- `python .opencode/skills/build-translator/build_proxy.py` — сборка прокси
- `python .opencode/skills/build-translator/build.test.py` — тесты сборки (19)

## Важные пути

- Корень игры: `C:\Program Files (x86)\Steam\steamapps\common\Third Crisis Neon Nights`
- Переводы: `translations/` (YAML)
- Дампы: `dump_assets/`
- Экстрактор: `.opencode/skills/extract-text/extractor.py`
- Дампер: `.opencode/skills/dump-assets/dump_assets.py`
- Рантайм: `.opencode/skills/build-translator/`
- Сборка DLL: `runtime/NeonTranslatorRuntime.dll`
- Прокси: `dwmapi.dll` (корень игры), `dwmapi_real.dll` (форвардер)
- Лог: `Third Crisis Neon Nights_Data/Managed/NeonTranslator.log`
