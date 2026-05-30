# Deprecated — Удалённые сторонние компоненты

Всё нижеперечисленное было **полностью удалено** из проекта.
Репозиторий содержит только кастомные файлы.

---

## Удалено полностью

| Компонент | Путь | Статус |
|-----------|------|--------|
| **XUnity.AutoTranslator** (ядро + плагины) | `BepInEx/plugins/XUnity.AutoTranslator/` | 🗑 Удалён |
| **XUnity.ResourceRedirector** | `BepInEx/plugins/XUnity.ResourceRedirector/` | 🗑 Удалён |
| **Плагины переводчиков** (15 DLL) | `BepInEx/plugins/XUnity.AutoTranslator/Translators/` | 🗑 Удалены |
| **Документация XUnity** | `BepInEx/plugins/README (AutoTranslator).md` | 🗑 Удалён |
| **Кэш английских строк** | `BepInEx/Translation/en/` | 🗑 Удалён |
| **Кэш BepInEx** | `BepInEx/cache/` | 🗑 Удалён |
| **Конфиг XUnity** | `BepInEx/config/AutoTranslatorConfig.ini` | 🗑 Удалён |
| **Конфиг ResourceRedirector** | `BepInEx/config/gravydevsupreme.xunity.resourceredirector.cfg` | 🗑 Удалён |
| **Конфиг BepInEx** | `BepInEx/config/BepInEx.cfg` | 🗑 Удалён |
| **Скрипт установки** | `install-translation.mjs` | 🗑 Удалён |

## Что осталось

### Наши кастомные файлы (единственное в репозитории)
```
├── .opencode/
│   ├── agents/translate-expert.md
│   ├── deprecated/README.md
│   └── skills/
│       ├── translate-analysis/{SKILL.md, analyze.mjs}
│       ├── translate-batch/{SKILL.md, batch.mjs}
│       └── find-strings/{SKILL.md, find.mjs}
├── .vscode/{extensions.json, settings.json}
├── AGENTS.md
├── opencode.json
├── package.json
├── README.md
└── .gitignore
```

### Runtime проекта (в .gitignore, не в репозитории)
- `BepInEx/` — будет удалён при переустановке игры
- `Third Crisis Neon Nights_Data/` — данные игры
- `MonoBleedingEdge/` — Mono runtime
- `*.exe`, `*.dll` — бинарники
- `doorstop_config.ini`, `.doorstop_version`, `winhttp.dll` — Doorstop

## Дальнейшие шаги
1. Переустановить игру через Steam — BepInEx и Doorstop исчезнут
2. С нуля настроить кастомную систему перевода
