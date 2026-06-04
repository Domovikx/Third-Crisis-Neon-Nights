# Third Crisis Neon Nights — Локализация

## Структура проекта

- Unity 2022.3.62f3 + BepInEx 5.4
- Основной код: Assembly-CSharp.dll (фреймворк ANToolkit) + PlayMaker FSM
- Текст диалогов и UI: scan-and-replace через NeonTranslatorRuntime
- Экстрактор текста: `extractor.py` — читает dump_assets/ и пишет YAML

## Извлечение текста

**`extractor.py`** — читает JSON-дампы из `dump_assets/` и собирает 3 YAML-файла в `translations/`.
Никакого парсинга бинарников — работает через данные, уже извлечённые `dump_assets.py`.

```
python .opencode/skills/extract-text/extractor.py
```

→ `translations/dialogues.yaml` — `[text, translation, speaker]` (1544 записи)
→ `translations/speakers.yaml` — `[name, translation, gender]` (23 спикера)
→ `translations/settings_keys.yaml` — `[key, translation]` (55 UI-строк)

### Источники данных

- **dialogues** — из `"dialogues"` поля MonoBehaviour в чанках (автопоиск по всем файлам)
- **speakers** — уникальные спикеры из dialogues (пустые/Narration исключены)
- **global_strings** — только `settings_keys.display` из summary JSON (реальный display-текст из бинарника)

Формат YAML позволяет писать комментарии `#` в файлах переводов.

### dump_assets

Перед запуском экстрактора нужен актуальный дамп:

```
python .opencode/skills/dump-assets/dump_assets.py
```

→ `dump_assets/` — 34 summary + 105 chunk файлов (UnityPy-объекты + raw-скан)

### DEPRECATED: parser.py

Старый `parser.py` — не использовать. Он сканировал бинарники напрямую с шумными эвристиками,
генерировал мусорные all-caps строки и непредсказуемые display-имена.
Вместо него — `extractor.py` + `dump_assets.py`.

## Сборка рантайма

```bash
python .opencode/skills/build-translator/build.py
python .opencode/skills/build-translator/build_proxy.py
```
→ `runtime/NeonTranslatorRuntime.dll`
→ `dwmapi.dll` (нативный прокси, корень игры)

## Команды

- `python .opencode/skills/extract-text/extractor.py` — извлечение переводов
- `python .opencode/skills/extract-text/extractor.test.py` — тесты (9)
- `python .opencode/skills/dump-assets/dump_assets.py` — дамп ассетов
- `python .opencode/skills/build-translator/build.py` — сборка DLL
- `python .opencode/skills/build-translator/build_proxy.py` — сборка прокси
- `python .opencode/skills/build-translator/build.test.py` — тесты сборки

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
