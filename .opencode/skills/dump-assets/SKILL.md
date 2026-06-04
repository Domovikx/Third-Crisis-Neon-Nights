---
name: dump-assets
description: Дамп всех Unity .assets файлов игры в структурированный JSON с реальными объектами (UnityPy)
---

# dump-assets — Дамп Unity asset-ов в JSON

## Описание

Использует [UnityPy](https://pypi.org/project/UnityPy/) для чтения настоящих Unity-объектов
(Object Table + Type Tree + typed fields). Каждый `.assets` превращается в набор JSON-файлов:

- `temp_assets/<name>.json` — **summary** (статистика по типам + ссылки на чанки)
- `temp_assets/<name>.chunk000.json` — объекты 0–4999
- `temp_assets/<name>.chunk001.json` — объекты 5000–9999
- …

## Использование

```bash
pip install UnityPy
python .opencode/skills/dump-assets/dump_assets.py
```

## Формат JSON

### Summary
```json
{
  "asset": "resources.assets",
  "chunk": "summary",
  "total_chunks": 21,
  "total_objects": 100776,
  "object_types": {
    "MonoBehaviour": 28475,
    "GameObject": 21251,
    "Transform": 13953,
    ...
  },
  "chunks": [
    {"chunk": 0, "file": "resources.chunk000.json", "objects": 5000, "range": "0–4999"},
    ...
  ]
}
```

### Data chunk
```json
{
  "asset": "resources.assets",
  "chunk": 0,
  "objects": [
    {
      "path_id": 1,
      "type": "Material",
      "strings": {
        "m_Name": "Orbitron-Bold Atlas Material"
      },
      "fields": {
        "m_CustomRenderQueue": -1,
        "m_DoubleSidedGI": false
      }
    },
    {
      "path_id": 73203,
      "type": "MonoBehaviour",
      "strings": {
        "m_Enabled": 1
      }
    }
  ]
}
```

## Поля объекта

| Поле | Описание |
|------|----------|
| `path_id` | уникальный ID объекта в файле |
| `type` | Unity class name (GameObject, MonoBehaviour, Texture2D, …) |
| `strings` | строковые поля объекта (m_Name, …) |
| `fields` | нестроковые поля (int, float, bool, PPtr, Vector3, …) |
| `dialogues` | найденные диалоги Speaker/Text (из raw-скана) |
| `raw_strings` | прочие строки из raw-байт объекта (top 20) |
| `error` | если объект не читается |

## Примечания

- Texture2D, AudioClip, Shader и другие бинарные типы — только meta, без пикселей/сэмплов
- PPtr-ссылки сохраняются как `{file_id, path_id}`
- **Dialogues** извлекаются из raw bytes MonoBehaviour (JSON-паттерн `"Speaker":"…","Text":"…"`)
- Объекты без текстовых полей всё равно присутствуют в дампе (для навигации по структуре)

## Тесты

```bash
python .opencode/skills/dump-assets/dump_assets.test.py
```

23 теста: raw-скан, JSON-парсинг, диалоги, PPtr, discover, интеграция с UnityPy, формат индекса.
