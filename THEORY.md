# Теория: Извлечение строк из Unity serialized файлов

> Документация для дипломной работы.
> Анализ формата и методология извлечения текста для локализации игры Third Crisis Neon Nights (Unity 2022.3.62f3).

---

## 1. Общая архитектура игры

### 1.1. Движок

| Компонент  | Значение                        |
| ---------- | ------------------------------- |
| Unity      | 2022.3.62f3 (LTS)               |
| Рендеринг  | URP (Universal Render Pipeline) |
| C# Runtime | .NET 4.x (Mono)                 |
| Скриптинг  | PlayMaker (FSM) + NToolkit      |

### 1.2. Файловая структура

```
Third Crisis Neon Nights_Data/
├── level0 — level15        — 16 бинарных Unity-сцен
├── sharedassets0.assets    — общие ресурсы
├── Managed/
│   ├── Assembly-CSharp.dll — NToolkit framework
│   └── PlayMaker.dll       — визуальный скриптинг
└── StreamingAssets/        — Addressables бандлы (~97 шт.)
```

Весь диалоговый текст и UI-надписи хранятся **внутри level файлов** (бинарные сцены).

---

## 2. Формат Unity serialized file

### 2.1. Общая структура

Каждый level/shareassets файл состоит из трёх секций:

```
┌─────────────────────────────┐
│         HEADER              │  ~60 байт
├─────────────────────────────┤
│        METADATA             │  ~1 МБ (все типы, объекты, ссылки)
├─────────────────────────────┤
│         DATA                │  весь остальной объём файла
└─────────────────────────────┘
```

### 2.2. Header (для Unity 2020+)

По результатам дампа level3 (7 371 304 байт):

| Смещение | Размер | Значение                  | Пояснение                             |
| -------- | ------ | ------------------------- | ------------------------------------- |
| 0x00     | 8      | `00 00 00 00 00 00 00 00` | Признак нового формата (Unity ≥ 2020) |
| 0x08     | 4      | `00 00 00 16`             | version = 22 (big-endian)             |
| 0x0C     | 4      | `00 00 00 00`             | dataOffset (старый, не используется)  |
| 0x10     | 1      | `00`                      | endianness: 0 = little                |
| 0x11     | 1      | `00`                      | reserved                              |
| 0x12     | 4      | `00 10 BD B5`             | **metadataSize** = 1 096 117 (BE)     |
| 0x16     | 4      | `00 00 00 00`             | padding                               |
| 0x1A     | 4      | `00 70 76 28`             | **fileSize** = 7 371 304 (BE)         |
| 0x1E     | 4      | `00 00 00 00`             | padding                               |
| 0x22     | 4      | `00 10 BD F0`             | **dataOffset** = 1 096 176 (BE)       |
| 0x26     | 4      | `00 00 00 00`             | padding                               |
| 0x2A     | 6      | нули                      | padding                               |
| 0x30     | 13     | `"2022.3.62f3\0"`         | Версия Unity                          |
| 0x3D     | 4      | `13 00 00 00`             | **headerSize** = 19 (в 4-байтсловах)  |

**Формулы:**

- `headerSize` = `dataOffset` − `metadataSize` = 1 096 176 − 1 096 117 = 59 байт
- `metadata %` = `metadataSize / fileSize` × 100% ≈ 14.9%
- metadata начинается с offset = `headerSize`
- data начинается с offset = `dataOffset`

### 2.3. Metadata

Metadata — это **Unity serialized объект**, который описывает сам себя. Содержит три ключевых раздела:

```
Metadata
├── enableTypeTree (1 байт)
├── typeTree (если enableTypeTree == 1)
│   └── для каждого класса:
│       ├── classID (int32)
│       ├── scriptID (Hash128 — 16 байт)
│       ├── baseClassID (int16)
│       ├── nodes: массив TypeTreeNode
│       │   └── для каждого поля:
│       │       ├── type (int16) — тип данных
│       │       ├── numFields (int16) — кол-во вложенных полей
│       │       ├── byteSize (uint32) — размер поля в байтах
│       │       ├── index (int32) — индекс в таблице
│       │       ├── metaFlag (uint32) — флаги сериализации
│       │       ├── name (aligned string) — имя поля
│       │       └── typeName (aligned string) — имя типа
│       └── stringBuffer — массив строк для имён полей
├── objectTable
│   └── для каждого GameObject:
│       ├── pathID (int64) — уникальный идентификатор
│       ├── byteStart (int64) — смещение в data секции
│       ├── byteSize (int64) — размер данных объекта
│       ├── typeID (int32) — ID типа (из typeTree)
│       └── classID (int32) — ID класса Unity
└── stringPool — все строковые константы (пути, имена)
```

### 2.4. Data секция

Data секция — это последовательность сырых бинарных блоков. Каждый блок соответствует одному объекту из ObjectTable.

Расположение: `fileOffset = dataOffset + object.byteStart`
Размер: `object.byteSize` байт

Внутри блока хранятся значения полей C# класса (MonoBehaviour) в порядке их объявления. Unity сериализует поля напрямую в бинарный вид.

---

## 3. Форматы хранения строк

### 3.1. Length-prefixed string (основной)

Используется для строковых полей MonoBehaviour:

```
┌─────────────────┬────────────────────┬──────────────┐
│ int32 length    │ UTF-8 data[length] │ padding to 4 │
│ (4 байта, LE)   │ (N байт)           │ (0-3 байта)  │
└─────────────────┴────────────────────┴──────────────┘
```

- Если `length > 0`: читаем `length` байт UTF-8
- Если `length == 0`: пустая строка (занимает 4 байта)
- Если `length < 0`: null-строка (занимает 4 байта)
- Выравнивание: общий размер всегда кратен 4

### 3.2. Aligned string (TypeTree)

Используется в TypeTree для имён полей и типов:

```
┌─────────────────┬────────────────────┬──────────────┐
│ int32 length    │ UTF-8 data[length] │ ALIGN to 4   │
│ (4 байта, LE)   │ (N байт)           │              │
└─────────────────┴────────────────────┴──────────────┘
```

Отличие от length-prefixed: даже если `length == 0`, выравнивание всё равно применяется.

### 3.3. Null-terminated string (C-string)

```
┌──────────────────────┬──────┐
│ ASCII data[length]   │ 0x00 │
└──────────────────────┴──────┘
```

Используется для:

- Имён объектов (m_Name)
- Тегов
- Внутренних путей Unity
- **Диалогового текста NToolkit** (данная игра)

Длина не указана — определяется положением нуль-терминатора.

**Важное открытие:** В Third Crisis Neon Nights диалоговый текст хранится
как null-terminated строки, а не length-prefixed. Это означает, что
стандартный Unity-формат (length-prefixed) не работает для поиска диалогов
в этой игре. Вместо этого нужен поиск null-terminated ASCII строк,
ограниченный data-секцией файла (для минимизации шума из TypeTree/метаданных).

---

## 4. Где искать строки в level файлах

### 4.1. PlayMakerFSM (classID = 114)

PlayMaker хранит строки в `FsmVariables.stringVariables[].value`:

```
PlayMakerFSM (MonoBehaviour)
├── FsmTemplate (optional)
├── FsmName: aligned string
├── FsmEvents: [FsmEvent]
├── FsmVariables:
│   ├── FloatVariables: [FsmFloat]
│   ├── IntVariables: [FsmInt]
│   ├── BoolVariables: [FsmBool]
│   ├── StringVariables: [FsmString]    ← ДИАЛОГИ
│   │   └── FsmString:
│   │       ├── name: aligned string
│   │       └── value: aligned string   ← строка диалога
│   ├── Vector3Variables: [FsmVector3]
│   └── ObjectVariables: [FsmObject]
└── FsmStates: [FsmState]
    └── Actions: [FsmStateAction]
```

**ClassID:** MonoBehaviour = 114 (но для PlayMakerFSM — кастомный скрипт)
**Метод поиска:** сканировать data блок на aligned strings

### 4.2. TextMeshPro (classID = 205)

```
TextMeshProUGUI (MonoBehaviour)
└── m_Text: aligned string    ← UI текст
```

**ClassID:** TMPro.TMP_Text = 205 (для UGUI варианта)
**Метод поиска:** первое aligned string поле в data блоке

### 4.3. GameObject (classID = 1)

```
GameObject
├── m_Name: aligned string    ← имя объекта
├── m_Component: [PPtr<Component>]
└── m_Layer: int32
```

Имя объекта часто содержит текст диалогов (когда объект назван по первой фразе).

---

## 5. Методология бинарного поиска

### 5.1. Архитектура пайплайна

Извлечение строк разделено на два независимых этапа:

1. **Parser** (`parser.mjs`) — читает бинарные файлы, извлекает все null-terminated ASCII строки из data-секции, выводит NDJSON: `[offset,"raw"]`
2. **Extractor** (`extractor.mjs`) — читает NDJSON от парсера, классифицирует строки (dialogue / UI / noise), выводит NDJSON для перевода: `["{source}_{seq}","{original}","{translated}","{offset}"]`

### 5.2. Parser: Data section null-terminated search

```
1. Parse header → dataOffset
2. Slice data section: buf.slice(dataOffset)
3. for each byte in data section:
     if printable ASCII → build string
     else:
       if string has >= 40% letters and length 4-500 → save with offset
       reset buffer
4. Write per-file NDJSON + manifest.json (headers + stats)
```

**Преимущества перед сканированием всего файла:**

- Без шума TypeTree (имена типов, классов)
- Без шума StringPool (внутренние строки путей)
- Без шума шейдеров и бинарных данных ресурсов
- В 2-10× быстрее (сканируется только data секция)

Также поддерживает raw-файлы (DLL) — сканирование всего файла целиком.

### 5.3. Extractor: классификация

Extractor применяет эвристики для разделения строк на три категории:

- **dialogue** — реплики персонажей (минимальная длина 12 символов, 3+ слова, common English words, без noise-слов)
- **UI** — строки интерфейса (ALL CAPS, длина 2-60)
- **noise** — всё остальное (FSM-состояния, имена объектов, пути)

После классификации группирует по source-файлам и выводит NDJSON с sequential ID:
```
["level3_001","And now hold still I'm not done yet.","","641239"]
["level3_002","(I hope she's okay.)","","642001"]
```

### 5.3. Object table guided extraction (перспективный метод)

```
1. Parse header → metadataOffset, dataOffset
2. Parse metadata → extract ObjectTable
3. For each object in ObjectTable:
   - if classID == 114 (MonoBehaviour) or 205 (TextMeshPro):
     - read data block at dataOffset + byteStart
     - scan for strings
4. No need to scan entire file
```

**Текущий статус:** ObjectTable не найден в metadata — структура
метаданных Unity 22 не соответствует документации. Парсинг metadata
требует обратной инженерии формата.

---

## 6. Результаты бинарного анализа

### 6.1. Статистика по файлам

| Файл          | Размер   | version | dataOffset | Строк (raw) | Диалогов | UI  |
| ------------- | -------- | ------- | ---------- | ----------- | -------- | --- |
| level0        | 0.11 MB  | 22      | 980        | 533         | 37       | 0   |
| level1        | 0.06 MB  | 22      | 648        | 130         | 8        | 0   |
| level2        | 0.13 MB  | 22      | 1 108      | 478         | 13       | 1   |
| level3        | 7.03 MB  | 22      | 1 097 200  | 46 040      | 1 532    | 3   |
| level4        | 1.77 MB  | 22      | 270 400    | 13 828      | 633      | 2   |
| level5        | 1.84 MB  | 22      | 281 176    | 11 483      | 500      | 1   |
| level6        | 1.51 MB  | 22      | 314 372    | 4 607       | 88       | 1   |
| level7        | 12.84 MB | 22      | 1 933 020  | 67 188      | 2 434    | 3   |
| level8        | 0.93 MB  | 22      | 144 848    | 5 130       | 132      | 1   |
| level9        | 2.05 MB  | 22      | 309 400    | 12 150      | 525      | 0   |
| level10       | 2.59 MB  | 22      | 390 376    | 15 647      | 754      | 0   |
| level11       | 3.32 MB  | 22      | 499 340    | 13 152      | 532      | 0   |
| level12       | 1.41 MB  | 22      | 221 396    | 9 078       | 494      | 1   |
| level13       | 1.22 MB  | 22      | 194 548    | 6 364       | 147      | 6   |
| level14       | 1.20 MB  | 22      | 190 876    | 5 679       | 102      | 3   |
| level15       | 4.06 MB  | 22      | 608 704    | 14 429      | 370      | 5   |
| sharedassets0 | 34.45 MB | 22      | 66 144     | 396 069     | 153      | 136 |
| Assembly-CSharp.dll | 3.75 MB | —  | —          | 27 678      | 2 504    | 11  |

**Всего:** 649 663 сырых строк → **10 958 диалогов + 174 UI** (после фильтрации extractor-ом)

### 6.2. Примеры найденных строк

```
In final Room Location Nova
Top right of Zoey
Fade in Room when entering
In Room Light
Upstairs in Room Door Trigger
Talking Walla in Downstairs Bar
Femboy walk out of Bathroom Position
Follow Her Cutscene
Scolding in Backroom Cutscene
Zoey in area trigger
```

### 6.3. Реальные примеры диалогов

```
"I don't know..." I murmur, fidgeting.
(I hope she's okay.)
(If only Sarah was here to see it...)
(Oh Jeez- Don't look down, Zoey...)
10-4. We will keep trying.
All this because of some 10-37 in the Red?
And now hold still I'm not done yet.
"Obedience Oral Therapy" is what they call it, heh.
```

### 6.4. Проблема разделения диалогов и FSM-логики

Большинство найденных строк (~82%) — это не диалоги, а имена состояний и
переменных PlayMaker FSM, а также описания действий из PlayMaker-документации
(из Assembly-CSharp.dll):

- `Are we in progress?` — состояние FSM, не диалог
- `Did talk to Cal already?` — условие FSM
- `Bind Display for Selectable Variant` — свойство UI
- `-A Vertical Slider linked to a Float Variable.` — описание FSM action

### 6.5. Оценка покрытия

| Метод                      | Всего строк | Чистых диалогов | Доля |
| -------------------------- | ----------- | --------------- | ---- |
| Parser (data section)      | 649 663     | —               | —    |
| Extractor (dialogue)       | 10 958      | ~1 500-2 000    | ~15% |
| Extractor (UI)             | 174         | 174             | 100% |

Слабое место: фильтр `isDialogue()` слишком широкий — пропускает
документационные строки из DLL и имена FSM-состояний.
UI-фильтр точный, но основная часть UI-строк (CONTINUE, NEW GAME, OPTIONS)
не найдена — они хранятся не как plain text в файлах игры.

---

## 7. Проблемы и решения

### 7.1. Замкнутый круг метаданных

**Проблема:** Metadata сериализована как Unity serialized объект. Чтобы прочитать ObjectTable, нужно распарсить metadata. Чтобы распарсить metadata, нужно знать структуру `SerializedFileMetadata` — которая описана TypeTree внутри самой metadata.

**Решение:** Структура `SerializedFileMetadata` фиксирована для данной версии Unity. Для Unity 22 она известна и может быть закодирована напрямую в парсере, без чтения TypeTree.

```
SerializedFileMetadata {
  enableTypeTree: bool (1 байт)
  typeTree: TypeTree (читаем только если нужно)
  objectTable: ObjectInfo[]
  virtualCallbackIDs: int[]
  sharedObjectTable: SharedObjectInfo[]
  externalRefs: ExternalRef[]
  refTypes: RefType[]
  ...
}
```

### 7.2. Идентификация MonoBehaviour

**Проблема:** У MonoBehaviour нет фиксированного classID — он зависит от сериализованного скрипта. Каждый кастомный C# класс (PlayMakerFSM, DialogueController) получает свой classID через `MonoScript`.

**Решение:** Использовать `scriptID` (Hash128 — 16 байт) из TypeTree для идентификации конкретных скриптов. В TypeTree для каждого класса указан `scriptID`.

### 7.3. Выравнивание строк

**Проблема:** Unity выравнивает данные до 4 байт, но не всегда очевидно, где заканчивается одно поле и начинается другое.

**Решение:** Использовать `byteSize` из TypeTree для каждого поля — Unity гарантирует, что поле занимает ровно byteSize байт.

---

## 8. Технический стек (самописный)

| Компонент        | Технология         | Обоснование                                        |
| ---------------- | ------------------ | -------------------------------------------------- |
| Парсер файлов    | Node.js 22+        | Кроссплатформенность, встроенная работа с Buffer   |
| Извлечение строк | Node.js Buffer API | Чтение бинарных данных без внешних библиотек       |
| Анализ перевода  | Node.js fs         | Чтение/запись текстовых файлов                     |
| Пакетный перевод | Node.js fetch      | HTTP-запросы к Google Translate (встроенный fetch) |

**Запрещённые инструменты** (не используются):

- Сторонние библиотеки для парсинга Unity (Python, .NET)
- Сторонние декомпиляторы
- Любые npm-пакеты для парсинга Unity

---

## 9. Ключевые классы Unity (classID)

| classID | Тип                       | Содержит текст              |
| ------- | ------------------------- | --------------------------- |
| 1       | GameObject                | m_Name                      |
| 4       | Transform                 | —                           |
| 21      | Material                  | —                           |
| 23      | MeshRenderer              | —                           |
| 28      | Texture2D                 | —                           |
| 48      | Mesh                      | —                           |
| 49      | TextAsset                 | Текстовые файлы             |
| 114     | MonoBehaviour             | **Да** — основное хранилище |
| 128     | Font                      | —                           |
| 205     | TMPro.TMP_Text            | **Да** — UI текст           |
| 212     | MonoBehaviour (PlayMaker) | **Да** — диалоги            |

---

## 10. Заключение

Бинарный поиск ASCII-строк даёт ~30-40% текста с высоким уровнем шума. Для полного извлечения необходим **структурный парсинг Unity serialized формата**: чтение ObjectTable и сканирование data-блоков MonoBehaviour на length-prefixed строки. Это реализуемо на чистом Node.js без сторонних библиотек, так как структура метаданных известна и стабильна для Unity 22.

---

_Документ создан в рамках анализа локализации Third Crisis Neon Nights (Anduo Games, Unity 2022.3.62f3)._
