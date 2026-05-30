# Third Crisis Neon Nights — Русский перевод / Russian localization

> 🚧 **В разработке** — инструментарий извлечения и перевода текста для игры **Third Crisis: Neon Nights** — киберпанк визуальной новеллы/RPG от **Anduo Games**.  
> Парсинг Unity serialized файлов (версия 22) без сторонних библиотек, на чистом Node.js.

**Поисковые теги:** `Third Crisis Neon Nights` `русская локализация` `русификатор` `Russian translation` `Anduo Games` `Unity` `PlayMaker` `визуальная новелла` `киберпанк` `перевод игры` `Node.js` `NDJSON`

---

## Об игре

**Third Crisis: Neon Nights** — самостоятельный приквел к Third Crisis, действие происходит через 3 года после мирового кризиса. Киберпанк-метрополия Neon City, коррумпированное правительство GAG, наёмница Зои Мэдисон. Выборы, соблазны, выживание. Жанр: RPG / Visual Novel. Движок: Unity 2022.3.62f3, скриптинг PlayMaker FSM.

Страницы: [Steam](https://store.steampowered.com/app/3400350/Third_Crisis_Neon_Nights/) · [Itch.io](https://anduogames.itch.io/third-crisis-neon-nights)

## Пайплайн

```
parser.mjs  →  NDJSON  →  extractor.mjs  →  NDJSON (dialogs + ui)
```

1. **parser.mjs** — читает бинарные файлы игры (level0-15, sharedassets0, Assembly-CSharp.dll), находит все null-terminated ASCII строки, сохраняет в NDJSON
2. **extractor.mjs** — читает NDJSON от парсера, классифицирует строки (dialogue / UI / noise), разбивает по source-файлам

## Использование

```bash
npm run parse                    # парсер (binary → NDJSON)
npm run extract                  # экстрактор (NDJSON → диалоги/UI)
npm run test:parse               # тесты парсера
```

## Формат NDJSON

Parser:

```json
[offset,"raw"]
[1131336,"In final Room Location Nova"]
```

Extractor:

```json
["{source}_{seq}","{original}","{translated}","{offset}"]
["level3_001","And now hold still I'm not done yet.","","641239"]
```

Третий элемент (`translated`) заполняется при переводе.

## Технический анализ

| Компонент     | Версия               | Примечание             |
| ------------- | -------------------- | ---------------------- |
| Unity         | 2022.3.62f3          | LTS                    |
| C# Runtime    | .NET 4.x (Mono)      | IL2CPP не используется |
| Сцены         | level0-level15       | 16 бинарных файлов     |
| Общие ресурсы | sharedassets0.assets | 34 MB                  |
| Основной код  | Assembly-CSharp.dll  | NToolkit framework     |
| Скриптинг     | PlayMaker FSM        | Визуальные скрипты     |

**Текст игры** хранится в data-секции level-файлов как null-terminated ASCII строки (не length-prefixed, как стандартный Unity). UI-строки (CONTINUE, NEW GAME) находятся в Assembly-CSharp.dll.

### Ключевые библиотеки (Managed/)

- PlayMaker — диалоги и логика на FSM
- spine-csharp / spine-unity — 2D скелетная анимация
- CsvHelper — парсинг CSV
- Lovense — интеграция с игрушками

## Структура репозитория

```
├── .opencode/skills/
│   ├── parse-unity/{parser.mjs, test.mjs}     # парсер
│   └── extractor/{extractor.mjs}               # экстрактор
├── output/
│   ├── parser/{manifest.json, *.ndjson}         # сырые строки
│   └── extractor/{dialogs/*.ndjson, ui/*.ndjson} # классифицированные строки
├── .vscode/
├── AGENTS.md               # правила проекта
├── THEORY.md                # техническая документация
├── package.json
└── README.md
```

## Требования

- Node.js 22+

## Лицензия

MIT — инструменты распространяются свободно.
Игра Third Crisis Neon Nights © Anduo Games.
