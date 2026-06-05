# Теория: Извлечение строк и рантайм-перевод Third Crisis Neon Nights

> Документация для проектной работы.
> Анализ формата, методология извлечения текста и архитектура рантайм-переводчика для игры Third Crisis Neon Nights (Unity 2022.3.62f3).

---

Разделы 1–4, 7.1–7.3, 7.4.1–7.4.3, 7.4.5–7.4.6, 11 описывают техническое устройство Unity serialized формата и архитектуру рантайм-переводчика — они актуальны. Разделы 5–6, 7.4.4, 8, 10, 12 обновлены под текущий пайплайн (`dump_assets.py` + `extractor.py`).

## 1. Общая архитектура игры

### 1.1. Движок

| Компонент  | Значение                        |
| ---------- | ------------------------------- |
| Unity      | 2022.3.62f3 (LTS)               |
| Рендеринг  | URP (Universal Render Pipeline) |
| C# Runtime | .NET 4.x (Mono)                 |
| Скриптинг  | PlayMaker (FSM) + AANToolkit    |

### 1.2. Файловая структура

```
Third Crisis Neon Nights_Data/
├── level0 — level15        — 16 бинарных Unity-сцен
├── sharedassets0.assets    — общие ресурсы
├── Managed/
│   ├── Assembly-CSharp.dll — ANToolkit framework
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
- **Диалогового текста ANToolkit** (данная игра)

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

## 5. Методология извлечения

### 5.1. Архитектура пайплайна (текущая)

Пайплайн двухступенчатый:

1. **`dump_assets.py`** — читает все `.assets` файлы игры через UnityPy, дампит структурированные JSON в `dump_assets/` (Object Table + Type Tree + typed fields, а также raw-скан для диалогов)
2. **`extractor.py`** — читает JSON-дампы, собирает 3 типа YAML-файлов в `translations/`:
   - `dialogues.{path_id}.yaml` — `["text", "translation", "speaker"]` (1793 записи, 4 источника)
   - `speakers.yaml` — `["name", "translation", "gender"]` (23 спикера)
   - `settings_keys.yaml` — `["key", "translation"]` (55 UI-строк)

Никакого прямого парсинга бинарников — всё через UnityPy-дампы.

### 5.2. Data section null-terminated search (исторический метод)

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

### 5.2b. Raw-файлы (DLL) — UTF-16 LE извлечение

Для .NET сборок (Assembly-CSharp.dll) строки могут храниться в двух форматах:

1. **Null-terminated ASCII** — классические C-строки в PE секциях (методы, комментарии)
2. **UTF-16 LE** — строковые литералы .NET (#US heap метаданных)

UTF-16 LE детекция использует двухпроходное сканирование:

```
ПРОХОД 1 (чётное выравнивание):
  for i in 0, 2, 4, ...:
    если buf[i] in 32-126 AND buf[i+1] == 0:
      накопить символ
    иначе:
      если длина >= 4 и >=40% букв — сохранить

ПРОХОД 2 (нечётное выравнивание):
  то же, но с i = 1, 3, 5, ...
```

Два прохода необходимы из-за возможного смещения alignment'а внутри .NET метаданных. Дедупликация по offset через Map.

Также поддерживает raw-файлы (DLL) — сканирование всего файла целиком.

### 5.3. Structured extraction: DialogueHistory (текущий метод)

В отличие от сырого ASCII-поиска, `dump_assets.py` через UnityPy читает **напрямую** сериализованный массив `DialogueHistory` внутри `resources.assets`. Формат записи:

```
DialogueHistory (MonoBehaviour)
├── m_Script: PPtr<MonoScript>
├── m_Name: aligned string
├── Speakers: MonoBehaviour[]         ← массив спикеров
│   └── speakerName: string
├── DialogueEntries: MonoBehaviour[]  ← массив диалогов
│   ├── speakerIndex: int32
│   ├── dialogueText: string          ← текст реплики
│   └── textColor: Color
```

Каждый диалог — структурированный объект, а не строка в сырой data-секции.

### 5.4. Object table guided extraction (перспективный метод)

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

### 6.1. Статистика по файлам (v3 — все .assets + level + DLL, историческая)

Данные ниже — от старого `parser.mjs` (сырой ASCII-поиск), оставлены для референса.
Текущий `dump_assets.py` + `extractor.py` обрабатывает все 34 `.assets` файла через UnityPy.

| Файл                          | Размер   | version | Строк (raw) | UI      |
| ----------------------------- | -------- | ------- | ----------- | ------- |
| level0                        | 0.11 MB  | 22      | 1 084       | 0       |
| level1                        | 0.06 MB  | 22      | 258         | 0       |
| level2                        | 0.13 MB  | 22      | 938         | 0       |
| level3                        | 7.03 MB  | 22      | 90 761      | 307     |
| level4                        | 1.77 MB  | 22      | 27 362      | 56      |
| level5                        | 1.84 MB  | 22      | 22 868      | 29      |
| level6                        | 1.51 MB  | 22      | 8 805       | 10      |
| level7                        | 12.84 MB | 22      | 131 889     | 388     |
| level8                        | 0.93 MB  | 22      | 9 003       | 64      |
| level9                        | 2.05 MB  | 22      | 23 895      | 44      |
| level10                       | 2.59 MB  | 22      | 31 204      | 71      |
| level11                       | 3.32 MB  | 22      | 25 710      | 60      |
| level12                       | 1.41 MB  | 22      | 17 936      | 21      |
| level13                       | 1.22 MB  | 22      | 12 634      | 72      |
| level14                       | 1.20 MB  | 22      | 11 110      | 57      |
| level15                       | 4.06 MB  | 22      | 27 361      | 108     |
| sharedassets0                 | 34.39 MB | 22      | 405 457     | 2 483   |
| sharedassets1                 | 0.61 MB  | 22      | 2 352       | 0       |
| sharedassets2                 | 0.40 MB  | 22      | 3 651       | 0       |
| sharedassets3                 | 7.18 MB  | 22      | 73 589      | 12 455  |
| sharedassets4                 | 2.66 MB  | 22      | 30 605      | 7 044   |
| sharedassets5                 | 4.30 MB  | 22      | 39 817      | 4 444   |
| sharedassets6                 | 0.75 MB  | 22      | 2 650       | 0       |
| sharedassets7                 | 3.45 MB  | 22      | 36 672      | 2 428   |
| sharedassets8                 | 0.77 MB  | 22      | 9 658       | 113     |
| sharedassets9                 | 0.19 MB  | 22      | 1 063       | 0       |
| sharedassets10                | 0.65 MB  | 22      | 1 147       | 0       |
| sharedassets11                | 0.54 MB  | 22      | 4 732       | 0       |
| sharedassets12                | 0.79 MB  | 22      | 9 457       | 0       |
| sharedassets13                | 0.09 MB  | 22      | 74          | 0       |
| sharedassets14                | 0.09 MB  | 22      | 41          | 0       |
| sharedassets15                | 2.94 MB  | 22      | 20 709      | 2 538   |
| resources                     | 78.90 MB | 22      | 984 103     | 714 876 |
| globalgamemanagers            | 1.97 MB  | 22      | 80 970      | 7 486   |
| Assembly-CSharp.dll           | 3.75 MB  | —       | 30 284      | 3 744   |
| Assembly-CSharp-firstpass.dll | 0.53 MB  | —       | 7 697       | 269     |

**Всего:** 2 187 546 сырых строк → **24 086 диалогов + 757 971 UI**

> Статистика выше — от старого `parser.mjs` (исторический метод). Текущий `extractor.py` не использует сырой ASCII-поиск.

### 6.1b. Статистика по бандлам (v2 — Addressables .bundle files)

| Бандл               | Размер | Строк (raw) | UI      |
| ------------------- | ------ | ----------- | ------- |
| level-cartelhideout | ~35 MB | 640 453     | 212 799 |
| level-glowinghole   | ~68 MB | 1 310 529   | 399 935 |
| 3dsuitcasescene     | ~2 MB  | 17 546      | 5 199   |
| releasenotesui      | ~1 MB  | 12 655      | 4 603   |

**Итого (v1 + v2):** 3 848 483 сырых строк → **~19K диалогов + 1.29M UI**

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

### 6.5. Оценка покрытия (текущая)

| Метод                                 | Всего     | Формат |
| ------------------------------------- | --------- | ------ |
| extractor.py (диалоги)                | 1 793     | YAML   |
| extractor.py (UI settings_keys)       | 55        | YAML   |
| extractor.py (speakers)               | 23        | YAML   |

**100% точность, 0% шума** — данные из структурированных Unity-объектов (DialogueHistory),
без сырого ASCII-поиска. Дедупликация в пределах каждого path_id.

Слабое место исторического метода (parser.mjs): фильтр `isDialogue()` слишком широкий — пропускал
документационные строки из DLL и имена FSM-состояний.

### 6.6. ANToolkit Localization: Settings.\* key system

Основная часть UI-текста настроек (Video, Game, Sound, Controls, Toys tabs +
~50 настроек) хранится в `resources.assets` в виде **aligned strings** с паттерном:

```
Settings.VideoTab       → "Video"
Settings.GameTab        → "Game"
Settings.Fullscreen     → "Fullscreen"
Settings.EnableVSync    → "Enable VSync"
Settings.FPSLimit       → "FPS Limit"
```

Каждая запись дублируется дважды (key + display text, каждый по 2 копии):

```
[offset A] Settings.Fullscreen
[offset A+4] Settings.Fullscreen
[offset A+24] Fullscreen
[offset A+28] Fullscreen
```

Это стандартный формат **ANToolkit localization**: ключ `Settings.XXX` и отображаемый текст.
Всего найдено **58 уникальных Settings.\* ключей** с соответствующими display text.

**Важное дополнение:** 4 UI-строки Video-таба (Resolution Scaling, Environment Effects,
Realtime Reflections, Post Processing) не имеют собственных `Settings.*` ключей.
Они хранятся как **UTF-16 LE строки** внутри Assembly-CSharp.dll, следуя после
`Settings.Resolution` с префиксными type-тегами сериализации (0x25, 0x27, 0x29, 0x1f).

```
Settings.Resolution → %Resolution Scaling | 'Environment Effects | )Realtime Reflections | \x1fPost Processing
```

Это sub-опции `Settings.Resolution`, которые отображаются на UI через `ToUpper()`:
`RESOLUTION SCALING`, `ENVIRONMENT EFFECTS`, `REALTIME REFLECTIONS`, `POST PROCESSING`.

Список ключей включает:

- **Tabs:** ControlsTab, GameTab, VideoTab, SoundTab, ToysTab, LewderShooterTab
- **Video:** Fullscreen, Resolution, FPSLimit, EnableVSync, DynamicLighting, TextureQuality
- **Game:** DialogueAutoplay (with sub: Off, Slow, Normal, Fast), GrassDetail (Deactivated, Low, High, Ultra), Language (Machine Translation), ShowFPS, ShowAdvancedPerformanceStats, etc.
- **Sound:** MusicVolume, EffectsVolume
- **Controls:** MouseSensitivity, MovementSpeed, UseVirtualJoystick, etc.
- **Toys:** Lovense (Enabled, IP, Port, UseHTTP, Setup, Buy, DialogueLine, UserInterface, NativeSetup, Search), SeasonalEvents, EnableMultiplayer
- **Values:** Off, On, High, Medium, Low, Ultra, Deactivated, Slow, Normal, Fast

Меню навигация (Options, Back, Reset to Default) находится в `sharedassets0.assets`.

---

## 6.7. Addressables Bundle формат (UnityFS)

### 6.7.1. Общая структура

Бандлы находятся в `StreamingAssets/aa/StandaloneWindows64/*.bundle` (~97 файлов).
Формат: **UnityFS v8**, LZ4HC сжатие.

```
┌──────────────────────────────┐
│  UnityFS Header (64 байт)    │
├──────────────────────────────┤
│  LZ4-сжатый Header (перемен.)│  ← только заголовок сжат!
├──────────────────────────────┤
│  Data Area (не сжата)        │  ← raw бинарные данные
└──────────────────────────────┘
```

### 6.7.2. UnityFS Header

| Смещение | Размер | Поле               | Формат    |
| -------- | ------ | ------------------ | --------- |
| 0x00     | 7      | Сигнатура          | "UnityFS" |
| 0x07     | 1      | Версия             | uint8 = 8 |
| 0x08     | 5      | Игровая версия     | "2022.3"  |
| 0x0D     | 1      | Engine version len | uint8     |
| 0x0E     | N      | Engine version     | ASCII     |
| ...      | ...    | ...                | ...       |
| 0x26     | 4      | Compressed size    | uint32 BE |
| 0x2A     | 4      | Decompressed size  | uint32 BE |
| 0x2E     | 4      | Flags              | uint32 BE |
| 0x32     | 30     | Padding            |           |

- Flags & 0x3F = compression type (3 = LZ4, 4 = LZMA)
- Header начинается с offset 64
- Data Area начинается: offset = 64 + compressedHeaderSize

### 6.7.3. CAB (Content Archive) узлы

После декомпрессии заголовка, CAB ноды следуют формату:

```
[path\0][offset 4BE][size 4BE][flags 4BE]
```

Где:

- **path** — null-terminated ASCII путь (имя ассета)
- **offset** — 4-байтовое смещение в data area (Big-Endian)
- **size** — 4-байтовый размер (Big-Endian)
- **flags** — 4-байтовые флаги (Big-Endian)

### 6.7.4. Data Area: не сжата

**Ключевое открытие:** Data area бандлов НЕ СЖАТА. Только заголовок (UnityFS header metadata) сжат LZ4. Data area — это raw бинарная память, которую можно сканировать напрямую.

Это означает, что все текстовые строки в бандлах читаемы как ASCII без декомпрессии.

### 6.7.5. Метод извлечения: raw ASCII scanning

```
1. Прочитать файл
2. Проверить сигнатуру "UnityFS"
3. Распарсить UnityFS header
4. Декомпрессировать LZ4-заголовок (pure JS lz4 block decoder)
5. Взять data area как Buffer.subarray(hdr.dataStart)
6. Сканировать на ASCII строки (byte >= 32 && < 127)
7. Фильтр: >= 4 символа, содержит 3+ буквы
8. Записать NDJSON: [offset, "raw"]
```

### 6.7.6. Pure JS LZ4 block decoder

Стандартный LZ4 block format:

```
Token (1 byte):
  high nibble = literal length
  low nibble  = match length - 4

After token:
  Literals (literal length bytes)
  Match offset (2 bytes LE)
  Match (match length bytes from matchPos)

Extended lengths:
  If literal length == 15 → add bytes until < 255
  If match length == 19 → add bytes until < 255
```

### 6.7.7. Какие бандлы содержат UI текст

Из 97 бандлов только 4 содержат значимые строки для перевода:

| Бандл               | Назначение         |
| ------------------- | ------------------ |
| level-cartelhideout | Сцена картеля      |
| level-glowinghole   | Сцена Glowing Hole |
| 3dsuitcasescene     | Сцена чемодана     |
| releasenotesui      | Release notes UI   |

Остальные бандлы (pinup, sexscene, music, sfx, background, etc.) содержат
только текстуры, шейдеры, анимации — без переводимого текста UI.

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

## 7.4. Длина перевода: бинарный патч vs рантайм-замена

**Проблема:** При переводе строки «Resolution» (10 символов) на русский
«Разрешение экрана» (18 символов) бинарный патч невозможен — данные не
влезают в исходный offset.

**Три подхода:**

| Метод                         | Ограничение                     | Сложность | Статус      |
| ----------------------------- | ------------------------------- | --------- | ----------- |
| Бинарный патч (write-back)    | translated ≤ original           | Низкая    | Отклонён    |
| Сдвиг данных + патч ссылок    | translated > original (сложный) | Высокая   | Отклонён    |
| **Scan-and-Replace** (выбран) | **Без ограничений**             | Средняя   | ✅ Работает |

Никакие бинарники игры не модифицируются. Перевод работает только в
оперативной памяти.

### 7.4.1. Scan-and-Replace — архитектура (текущая)

```
Игра: TMP_Text.text = "Resolution"
                        │
               ┌────────┴─────────┐
               │   NeonLateUpdate │
               │  [DefaultExecOrd │
               │   er=10000]      │
               │   ↓              │
               │  PopulateAllText │
               │  Public()        │
               │   ├─FindObjects  │
               │   ├─replace match│
               │   └─FastScan re- │
               │     register     │
               │                  │
               │  Canvas.         │
               │  willRenderCanv  │
               │  ases → FastScan │
               │  (last handler)  │
               │                  │
               │  PostRebuild     │
               │  (force rebuild) │
               │                  │
               │ Dictionary:      │
               │ "Resolution" →   │
               │ "Разрешение      │
               │  экрана"         │
               └────────┬─────────┘
                        │
               Любая длина!
                        ▼
     На экране: "Разрешение экрана"
```

**Три фиксера (в порядке вызова):**

1. **PopulateAllTextPublic()** — вызывается из `LateUpdate()` каждым
   `NeonLateUpdate` (exec order 10000). `FindObjectsOfType` + замена по
   словарю. Затем снимает и вешает `FastScan` на `Canvas.willRenderCanvases`
   заново, чтобы `FastScan` гарантированно был последним в списке
   (другие хендлеры могут добавляться между сканами).

2. **FastScan** — висит на `Canvas.willRenderCanvases` через
   `Canvas.willRenderCanvases += FastScan`. Срабатывает ПОСЛЕ того, как
   все Canvas перестроили свой текст (но ДО отрисовки). Сканирует ещё раз
   и заменяет. **Критично:** перерегистрируется каждый кадр, чтобы быть
   последним в списке делегатов.

3. **PostRebuildHandler** — висит на `TMPro_EventManager.OnPreRenderObject`
   (он же `TMP_ResourceManager.OnPreRenderObject`). Если текст был
   изменён через `SetTextFieldDirect` (без `SetAllDirty`), принудительно
   вызывает `SetAllDirty()` для свежезаменённых строк.

**Почему не JMP hook?** JMP-хук на `set_text` был реализован
(MethodPatcher.cs), но deactivated — native detour через
`VirtualProtect + E9 JMP` приводил к повреждению UI некоторых
компонентов (LayoutGroup, ContentSizeFitter). Scan-and-Replace
надёжнее и безопаснее для Production.

### 7.4.2. Механизм доставки DLL

Игра не вызывает нашу DLL напрямую, и BepInEx не может загрузить
стороннюю DLL без плагина. Решение — **native proxy DLL**:

```
dwmapi.dll (наш прокси, 13.5 KB)
  ├── 32 экспорта forwarded → dwmapi_real.dll
  └── 2 перехваченных экспорта (бутстрап NeonTranslatorRuntime)
        └── DwmSetWindowAttribute / DwmGetWindowAttribute

dwmapi_real.dll (оригинальная, 187 KB)
  └── переименована, все вызовы Unity проходят через неё
```

1. `dwmapi.dll` — единственная DLL из imports UnityPlayer.dll,
   чьи экспорты гарантированно вызываются при старте (2 из 34 экспортов
   используются Unity: `DwmSetWindowAttribute`, `DwmGetWindowAttribute`)

2. При первом вызове — `BootstrapTranslator()`:
   - Загружает `mono-2.0-bdwgc.dll` (Mono runtime игры)
   - Открывает `NeonTranslatorRuntime.dll` через `mono_domain_assembly_open`
   - Вызывает `TranslatorPlugin.Initialize()` через `mono_runtime_invoke`

3. `Initialize()` (C#) — вызывается через `mono_runtime_invoke`:
   - Загружает словарь из `NeonTranslatorRuntime_Data.ndjson`
   - Создаёт `new GameObject("NeonTranslator")` +
     `AddComponent<NeonLateUpdate>()` — нативный Unity-контекст,
     где Update/LateUpdate работают корректно
   - Регистрирует `SceneManager.sceneLoaded` хендлер (перезапуск сканирования)

4. `NeonLateUpdate` (MonoBehaviour, `[DefaultExecutionOrder(10000)]`):
   - `LateUpdate()` → `PopulateAllTextPublic()`:
     - Использует кэш: `_cachedComponents` (заполнен в OnPreRender)
     - Для каждого: сверяет текст со словарём, заменяет при совпадении
   - `willRenderCanvases` → `OnPreRender()`:
     - `InvalidateCache()` — сбрасывает флаг кэша
     - `ScanAllUiLocs()` — инжектит русские переводы в ANToolkit "Russian" + "English" словари
     - `PopulateAllText()` — перестраивает кэш через `FindObjectsOfType` + заменяет
   - ANToolkit injection: игра сама ставит русский текст через
     UILocalization компоненты, кэширование предотвращает пер-фрейм оверхед
   - Логирует замены в `NeonTranslator.log` (до 30 строк, затем summary)

### 7.4.3. Проблема Monobehaviour.Update (решена)

**Найдено эмпирически:** `GameObject.AddComponent<MonoBehaviour>()`,
вызванный из `mono_runtime_invoke` (native → C#), создаёт рабочий
GameObject (Awake/OnEnable срабатывают), но Update() никогда не вызывается.
Unity не регистрирует такой скрипт в игровом цикле, если он создан до
завершения инициализации Unity.

**Решение v1 (промежуточное):** Вместо `MonoBehaviour.Update` —
`System.Threading.Timer` + `SynchronizationContext.Post`. Работало,
но давало задержку 0-500ms (английский был виден до сканирования).

**Решение v2 (текущее):** Вместо Timer — `[DefaultExecutionOrder(10000)]`
на класс `NeonLateUpdate` (MonoBehaviour). Запускается через
`RuntimeInitializeOnLoadMethod` + `new GameObject().AddComponent()`,
что даёт нативный Unity-контекст, где Update() работает корректно.
Execution order 10000 гарантирует, что `NeonLateUpdate` срабатывает
ПОСЛЕ всех игровых LateUpdate (которые могут перезаписывать текст
на английский).

### 7.4.4. Переводной словарь

Словарь загружается из YAML-файлов рекурсивно через `TranslationLoader.Load()`.
Формат: `["original","translated","speaker?"]`. Все `*.yaml` из `translations/`
копируются в `Managed/`. Словарь регистронезависимый
(`StringComparer.OrdinalIgnoreCase`), т.к. игра передаёт `set_text` с разным регистром.

Текущие переводы:

- **диалоги:** 1793 записи в 4 файлах (формат `["eng","rus","speaker"]`)
- **UI:** 55 строк (формат `["key","translation"]`)
- **персонажи:** 23 имени (формат `["name","translation","gender"]`)

Наша DLL (финальная сборка):

```
NeonTranslatorRuntime.dll (22.5 KB)
├── TranslatorPlugin.cs         ← точка входа + [RuntimeInitOnLoadMethod]
├── NeonLateUpdate.cs           ← MonoBehaviour с exec order 10000
├── TranslationLoader.cs        ← Reader YAML → Dictionary<string,string>
└── NativeMethods.cs            ← P/Invoke kernel32 (лог) + MethodPatcher (отключён)

translations/
  dialogues.73203.yaml          ← 1503 диалога
  dialogues.73262.yaml          ← 93 диалога
  dialogues.73263.yaml          ← 97 диалогов
  dialogues.73264.yaml          ← 100 диалогов
  speakers.yaml                 ← 23 персонажа
  settings_keys.yaml            ← 55 UI строк

dwmapi.dll (13.5 KB, нативный прокси)
└── 32 forward + 2 интерсепта + BootstrapTranslator
```

---

## 8. Архитектура файлов перевода

### 8.1. Структура репозитория

```
translations/                      ← версионируется в git
  dialogues.73203.yaml             ← диалоги (1503, [text, translation, speaker])
  dialogues.73262.yaml             ← диалоги (93)
  dialogues.73263.yaml             ← диалоги (97)
  dialogues.73264.yaml             ← диалоги (100)
  speakers.yaml                    ← персонажи (23, [name, translation, gender])
  settings_keys.yaml               ← UI строки (55, [key, translation])

Third Crisis Neon Nights_Data/Managed/
  *.yaml                           ← все yaml копируются сюда для рантайма
```

### 8.2. Формат YAML (перевод)

```yaml
# Dialogues (path_id=73203): [text, translation, speaker]
- ["Yesss...!~", "Да-а-а...!~", "Zoey"]
- ["Fhaaa..!!", "Ахха..!!", "Zoey"]

# Settings keys: [key, translation]
- ["Fullscreen", "Полный экран"]

# Speakers: [name, translation, gender]
- ["Zoey", "Зои", "female"]
```

| Поле            | Формат диалогов                                 |
| --------------- | ----------------------------------------------- |
| `text`          | Оригинал (английский)                           |
| `translation`   | Перевод (русский), пустая строка = не переведено|
| `speaker`       | Имя персонажа (опционально)                     |

### 8.3. Пайплайн (текущий)

```
Шаг 1: Дамп ассетов
  dump_assets.py → dump_assets/ (140 JSON-файлов, UnityPy)

Шаг 2: Извлечение текста
  extractor.py
    → translations/dialogues.{path_id}.yaml  (из dialogues-полей MonoBehaviour)
    → translations/speakers.yaml             (уникальные спикеры)
    → translations/settings_keys.yaml        (из settings_keys display)

Шаг 3: Перевод
  Редактирование yaml вручную или через translate-expert агента

Шаг 4: Деплой
  build.py → runtime/NeonTranslatorRuntime.dll
  Копирование *.yaml → Managed/ + dwmapi.dll в корень игры
```

---

## 10. Технический стек

| Компонент            | Технология              | Обоснование                                |
| -------------------- | ----------------------- | ------------------------------------------ |
| Дамп ассетов         | Python 3.11 + UnityPy   | Чтение Unity-объектов через typed API      |
| Извлечение строк     | Pure Python (YAML)      | Из дампов, без парсинга бинарников         |
| Компиляция C#        | csc.exe (MS .NET)       | Стандартный компилятор .NET Framework      |
| Компиляция C         | MSVC cl.exe             | Нативная сборка dwmapi.dll прокси          |
| Рантайм-перевод      | C#                      | MonoBehaviour, Canvas.willRenderCanvases   |

**Запрещённые инструменты** (не используются):

- Сторонние декомпиляторы
- Unity Editor, AssetRipper, uTinyRipper, AssetStudio

---

## 11. Ключевые классы Unity (classID)

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

## 12. Заключение

Пайплайн прошёл три поколения:

1. **JS `parser.mjs`** — сырой ASCII-поиск по data секции, ~40-60% текста с шумом
2. **Python `parser.py`** — прямой парсинг структурированных Unity-объектов (DialogueHistory, TMP_Text), 1544 диалога без шума
3. **Python `dump_assets.py` + `extractor.py`** (текущий) — дамп ассетов через UnityPy, извлечение в YAML, 1793 диалога, 55 UI, 23 спикера

Ключевые достижения:

- **UnityPy-дамп** всех .assets файлов → JSON (140 файлов, 100k+ объектов)
- **1793 структурированных диалога** из DialogueHistory — 100% точность, 0% шума
- **55 UI-строк** из settings_keys — реальный display-текст из бинарника
- **Scan-and-Replace** — метод перевода без ограничения длины (секция 7.4)
- **Native proxy dwmapi.dll** — бутстрап NeonTranslatorRuntime через Mono API
- **NeonLateUpdate + [DefaultExecutionOrder(10000)]** — замена Timer+SyncCtx (0ms задержка)
- **Два фиксера:** PopulateAllText (кэш) + willRenderCanvases (инвалидация)
- **Кэш компонентов** — FindObjectsOfType только при инвалидации (OnPreRender)
- **ANtoolkit инжекция** — AddTranslation в оба словаря (Russian + English) — мерцание устранено

**Итоговая архитектура:**

```
dump_assets.py → dump_assets/ (140 JSON)
         │ UnityPy
         ▼
extractor.py
         │
         ▼
translations/
  dialogues.73203.yaml    ← ["text","translation","speaker"]  (1503)
  dialogues.73262.yaml    ← (93)
  dialogues.73263.yaml    ← (97)
  dialogues.73264.yaml    ← (100)
  speakers.yaml           ← ["name","translation","gender"]   (23)
  settings_keys.yaml      ← ["key","translation"]            (55)
         │
         ▼ (копирование *.yaml → Managed/)
         │
 ┌────────────────────────────────┐
 │          dwmapi.dll            │
 │  (native proxy, бутстрап через │
 │   DwmSetWindowAttribute)       │
 └───────────┬────────────────────┘
             │ mono_runtime_invoke
             ▼
 ┌───────────────────────────────────┐
 │   NeonTranslatorRuntime.dll       │
 │  (22.5 KB, C#)                    │
 │                                   │
 │  [RuntimeInitializeOnLoadMethod]  │
 │    ├── InitReflection()           │
 │    ├── new GameObject()           │
 │    ├── AddComponent<NeonLateUpd>  │
 │    └── загрузка словаря           │
 │                                   │
 │  willRenderCanvases → OnPreRender │
 │    ├── InvalidateCache()          │
 │    ├── ScanAllUiLocs() (ANToolkit)│
 │    └── PopulateAllText()          │
 │        └── FindObjectsOfType      │
 │            → замена по словарю    │
 │                                   │
 │  NeonLateUpdate (exec 10000)      │
 │    └── PopulateAllTextPublic()    │
 │        └── итерация по кэшу       │
 └───────────────────────────────────┘
             ↓
 Любой текст на экране
 — без мерцания
 — кэш + инжекция в ANToolkit
```

### 7.4.5. Ограничения и известные проблемы

1. ~~**Flickering на Toys tab (~10 строк Lovense):**~~ **РЕШЕНО** — через
   инжекцию русских переводов в ANToolkit словари "Russian" + "English"
   (AddTranslation). Игра сама ставит русский текст, без гонки.
2. ~~**Canvas.ForceUpdateCanvases() в LateUpdate:**~~ **РЕШЕНО** — кэш
   компонентов (OnPreRender инвалидирует, LateUpdate использует),
   willRenderCanvases перестраивает Canvas после замены.
3. **SetTextFieldDirect не обновляет Layout:** Если текст заменён через
   отражение поля (m_Text/m_text), система Layout не узнаёт о новом
   размере текста — требуется `SetVerticesDirty()`.
4. **Перевод через словарь (original→translated):** Если одна и та же
   английская фраза используется в разных контекстах с разным смыслом,
   перевод будет одинаковым везде. Контекстно-зависимый перевод не
   поддерживается (потребует GUID-based подхода).

### 7.4.6. Root cause: почему русский текст НЕ появлялся (два бага)

**Симптом:** После перехода от Timer к NeonLateUpdate — все три фиксера
находили английский текст, сверяли со словарём, но русский НЕ появлялся
на экране.

**Баг №1: `c.GetType() == _tmpType` — exact type check**

```csharp
// Было (не работало для TextMeshProUGUI):
if (c.GetType() == _tmpType) { ... }

// Стало (работает для всех наследников TMP_Text):
if (_tmpType.IsAssignableFrom(c.GetType())) { ... }
```

`TextMeshProUGUI` наследуется от `TMP_Text`, но `GetType()` возвращает
именно `TextMeshProUGUI`, а не `TMP_Text`. Сравнение через `==` давало
false для всех TMP-компонентов (текст не заменялся).

**Баг №2: `"m_Text"` — capital T, а нужно `"m_text"` (lowercase)**

```csharp
// Было (field == null для TMP_Text):
var field = type.GetField("m_Text", flags);

// Стало (работает):
var field = type.GetField("m_text", flags);
```

`TMP_Text` использует `m_text` (camelCase) для внутреннего поля, а
`m_Text` — для свойства `text`. Чтение через GetField("m_Text")
возвращало null → `SetTextFieldDirect` ничего не делала.

**Следствие:** Оба фиксера находили English→Russian в словаре, но
физически не записывали русский текст в поле. `text` property setter
не вызывался, т.к. проверка типа отбрасывала TMP-компоненты.
Поле m_text не заполнялось, т.к. имя поля было неверным.

**Дополнение:** Для корректной работы SetTextFieldDirect также:

- Устанавливает `m_havePropertiesChanged = true` (флаг перестроения mesh)
- Вызывает `SetVerticesDirty()` для принудительного перестроения TMP-меша

---

_Документ создан в рамках анализа локализации Third Crisis Neon Nights (Anduo Games, Unity 2022.3.62f3)._
_Последнее обновление: 2026-06-05 (актуализирован под пайплайн dump_assets.py + extractor.py → YAML)._
