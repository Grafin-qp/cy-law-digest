# План Б: сбор вне Claude

Парсеру нужен исходящий доступ к шести кипрским хостам. Если у среды Claude его нет (в облачной песочнице это `proxy_denied` в `status.json`; в Enterprise — политика организации), сбор переносится туда, где сеть есть, а Claude только читает готовый `skeleton.md` и пишет дайджест. Проверено: GitHub (`github.com`, `raw.githubusercontent.com`, `api.github.com`) доступен из песочницы даже при политике «package managers only», в отличие от кипрских сайтов.

## Вариант 1 — GitHub Actions (рекомендуется: без ноутбука, бесплатно, лог каждого прогона)

1. Создать репозиторий (публичный — содержимое и так публичное право; приватный потребует токен, см. ниже), положить в корень содержимое папки скилла: `SKILL.md`, `scripts/`, `references/`, `tests/`.
2. Скопировать `deploy/github-actions/digest.yml` в `.github/workflows/digest.yml`.
3. Settings → Actions → General → Workflow permissions → **Read and write permissions**.
4. Actions → `cyprus-law-digest` → Run workflow (окно `previous`, или `days:14`, или `2026-09-01..2026-09-15`) — первый прогон вручную. Дальше — каждый понедельник 03:30 UTC.
5. Ε.Ε. (mof.gov.cy) отдаёт сертификат без промежуточного CA: шаг «Complete the Gazette certificate chain» достраивает цепочку через `scripts/fix_chain.py` (проверка остаётся включённой); если не удалось — для этого хоста включается `--insecure-hosts` с warning в интерфейсе Actions. Nomoplatform с серверов GitHub отвечает Cloudflare 403 (подтверждено 21.09.2026) — в дайджесте его добирает WebFetch из чата.
6. Результат каждого прогона коммитится в `runs/<окно>/` и `runs/latest/` (`status.json`, `items.json`, `skeleton.md`, `texts/`, `collect.log`); кэш `raw/` не коммитится. Лог шага «Collect» показывает статусы источников; при блокировках — warning в интерфейсе Actions.

Как читает Claude (в SKILL.md это «режим B»):
```bash
python3 scripts/fetch_run.py --repo <owner>/<repo>            # → ~/digest_out/remote/latest/skeleton.md
python3 scripts/fetch_run.py --repo <owner>/<repo> --run 2026-09-07_2026-09-13
```
Дальше — шаги 2–5 SKILL.md как обычно. Приватный репозиторий: переменная окружения `GITHUB_TOKEN` (fine-grained, contents: read); токен в чат не вставлять.

## Вариант 2 — launchd на Mac (только если сессии всегда идут с подключённой папкой; для сервисного аккаунта не подходит)

`deploy/macos-launchd/`: `run.sh` запускает сборщик каждый понедельник 07:00 и кладёт `runs/latest/` в папку, которую видит Cowork (подключённая папка сессии или папка, синхронизируемая Obsidian Sync / iCloud). В `run.sh` поправить `SKILL_DIR` и `OUT_DIR`, в plist — путь к `run.sh`; `launchctl load`. Минусы: ноутбук должен быть включён в понедельник утром (пропущенный запуск launchd выполнит при следующем пробуждении); зависимости ставятся на Mac (`pip3 install requests beautifulsoup4 lxml pypdf reportlab`, `brew install poppler`).

Как читает Claude: `python3 scripts/fetch_run.py --dir "<путь к папке>/runs/latest"` или просто открыть `skeleton.md` из подключённой папки.

## Вариант 3 — попросить админа открыть шесть доменов

Для Team/Enterprise: Organization settings → Capabilities → «Allow network egress to package managers and specific domains» → добавить `www.mof.gov.cy`, `www.cylaw.org`, `www.nomoplatform.cy`, `www.gov.cy`, `www.companies.gov.cy`, `www.centralbank.cy`. Тогда работает режим A (скрипт прямо в сессии) без внешних движущихся частей. Проверка: `python3 scripts/selftest.py --live`.

## Что даёт каждый вариант

| | Ε.Ε. (законы, Κ.Δ.Π.) | CyLaw | Nomoplatform | gov.cy | Έφορος, ΚΤΚ | Нужен ноутбук |
|---|---|---|---|---|---|---|
| A. скрипт в сессии (egress открыт) | да | да | да* | да | да | нет |
| B1. GitHub Actions | да | да | да* | да | да | нет |
| B2. launchd на Mac | да | да | да* | да | да | да |
| C. WebFetch fallback | сайт — нет (TLS); законы и Κ.Δ.Π. — да, через индексы CyLII/CyLaw | да | да | **нет** (403) | да | нет |

\* Nomoplatform за Cloudflare; с серверов GitHub и из песочницы Python-клиент может получить бот-проверку — тогда `status.json` покажет `cloudflare`, и для этого источника Claude добирает через WebFetch (он Cloudflare проходит). Остальные источники это не затрагивает.
