# Third Crisis: Neon Nights — Русская локализация

> Инструментарий для извлечения, перевода и рантайм-замены текста игры **Third Crisis: Neon Nights** (Anduo Games).
> Парсинг Unity serialized данных (версия 22) на чистом Python + рантайм-переводчик C# через scan-and-replace.

**Поисковые теги:** `Third Crisis Neon Nights` `русская локализация` `русификатор` `Russian translation` `Anduo Games` `Unity 2022.3` `PlayMaker` `визуальная новелла` `киберпанк` `перевод игры` `Python` `NDJSON` `BepInEx`

---

## Об игре

**Third Crisis: Neon Nights** — приквел к Third Crisis, действие через 3 года после мирового кризиса. Киберпанк-метрополия Neon City, коррумпированное правительство GAG, наёмница Зои Мэдисон. Выборы, соблазны, выживание. RPG / Visual Novel на Unity 2022.3.62f3 (URP) со скриптингом PlayMaker FSM.

Страницы: [Steam](https://store.steampowered.com/app/3400350/Third_Crisis_Neon_Nights/) · [Itch.io](https://anduogames.itch.io/third-crisis-neon-nights)

---

## Пайплайн локализации

```
parser.py --dialogue ─→ translations/dialogs/dialogue.ndjson (1544 диалога)
parser.py --texts    ─→ translations/texts/ui.ndjson         (102 UI строки)
parser.py --characters ─→ translations/characters.ndjson      (24 персонажа)
                              │
                              ▼ (перевод → деплой)
                   build.py → NeonTranslatorRuntime.dll
                   build_proxy.py → dwmapi.dll (native proxy)
```

Все переводы — плоские NDJSON-файлы без вложенности. Копируются в `Managed/` для загрузки рантаймом.

---

## Быстрый старт

```bash
python .opencode/skills/extract-text/parser.py --dialogue    # диалоги
python .opencode/skills/extract-text/parser.py --texts       # UI
python .opencode/skills/extract-text/parser.py --characters  # персонажи
python .opencode/skills/extract-text/parser.test.py          # тесты парсера (43)
python .opencode/skills/build-translator/build.py       # сборка DLL
python .opencode/skills/build-translator/build.test.py  # тесты сборки
python .opencode/skills/build-translator/build_proxy.py # сборка прокси
```

---

## Ключевые открытия (технические)

### Диалоги: DialogueHistory в resources.assets

Вся структура диалогов (Speaker + Text + color) хранится в сериализованном массиве `DialogueHistory` внутри `resources.assets`. 1544 записи, 24 уникальных спикера.

### UI: TMP_Text + Settings.* ключи

UI-текст читается из TMP_Text компонентов во всех level/бандлах + ANToolkit локализационные ключи `Settings.*`. 102 строки: настройки, меню, интерфейс.

### Addressables .bundle: только 4 с текстом

Из 97 бандлов только 4 содержат UI текст: level-cartelhideout, level-glowinghole, 3dsuitcasescene, releasenotesui.

### Scan-and-Replace вместо патча

Перевод в оперативной памяти через NeonLateUpdate + Canvas.willRenderCanvases. Бинарники игры не модифицируются. Длина перевода не ограничена.

---

## Формат NDJSON

**Диалоги:**
```ndjson
["I don't know...","Я не знаю...","Zoey"]
```

**UI:**
```ndjson
["Resolution Scaling","Масштабирование разрешения"]
```

**Персонажи:**
```ndjson
["Zoey","Зои","ж"]
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
| Диалогов всего           | 1 544     |
| UI-строк                 | 102       |
| Персонажей               | 24        |
| Settings.\* ключей       | 57        |
| Парсер                   | parser.py (Python) |
| Рантайм                  | NeonTranslatorRuntime.dll (C#) |

---

## Структура репозитория

```
├── .opencode/
│   ├── agents/
│   │   └── translate-expert.md       # агент-переводчик для opencode
│   └── skills/
│       ├── extract-text/
│       │   ├── parser.py          # парсер Unity serialized (Python)
│       │   ├── parser.test.py     # 43 теста
│       │   └── SKILL.md
│       ├── build-translator/
│       │   ├── source/               # C# исходники
│       │   ├── build.py              # сборка DLL
│       │   ├── build_proxy.py        # сборка dwmapi.dll
│       │   └── SKILL.md
│       └── deploy-translator/
│           └── SKILL.md
├── translations/
│   ├── dialogs/dialogue.ndjson       # диалоги (1544)
│   ├── texts/ui.ndjson               # UI строки (102)
│   └── characters.ndjson             # персонажи (24)
├── runtime/
│   └── NeonTranslatorRuntime.dll     # скомпилированная DLL
├── AGENTS.md                         # правила проекта для opencode
├── THEORY.md                         # техническая документация
└── README.md
```

## Требования

- Python 3.11+
- .NET Framework SDK (csc.exe) — для сборки DLL
- MSVC Build Tools (cl.exe) — для сборки прокси
- Игра Third Crisis: Neon Nights (Steam)

## Лицензия

MIT — инструменты распространяются свободно.
Игра Third Crisis Neon Nights © Anduo Games.
