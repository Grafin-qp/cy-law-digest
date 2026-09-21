---
name: opiniq-law-digest
description: "Weekly Cyprus law digest for Opiniq (English; the acts' own wording quoted and translated), collected by a parser from Επίσημη Εφημερίδα, CyLaw, Nomoplatform, gov.cy, the Registrar of Companies and the Central Bank for a window (default: previous week), or from a run made elsewhere (GitHub Actions) when the session has no network. ОБЯЗАТЕЛЬНО использовать, когда пользователь просит дайджест кипрского законодательства, «что нового в законах Кипра», «проверь обновления законодательства / регуляторов», «что приняли на Кипре за неделю», «есть ли изменения по недвижимости / налогам / корпоративному / миграции / трудовому праву Кипра», упоминает мониторинг Ε.Ε./Gazette, CyLaw, Nomoplatform, циркуляры Tax Department / ΚΤΚ, просит Cyprus law digest / legislative update, запускает дайджест по расписанию, или хочет самотест парсера / настройку сбора на GitHub Actions. Маркер: CY_LAW_DIGEST_V2."
---

# Cyprus Law Digest — v2

Скилл делает две вещи, строго по очереди: (1) **скрипт** собирает всё, что произошло в окне, из первоисточников и кладёт в `skeleton.md` дословные поля; (2) **модель** пишет из skeleton дайджест **на английском** по `references/digest-format.md` — каждая позиция: реквизиты → вординг акта (греческий дословно + перевод) → English summary в конце. Модель ничего не ищет «по памяти» и не добавляет фактов, которых нет в skeleton или в открытых по ссылкам документах.

Почему так: v1 жил в одном ходе чата — не мог листать выдачу, читал CyLaw в битой кодировке и додумывал названия, брал «хвост» неполного индекса. Здесь пагинация, кодировки, даты и дедупликация — в коде, а суждение о том, что важно и как это сказать, — у модели.

## Три режима получения данных

| Режим | Когда | Что делать |
|---|---|---|
| **A. Скрипт в сессии** | у среды есть исходящий доступ к кипрским сайтам (`selftest.py --live` → всё OK) | шаг 1 ниже |
| **B. Готовый прогон извне** | egress закрыт (`proxy_denied`), сбор настроен на GitHub Actions (`deploy/README.md`) | `scripts/fetch_run.py --repo <owner>/<repo>` → дальше шаг 2 (вариант с папкой на Mac — только если папка гарантированно подключена; для сервисного аккаунта не рассчитывать) |
| **C. WebFetch fallback** | ни A, ни B недоступны | `references/fallback-webfetch.md`; законы и Κ.Δ.Π. — через UTF-8 индексы CyLII + PDF CyLaw; gov.cy (Tax Department и др.) не виден — дайджест обязан это сказать |

Первый запуск в новой среде — `python3 scripts/selftest.py --live`. Если строки `BLOCKED proxy_denied` — сеть закрыта политикой (в claude.ai: Settings → Capabilities → «Allow network egress»; в Enterprise — администратор), это не ошибка скрипта. Тогда режим B — и это штатный режим, а не аварийный: GitHub из песочницы доступен даже при политике «package managers only», кипрские сайты — нет.

## Порядок работы

### 0. Окно
По умолчанию — предыдущая календарная неделя (понедельник–воскресенье по времени Кипра); это режим для запуска по расписанию в понедельник. Пользователь может задать: «за две недели» → `--days 14`; «с 1 по 15 сентября» → `--from 2026-09-01 --to 2026-09-15`; «за эту неделю» → `--week current`. Окно всегда печатается в шапке дайджеста. В режиме B окно задано прогоном; если нужно другое — запустить workflow вручную с параметром `window` (см. `deploy/README.md`).

### 1. Сбор (режим A)
```bash
python3 <папка скилла>/scripts/digest_collect.py --week previous --out ~/digest_out
# либо --days N / --from … --to … ; --today YYYY-MM-DD фиксирует «сегодня» для воспроизводимости; -v — подробный лог
```
Папка скилла может быть read-only — вывод всегда в `--out` вне её (по умолчанию `~/digest_out`).
Зависимости: `requests`, `beautifulsoup4`, `lxml`, `pdftotext` (poppler; иначе `pypdf`). Скрипт не падает на недоступном источнике — пишет причину в `status.json`. Выход: `digest_out/<окно>/`:
- `status.json` — статус каждого источника: `items`, `reason` (источник не дал ничего: `proxy_denied`, `cloudflare`, `ssl_error`…), `partial` (часть запросов не прошла), предупреждения о покрытии. **Читать первым.** Консольная сводка показывает то же: `ok` / `ok (partial: …)` / `BLOCKED …`.
- `skeleton.md` — секции A1–E со всеми дословными полями (название, длинное название, норма, вступление в силу, Σκοπός, событие, ссылки, практика и балл фильтра).
- `items.json` / `all_items.json` — то же машинно; `texts/<id>.txt` — полные тексты законов и Κ.Δ.Π.; `raw/` — кэш ответов (повторный прогон `--offline --cache-dir digest_out/<окно>/raw` не ходит в сеть).

Режим B даёт ту же папку (без `raw/`): `python3 scripts/fetch_run.py --repo <owner>/<repo>` кладёт последний прогон в `~/digest_out/remote/latest/` и печатает ту же сводку.

### 2. Статус источников
Если у источника `reason`, `partial` или `error` — открыть `references/fallback-webfetch.md` и действовать по таблице: WebFetch для того, что он покрывает (CyLaw, Nomoplatform, Έφορος, ΚΤΚ), флаг `--insecure-hosts` для TLS, и честное "Not verified" для того, что фетчер не берёт (Ε.Ε. на mof.gov.cy, gov.cy). `proxy_denied` у всех источников = закрытый egress — одна строка пользователю об этом и о режиме B. В режиме B ничего не дозапрашивать: статусы прогона только раскрываются в дайджесте. Ничего не обходить: ни бот-защиту, ни TLS без явного флага.

### 3. Проверка skeleton
- Раздел E («dropped») — прочитать. Если там позиция по практике (нетипичное название, английский заголовок ΚΤΚ) — включить в дайджест и запомнить ключ для `relevance.py` (см. `references/relevance.md`).
- Позиции с `⚠ parser warnings` (нет названия, нет даты, нет короткого названия) — открыть `texts/<id>.txt` или PDF по ссылке и заполнить вручную; если дата не подтверждена — в дайджест не ставить.
- Для закона или Κ.Δ.Π., у которого выдержка не показывает саму норму (только «τροποποιείται ως ακολούθως:»), прочитать `texts/<id>.txt` и выбрать предложение с содержательным изменением (ставка, срок, обязанность).
- Дубли по смыслу (Κ.Δ.Π. и ведомственное сообщение о том же) — оставить обе позиции, но во второй одна строка со ссылкой на первую.
- Строка «Coverage» в шапке skeleton (выпуски Ε.Ε. в окне, до какого номера пройден CyLaw, хост и время прогона) — источник для блока Verification.

### 4. Дайджест
Писать строго по `references/digest-format.md`, по-английски: header → "At a glance" → 1. Enacted (laws / Κ.Δ.Π. / voted) → 2. In progress → 3. Regulators → 4. Other laws of the week → "Verification". Каждая позиция: identification → wording (греческий дословно + English translation) → Summary (English, закрывает позицию; внутри — practice note). Названия актов — в оригинале с английским переводом в скобках при первом упоминании. Лимиты плотности — там же. Пустая секция — "No changes"; недоступный источник — "Not verified: … (reason)". Русскую версию делать только по просьбе пользователя.

Кипрское право — не практика автора: там, где вывод зависит от местной практики, писать "to be confirmed with the Cyprus team", а не выдавать за установленное.

### 5. Выдача
Файл `digest_<окно>.md` (например `digest_2026-09-07_2026-09-13.md`). Отдать пользователю; если подключена папка или указан Project — положить туда же, но только когда есть хотя бы одна подтверждённая позиция: пустой или в основном "not verified" дайджест — ответом в чате, чтобы не засорять общий Project. В ответе — окно, число позиций по секциям и что не удалось проверить. Без пересказа дайджеста.

## Самотест
```bash
python3 scripts/selftest.py            # офлайн: фикстуры + 21 тест (парсеры, фильтр, сквозной прогон)
python3 scripts/selftest.py --live     # + доступность каждого источника и живая структура страниц
```
`--live` запускать один раз в каждой новой среде (личный Cowork, сервисный аккаунт, первое срабатывание расписания, GitHub Actions — он там в workflow). Строки `BLOCKED <reason>` — сетевая политика; `PARSE-EMPTY` — изменилась вёрстка, см. `references/sources.md`.

## Запуск по расписанию
Промпт для scheduled task (понедельник, утро по Кипру): «Prepare the Cyprus law digest for the previous week using the opiniq-law-digest skill (default window). Mode A: run `scripts/digest_collect.py --week previous`; if sources are blocked (proxy_denied), mode B: `scripts/fetch_run.py --repo <owner>/<repo>`; only then mode C (references/fallback-webfetch.md). Write the digest in English per references/digest-format.md, mark anything not verified in the Verification block, and deliver `digest_<window>.md`.» Окно считается от даты запуска, состояние между запусками не хранится; при пропуске недели — `--days 14` (в режиме B — workflow с `window: days:14`).

## Файлы
- `scripts/digest_collect.py` — CLI сбора; `--plan` печатает URL, `--webfetch-plan` — план для fallback.
- `scripts/fetch_run.py` — режим B: забрать готовый прогон из GitHub-репозитория или папки.
- `scripts/cylaw_digest/` — `gazette.py` (Ε.Ε.), `cylaw.py` (законы + индекс Κ.Δ.Π. с per-act PDF), `nomoplatform.py`, `govcy.py`, `registrar.py`, `cbc.py`, `acts.py` (разбор текстов актов), `relevance.py` (фильтр практик), `window.py`, `http.py`, `greekdates.py`, `pdftext.py`, `model.py`.
- `scripts/selftest.py`, `tests/` — фикстуры и тесты.
- `deploy/README.md`, `deploy/github-actions/digest.yml`, `deploy/macos-launchd/` — сбор вне Claude (план Б).
- `references/digest-format.md` — структура, плотность, язык дайджеста, примеры.
- `references/sources.md` — реестр источников и их особенностей.
- `references/relevance.md` — практики, ключи, id тем Nomoplatform.
- `references/fallback-webfetch.md` — что делать при заблокированных источниках.
