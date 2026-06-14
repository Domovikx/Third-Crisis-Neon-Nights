# TODO — известные баги и нерешённые вопросы

> YAML-файлы в `translations/` генерируются extractor'ом из `dump_assets/`.  
> Если баг в дампе — фикс в `dump_assets.py`, YAML перегенерируется.

## dump_assets

### [BUG] Обрубленные строки dialogues через parse_dialogue_from_raw

**Симптом:** в дампе `dump_assets/bundle_level-glowinghole_scenes_all_741d8619fcc0f42c035ae5010cf5392.chunk000.json` (path_id=1001) есть dialogue entry:
```json
"dialogues": [
  {
    "speaker": "Zoey",
    "text": "(I can hear someone in there",
    "rich_text": "<i>(I can hear someone in there"
  }
]
```

Текст обрублен: нет закрывающей `)`, нет `</i>`. В `raw_strings[2]` обрыв на non-printable байте. В `raw_strings[3]` сразу идёт speaker `Zoey`.

**Причина:** `parse_dialogue_from_raw` в `dump_assets.py` ищет паттерн `"Speaker":"X","Text":"Y"` в raw bytes MonoBehaviour. Случайно нашёл его в данных (видимо, байты содержат последовательность, похожую на JSON-диалог). Создал false-positive dialogue entry.

Текст **`"I can hear someone in there"` НЕ существует ни в одном бинарнике игры** (resources/assets/bundle/dll — проверено полным перебором). Значит это артефакт парсера, а не реальная строка.

**Что проверить:**
- [ ] Убедиться что false positive (текст реально от парсера, не из игры)
- [ ] Поправить `parse_dialogue_from_raw` — добавить валидацию: dialogue text должен быть похож на реальную реплику (длина > N, содержит пробелы, не обрублен)
- [ ] Добавить sanity-check: если `rich_text` начинается с `<i>` но не заканчивается на `</i>` — вероятно обрубок, skip

**Правильный фикс:** в `parse_dialogue_from_raw` после извлечения text/rich_text:
- Если rich_text содержит открывающий тег без закрывающего (`<i>...` без `</i>`) — skip
- Если text не имеет смысла (обрубок в середине слова, нет закрывающей скобки/punctuation) — skip

**Файл-источник:** `dump_assets/bundle_level-glowinghole_scenes_all_741d8619fcc0f42c035ae5010cf5392.chunk000.json` (path_id=1001)
**Код-источник:** `.opencode/skills/dump-assets/dump_assets.py:159-200` (`parse_dialogue_from_raw`)
