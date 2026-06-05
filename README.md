# Third Crisis: Neon Nights — Русская локализация

> Инструментарий для извлечения, перевода и рантайм-замены текста игры **Third Crisis: Neon Nights** (Anduo Games).
> Парсинг Unity через UnityPy + структурированный дамп ассетов + рантайм-переводчик C# через scan-and-replace.

**Поисковые теги:** `Third Crisis Neon Nights` `русская локализация` `русификатор` `Russian translation` `Anduo Games` `Unity 2022.3` `PlayMaker` `визуальная новелла` `киберпанк` `перевод игры` `Python` `YAML` `BepInEx`

---

## Об игре

**Third Crisis: Neon Nights** — приквел к Third Crisis, действие через 3 года после мирового кризиса. Киберпанк-метрополия Neon City, коррумпированное правительство GAG, наёмница Зои Мэдисон. Выборы, соблазны, выживание. RPG / Visual Novel на Unity 2022.3.62f3 (URP) со скриптингом PlayMaker FSM.

Страницы: [Steam](https://store.steampowered.com/app/3400350/Third_Crisis_Neon_Nights/) · [Itch.io](https://anduogames.itch.io/third-crisis-neon-nights)

---

## Пайплайн локализации

```
dump_assets.py ─→ dump_assets/ (140 JSON-файлов: 34 summary + 105 chunk)
       │
       ▼
extractor.py ─→ translations/
                   ├── dialogues.{path_id}.yaml  (1793 диалога, 4 источника)
                   ├── speakers.yaml             (23 спикера)
                   └── settings_keys.yaml        (55 UI-строк)
       │
       ▼ (перевод → деплой)
build.py → runtime/NeonTranslatorRuntime.dll
build_proxy.py → dwmapi.dll (native proxy)
```

Все переводы — плоские YAML-файлы (списки `[original, translation, speaker?]`). Рантайм загружает `*.yaml` из `Managed/`.

---

## Быстрый старт

```bash
# 1. Дамп ассетов (UnityPy)
python .opencode/skills/dump-assets/dump_assets.py

# 2. Извлечение переводов
python .opencode/skills/extract-text/extractor.py

# 3. Тесты
python .opencode/skills/extract-text/extractor.test.py  # 14 тестов
python .opencode/skills/build-translator/build.test.py   # 19 тестов
python .opencode/skills/dump-assets/dump_assets.test.py  # 23 теста

# 4. Сборка
python .opencode/skills/build-translator/build.py       # сборка DLL
python .opencode/skills/build-translator/build_proxy.py # сборка прокси
```

---

## Ключевые открытия (технические)

### Диалоги: DialogueHistory в resources.assets

Вся структура диалогов (Speaker + Text + color) хранится в сериализованном массиве `DialogueHistory` внутри `resources.assets`. 1793 записи в 4 MonoBehaviour, 23 уникальных спикера.

### UI: Settings.* ключи

UI-текст читается из `settings_keys` поля summary JSON (реальный display-текст из бинарника). 55 строк: настройки, меню, интерфейс.

### Addressables .bundle: только 4 с текстом

Из 97 бандлов только 4 содержат UI текст: level-cartelhideout, level-glowinghole, 3dsuitcasescene, releasenotesui.

### Scan-and-Replace вместо патча

Перевод в оперативной памяти через NeonLateUpdate + Canvas.willRenderCanvases. Бинарники игры не модифицируются. Длина перевода не ограничена.

---

## Формат YAML

**Диалоги:**
```yaml
- ["Yesss...!~", "Да-а-а...!~", "Zoey"]
- ["Fhaaa..!!", "Ахха..!!", "Zoey"]
```

**UI:**
```yaml
- ["Fullscreen", "Полный экран"]
```

**Персонажи:**
```yaml
- ["Zoey", "Зои", "female"]
```

Пустая строка `""` на месте перевода → не переведено.

---

## Технический анализ

| Компонент      | Версия                                    | Примечание                      |
| -------------- | ----------------------------------------- | ------------------------------- |
| Unity          | 2022.3.62f3 (LTS)                         | URP рендеринг                   |
| C# Runtime     | .NET 4.x (Mono)                           | IL2CPP не используется          |
| Фреймворк      | ANToolkit                                 | Кастомная система настроек и UI |
| Скриптинг      | PlayMaker FSM                             | Визуальные скрипты, диалоги     |
| Локализация    | NeonTranslatorRuntime (самописный)        | Scan-and-replace, 0 библиотек   |
| Сцен           | 16 (level0–15)                            | Бинарные Unity-сцены            |
| Addressables   | 97 .bundle файлов                         | LZ4HC сжатие                    |

### Статистика перевода

| Показатель               | Значение  |
| ------------------------ | --------- |
| Диалогов всего           | 1 793     |
| UI-строк                 | 55        |
| Персонажей               | 23        |
| Settings.\* ключей       | 55        |
| Дампер                   | dump_assets.py (UnityPy) |
| Экстрактор               | extractor.py (Python) |
| Рантайм                  | NeonTranslatorRuntime.dll (C#) |

---

## Структура репозитория

```
├── .opencode/
│   ├── agents/
│   │   └── translate-expert.md       # агент-переводчик для opencode
│   └── skills/
│       ├── extract-text/
│       │   ├── extractor.py       # экстрактор из dump_assets/ в YAML
│       │   ├── extractor.test.py  # 14 тестов
│       │   ├── parser.py          # [REMOVED] старый парсер (удалён)
│       │   └── SKILL.md
│       ├── build-translator/
│       │   ├── source/               # C# исходники
│       │   ├── build.py              # сборка DLL
│       │   ├── build_proxy.py        # сборка dwmapi.dll
│       │   └── SKILL.md
│       ├── dump-assets/
│       │   ├── dump_assets.py        # дампер ассетов
│       │   ├── dump_assets.test.py   # 23 теста
│       │   └── SKILL.md
│       └── deploy-translator/
│           └── SKILL.md
├── dump_assets/                      # 140 JSON-файлов (UnityPy дампы)
├── translations/
│   ├── dialogues.73203.yaml          # диалоги (1503)
│   ├── dialogues.73262.yaml          # диалоги (93)
│   ├── dialogues.73263.yaml          # диалоги (97)
│   ├── dialogues.73264.yaml          # диалоги (100)
│   ├── speakers.yaml                 # персонажи (23)
│   └── settings_keys.yaml            # UI строки (55)
├── runtime/
│   └── NeonTranslatorRuntime.dll     # скомпилированная DLL
├── AGENTS.md                         # правила проекта для opencode
├── THEORY.md                         # техническая документация
└── README.md
```

## Требования

- Python 3.11+
- UnityPy (`pip install UnityPy`)
- PyYAML (`pip install PyYAML`)
- .NET Framework SDK (csc.exe) — для сборки DLL
- MSVC Build Tools (cl.exe) — для сборки прокси
- Игра Third Crisis: Neon Nights (Steam)

## Лицензия

MIT — инструменты распространяются свободно.
Игра Third Crisis Neon Nights © Anduo Games.
